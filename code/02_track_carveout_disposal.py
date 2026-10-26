#!/usr/bin/env python3
"""02_track_carveout_disposal.py — What happened to carved-out subsidiaries?

Sources (all open):
  DART otrCprInvstmntSttus  (사업보고서 타법인출자현황; per parent, per fiscal year; fields incl. inv_prm 법인명,
                             frst_acqs_de 최초취득일자, trmend_blce_qota_rt 기말 지분율, trmend_blce_qy 기말 수량)
  DART otcprStkInvscrTrfDecsn (타법인 주식 및 출자증권 양도결정) and cmpMgDecsn (회사합병결정), per parent after the division
  KIND corpList (listed companies with 상장일) for IPO detection; DART CORPCODE.xml stock_code as backup
Field meanings taken from the DART Open API guide (DS002 사업보고서 주요정보 / DS005 주요사항보고서).

Outcome classes (as of the latest fiscal year available, by default FY2025 filed Mar 2026):
  retained_100      parent still reports ~100% of the new company
  ipo_listed        new company appears in KIND (listed) after the division date
  partial_sale      parent stake fell below 99.5% but stays >= 50%, no listing
  majority_disposed parent stake < 50% or the row disappears after having appeared (sale / merger / transfer)
  unmatched         no row for the new company could be matched (needs manual check)
"""
import json, os, re, sys, time, configparser, urllib.request, urllib.parse, datetime as dt
from difflib import SequenceMatcher
import xml.etree.ElementTree as ET

P = "/Users/jihwanw/PhD/Finance/0_pipeline/물적분할-인적분할"
EVENTS = f"{P}/data/raw/dart_division_decisions_2017_2026.json"
OUT = f"{P}/data/processed/carveout_disposal_tracking.json"
CACHE = f"{P}/data/raw/dart_cache_otrCprInvstmntSttus.json"
KIND = "/tmp/dart_div/kind_corplist.csv"
cfg = configparser.ConfigParser(); cfg.read("/Users/jihwanw/PhD/code/api_info/api_keys.ini")
KEY = cfg["dart"].get("api_key") or cfg["dart"].get("key") or list(cfg["dart"].values())[0]
LAST_FY = 2025
TODAY = dt.date.today().strftime("%Y%m%d")


def api(ep, **kw):
    q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in kw.items())
    url = f"https://opendart.fss.or.kr/api/{ep}.json?crtfc_key={KEY}&{q}"
    for a in range(3):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                d = json.load(r)
            if d.get("status") in ("020", "800"):
                print("STOP", d.get("status"), d.get("message"), flush=True); sys.exit(2)
            return d.get("list", []) or []
        except Exception:
            time.sleep(2 + 3 * a)
    return []


ALIAS = [("엘지", "lg"), ("에스케이", "sk"), ("지에스", "gs"), ("씨제이", "cj"), ("케이티", "kt"), ("엘에스", "ls"), ("에이치디", "hd"),
         ("디엘", "dl"), ("에이치엘", "hl"), ("디비", "db"), ("오씨아이", "oci"), ("엘엔지", "lng"), ("아이앤씨", "i&c"), ("디엑스", "dx"), ("이엔지", "eng")]


def norm(s):
    s = (s or "")
    s = re.sub(r"\(.*?\)|（.*?）", "", s, flags=re.S)  # drop parenthetical (also across line breaks): (비상장), (가칭), (주)
    s = re.sub(r"\([^)]*$", "", s)                     # unbalanced trailing parenthesis
    s = re.sub(r"주식회사|㈜|\(주\)|유한회사|Co\.,?\s*Ltd\.?|Inc\.?|Corp\.?|Corporation|Company|Ltd\.?", "", s, flags=re.I)
    s = re.sub(r"[\s\.\,\-–_'\"·]+", "", s).lower()
    for ko, en in ALIAS:
        s = s.replace(ko, en)
    return s


def sim(a, b):
    """Name similarity. Substring containment counts only when the shorter name is >= 4 chars and
    covers >= 60% of the longer one (avoids '포스코' ~ '포스코DX', '워트' ~ 'LG마그나이파워트레인')."""
    if not a or not b: return 0.0
    if a == b: return 1.0
    sh, lo = (a, b) if len(a) <= len(b) else (b, a)
    if len(sh) >= 4 and sh in lo and len(sh) / len(lo) >= 0.6: return 0.95
    return SequenceMatcher(None, a, b).ratio()


def kdate(s):
    """'2020년 12월 01일' or '20201201' -> date or None"""
    if not s: return None
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", s)
    if m: return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.search(r"(\d{4})(\d{2})(\d{2})", s)
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def pct(s):
    try: return float(str(s).replace(",", "").replace("%", "").strip())
    except Exception: return None


# --- load inputs -----------------------------------------------------------
events = json.load(open(EVENTS, encoding="utf-8"))
carve = [e for e in events if e["type"] in ("carve_out", "mixed")]
import csv
kind = list(csv.DictReader(open(KIND, encoding="utf-8")))
kind_idx = [(norm(r["회사명"]), r) for r in kind]
cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
print(f"carve-outs to track: {len(carve)} | KIND listed companies: {len(kind)}", flush=True)


def holdings(corp, fy):
    k = f"{corp}:{fy}"
    if k not in cache:
        cache[k] = api("otrCprInvstmntSttus", corp_code=corp, bsns_year=fy, reprt_code="11011")
        time.sleep(0.05)
    return cache[k]


results = []
t0 = time.time()
for i, e in enumerate(carve, 1):
    corp = e["corp_code"]; ddate = kdate(e["division_date"]) or kdate(e["board_date"])
    y0 = ddate.year if ddate else int((e["board_date"] or "2017")[:4])
    newco_raw = e.get("new_co") or ""
    clean = re.sub(r"\(.*?\)|（.*?）", "", newco_raw, flags=re.S)
    newcos = [norm(x) for x in re.split(r"[\n/;]|\s및\s", clean) if norm(x) and len(norm(x)) >= 2]
    if not newcos and norm(newco_raw): newcos = [norm(newco_raw)]
    track = []
    locked = None  # normalized investee name once identified; prevents re-matching a different row in later years
    usable_name = bool(newcos) and not any(("아래" in n or "기타" in n or "참고" in n) for n in newcos)
    for fy in range(y0, min(y0 + 6, LAST_FY) + 1):
        rows = holdings(corp, str(fy))
        best, best_s, how = None, 0.0, ""
        if locked:
            for r in rows:
                sc = sim(locked, norm(r.get("inv_prm")))
                if sc > best_s: best, best_s, how = r, sc, "locked"
            if best_s < 0.85: best, how = None, ""
        else:
            if usable_name:
                for r in rows:
                    nm = norm(r.get("inv_prm"))
                    sc = max([sim(n, nm) for n in newcos] or [0.0])
                    if sc > best_s: best, best_s, how = r, sc, "name"
                if best_s < 0.85: best, how = None, ""
            else:  # no usable name in the filing: acquisition date within +-120 days and ~100% at first appearance
                cands = [r for r in rows if kdate(r.get("frst_acqs_de")) and ddate and abs((kdate(r.get("frst_acqs_de")) - ddate).days) <= 120
                         and (pct(r.get("bsis_blce_qota_rt")) or pct(r.get("trmend_blce_qota_rt")) or 0) >= 99.5]
                if len(cands) == 1: best, best_s, how = cands[0], 0.84, "acq_date"
            if best is not None: locked = norm(best.get("inv_prm"))
        if best is not None:
            track.append({"fy": fy, "inv_prm": best.get("inv_prm"), "match": how, "score": round(best_s, 2),
                          "ratio_begin": pct(best.get("bsis_blce_qota_rt")), "ratio_end": pct(best.get("trmend_blce_qota_rt")),
                          "qty_end": best.get("trmend_blce_qy"), "frst_acqs_de": best.get("frst_acqs_de"), "n_rows": len(rows)})
        else:
            track.append({"fy": fy, "inv_prm": None, "match": None, "n_rows": len(rows)})
    # listing check (KIND) — name match of the new company, listing date after division
    listed = None
    for n in newcos:
        for kn, r in kind_idx:
            if sim(n, kn) >= 0.9:
                ld = kdate(r["상장일"])
                if ld and ddate and ld > ddate:
                    listed = {"name": r["회사명"], "stock_code": r["종목코드"], "market": r["시장구분"], "listing_date": r["상장일"]}
    # parent-level sale / merger disclosures after the division
    sales = api("otcprStkInvscrTrfDecsn", corp_code=corp, bgn_de=(ddate or dt.date(y0, 1, 1)).strftime("%Y%m%d"), end_de=TODAY)
    sale_hits = [{"rcept_no": s.get("rcept_no"), "target": s.get("iscmp_cmpnm") or s.get("tfcmp_nm") or s.get("stk_cmpnm"), "date": s.get("tfdt") or s.get("trf_dt")}
                 for s in sales if max([sim(n, norm(s.get("iscmp_cmpnm") or s.get("tfcmp_nm") or s.get("stk_cmpnm"))) for n in newcos] or [0]) >= 0.85]
    mergers = api("cmpMgDecsn", corp_code=corp, bgn_de=(ddate or dt.date(y0, 1, 1)).strftime("%Y%m%d"), end_de=TODAY)
    merger_hits = [{"rcept_no": m.get("rcept_no"), "target": m.get("mgptncmp_cmpnm") or m.get("mg_cmpnm"), "date": m.get("mgdt")}
                   for m in mergers if max([sim(n, norm(m.get("mgptncmp_cmpnm") or m.get("mg_cmpnm"))) for n in newcos] or [0]) >= 0.85]
    time.sleep(0.05)
    # cancellation check: any (correction) filing of the division decision mentioning 철회/취소
    bd = kdate(e["board_date"]) or dt.date(y0, 1, 1)
    decs = api("cmpDvDecsn", corp_code=corp, bgn_de=bd.strftime("%Y%m%d"), end_de=(bd + dt.timedelta(days=400)).strftime("%Y%m%d"))
    cancelled = any(re.search(r"철회|취소", json.dumps(d, ensure_ascii=False)) for d in decs)
    # classify
    matched = [t for t in track if t.get("match")]
    ratios = [t["ratio_end"] for t in matched if t.get("ratio_end") is not None]
    if cancelled and not matched: cls = "cancelled"
    elif listed: cls = "ipo_listed"
    elif not matched and ddate and ddate >= dt.date(2025, 7, 1): cls = "too_recent"
    elif not matched: cls = "unmatched"
    else:
        last_ratio = ratios[-1] if ratios else None
        min_ratio = min(ratios) if ratios else None
        disappeared = matched[-1]["fy"] < track[-1]["fy"]  # identified earlier, absent in a later FY
        if (min_ratio is not None and min_ratio < 50) or disappeared or merger_hits or sale_hits: cls = "majority_disposed"
        elif min_ratio is not None and min_ratio < 99.5: cls = "partial_sale"
        elif last_ratio is not None and last_ratio >= 99.5: cls = "retained_100"
        else: cls = "unmatched"
    results.append({**{k: e[k] for k in ("corp_code", "corp_name", "stock_code", "corp_cls", "rcept_no", "board_date", "division_date", "type", "new_co", "ratio", "purpose")},
                    "division_year": y0, "track": track, "kind_listing": listed, "sale_disclosures": sale_hits, "merger_disclosures": merger_hits, "cancelled_flag": cancelled, "outcome": cls})
    if i % 25 == 0 or i == len(carve):
        from collections import Counter
        c = Counter(r["outcome"] for r in results)
        json.dump(cache, open(CACHE, "w"), ensure_ascii=False)
        json.dump(results, open(OUT, "w"), ensure_ascii=False, indent=1)
        print(f"{i}/{len(carve)} {dict(c)} [{time.time()-t0:.0f}s]", flush=True)
print("done", flush=True)
