#!/usr/bin/env python3
"""12_collect_division_filings_2001_2016.py — all DART filings with '분할' in the title, 2001-01 .. 2016-12.

Why: the structured endpoint cmpDvDecsn returns records only from about 2017 (01_collect_division_decisions.py), but the
disclosure search endpoint list.json (DART DS001 공시검색) covers earlier years. Scanning by date range WITHOUT corp_code
returns every company's filings of a type (checked 2026-10-18: 2016-11 type B = 635 filings / 7 pages; 2005-03 type B =
7,866 — pre-2009 수시공시 titles such as '회사분할결정' are classified under B; type I (거래소공시) = 2,167).
Parameters (DART developer guide, 공시검색): bgn_de/end_de YYYYMMDD, pblntf_ty (A 정기공시, B 주요사항보고, I 거래소공시, ...),
page_no, page_count <= 100; response total_count/total_page; status 013 = no data.
Output: data/raw/dart_division_filings_2001_2016_raw.json (list of filing rows incl. corp_code/corp_name/corp_cls/report_nm/rcept_no/rcept_dt)
        data/raw/dart_list_scan_cache_2001_2016.json (per month/type: pages done, rows kept) — resumable.
"""
import os, json, time, sys, urllib.request, urllib.parse, configparser, datetime as dt

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = f"{P}/data/raw/dart_list_scan_cache_2001_2016.json"
OUT = f"{P}/data/raw/dart_division_filings_2001_2016_raw.json"
cfg = configparser.ConfigParser(); cfg.read("/Users/jihwanw/PhD/code/api_info/api_keys.ini")
KEY = cfg["dart"].get("api_key") or cfg["dart"].get("key") or list(cfg["dart"].values())[0]
TYPES = ("B", "I")
YEARS = range(2001, 2017)


def api(**kw):
    q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in kw.items())
    for a in range(4):
        try:
            with urllib.request.urlopen(f"https://opendart.fss.or.kr/api/list.json?crtfc_key={KEY}&{q}", timeout=60) as r: d = json.load(r)
            if d.get("status") in ("020", "800", "021"): print("STOP", d, flush=True); sys.exit(2)   # key limit / maintenance
            return d
        except SystemExit: raise
        except Exception as e:
            time.sleep(3 + 5 * a)
    return {}


cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
t0 = time.time(); calls = 0
for y in YEARS:
    for m in range(1, 13):
        last = (dt.date(y + (m == 12), (m % 12) + 1, 1) - dt.timedelta(days=1)).day
        bgn, end = f"{y}{m:02d}01", f"{y}{m:02d}{last:02d}"
        for ty in TYPES:
            k = f"{y}-{m:02d}:{ty}"
            if cache.get(k, {}).get("done"): continue
            rows, page, total_page = [], 1, 1
            while page <= total_page:
                d = api(bgn_de=bgn, end_de=end, pblntf_ty=ty, page_no=page, page_count=100); calls += 1
                if d.get("status") == "013": break
                total_page = int(d.get("total_page", 1) or 1)
                for r in d.get("list", []) or []:
                    if "분할" in (r.get("report_nm") or ""): rows.append(r)
                page += 1; time.sleep(0.2)
            cache[k] = {"done": True, "pages": total_page, "total_count": int(d.get("total_count", 0) or 0) if d else 0, "kept": len(rows), "rows": rows}
            json.dump(cache, open(CACHE, "w"), ensure_ascii=False)
        kept = sum(v["kept"] for kk, v in cache.items() if kk.startswith(f"{y}-{m:02d}"))
        print(f"{y}-{m:02d}: kept {kept} filings with '분할' (calls so far {calls}, {time.time()-t0:.0f}s)", flush=True)
allrows = [r for v in cache.values() for r in v["rows"]]
# de-duplicate by rcept_no
seen, out = set(), []
for r in allrows:
    if r["rcept_no"] not in seen: seen.add(r["rcept_no"]); out.append(r)
json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
import collections
print("done:", len(out), "filings; by year:", dict(sorted(collections.Counter(r["rcept_dt"][:4] for r in out).items())))
print("title kinds:", collections.Counter(r["report_nm"].replace("[기재정정]", "").replace("[첨부정정]", "").replace("[첨부추가]", "").replace("[정정]", "")[:16] for r in out).most_common(15))
