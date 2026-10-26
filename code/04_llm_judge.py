#!/usr/bin/env python3
"""04_llm_judge.py — Was the disposal of a carved-out subsidiary legible at announcement? (Part 1 experiment)

For each 물적분할 with a resolved outcome, two frontier models read the 회사분할결정 filing text as of the
announcement date and return (i) a probability that the parent disposes of / dilutes the new subsidiary within
the tracking window, (ii) the most likely path, (iii) reasons with verbatim evidence, (iv) structured facts
stated in the filing. Two conditions: identified text and anonymized text (names/dates masked) — the gap
measures memorization of post-announcement outcomes. Output: results/llm_judge/<model>__<condition>.jsonl

Usage (EC2):  ./venv/bin/python code/04_llm_judge.py --model anthropic|openai --condition identified|anonymized [--workers 4] [--limit N]
"""
import argparse, json, os, re, sys, time, threading, random
from concurrent.futures import ThreadPoolExecutor, as_completed
import boto3
from botocore.config import Config

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRACK = f"{BASE}/data/processed/carveout_disposal_tracking.json"
INDEX = f"{BASE}/data/processed/disclosure_text_index.json"
TEXTDIR = f"{BASE}/data/raw/disclosure_text"
OUTDIR = f"{BASE}/results/llm_judge"; os.makedirs(OUTDIR, exist_ok=True)
MODELS = {"anthropic": "us.anthropic.claude-fable-5-1", "openai": "us.openai.gpt-6.1-sol"}
RESOLVED = {"retained_100", "partial_sale", "majority_disposed", "ipo_listed"}

SYSTEM = """You are a corporate-finance analyst specializing in Korean corporate restructurings (상법 제530조의2 회사분할).
You will read ONE Korean regulatory filing — a 주요사항보고서(회사분할결정) announcing a 물적분할 ("captive spin-off":
the new company becomes a wholly owned subsidiary of the parent; existing shareholders receive no shares).

Your task is a forecast AS OF THE FILING DATE, using only the filing text and general knowledge available before that date.
Do NOT use any knowledge of what happened to this company after the filing date. If you recognize the company, ignore
everything you know about subsequent events; forecast only from the document.

Forecast target (binary, as tracked by the researchers): within roughly 3–5 fiscal years after the division, does the parent
cease to hold ~100% of the new subsidiary — i.e. sell a majority stake, list the subsidiary (IPO), merge it away, or let its
stake fall below 99.5% through any stake sale or third-party investment? "Retained" means the parent still reports ~100%.

Return ONLY a JSON object with these keys:
  "p_disposal": integer 0–100 (probability that the stake is NOT retained at ~100% within the window),
  "most_likely_path": one of "retain", "ipo", "sale_to_third_party", "partial_stake_sale_or_investor", "intragroup_transfer_or_merger",
  "horizon_years": integer (expected years to the first disposal event; 0 if retain),
  "reasons": list of 3–6 short strings explaining the forecast,
  "evidence_quotes": list of verbatim Korean snippets (<=120 chars each) from the filing that support the reasons,
  "facts": {
      "stated_purpose_categories": list from ["specialization","efficiency","sale_or_disposal","fundraising_or_investment_attraction","holding_company_or_group_restructuring","regulatory_or_legal","other"],
      "mentions_listing_or_ipo": true/false, "listing_plan_statement": short string or null,
      "mentions_external_investment_or_strategic_investor": true/false,
      "mentions_sale_or_buyer": true/false,
      "mentions_shareholder_protection_measures": true/false,
      "new_company_business": short string, "new_company_capital_krw": number or null,
      "division_ratio_or_relative_size": short string or null,
      "appraisal_rights_mentioned": true/false
  },
  "confidence": one of "low","medium","high",
  "used_outside_knowledge": true/false  (true if you could not avoid recognizing the company and its later events)
No prose outside the JSON."""


def load_events(only=None):
    """Events with a resolved outcome and a fetched filing text. If `only` (a set of rcept_no) is given, take exactly
    those events regardless of the current outcome field — used to repeat a run on the identical event set."""
    track = json.load(open(TRACK, encoding="utf-8")); idx = json.load(open(INDEX, encoding="utf-8"))
    ev = []
    for r in track:
        if only is not None:
            if r["rcept_no"] not in only: continue
        elif r["outcome"] not in RESOLVED: continue
        meta = idx.get(r["rcept_no"]); 
        if not meta or not meta.get("path"): continue
        path = meta["path"] if os.path.isabs(meta["path"]) else f"{BASE}/{meta['path']}"
        txt = open(path, encoding="utf-8").read()
        ev.append({**r, "text": txt})
    return ev


def anonymize(e):
    """Mask parent/new-company names, group prefixes and dates so the model cannot key on identity."""
    t = e["text"]
    names = [e["corp_name"]] + [x.strip() for x in re.split(r"[\n/;]|\s및\s", re.sub(r"\(.*?\)", "", e.get("new_co") or "", flags=re.S)) if len(x.strip()) >= 2]
    variants = set()
    for n in names:
        n2 = re.sub(r"주식회사|㈜|\(주\)|\s+", "", n)
        if len(n2) >= 2: variants.update({n, n2})
    for v in sorted(variants, key=len, reverse=True):
        t = t.replace(v, "[회사명]")
    t = re.sub(r"(19|20)\d{2}\s*년", "[연도]년", t); t = re.sub(r"(19|20)\d{2}[.\-/](\d{1,2})[.\-/](\d{1,2})", "[날짜]", t)
    t = re.sub(r"\b(19|20)\d{6}\b", "[날짜]", t)
    t = re.sub(r"(엘지|LG|에스케이|SK|지에스|GS|씨제이|CJ|롯데|한화|두산|현대|삼성|포스코|POSCO|효성|코오롱|HD|DL|대림|태영|OCI|오씨아이)\s*", "[그룹]", t)
    return t


def client():
    return boto3.Session(profile_name=os.environ.get("AWS_PROFILE", "default")).client(
        "bedrock-runtime", region_name="us-east-1", config=Config(retries={"max_attempts": 4, "mode": "adaptive"}, read_timeout=1800))


def call(c, provider, model, text, board_date, max_tokens=16000):
    user = f"Filing date (board resolution): {'[masked]' if ANON else board_date}\n\n=== FILING TEXT ===\n{text[:60000]}\n=== END ==="
    kw = dict(modelId=model, system=[{"text": SYSTEM}], messages=[{"role": "user", "content": [{"text": user}]}], inferenceConfig={"maxTokens": max_tokens})
    def extra(effort):
        if effort is None: return None
        return {"thinking": {"type": "adaptive"}, "output_config": {"effort": effort}} if provider == "anthropic" else {"reasoning": {"effort": effort}}
    for attempt, effort in enumerate(["max", "max", "high", None]):
        try:
            k = dict(kw); x = extra(effort)
            if x: k["additionalModelRequestFields"] = x
            r = c.converse_stream(**k); out = []; stop = None
            for ev in r["stream"]:
                if "contentBlockDelta" in ev:
                    d = ev["contentBlockDelta"].get("delta", {})
                    if "text" in d: out.append(d["text"])
                elif "messageStop" in ev: stop = ev["messageStop"].get("stopReason")
            txt = "".join(out).strip()
            if txt: return txt, stop, (effort or "none")
        except Exception as ex:
            err = str(ex)
            if "thinking" in err or "output_config" in err or "reasoning" in err: continue
            time.sleep(5 * (attempt + 1))
    return None, "error", None


def parse_json(s):
    m = re.search(r"\{.*\}", s, re.S)
    if not m: return None
    try: return json.loads(m.group(0))
    except Exception:
        try: return json.loads(re.sub(r",\s*([}\]])", r"\1", m.group(0)))
        except Exception: return None


ANON = False

def main():
    global ANON, TRACK, INDEX, OUTDIR
    ap = argparse.ArgumentParser(); ap.add_argument("--model", choices=list(MODELS), required=True); ap.add_argument("--condition", choices=["identified", "anonymized"], required=True)
    ap.add_argument("--workers", type=int, default=4); ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--run", type=int, default=0, help="repeat-run id; >0 writes <model>__<condition>__run<N>.jsonl (test-retest stability), 0 = original file")
    ap.add_argument("--only-from", default="", help="jsonl of a previous run: process exactly its rcept_no set (ignores the current outcome filter)")
    ap.add_argument("--tracking", default=TRACK, help="tracking-format event file"); ap.add_argument("--index", default=INDEX, help="disclosure text index (rcept_no -> {path})")
    ap.add_argument("--outdir", default=OUTDIR, help="output directory"); ap.add_argument("--all-events", action="store_true", help="score every event in the tracking file (no resolved-outcome filter)")
    a = ap.parse_args()
    TRACK, INDEX, OUTDIR = a.tracking, a.index, a.outdir; os.makedirs(OUTDIR, exist_ok=True)
    ANON = a.condition == "anonymized"; model = MODELS[a.model]
    out = f"{OUTDIR}/{a.model}__{a.condition}{'__run' + str(a.run) if a.run else ''}.jsonl"
    done = {json.loads(l)["rcept_no"] for l in open(out, encoding="utf-8")} if os.path.exists(out) else set()
    only = {json.loads(l)["rcept_no"] for l in open(a.only_from, encoding="utf-8")} if a.only_from else None
    if a.all_events and only is None: only = {r["rcept_no"] for r in json.load(open(TRACK, encoding="utf-8"))}
    events = [e for e in load_events(only) if e["rcept_no"] not in done]
    random.seed(42); random.shuffle(events)
    if a.limit: events = events[:a.limit]
    print(f"model={model} condition={a.condition} todo={len(events)} done={len(done)}", flush=True)
    lock = threading.Lock(); c = client(); t0 = time.time(); n = 0

    def work(e):
        text = anonymize(e) if ANON else e["text"]
        t1 = time.time(); raw, stop, effort = call(c, a.model, model, text, e["board_date"] or "")
        rec = {"rcept_no": e["rcept_no"], "corp_name": e["corp_name"], "division_year": e["division_year"], "outcome": e["outcome"],
               "label_disposed": int(e["outcome"] != "retained_100"), "model": model, "condition": a.condition, "effort": effort,
               "stop_reason": stop, "latency_s": round(time.time() - t1, 1), "raw": raw, "parsed": parse_json(raw) if raw else None, "text_chars": len(text)}
        return rec

    with ThreadPoolExecutor(max_workers=a.workers) as ex, open(out, "a", encoding="utf-8") as f:
        futs = {ex.submit(work, e): e for e in events}
        for fu in as_completed(futs):
            rec = fu.result(); n += 1
            with lock:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
            p = (rec["parsed"] or {}).get("p_disposal")
            print(f"[{n}/{len(events)}] {rec['corp_name'][:12]:12s} y={rec['division_year']} label={rec['label_disposed']} p={p} path={(rec['parsed'] or {}).get('most_likely_path')} {rec['latency_s']}s [{time.time()-t0:.0f}s]", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
