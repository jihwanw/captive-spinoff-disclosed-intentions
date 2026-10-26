#!/usr/bin/env python3
"""09b_llm_extract_subsidiary_status.py — read the annual-report passages (09a) and extract, per fiscal year, whether the
carved-out company is still a (100%/partial) subsidiary of the parent, was sold, merged back, listed, liquidated, or
whether the division was cancelled; with verbatim evidence. One Bedrock call per event (Claude, adaptive thinking).

Input : data/processed/annual_report_subsidiary_passages_v1.json
Output: results/subsidiary_status_llm/<model>.jsonl   (append; resumable)
Usage : python code/09b_llm_extract_subsidiary_status.py [--workers 4] [--limit N] [--effort high]
"""
import argparse, json, os, re, sys, time, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import boto3
from botocore.config import Config

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INP = f"{P}/data/processed/annual_report_subsidiary_passages_v1.json"
OUTDIR = f"{P}/results/subsidiary_status_llm"; os.makedirs(OUTDIR, exist_ok=True)
MODEL = "us.anthropic.claude-fable-5-1"

SYSTEM = """You are an analyst reading excerpts from Korean annual reports (사업보고서, including attached audit reports) of a
parent company that carried out a 물적분할 (the new company was created as a wholly owned subsidiary). Your task is purely
extractive: determine, for each fiscal year for which excerpts are given, the parent's ownership status of the carved-out
company at that fiscal year-end, using ONLY the excerpts. The new company may appear under a different name than the
provisional name in the division filing (e.g. '(가칭)' names); identify it from statements such as '분할신설', '물적분할의
방법으로 … 분할신설', the division date, or the business description. Report what the excerpts say; if they do not mention the
company, say not_mentioned. Never guess an ownership percentage that is not written in the excerpts.

Return ONLY a JSON object:
{"actual_new_company_name": string|null,
 "by_fiscal_year": [{"fy": int, "status": "subsidiary_100"|"subsidiary_partial"|"sold_out"|"merged_into_parent"|"listed"|"liquidated"|"not_mentioned"|"unclear",
                      "ownership_pct": number|null, "evidence": string (verbatim, <= 200 chars, Korean as written)}],
 "overall_outcome": "retained_100"|"partial_sale"|"majority_disposed"|"ipo_listed"|"merged_back_into_parent"|"liquidated"|"division_cancelled"|"unclear",
 "first_change_fy": int|null,
 "confidence": "high"|"medium"|"low",
 "notes": string}
Rules: ownership_pct is the parent's direct+indirect stake if stated, else the stated figure; 'partial_sale' = parent still holds
>= 50% but < 99.5%; 'majority_disposed' = parent holds < 50% or the company left the group by sale; 'ipo_listed' = the company
listed its shares; 'merged_back_into_parent' = absorbed by the parent; 'division_cancelled' only if the excerpts say the division
did not take place."""


def client():
    return boto3.Session(profile_name=os.environ.get("AWS_PROFILE", "default")).client(
        "bedrock-runtime", region_name="us-east-1", config=Config(retries={"max_attempts": 2, "mode": "adaptive"}, connect_timeout=30, read_timeout=300))  # a stalled connection must fail in minutes, not hours (2026-10-17: 4 workers hung 3 h behind a proxy with read_timeout=1800)


def build_user(ev, max_chars=60000):
    head = (f"Parent: {ev['corp_name']} (DART corp_code {ev['corp_code']}, class {ev['corp_cls']}). Division date: {ev['division_date']} "
            f"(division year {ev['division_year']}). New company name in the division filing: {ev['new_co']}; candidates: {ev['candidates']}; "
            f"search variants used: {ev['name_variants']}.\n\n")
    parts = []; budget = max_chars - len(head)
    for rep in ev["annual_reports"]:
        if rep.get("error"): parts.append(f"=== FY{rep['fy']} {rep['report_nm']} (filed {rep['rcept_dt']}): download failed ===\n"); continue
        pas = rep.get("passages", [])
        order = {"subsidiary_table": 1, "division": 2}
        pas = sorted(pas, key=lambda p: (0 if p["kind"].startswith("name:") else order.get(p["kind"], 3)))
        block = f"=== FY{rep['fy']} {rep['report_nm']} (filed {rep['rcept_dt']}); name hits in full report: {rep.get('name_hits')} ===\n"
        used = 0
        for p_ in pas:
            if used > 7000: break
            block += f"[{p_['kind']}] …{p_['text']}…\n"; used += len(p_["text"])
        if not pas: block += "(no passage mentioning the new company, division, or a subsidiary table was found in this report)\n"
        parts.append(block)
    body = "\n".join(parts)
    if len(body) > budget: body = body[:budget] + "\n…(truncated)"
    return head + body


def call(c, text, effort):
    kw = dict(modelId=MODEL, system=[{"text": SYSTEM}], messages=[{"role": "user", "content": [{"text": text}]}], inferenceConfig={"maxTokens": 8000})
    for attempt, eff in enumerate([effort, effort, "high", None]):
        try:
            k = dict(kw)
            if eff: k["additionalModelRequestFields"] = {"thinking": {"type": "adaptive"}, "output_config": {"effort": eff}}
            r = c.converse(**k)
            txt = "".join(b.get("text", "") for b in r["output"]["message"]["content"] if "text" in b)
            if txt: return txt, r.get("stopReason"), eff or "none"
        except Exception as e:
            err = str(e)[:200]; time.sleep(5 * (attempt + 1))
    return "", f"failed: {err}", "none"


def parse_json(s):
    m = re.search(r"\{.*\}", s, re.S)
    if not m: return None
    try: return json.loads(m.group(0))
    except Exception:
        try: return json.loads(re.sub(r",\s*([}\]])", r"\1", m.group(0)))
        except Exception: return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--workers", type=int, default=4); ap.add_argument("--limit", type=int, default=0); ap.add_argument("--effort", default="high")
    ap.add_argument("--inp", default=INP, help="passages file from 09a"); ap.add_argument("--out", default=f"{OUTDIR}/anthropic__status.jsonl", help="output jsonl (append; resumable)")
    a = ap.parse_args()
    data = json.load(open(a.inp, encoding="utf-8"))
    out = a.out
    done = {json.loads(l)["rcept_no"] for l in open(out, encoding="utf-8")} if os.path.exists(out) else set()
    todo = [(rn, ev) for rn, ev in data.items() if ev.get("complete") and rn not in done]
    if a.limit: todo = todo[:a.limit]
    print(f"model={MODEL} effort={a.effort} todo={len(todo)} done={len(done)}", flush=True)
    c = client(); lock = threading.Lock(); t0 = time.time(); n = 0

    def work(item):
        rn, ev = item; user = build_user(ev); t1 = time.time()
        raw, stop, eff = call(c, user, a.effort); parsed = parse_json(raw) if raw else None
        return {"rcept_no": rn, "corp_name": ev["corp_name"], "division_year": ev["division_year"], "queue_outcome": ev["queue_outcome"], "v3_outcome": ev["v3_outcome"],
                "model": MODEL, "effort": eff, "stop_reason": stop, "latency_s": round(time.time() - t1, 1), "prompt_chars": len(user), "raw": raw, "parsed": parsed}

    with ThreadPoolExecutor(max_workers=a.workers) as ex, open(out, "a", encoding="utf-8") as f:
        futs = [ex.submit(work, it) for it in todo]
        for fu in as_completed(futs):
            rec = fu.result(); n += 1
            with lock: f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
            pr = rec["parsed"] or {}
            print(f"[{n}/{len(todo)}] {rec['corp_name'][:12]:12s} y={rec['division_year']} v3={rec['v3_outcome'][:18]:18s} -> {pr.get('overall_outcome')} ({pr.get('confidence')}) name={str(pr.get('actual_new_company_name'))[:20]} {rec['latency_s']}s [{time.time()-t0:.0f}s]", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
