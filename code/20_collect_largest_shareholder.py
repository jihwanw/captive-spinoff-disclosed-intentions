#!/usr/bin/env python3
"""20_collect_largest_shareholder.py — controlling-shareholder ownership of the parent before each 물적분할 announcement (DART open API).

Endpoint: opendart.fss.or.kr/api/hyslrSttus.json (최대주주 현황), parameters corp_code, bsns_year, reprt_code=11011 (사업보고서).
Response rows (read from an actual response, INVENI FY2017, 2026-10-25): one row per holder with
  nm (name), relate (relationship to the largest shareholder: observed values include 본인, 친인척, 등기임원, 자사주, 계열회사 …),
  stock_knd (share class, e.g. 보통주), bsis_posesn_stock_qota_rt / trmend_posesn_stock_qota_rt (ownership % at fiscal-year start / end),
  rm (remark; '최대주주' marks the largest shareholder), stlm_dt (fiscal year-end);
  plus total rows with nm == '계' (per share class) that have no 'relate' key — the 계 INCLUDES treasury shares (자사주), e.g. 54.59% of
  which 15.83% was ㈜예스코's own stock. Treasury shares do not vote, so they are separated here.
Variables per event (common shares, fiscal year-end before the announcement year, i.e. bsns_year = event year - 1):
  largest_pct      ownership % of the row marked 최대주주 (rm) or relate == 본인 (first match)
  block_ex_treasury_pct  sum of % over all non-total rows except relate == 자사주 (largest shareholder + related persons/affiliates/officers)
  treasury_pct     sum over relate == 자사주 rows
  n_related        number of non-total rows other than the largest shareholder and treasury
  block_from_total_pct  the 계 row minus treasury (consistency check against the row sum)
Coverage: the API carries periodic-report tables from fiscal 2015; events announced before 2016 get status 013 (no data) and are left for the
annual-report text route (20b). Raw responses cached in data/raw/dart_hyslr/<corp_code>_<year>.json.
Output: data/processed/largest_shareholder_pre_event.json (one record per carve-out event, both periods), results/largest_shareholder_coverage_<date>.json
"""
import os, re, json, time, configparser, datetime as dt, urllib.request, urllib.parse, collections

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = f"{P}/data/raw/dart_hyslr"; os.makedirs(CACHE, exist_ok=True)
cfg = configparser.ConfigParser(); cfg.read("/Users/jihwanw/PhD/code/api_info/api_keys.ini"); KEY = cfg["dart"][[k for k in cfg["dart"] if "key" in k][0]]

def fetch(corp_code, year):
    f = f"{CACHE}/{corp_code}_{year}.json"
    if os.path.exists(f): return json.load(open(f, encoding="utf-8"))
    url = "https://opendart.fss.or.kr/api/hyslrSttus.json?" + urllib.parse.urlencode({"crtfc_key": KEY, "corp_code": corp_code, "bsns_year": str(year), "reprt_code": "11011"})
    for a in range(3):
        try:
            d = json.loads(urllib.request.urlopen(url, timeout=40).read().decode("utf-8")); break
        except Exception as e:
            d = {"status": "ERR", "message": str(e)[:200]}; time.sleep(2 + 2 * a)
    json.dump(d, open(f, "w"), ensure_ascii=False); time.sleep(0.12); return d

def pct(s):
    try: return float(str(s).replace(",", "").replace("%", ""))
    except Exception: return None

def summarize(rows):
    common = [r for r in rows if str(r.get("stock_knd", "")).startswith("보통주")] or rows
    body = [r for r in common if r.get("nm") != "계"]                       # holder rows (some filers omit the relate key)
    tot = [r for r in common if r.get("nm") == "계"]
    is_tre = lambda r: bool(re.search(r"자사주|자기주식", str(r.get("relate", ""))))
    tre = [r for r in body if is_tre(r)]; non_tre = [r for r in body if not is_tre(r)]
    def is_largest(r):
        rel = re.sub(r"\s+", "", str(r.get("relate", ""))); rm = str(r.get("rm", ""))
        return ("최대주주" in rm) or rel in ("본인", "최대주주", "최대주주본인", "최대주주(본인)", "본인(최대주주)")
    big = next((r for r in non_tre if is_largest(r)), None); largest_method = "marked"
    if big is None and non_tre:                                             # fall back to the largest holder by stake
        cand = [(pct(r.get("trmend_posesn_stock_qota_rt")) or -1, r) for r in non_tre]; big = max(cand, key=lambda x: x[0])[1]; largest_method = "max_stake_fallback"
    vals = lambda rs: [pct(r.get("trmend_posesn_stock_qota_rt")) for r in rs]
    s_block = sum(v for v in vals(non_tre) if v is not None); s_tre = sum(v for v in vals(tre) if v is not None)
    tot_v = next((pct(r.get("trmend_posesn_stock_qota_rt")) for r in tot if pct(r.get("trmend_posesn_stock_qota_rt")) is not None), None)
    from_total = round(tot_v - s_tre, 2) if tot_v is not None else None
    disagree = from_total is not None and abs(from_total - s_block) > 1.0
    block = from_total if from_total is not None else round(s_block, 2)   # the filer's own total (minus treasury) is preferred; row sums can double-count
    return {"largest_name": big.get("nm") if big else None, "largest_pct": pct(big.get("trmend_posesn_stock_qota_rt")) if big else None, "largest_method": largest_method if big else None,
            "block_ex_treasury_pct": block, "block_rowsum_pct": round(s_block, 2), "block_from_total_pct": from_total, "rowsum_total_disagree": disagree,
            "treasury_pct": round(s_tre, 2), "n_related": max(0, len(non_tre) - (1 if big else 0)), "total_row_pct": tot_v,
            "relate_values": sorted({str(r.get("relate")) for r in body}), "stlm_dt": next((r.get("stlm_dt") for r in body if r.get("stlm_dt")), None), "n_rows": len(rows)}

events = []
for r in json.load(open(f"{P}/data/processed/carveout_disposal_tracking_2001_2016.json", encoding="utf-8")):
    events.append({"rcept_no": r["rcept_no"], "corp_code": r["corp_code"], "corp_name": r["corp_name"], "period": "2001-2016", "event_year": int(r["rcept_no"][:4])})
for r in json.load(open(f"{P}/data/raw/dart_division_decisions_2017_2026.json", encoding="utf-8")):
    if r.get("type") == "carve_out": events.append({"rcept_no": r["rcept_no"], "corp_code": r["corp_code"], "corp_name": r["corp_name"], "period": "2017+", "event_year": int(r["rcept_no"][:4])})
out, status = [], collections.Counter(); t0 = time.time()
for i, e in enumerate(events, 1):
    y = e["event_year"] - 1; rec = dict(e, bsns_year=y)
    if y < 2015: rec.update(status="before_api_coverage"); status["before_api_coverage"] += 1; out.append(rec); continue
    d = fetch(e["corp_code"], y); st = d.get("status")
    if st == "000" and d.get("list"):
        rec.update(status="ok", **summarize(d["list"])); status["ok"] += 1
    else:
        # some filers' annual report for FY y is absent (newly listed, late filer); try the previous fiscal year once
        d2 = fetch(e["corp_code"], y - 1) if y - 1 >= 2015 else {"status": "n/a"}
        if d2.get("status") == "000" and d2.get("list"): rec.update(status="ok_prior_fy", bsns_year=y - 1, **summarize(d2["list"])); status["ok_prior_fy"] += 1
        else: rec.update(status=f"no_data_{st}", message=d.get("message")); status[f"no_data_{st}"] += 1
    out.append(rec)
    if i % 50 == 0: print(f"{i}/{len(events)} {dict(status)} [{time.time()-t0:.0f}s]", flush=True)
json.dump(out, open(f"{P}/data/processed/largest_shareholder_pre_event.json", "w"), ensure_ascii=False, indent=1)
ok = [r for r in out if r["status"].startswith("ok")]
import statistics as stx
cov = {"events": len(out), "status": dict(status), "by_period": {p: dict(collections.Counter(r["status"] for r in out if r["period"] == p)) for p in ("2001-2016", "2017+")},
       "relate_values_seen": sorted({v for r in ok for v in r.get("relate_values", [])}),
       "block_ex_treasury_pct": {"n": len(ok), "median": stx.median([r["block_ex_treasury_pct"] for r in ok]) if ok else None, "q1": stx.quantiles([r["block_ex_treasury_pct"] for r in ok], n=4)[0] if len(ok) > 4 else None, "q3": stx.quantiles([r["block_ex_treasury_pct"] for r in ok], n=4)[2] if len(ok) > 4 else None},
       "largest_pct_median": stx.median([r["largest_pct"] for r in ok if r.get("largest_pct") is not None]) if ok else None,
       "treasury_pct_nonzero_share": round(sum(1 for r in ok if r["treasury_pct"] > 0) / len(ok), 3) if ok else None,
       "rowsum_vs_total_disagree": sum(1 for r in ok if r.get("rowsum_total_disagree")), "largest_method": dict(collections.Counter(r.get("largest_method") for r in ok)), "disagree_cases": [(r["corp_name"], r["bsns_year"], r["block_rowsum_pct"], r["block_from_total_pct"]) for r in ok if r.get("rowsum_total_disagree")]}
stamp = dt.date.today().strftime("%Y%m%d"); json.dump(cov, open(f"{P}/results/largest_shareholder_coverage_{stamp}.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(cov, ensure_ascii=False, indent=1)); print("saved data/processed/largest_shareholder_pre_event.json")
