#!/usr/bin/env python3
"""Count Korean listed-company division decisions via DART Open API (feasibility pilot).

Endpoints: cmpDvDecsn (회사분할결정), cmpDvmgDecsn (회사분할합병결정); period 2017-01-01 .. today.
Universe: every corp_code in CORPCODE.xml with a non-empty stock_code (listed at some point).
De-duplication: one event per (corp_code, dvdt 분할기일); corrections (정정) collapse onto it.
Classification from dv_mth (분할방법) text: '인적' -> spin_off, '물적' -> carve_out, else other.
Output: /tmp/dart_div/divisions.json (events) and progress.json (counts so far).
"""
import json, os, re, sys, time, urllib.request, urllib.parse, configparser
import xml.etree.ElementTree as ET

OUT = "/tmp/dart_div"; os.makedirs(OUT, exist_ok=True)
cfg = configparser.ConfigParser(); cfg.read("/Users/jihwanw/PhD/code/api_info/api_keys.ini")
KEY = cfg["dart"].get("api_key") or cfg["dart"].get("key") or list(cfg["dart"].values())[0]
BGN, END = "20170101", time.strftime("%Y%m%d")

root = ET.parse("/tmp/CORPCODE.xml").getroot()
listed = []
for el in root.iter("list"):
    s = (el.findtext("stock_code") or "").strip()
    if s:
        listed.append(((el.findtext("corp_code") or "").strip(), (el.findtext("corp_name") or "").strip(), s))
listed.sort()
print(f"listed corp codes: {len(listed)}", flush=True)


def fetch(ep, corp_code):
    url = f"https://opendart.fss.or.kr/api/{ep}.json?crtfc_key={KEY}&corp_code={corp_code}&bgn_de={BGN}&end_de={END}"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                d = json.load(r)
            if d.get("status") in ("000", "013"):
                return d.get("list", []) or []
            if d.get("status") in ("020", "800"):  # quota exceeded / system maintenance
                print("STOP:", d.get("status"), d.get("message"), flush=True); sys.exit(2)
            return []
        except Exception as e:  # noqa: BLE001
            time.sleep(2 + 3 * attempt)
    return []


def classify(mth):
    t = re.sub(r"\s+", "", mth or "")
    if "인적" in t and "물적" in t: return "mixed"
    if "인적" in t: return "spin_off"
    if "물적" in t: return "carve_out"
    return "other"


events, seen = [], set()
t0 = time.time()
for i, (code, name, stk) in enumerate(listed, 1):
    for ep in ("cmpDvDecsn", "cmpDvmgDecsn"):
        for x in fetch(ep, code):
            key = (code, x.get("dvdt") or x.get("dvmgdt") or x.get("rcept_no"))
            if key in seen: continue
            seen.add(key)
            events.append({"endpoint": ep, "corp_code": code, "corp_name": x.get("corp_name", name), "stock_code": stk,
                           "corp_cls": x.get("corp_cls"), "rcept_no": x.get("rcept_no"), "board_date": x.get("bddd"),
                           "division_date": x.get("dvdt") or x.get("dvmgdt"), "method": (x.get("dv_mth") or x.get("dvmg_mth") or "")[:400],
                           "type": classify(x.get("dv_mth") or x.get("dvmg_mth")), "ratio": x.get("dv_rt"),
                           "new_co": x.get("dvfcmp_cmpnm"), "new_shares_listing_plan": x.get("abcr_nstklstprd"),
                           "appraisal_right": x.get("popt_ctr_atn"), "purpose": (x.get("dv_impef") or "")[:600]})
        time.sleep(0.05)
    if i % 100 == 0 or i == len(listed):
        from collections import Counter
        c = Counter(e["type"] for e in events)
        prog = {"processed": i, "of": len(listed), "events": len(events), "by_type": dict(c), "elapsed_s": round(time.time() - t0),
                "by_year": dict(Counter((e["board_date"] or "")[:4] for e in events))}
        json.dump(prog, open(f"{OUT}/progress.json", "w"), ensure_ascii=False, indent=1)
        json.dump(events, open(f"{OUT}/divisions.json", "w"), ensure_ascii=False, indent=1)
        print(f"{i}/{len(listed)} events={len(events)} {dict(c)} [{prog['elapsed_s']}s]", flush=True)
print("done", flush=True)
