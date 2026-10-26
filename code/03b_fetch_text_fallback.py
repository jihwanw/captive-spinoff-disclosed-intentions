#!/usr/bin/env python3
"""03b_fetch_text_fallback.py — filing text for events whose collected rcept_no has no document file on DART.

Finding (2026-10-17): for 26 clean-labelled carve-outs the DART document API returns status 014 '파일이 존재하지 않습니다'.
In every inspected case the collected rcept_no is a [기재정정] (correction) version of 주요사항보고서(회사분할결정) and the
ORIGINAL filing (earlier date) is downloadable. Fallback: list the company's 주요사항보고 filings (pblntf_ty=B) from 15 days
before the board date to 10 days after the collected filing, keep those with '회사분할결정' in the title, and take the
earliest downloadable one. The text is stored under the EVENT rcept_no (so downstream loaders are unchanged) and the index
records `text_rcept_no`, `text_report_nm`, `text_is_original_filing`. Using the original filing is also the cleaner
"as-of-announcement" text (a correction filed later can carry later information).
"""
import os, re, json, time, datetime as dt, urllib.request, urllib.parse

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(f"{P}/code/03_fetch_disclosure_text.py", encoding="utf-8").read()
ns = {"__file__": os.path.abspath(f"{P}/code/03_fetch_disclosure_text.py")}; exec(src.split("\nevents = json.load(")[0], ns)
fetch, OUTDIR, INDEX, KEY = ns["fetch"], ns["OUTDIR"], ns["INDEX"], ns["KEY"]
EVENTS = f"{P}/data/raw/dart_division_decisions_2017_2026.json"


def api(ep, **kw):
    q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in kw.items())
    for a in range(3):
        try:
            with urllib.request.urlopen(f"https://opendart.fss.or.kr/api/{ep}.json?crtfc_key={KEY}&{q}", timeout=40) as r: return json.load(r)
        except Exception: time.sleep(2 + 3 * a)
    return {}


def kdate(s):
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", s or "")
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


ev = {e["rcept_no"]: e for e in json.load(open(EVENTS, encoding="utf-8"))}
idx = json.load(open(INDEX, encoding="utf-8"))
targets = [rn for rn, m in idx.items() if not m.get("path") and rn in ev]
print("events without text:", len(targets))
ok = 0
for rn in targets:
    e = ev[rn]; d_rc = dt.datetime.strptime(rn[:8], "%Y%m%d").date(); d_bd = kdate(e["board_date"]) or d_rc
    bgn = (min(d_bd, d_rc) - dt.timedelta(days=15)).strftime("%Y%m%d"); end = (d_rc + dt.timedelta(days=10)).strftime("%Y%m%d")
    lst = api("list", corp_code=e["corp_code"], bgn_de=bgn, end_de=end, pblntf_ty="B", page_count=100).get("list", []) or []
    cands = sorted([r for r in lst if "회사분할결정" in r["report_nm"]], key=lambda r: r["rcept_no"])
    got = None
    for r in cands:
        txt = fetch(r["rcept_no"])
        if txt: got = (r, txt); break
        time.sleep(0.2)
    if got:
        r, txt = got; path = f"{OUTDIR}/{rn}.txt"; open(path, "w", encoding="utf-8").write(txt)
        idx[rn].update({"chars": len(txt), "path": f"data/raw/disclosure_text/{rn}.txt", "text_rcept_no": r["rcept_no"], "text_report_nm": r["report_nm"],
                        "text_is_original_filing": not r["report_nm"].startswith("["), "text_fetch_note": "collected rcept_no has no document file on DART (status 014); text taken from this filing"})
        ok += 1; print(f"  {e['corp_name']:14s} {rn} -> {r['rcept_dt']} {r['report_nm']} ({len(txt):,} chars)", flush=True)
    else:
        idx[rn]["text_fetch_note"] = f"no downloadable 회사분할결정 filing among {len(cands)} candidates ({bgn}-{end})"
        print(f"  {e['corp_name']:14s} {rn} -> none of {len(cands)} candidates downloadable", flush=True)
json.dump(idx, open(INDEX, "w"), ensure_ascii=False, indent=1)
print(f"done: fetched {ok} / {len(targets)}")
