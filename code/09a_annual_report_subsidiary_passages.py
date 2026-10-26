#!/usr/bin/env python3
"""09a_annual_report_subsidiary_passages.py — passages about the carved-out company in the parent's annual reports.

Why: the v3 tracker reads 타법인출자현황 (DART otrCprInvstmntSttus), which many parents omit for 100%-owned
subsidiaries, and it matches the new company by the (often provisional, '(가칭)') name in the division filing.
Example (checked 2026-10-17): 남선알미늄 2018 — decision filing names '주식회사 남선인베스트먼트(가칭)', the company
was established as '주식회사 남선홀딩스'; the parent's annual reports state '종속기업명 주식회사 남선홀딩스 … 지분율(%) 100 …
2018년 12월 27일을 분할기일로 하여 물적분할의 방법으로 지배기업에서 분할신설' — never matched by name.

What: for each queued event (outcome unmatched / majority_disposed_or_dropped / retained_100-with-filings),
  1. list the parent's 사업보고서 for fiscal years division_year..min(division_year+6, 2025) (DART list.json, pblntf_ty=A;
     report_nm '사업보고서 (YYYY.MM)', latest correction per fiscal period),
  2. download each report (document.xml zip: main document + attachments such as audit reports; text via the same
     decoder as 03_fetch_disclosure_text.py — the XML declares utf-8 but is often CP949),
  3. extract passages: (a) around any variant of the new company's name, (b) around '분할신설/물적분할/분할기일' in the
     notes, (c) the '종속기업 현황' / '연결대상 종속기업' tables (header + 2,500 chars), keeping windows that mention 지분율/%.
Output: data/processed/annual_report_subsidiary_passages_v1.json ; cache: data/raw/annual_report_text/<rcept_no>.txt.gz
The LLM extraction over these passages is step 09b.
"""
import os, re, io, sys, json, gzip, time, zipfile, urllib.request, urllib.parse, configparser, html

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = f"{P}/results/label_audit_queue_v3.json"
V3 = f"{P}/data/processed/carveout_disposal_tracking_v3.json"
TXTDIR = f"{P}/data/raw/annual_report_text"; os.makedirs(TXTDIR, exist_ok=True)
LISTCACHE = f"{P}/data/raw/dart_cache_annual_report_list.json"
OUT = f"{P}/data/processed/annual_report_subsidiary_passages_v1.json"
LAST_FY = 2025
cfg = configparser.ConfigParser(); cfg.read("/Users/jihwanw/PhD/code/api_info/api_keys.ini")
KEY = cfg["dart"].get("api_key") or cfg["dart"].get("key") or list(cfg["dart"].values())[0]


def to_text(raw: bytes) -> str:  # identical to 03_fetch_disclosure_text.py
    for enc in ("utf-8", "cp949", "euc-kr"):
        try: s = raw.decode(enc); break
        except Exception: s = None
    if s is None: s = raw.decode("utf-8", "replace")
    s = re.sub(r"<(TD|TH|TR|P|BR|TABLE|TU|TE)[^>]*>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s); s = html.unescape(s).replace("&cr;", "\n")
    s = re.sub(r"[ \t\xa0]+", " ", s); s = re.sub(r"\n\s*\n+", "\n", s)
    return s.strip()


def api(ep, **kw):
    q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in kw.items())
    for a in range(3):
        try:
            with urllib.request.urlopen(f"https://opendart.fss.or.kr/api/{ep}.json?crtfc_key={KEY}&{q}", timeout=40) as r: d = json.load(r)
            if d.get("status") in ("020", "800"): print("STOP", d, flush=True); sys.exit(2)
            return d
        except Exception: time.sleep(2 + 3 * a)
    return {}


lcache = json.load(open(LISTCACHE, encoding="utf-8")) if os.path.exists(LISTCACHE) else {}


def annual_reports(corp, y0):
    """{fy: {rcept_no, report_nm, rcept_dt}} — latest filing per fiscal period among 사업보고서 variants."""
    k = f"{corp}:{y0}"
    if k not in lcache:
        rows = []
        for page in (1, 2, 3):
            d = api("list", corp_code=corp, bgn_de=f"{y0}0101", end_de=f"{LAST_FY + 1}1231", pblntf_ty="A", page_no=page, page_count=100)
            rows += d.get("list", []) or []
            if page >= int(d.get("total_page", 1) or 1): break
        lcache[k] = rows; time.sleep(0.05)
    out = {}
    for r in lcache[k]:
        m = re.match(r"(?:\[[^\]]+\])?\s*사업보고서\s*\((\d{4})\.(\d{2})\)", r.get("report_nm", ""))
        if not m: continue
        fy = int(m.group(1))
        if y0 <= fy <= LAST_FY and (fy not in out or r["rcept_dt"] > out[fy]["rcept_dt"]):
            out[fy] = {"rcept_no": r["rcept_no"], "report_nm": r["report_nm"], "rcept_dt": r["rcept_dt"]}
    return out


def fetch_doc(rn):
    p = f"{TXTDIR}/{rn}.txt.gz"
    if os.path.exists(p): return gzip.open(p, "rt", encoding="utf-8").read()
    for a in range(3):
        try:
            with urllib.request.urlopen(f"https://opendart.fss.or.kr/api/document.xml?crtfc_key={KEY}&rcept_no={rn}", timeout=180) as r: data = r.read()
            if data[:2] != b"PK": return None
            z = zipfile.ZipFile(io.BytesIO(data)); txt = "\n\n".join(f"[[FILE {n}]]\n" + to_text(z.read(n)) for n in z.namelist())
            with gzip.open(p, "wt", encoding="utf-8") as f: f.write(txt)
            return txt
        except Exception: time.sleep(3 + 5 * a)
    return None


def name_variants(names):
    out = set()
    for n in names:
        if not n: continue
        s = re.sub(r"\([^)]*[A-Za-z][^)]*\)", "", n)           # drop English in parentheses
        s = re.sub(r"\(?가칭\)?|주식회사|\(주\)|㈜|유한회사|\s+", "", s)
        s = s.strip("()·,.")
        if len(s) >= 2: out.add(s)
    return sorted(out, key=len, reverse=True)


def passages(txt, variants, ddate_str):
    t = re.sub(r"\s+", " ", txt)
    win, seen = [], set()
    def add(center, kind, half=320, must=None):
        a, b = max(0, center - half), min(len(t), center + half); w = t[a:b]
        if must and not re.search(must, w): return
        key = a // 200
        if key in seen: return
        seen.add(key); win.append({"kind": kind, "text": w})
    hits_name = 0
    for v in variants:
        for m in re.finditer(re.escape(v), t):
            hits_name += 1
            if len(win) < 40: add(m.start(), f"name:{v}")
    for m in re.finditer(r"분할신설|물적분할|분할기일|분할되는회사|분할로 인한|분할에 따라", t):
        if len(win) < 70: add(m.start(), "division", must=r"지분율|%|종속|신설|설립")
    for m in re.finditer(r"연결대상 ?종속(?:회사|기업)|종속기업(?:의)? ?현황|종속기업명|종속회사명", t):
        if len(win) < 85:
            a = m.start(); w = t[a:a + 2500]; key = a // 200
            if key not in seen: seen.add(key); win.append({"kind": "subsidiary_table", "text": w})
    return hits_name, win


import argparse
_ap = argparse.ArgumentParser()
_ap.add_argument("--events", default="", help="JSON file with a list of rcept_no (or of objects with rcept_no); default = the v3 audit queue")
_ap.add_argument("--out", default=OUT, help="output passages file (default data/processed/annual_report_subsidiary_passages_v1.json)")
_ap.add_argument("--tracking", default=V3, help="tracking-format event file providing corp_code/corp_name/corp_cls/division_year/division_date/new_co/candidates/outcome")
_a = _ap.parse_args(); OUT = _a.out; V3 = _a.tracking
v3 = {r["rcept_no"]: r for r in json.load(open(V3, encoding="utf-8"))}
if _a.events:
    _lst = json.load(open(_a.events, encoding="utf-8"))
    targets = [{"rcept_no": (x["rcept_no"] if isinstance(x, dict) else x), "outcome": v3[(x["rcept_no"] if isinstance(x, dict) else x)]["outcome"]} for x in _lst]
else:
    queue = json.load(open(QUEUE, encoding="utf-8"))
    targets = [q for q in queue if q["outcome"] in ("unmatched", "majority_disposed_or_dropped", "observed_no_ratio", "retained_100")]
results = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
t0 = time.time(); n_docs = 0
for i, q in enumerate(targets, 1):
    rn = q["rcept_no"]
    if rn in results and results[rn].get("complete"): continue
    r = v3[rn]; y0 = r["division_year"]
    variants = name_variants([r.get("new_co")] + list(r.get("candidates") or []))
    reports = annual_reports(r["corp_code"], y0)
    per_fy = []
    for fy in sorted(reports):
        rep = reports[fy]; txt = fetch_doc(rep["rcept_no"]); n_docs += 1
        if txt is None:
            per_fy.append({"fy": fy, **rep, "error": "download failed"}); continue
        hits, win = passages(txt, variants, r.get("division_date"))
        per_fy.append({"fy": fy, **rep, "chars": len(txt), "name_hits": hits, "passages": win})
    results[rn] = {"corp_code": r["corp_code"], "corp_name": r["corp_name"], "corp_cls": r["corp_cls"], "division_year": y0, "division_date": r.get("division_date"),
                   "new_co": r.get("new_co"), "candidates": r.get("candidates"), "name_variants": variants, "queue_outcome": q["outcome"],
                   "v3_outcome": r["outcome"], "annual_reports": per_fy, "complete": True}
    if i % 5 == 0 or i == len(targets):
        json.dump(lcache, open(LISTCACHE, "w"), ensure_ascii=False); json.dump(results, open(OUT, "w"), ensure_ascii=False)
        done = sum(1 for v in results.values() if v.get("complete"))
        print(f"{i}/{len(targets)} events | reports fetched so far {n_docs} | with name hits in >=1 report: {sum(1 for v in results.values() if any(p.get('name_hits') for p in v['annual_reports']))} [{time.time()-t0:.0f}s]", flush=True)
json.dump(lcache, open(LISTCACHE, "w"), ensure_ascii=False); json.dump(results, open(OUT, "w"), ensure_ascii=False)
print("done")
