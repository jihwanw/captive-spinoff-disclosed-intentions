#!/usr/bin/env python3
"""12e_extract_filing_financials.py — numeric fields of a 회사분할결정 filing from its text (for years without cmpDvDecsn).

The 2017+ financial baseline (05) uses the structured API fields ffdtl_tast/tdbt/teqt/cpt (분할설립회사 자산/부채/자본/자본금),
dvfcmp_nbsn_rsl (신설부문 매출), atdvfdtl_* (존속회사 재무), atdv_excmp_exbsn_rsl (존속부문 매출). The same table exists in the
filing text for every year, so an LLM reads it off the text. Validation: run on 2017+ filings and compare with the API values
(--validate uses data/processed/baseline_features.json).
Usage: python code/12e_extract_filing_financials.py --tracking data/processed/carveout_events_2001_2016.json \
          --index data/processed/disclosure_text_index_2001_2016.json --out results/filing_financials_2001_2016.jsonl [--workers 3]
       python code/12e_extract_filing_financials.py --validate --limit 60 --out results/filing_financials_validation_2017.jsonl
"""
import os, re, json, time, argparse, random, threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import boto3
from botocore.config import Config

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = "us.anthropic.claude-fable-5-1"
SYSTEM = """You read ONE Korean filing announcing a corporate division (회사분할결정 / 주요사항보고서(회사분할결정)). Extract the numbers
exactly as written in the filing's tables (do not compute, do not convert units; report the unit you see). Return ONLY JSON:
{"unit": string (e.g. "원", "천원", "백만원", as stated or inferred from the table header; null if unclear),
 "new_company": {"total_assets": number|null, "total_debt": number|null, "total_equity": number|null, "paid_in_capital": number|null, "recent_year_sales": number|null},
 "surviving_company_after_division": {"total_assets": number|null, "total_debt": number|null, "total_equity": number|null, "paid_in_capital": number|null, "recent_year_sales": number|null},
 "dividing_company_before_division": {"total_assets": number|null, "total_debt": number|null, "total_equity": number|null},
 "relisting_or_listing_application": "yes"|"no"|"not_stated", "appraisal_rights": "yes"|"no"|"not_stated", "put_option_or_similar_contract": "yes"|"no"|"not_stated",
 "outside_directors_present": number|null, "outside_directors_absent": number|null,
 "multiple_new_companies": true|false, "evidence": {"new_company_assets": string (verbatim row, <=120 chars), "surviving_assets": string},
 "confidence": "high"|"medium"|"low"}
If several new companies are created, report the sum only if the filing gives a total; otherwise report the first and set multiple_new_companies=true."""


def client():
    return boto3.Session(profile_name=os.environ.get("AWS_PROFILE", "default")).client("bedrock-runtime", region_name="us-east-1",
                                                                                        config=Config(retries={"max_attempts": 2, "mode": "adaptive"}, connect_timeout=30, read_timeout=300))


def call(c, text, effort):
    kw = dict(modelId=MODEL, system=[{"text": SYSTEM}], messages=[{"role": "user", "content": [{"text": text[:60000]}]}], inferenceConfig={"maxTokens": 3000})
    for attempt, eff in enumerate([effort, effort, None]):
        try:
            k = dict(kw)
            if eff: k["additionalModelRequestFields"] = {"thinking": {"type": "adaptive"}, "output_config": {"effort": eff}}
            r = c.converse(**k); txt = "".join(b.get("text", "") for b in r["output"]["message"]["content"] if "text" in b)
            if txt: return txt
        except Exception: time.sleep(5 * (attempt + 1))
    return ""


def parse_json(s):
    m = re.search(r"\{.*\}", s, re.S)
    if not m: return None
    try: return json.loads(m.group(0))
    except Exception:
        try: return json.loads(re.sub(r",\s*([}\]])", r"\1", m.group(0)))
        except Exception: return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--tracking", default=f"{P}/data/processed/carveout_events_2001_2016.json"); ap.add_argument("--index", default=f"{P}/data/processed/disclosure_text_index_2001_2016.json")
    ap.add_argument("--out", required=True); ap.add_argument("--workers", type=int, default=3); ap.add_argument("--limit", type=int, default=0); ap.add_argument("--effort", default="medium"); ap.add_argument("--validate", action="store_true")
    a = ap.parse_args()
    if a.validate:
        ev = [e for e in json.load(open(f"{P}/data/raw/dart_division_decisions_2017_2026.json", encoding="utf-8")) if e["type"] in ("carve_out", "mixed")]
        idx = json.load(open(f"{P}/data/processed/disclosure_text_index.json", encoding="utf-8")); ev = [e for e in ev if idx.get(e["rcept_no"], {}).get("path")]
        random.seed(11); random.shuffle(ev)
    else:
        ev = json.load(open(a.tracking, encoding="utf-8")); idx = json.load(open(a.index, encoding="utf-8")); ev = [e for e in ev if idx.get(e["rcept_no"], {}).get("path")]
    done = {json.loads(l)["rcept_no"] for l in open(a.out, encoding="utf-8")} if os.path.exists(a.out) else set()
    todo = [e for e in ev if e["rcept_no"] not in done]
    if a.limit: todo = todo[:a.limit]
    print(f"todo {len(todo)} done {len(done)}", flush=True)
    c = client(); lock = threading.Lock(); t0 = time.time(); n = 0

    def work(e):
        path = idx[e["rcept_no"]]["path"]; path = path if os.path.isabs(path) else f"{P}/{path}"
        t = open(path, encoding="utf-8").read(); t1 = time.time()
        raw = call(c, f"Filer: {e['corp_name']}. Filing receipt no. {e['rcept_no']}.\n\n{t}", a.effort)
        return {"rcept_no": e["rcept_no"], "corp_name": e["corp_name"], "model": MODEL, "latency_s": round(time.time() - t1, 1), "parsed": parse_json(raw) if raw else None, "raw_chars": len(raw)}

    with ThreadPoolExecutor(max_workers=a.workers) as ex, open(a.out, "a", encoding="utf-8") as f:
        for fu in as_completed([ex.submit(work, e) for e in todo]):
            rec = fu.result(); n += 1
            with lock: f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
            p = rec["parsed"] or {}
            if n % 10 == 0 or n == len(todo): print(f"  [{n}/{len(todo)}] last: {rec['corp_name'][:10]} unit={p.get('unit')} newco_assets={(p.get('new_company') or {}).get('total_assets')} conf={p.get('confidence')} [{time.time()-t0:.0f}s]", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
