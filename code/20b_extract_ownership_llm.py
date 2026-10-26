#!/usr/bin/env python3
"""20b_extract_ownership_llm.py — controlling-shareholder ownership before pre-2016 carve-outs, from the cached annual-report texts.

The DART ownership API (20) starts at fiscal 2015. For earlier announcements the table "최대주주 및 특수관계인의 주식소유 현황"
(older reports: "주주의 분포") in the parent's 사업보고서 is read instead. Report choice per event: the report for the fiscal year
BEFORE the division year when it is cached (76 events), otherwise the division-year report, whose 기초 (fiscal-year-start) column is the
ownership at the end of the previous year, i.e. before the division (349 events). The table lists the largest shareholder and related
persons/entities with shares and % at 기초 and 기말, a 계 (total) row, and sometimes treasury rows (자사주/자기주식).

Two steps:
  --build   (Mac) locate the table passage in data/raw/annual_report_text/<rcept_no>.txt.gz (heading regex, the occurrence followed by a
            기준일 line within 400 chars, 7,000 characters) -> data/processed/ownership_passages_pre2016.json
  --extract (EC2) send each passage to the model and parse strict JSON -> results/ownership_llm/<model>.jsonl
Extraction schema (per event): basis ('기초' or '기말' column used, as instructed), fiscal_year_end, largest_name, largest_pct, block_pct
(sum of all listed holders' % in that column, treasury rows excluded), treasury_pct, n_rows, table_found, notes. The model is told to copy
numbers, never to compute from share counts, and to return null when the table is absent.
"""
import os, re, json, gzip, time, argparse, datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASS = f"{P}/data/processed/ownership_passages_pre2016.json"; OUTDIR = f"{P}/results/ownership_llm"; os.makedirs(OUTDIR, exist_ok=True)
MODELS = {"anthropic": "us.anthropic.claude-fable-5-1", "openai": "us.openai.gpt-6.1-sol"}
HEAD = re.compile(r"(최대주주\s*및\s*(그\s*)?특수\s*관계인(의)?\s*(주식\s*)?소유\s*현황|주주의\s*분포|최대주주\s*및\s*특수관계인의\s*주식\s*소유)", re.I)
BASIS = re.compile(r"기준일")

SYSTEM = """You read one passage from a Korean listed company's annual report (사업보고서) containing the table of the largest shareholder and related
parties' share ownership (최대주주 및 특수관계인의 주식소유 현황; in older reports 주주의 분포). The table lists holders (성명), their relation to
the largest shareholder (관계), share class (주식의 종류), and shares / ownership % — usually both at fiscal-year start (기초) and end (기말) —
and a total row (계). Some rows are the company's own treasury shares (자사주, 자기주식).

Task: copy the numbers for COMMON shares (보통주) in the column the user names (기초 or 기말). Do not compute percentages from share counts;
copy the percentage printed. Return ONLY a JSON object:
 {"table_found": true/false,
  "fiscal_year_end": "YYYY-MM-DD or null",
  "column_used": "기초" or "기말" or null,
  "largest_name": string or null, "largest_relation": string or null, "largest_pct": number or null,
  "block_pct_total_row": number or null  (the 계 row's % in that column, if printed),
  "block_pct_sum_ex_treasury": number or null  (sum of the listed holders' % in that column excluding treasury rows; copy and add the printed values),
  "treasury_pct": number (0 if no treasury row),
  "n_holder_rows": integer,
  "notes": short string (e.g. 'only 기말 printed', 'two share classes', 'percentages missing')}"""


def build():
    lc = json.load(open(f"{P}/data/raw/dart_cache_annual_report_list.json", encoding="utf-8"))
    old = json.load(open(f"{P}/data/processed/carveout_disposal_tracking_2001_2016.json", encoding="utf-8"))
    out, stat = [], {}
    for r in old:
        if int(r["rcept_no"][:4]) - 1 >= 2015: continue                      # covered by the API (20)
        dy = int(r["division_year"]); fys = {}
        for kk in [k for k in lc if k.startswith(r["corp_code"] + ":")]:
            for row in lc[kk]:
                m = re.search(r"\((\d{4})\.(\d{2})\)", row.get("report_nm", ""))
                if "사업보고서" in row.get("report_nm", "") and m and os.path.exists(f"{P}/data/raw/annual_report_text/{row['rcept_no']}.txt.gz"):
                    fy = int(m.group(1)); fys.setdefault(fy, []).append((row["rcept_dt"], row["rcept_no"]))
        rec = {"rcept_no": r["rcept_no"], "corp_code": r["corp_code"], "corp_name": r["corp_name"], "division_year": dy, "event_year": int(r["rcept_no"][:4])}
        if dy - 1 in fys: fy, col = dy - 1, "기말"
        elif dy in fys: fy, col = dy, "기초"
        else: rec["status"] = "no_report_cached"; stat["no_report_cached"] = stat.get("no_report_cached", 0) + 1; out.append(rec); continue
        rn = sorted(fys[fy])[-1][1]                                             # latest filing for that FY (corrections included)
        t = gzip.open(f"{P}/data/raw/annual_report_text/{rn}.txt.gz", "rt", encoding="utf-8", errors="ignore").read()
        cands = [m.start() for m in HEAD.finditer(t)]
        pos = next((i for i in cands if BASIS.search(t[i:i + 400])), None)       # the table itself, not a table-of-contents line
        if pos is None and cands: pos = cands[-1]
        if pos is None: rec.update(status="heading_not_found", report_rcept_no=rn, report_fy=fy); stat["heading_not_found"] = stat.get("heading_not_found", 0) + 1; out.append(rec); continue
        rec.update(status="ok", report_rcept_no=rn, report_fy=fy, column=col, passage=t[pos:pos + 7000]); stat["ok"] = stat.get("ok", 0) + 1; out.append(rec)
    json.dump(out, open(PASS, "w"), ensure_ascii=False)
    print("passages:", stat, "| column use:", {c: sum(1 for r in out if r.get("column") == c) for c in ("기초", "기말")})


def client():
    import boto3; from botocore.config import Config
    return boto3.Session(profile_name=os.environ.get("AWS_PROFILE", "default")).client("bedrock-runtime", region_name="us-east-1", config=Config(retries={"max_attempts": 4, "mode": "adaptive"}, read_timeout=300))

def call(c, provider, model, text):
    kw = dict(modelId=model, system=[{"text": SYSTEM}], messages=[{"role": "user", "content": [{"text": text}]}], inferenceConfig={"maxTokens": 4000})
    def extra(effort):
        if effort is None: return None
        return {"thinking": {"type": "adaptive"}, "output_config": {"effort": effort}} if provider == "anthropic" else {"reasoning": {"effort": effort}}
    for attempt, effort in enumerate(["high", "high", None]):
        try:
            k = dict(kw); x = extra(effort)
            if x: k["additionalModelRequestFields"] = x
            r = c.converse_stream(**k); out = []
            for ev in r["stream"]:
                if "contentBlockDelta" in ev:
                    d = ev["contentBlockDelta"].get("delta", {})
                    if "text" in d: out.append(d["text"])
            txt = "".join(out).strip()
            if txt: return txt, effort or "none"
        except Exception as ex:
            if any(w in str(ex) for w in ("thinking", "output_config", "reasoning")): continue
            time.sleep(5 * (attempt + 1))
    return None, None

def parse_json(s):
    m = re.search(r"\{.*\}", s or "", re.S)
    if not m: return None
    try: return json.loads(m.group(0))
    except Exception:
        try: return json.loads(re.sub(r",\s*([}\]])", r"\1", m.group(0)))
        except Exception: return None

def extract(provider, workers):
    model = MODELS[provider]; out = f"{OUTDIR}/{provider}.jsonl"
    done = {json.loads(l)["rcept_no"] for l in open(out, encoding="utf-8")} if os.path.exists(out) else set()
    todo = [r for r in json.load(open(PASS, encoding="utf-8")) if r.get("status") == "ok" and r["rcept_no"] not in done]
    print(f"model={model} todo={len(todo)} done={len(done)}", flush=True); c = client(); t0 = time.time()
    def one(r):
        user = f"Company: {r['corp_name']}. Report fiscal year: {r['report_fy']}. Use the {r['column']} column (ownership at {'fiscal-year start' if r['column']=='기초' else 'fiscal-year end'}).\n\n=== PASSAGE ===\n{r['passage']}\n=== END ==="
        t1 = time.time(); txt, eff = call(c, provider, model, user); p = parse_json(txt)
        return {"rcept_no": r["rcept_no"], "corp_name": r["corp_name"], "division_year": r["division_year"], "report_rcept_no": r["report_rcept_no"], "report_fy": r["report_fy"], "column": r["column"],
                "model": model, "effort": eff, "latency_s": round(time.time() - t1, 1), "raw": txt, "parsed": p}
    with ThreadPoolExecutor(max_workers=workers) as ex, open(out, "a", encoding="utf-8") as f:
        futs = {ex.submit(one, r): r for r in todo}
        for i, fu in enumerate(as_completed(futs), 1):
            rec = fu.result(); f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush(); p = rec["parsed"] or {}
            print(f"[{i}/{len(todo)}] {rec['corp_name'][:12]:12s} FY{rec['report_fy']} {rec['column']} found={p.get('table_found')} largest={p.get('largest_pct')} block={p.get('block_pct_total_row')}/{p.get('block_pct_sum_ex_treasury')} {rec['latency_s']}s [{time.time()-t0:.0f}s]", flush=True)
    print("done")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--build", action="store_true"); ap.add_argument("--extract", choices=list(MODELS)); ap.add_argument("--workers", type=int, default=4)
    a = ap.parse_args()
    if a.build: build()
    if a.extract: extract(a.extract, a.workers)
