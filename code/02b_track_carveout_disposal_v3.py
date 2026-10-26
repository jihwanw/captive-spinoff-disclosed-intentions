#!/usr/bin/env python3
"""02b_track_carveout_disposal_v3.py — per-new-company disposal tracking with provenance.

Improvements over v2 (2026-10-15 audit): (1) new-company names taken from the filing text ('회사명 :' / '상호 :' lines,
excluding the parent) in addition to the DART field; (2) each new company is tracked separately and its identity is
locked after the first match; (3) acquisition-date fallback only with an exact date (+-10 days) and only when no name
matched; (4) half-year reports (reprt_code 11012) are read too, so disposals inside a fiscal year are seen;
(5) the parent's subsequent 주요사항보고 filing titles (DART list.json, pblntf_ty=B) are scanned for 양도/합병/처분
events naming the new company; (6) merger endpoint fields use the documented names (mgptncmp_cmpnm, mgsc_mgdt).
Outputs: data/processed/carveout_disposal_tracking_v3.json ; results/label_audit_queue_v3.json (cases to check by hand).
Field meanings: DART DS002 타법인출자현황 (inv_prm, frst_acqs_de, bsis/trmend_blce_qota_rt), DS001 공시검색 list.json
(report_nm, rcept_dt), DS005 회사합병결정 (mgptncmp_cmpnm, mgsc_mgdt).
"""
import json, os, re, sys, time, csv, configparser, urllib.request, urllib.parse, datetime as dt
from difflib import SequenceMatcher

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = f"{P}/data/raw/dart_division_decisions_2017_2026.json"
INDEX = f"{P}/data/processed/disclosure_text_index.json"
CACHE = f"{P}/data/raw/dart_cache_otrCprInvstmntSttus.json"
LISTCACHE = f"{P}/data/raw/dart_cache_filing_list.json"
KIND = f"{P}/data/raw/kind_corplist_20261014.csv"
OUT = f"{P}/data/processed/carveout_disposal_tracking_v3.json"
QUEUE = f"{P}/results/label_audit_queue_v3.json"
cfg = configparser.ConfigParser(); cfg.read("/Users/jihwanw/PhD/code/api_info/api_keys.ini")
KEY = cfg["dart"].get("api_key") or cfg["dart"].get("key") or list(cfg["dart"].values())[0]
LAST_FY = 2025; TODAY = dt.date.today().strftime("%Y%m%d")
ALIAS = [("엘지", "lg"), ("에스케이", "sk"), ("지에스", "gs"), ("씨제이", "cj"), ("케이티", "kt"), ("엘에스", "ls"), ("에이치디", "hd"), ("디엘", "dl"),
         ("에이치엘", "hl"), ("디비", "db"), ("오씨아이", "oci"), ("엘엔지", "lng"), ("아이앤씨", "i&c"), ("디엑스", "dx"), ("이엔지", "eng"), ("이앤피", "e&p")]


def api(ep, **kw):
    q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in kw.items())
    for a in range(3):
        try:
            with urllib.request.urlopen(f"https://opendart.fss.or.kr/api/{ep}.json?crtfc_key={KEY}&{q}", timeout=40) as r: d = json.load(r)
            if d.get("status") in ("020", "800"): print("STOP", d, flush=True); sys.exit(2)
            return d
        except Exception: time.sleep(2 + 3 * a)
    return {}


def norm(s):
    s = re.sub(r"\(.*?\)|（.*?）", "", s or "", flags=re.S); s = re.sub(r"\([^)]*$", "", s)
    s = re.sub(r"주식회사|㈜|\(주\)|유한회사|Co\.,?\s*Ltd\.?|Inc\.?|Corp\.?|Corporation|Company|Ltd\.?|LTD\.?", "", s, flags=re.I)
    s = re.sub(r"[\s\.\,\-–_'\"·]+", "", s).lower()
    for ko, en in ALIAS: s = s.replace(ko, en)
    return s


def sim(a, b):
    if not a or not b: return 0.0
    if a == b: return 1.0
    sh, lo = (a, b) if len(a) <= len(b) else (b, a)
    if len(sh) >= 4 and sh in lo and len(sh) / len(lo) >= 0.6: return 0.95
    return SequenceMatcher(None, a, b).ratio()


def kdate(s):
    if not s: return None
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", s) or re.search(r"(\d{4})(\d{2})(\d{2})", s)
    try: return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
    except Exception: return None


def pct(s):
    try: return float(str(s).replace(",", "").replace("%", "").strip())
    except Exception: return None


def names_from_text(txt, parent):
    out = []
    for m in re.finditer(r"(?:회사명|상호)\s*[:：]\s*([^\n|]{2,60})", txt or ""):
        n = re.sub(r"\(가칭\)|（가칭）|\(변경예정\)", "", m.group(1)).strip(" .")
        if norm(n) and sim(norm(n), norm(parent)) < 0.9 and norm(n) not in [norm(x) for x in out]: out.append(n)
    return out


events = json.load(open(EVENTS, encoding="utf-8")); idx = json.load(open(INDEX, encoding="utf-8"))
carve = [e for e in events if e["type"] in ("carve_out", "mixed")]
kind = [(norm(r["회사명"]), r) for r in csv.DictReader(open(KIND, encoding="utf-8"))]
cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}
lcache = json.load(open(LISTCACHE, encoding="utf-8")) if os.path.exists(LISTCACHE) else {}


def holdings(corp, fy, code="11011"):
    k = f"{corp}:{fy}" if code == "11011" else f"{corp}:{fy}:{code}"
    if k not in cache:
        cache[k] = api("otrCprInvstmntSttus", corp_code=corp, bsns_year=fy, reprt_code=code).get("list", []) or []; time.sleep(0.05)
    return cache[k]


def filings(corp, bgn, end):
    k = f"{corp}:{bgn}:{end}"
    if k not in lcache:
        rows = []
        for page in range(1, 6):
            d = api("list", corp_code=corp, bgn_de=bgn, end_de=end, pblntf_ty="B", page_no=page, page_count=100)
            rows += d.get("list", []) or []
            if page >= int(d.get("total_page", 1) or 1): break
        lcache[k] = [{"rcept_no": r.get("rcept_no"), "rcept_dt": r.get("rcept_dt"), "report_nm": r.get("report_nm")} for r in rows]; time.sleep(0.05)
    return lcache[k]


results, queue = [], []
t0 = time.time()
for i, e in enumerate(carve, 1):
    corp = e["corp_code"]; ddate = kdate(e["division_date"]) or kdate(e["board_date"]); y0 = ddate.year if ddate else int((e["board_date"] or "2017")[:4])
    txt = open(f"{P}/{idx[e['rcept_no']]['path']}", encoding="utf-8").read() if idx.get(e["rcept_no"], {}).get("path") else ""
    field_names = [x for x in re.split(r"[\n/;]|\s및\s", re.sub(r"\(.*?\)", "", e.get("new_co") or "", flags=re.S)) if len(norm(x)) >= 2 and not re.search(r"아래|기타|참고", x)]
    cand = []
    for n in names_from_text(txt, e["corp_name"]) + field_names:
        if norm(n) not in [norm(c) for c in cand]: cand.append(n)
    # --- per-new-company tracking through annual (and half-year) holdings
    periods = []
    for fy in range(y0, min(y0 + 6, LAST_FY) + 1):
        periods.append((fy, "11012", f"{fy}H1")); periods.append((fy, "11011", f"{fy}FY"))
    tracks = {}  # locked normalized name -> list of observations
    unlocked = [norm(c) for c in cand]
    for fy, code, label in periods:
        rows = holdings(corp, str(fy), code)
        for r in rows:
            nm = norm(r.get("inv_prm")); obs = {"period": label, "inv_prm": r.get("inv_prm"), "ratio_begin": pct(r.get("bsis_blce_qota_rt")), "ratio_end": pct(r.get("trmend_blce_qota_rt")), "frst_acqs_de": r.get("frst_acqs_de")}
            hit = None
            for locked in tracks:
                if sim(locked, nm) >= 0.85: hit = locked; break
            if hit is None:
                for c in unlocked:
                    if sim(c, nm) >= 0.85: hit = nm; tracks[nm] = {"matched_by": "name", "candidate": c, "obs": []}; unlocked.remove(c); break
            if hit is None and (not cand or unlocked) and ddate:  # no name matched (yet): exact acquisition date + ~100%
                ad = kdate(r.get("frst_acqs_de"))
                if ad and abs((ad - ddate).days) <= 10 and (pct(r.get("bsis_blce_qota_rt")) or pct(r.get("trmend_blce_qota_rt")) or 0) >= 99.5 and nm not in tracks:
                    hit = nm; tracks[nm] = {"matched_by": "acq_date", "candidate": (unlocked.pop(0) if unlocked else None), "obs": []}
            if hit: tracks[hit]["obs"].append(obs)
    # --- KIND listing per candidate
    listings = []
    for c in cand:
        for kn, r in kind:
            if sim(norm(c), kn) >= 0.9 and kdate(r["상장일"]) and ddate and kdate(r["상장일"]) > ddate:
                listings.append({"candidate": c, "listed_name": r["회사명"], "stock_code": r["종목코드"], "listing_date": r["상장일"]})
    # --- parent filing titles after the division (주요사항보고)
    fl = filings(corp, (ddate or dt.date(y0, 1, 1)).strftime("%Y%m%d"), TODAY) if ddate else []
    ev_titles = [f for f in fl if re.search(r"양도|합병|처분|매각|분할합병|주식교환", f.get("report_nm") or "")]
    # --- merger decisions naming a candidate
    mk = f"mg:{corp}:{y0}"
    if mk not in lcache:
        lcache[mk] = api("cmpMgDecsn", corp_code=corp, bgn_de=(ddate or dt.date(y0, 1, 1)).strftime("%Y%m%d"), end_de=TODAY).get("list", []) or []
    mg = lcache[mk]
    tracked_names = list(tracks.keys()) if 'tracks' in dir() else []
    mg_hits = [{"rcept_no": m.get("rcept_no"), "partner": m.get("mgptncmp_cmpnm"), "relation": m.get("mgptncmp_rl_cmpn"), "merger_date": m.get("mgsc_mgdt")} for m in mg
               if any(sim(norm(c), norm(m.get("mgptncmp_cmpnm"))) >= 0.85 for c in cand + tracked_names)]
    time.sleep(0.05)
    # --- classify per new company, then event
    per = []
    for nm, tr in tracks.items():
        ratios = [(o["period"], o["ratio_end"]) for o in tr["obs"] if o["ratio_end"] is not None]
        vals = [v for _, v in ratios]
        last_period = tr["obs"][-1]["period"] if tr["obs"] else None
        disappeared = bool(tr["obs"]) and last_period != periods[-1][2] and any(p[2] == last_period for p in periods[:-1])
        if listings and any(sim(norm(l["candidate"]), nm) >= 0.85 for l in listings): c = "ipo_listed"
        elif mg_hits and any(sim(norm(h["partner"]), nm) >= 0.85 for h in mg_hits): c = "merged_back_into_parent"
        elif vals and min(vals) < 50: c = "majority_disposed"
        elif disappeared and (not vals or vals[-1] >= 99.5): c = "disappeared_from_holdings"
        elif vals and min(vals) < 99.5: c = "partial_sale"
        elif vals and vals[-1] >= 99.5: c = "retained_100"
        else: c = "observed_no_ratio"
        per.append({"new_company": nm, "matched_by": tr["matched_by"], "n_obs": len(tr["obs"]), "min_ratio": min(vals) if vals else None, "last_ratio": vals[-1] if vals else None, "last_period": last_period, "class": c})
    if listings and not per: per.append({"new_company": listings[0]["candidate"], "matched_by": "kind", "class": "ipo_listed"})
    order = ["ipo_listed", "majority_disposed", "partial_sale", "disappeared_from_holdings", "merged_back_into_parent", "observed_no_ratio", "retained_100"]
    if per: outcome = sorted(per, key=lambda x: order.index(x["class"]))[0]["class"]
    elif ddate and ddate >= dt.date(2025, 7, 1): outcome = "too_recent"
    else: outcome = "unmatched"
    if outcome == "disappeared_from_holdings": outcome = "majority_disposed_or_dropped"  # needs manual confirmation
    rec = {**{k: e[k] for k in ("corp_code", "corp_name", "stock_code", "corp_cls", "rcept_no", "board_date", "division_date", "type", "new_co", "ratio")},
           "division_year": y0, "candidates": cand, "per_new_company": per, "kind_listings": listings, "parent_event_filings": ev_titles[:12], "merger_hits": mg_hits, "outcome": outcome}
    results.append(rec)
    if outcome in ("unmatched", "majority_disposed_or_dropped", "observed_no_ratio") or (ev_titles and outcome == "retained_100"):
        queue.append({"rcept_no": e["rcept_no"], "corp_name": e["corp_name"], "division_year": y0, "candidates": cand, "outcome": outcome, "event_filings": [f["report_nm"] + " " + f["rcept_dt"] for f in ev_titles[:6]]})
    if i % 25 == 0 or i == len(carve):
        from collections import Counter
        json.dump(cache, open(CACHE, "w"), ensure_ascii=False); json.dump(lcache, open(LISTCACHE, "w"), ensure_ascii=False)
        json.dump(results, open(OUT, "w"), ensure_ascii=False, indent=1); json.dump(queue, open(QUEUE, "w"), ensure_ascii=False, indent=1)
        print(f"{i}/{len(carve)} {dict(Counter(r['outcome'] for r in results))} queue={len(queue)} [{time.time()-t0:.0f}s]", flush=True)
print("done", flush=True)
