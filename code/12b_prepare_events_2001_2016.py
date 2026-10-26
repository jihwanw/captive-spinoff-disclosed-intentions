#!/usr/bin/env python3
"""12b_prepare_events_2001_2016.py — from the raw '분할' filing list (12) to structured division events for 2001-2016.

Steps
 1. Keep filings whose title (without [정정] prefixes) is 회사분할결정 or 회사분할합병결정 (drop 주식분할결정 = stock splits, which
    dominate the raw list: 410 of 536 rows in the first 76 months).
 2. Fetch the filing text (DART document.xml; same decoder as 03). Early documents can be irrecoverably mangled on DART's
    side (2001-01-17 디지탈엔비전: UTF-8 bytes already containing U+FFFD) — flagged `unreadable` when the Korean-character
    share of the text is below 15% or U+FFFD appears, and excluded from text-based steps.
 3. Cluster filings of the same corp_code within 200 days into one event (original + corrections); event id = earliest rcept_no.
 4. LLM extraction (Claude, adaptive thinking, effort medium) of structured fields from the latest readable filing text of
    the event: division type (물적/인적/혼합/분할합병), board date, division date, new company name(s), whether the new
    company's shares are allotted to the parent (물적) or to shareholders (인적), stated listing plan, purpose; verbatim evidence.
Outputs: data/raw/division_filings_2001_2016_filtered.json, data/raw/disclosure_text_2001_2016/<rcept_no>.txt,
         data/processed/division_events_2001_2016.json (events with LLM fields), results/division_events_2001_2016_extract.log
Usage: python code/12b_prepare_events_2001_2016.py [--skip-llm] [--workers 3]
"""
import os, re, json, time, argparse, datetime as dt, threading, collections
from concurrent.futures import ThreadPoolExecutor, as_completed

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = f"{P}/data/raw/dart_division_filings_2001_2016_raw.json"
FILT = f"{P}/data/raw/division_filings_2001_2016_filtered.json"
TXTDIR = f"{P}/data/raw/disclosure_text_2001_2016"; os.makedirs(TXTDIR, exist_ok=True)
OUT = f"{P}/data/processed/division_events_2001_2016.json"
_fetch = None
def fetch(rn):
    """DART document fetch from 03 (loaded lazily: needs api_keys.ini, absent on EC2 where only the LLM step runs on synced texts)."""
    global _fetch
    if _fetch is None:
        src03 = open(f"{P}/code/03_fetch_disclosure_text.py", encoding="utf-8").read()
        ns = {"__file__": os.path.abspath(f"{P}/code/03_fetch_disclosure_text.py")}; exec(src03.split("\nevents = json.load(")[0], ns); _fetch = ns["fetch"]
    return _fetch(rn)

ap = argparse.ArgumentParser(); ap.add_argument("--skip-llm", action="store_true"); ap.add_argument("--workers", type=int, default=3); ap.add_argument("--effort", default="medium"); a = ap.parse_args()

rows = json.load(open(RAW, encoding="utf-8"))
def base_title(t): return re.sub(r"\[[^\]]+\]", "", t or "").strip()
# Filer's OWN division decisions, every title variant seen in the 2001-2016 scan (listed 2026-10-19 from the raw file):
OWN_TITLES = {"회사분할결정", "회사분할합병결정", "회사분할결정(물적분할)", "주요사항보고서(회사분할결정)", "주요사항보고서(회사분할합병결정)",
              "주요사항보고서(분할(분할합병)결정)", "주요사항보고서(회사분할(분할합병)결정)"}
# excluded on purpose: '…(종속회사의주요경영사항)' / '…(자회사의 주요경영사항)' (a subsidiary's division reported by its parent), 주권매매거래정지,
# 소송, 최대주주 변동, 기타시장안내, 임시주주총회결과, 주식분할(액면분할)결정.
filt = [r for r in rows if base_title(r["report_nm"]) in OWN_TITLES]
json.dump(filt, open(FILT, "w"), ensure_ascii=False, indent=1)
print(f"raw rows {len(rows)} -> division filings {len(filt)}; by year:", dict(sorted(collections.Counter(r['rcept_dt'][:4] for r in filt).items())), flush=True)

# ---- text
def readable(t):
    if not t: return False
    body = re.sub(r"\s+", "", t)
    if not body: return False
    return ("\ufffd" not in body) and (len(re.findall(r"[가-힣]", body)) / len(body) >= 0.15)
texts = {}
for i, r in enumerate(filt, 1):
    rn = r["rcept_no"]; p = f"{TXTDIR}/{rn}.txt"
    if os.path.exists(p): t = open(p, encoding="utf-8").read()
    else:
        t = fetch(rn) or ""; open(p, "w", encoding="utf-8").write(t); time.sleep(0.15)
    texts[rn] = {"chars": len(t), "readable": readable(t)}
    if i % 100 == 0: print(f"  text {i}/{len(filt)} readable so far {sum(v['readable'] for v in texts.values())}", flush=True)
print("texts: readable", sum(v["readable"] for v in texts.values()), "unreadable/empty", sum(not v["readable"] for v in texts.values()), flush=True)

# ---- cluster into events
filt.sort(key=lambda r: (r["corp_code"], r["rcept_dt"]))
events = []
import itertools
for corp, grp in [(k, list(g)) for k, g in itertools.groupby(filt, key=lambda r: r["corp_code"])]:
    cur = []
    for r in grp:
        d = dt.datetime.strptime(r["rcept_dt"], "%Y%m%d").date()
        if cur and (d - dt.datetime.strptime(cur[0]["rcept_dt"], "%Y%m%d").date()).days > 200:
            events.append(cur); cur = []
        cur.append(r)
    if cur: events.append(cur)
ev_out = []
for grp in events:
    orig = grp[0]; readable_rns = [r["rcept_no"] for r in grp if texts[r["rcept_no"]]["readable"]]
    ev_out.append({"event_id": orig["rcept_no"], "corp_code": orig["corp_code"], "corp_name": orig["corp_name"], "corp_cls": orig.get("corp_cls"), "stock_code": orig.get("stock_code"),
                   "first_filing_date": orig["rcept_dt"], "filings": [{"rcept_no": r["rcept_no"], "rcept_dt": r["rcept_dt"], "report_nm": r["report_nm"], "readable": texts[r["rcept_no"]]["readable"]} for r in grp],
                   "is_division_merger": any("분할합병" in r["report_nm"] for r in grp), "text_rcept_no": (readable_rns[-1] if readable_rns else None)})
print(f"events: {len(ev_out)} (with readable text: {sum(1 for e in ev_out if e['text_rcept_no'])}); by year:", dict(sorted(collections.Counter(e['first_filing_date'][:4] for e in ev_out).items())), flush=True)
prev = {e["event_id"]: e for e in json.load(open(OUT, encoding="utf-8"))} if os.path.exists(OUT) else {}
for e in ev_out:
    if e["event_id"] in prev and prev[e["event_id"]].get("llm"): e["llm"] = prev[e["event_id"]]["llm"]
json.dump(ev_out, open(OUT, "w"), ensure_ascii=False, indent=1)
if a.skip_llm: raise SystemExit

# ---- LLM extraction
import boto3
from botocore.config import Config
MODEL = "us.anthropic.claude-fable-5-1"
SYSTEM = """You extract structured facts from ONE Korean regulatory filing announcing a corporate division (회사분할결정 or 회사분할합병결정,
2001-2016 formats: either a short 수시공시 table or a 주요사항보고서). Use only the filing text. Return ONLY JSON:
{"division_type": "물적분할"|"인적분할"|"혼합(물적+인적)"|"분할합병"|"unclear",
 "type_evidence": string (verbatim, <=150 chars),
 "board_date": "YYYY-MM-DD"|null, "division_date": "YYYY-MM-DD"|null (분할기일),
 "new_companies": [{"name": string, "business": string, "shares_allotted_to": "parent"|"shareholders"|"unclear"}],
 "surviving_company_listed": true|false|null, "new_company_listing_plan": "none_stated"|"relisting_or_listing_planned"|"explicitly_no_listing"|"unclear",
 "stated_purpose": string (<=200 chars, Korean as written), "appraisal_rights": true|false|null,
 "confidence": "high"|"medium"|"low"}
물적분할 = all new shares go to the dividing company itself (단순분할, 분할되는 회사에 100% 배정); 인적분할 = new shares go to the dividing
company's shareholders pro rata; 혼합 = both within one plan; 분할합병 = the divided part merges into another company."""


def client():
    return boto3.Session(profile_name=os.environ.get("AWS_PROFILE", "default")).client("bedrock-runtime", region_name="us-east-1",
                                                                                        config=Config(retries={"max_attempts": 2, "mode": "adaptive"}, connect_timeout=30, read_timeout=300))


def call(c, text):
    kw = dict(modelId=MODEL, system=[{"text": SYSTEM}], messages=[{"role": "user", "content": [{"text": text[:60000]}]}], inferenceConfig={"maxTokens": 4000})
    for attempt, eff in enumerate([a.effort, a.effort, None]):
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


todo = [e for e in ev_out if e["text_rcept_no"] and not e.get("llm")]
print(f"LLM extraction: todo {len(todo)}", flush=True)
c = client(); lock = threading.Lock(); t0 = time.time(); n = 0
def work(e):
    t = open(f"{TXTDIR}/{e['text_rcept_no']}.txt", encoding="utf-8").read()
    raw = call(c, f"Filing date: {e['first_filing_date']}. Filer: {e['corp_name']}.\n\n{t}"); return e, raw, parse_json(raw) if raw else None
with ThreadPoolExecutor(max_workers=a.workers) as ex:
    for fu in as_completed([ex.submit(work, e) for e in todo]):
        e, raw, parsed = fu.result(); n += 1
        with lock:
            e["llm"] = {"model": MODEL, "parsed": parsed, "raw_chars": len(raw)}
            if n % 10 == 0 or n == len(todo):
                json.dump(ev_out, open(OUT, "w"), ensure_ascii=False, indent=1)
                print(f"  [{n}/{len(todo)}] types so far: {dict(collections.Counter((x.get('llm') or {}).get('parsed', {}).get('division_type') for x in ev_out if x.get('llm')))} [{time.time()-t0:.0f}s]", flush=True)
json.dump(ev_out, open(OUT, "w"), ensure_ascii=False, indent=1)
print("done", flush=True)
