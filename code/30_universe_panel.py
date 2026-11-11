#!/usr/bin/env python3
"""30_universe_panel.py — the Korean listed-common-stock universe from the Compustat Global pull of 25 (verified in 26):
securities, daily returns, month-end market values, firm-year fundamentals, and size/book-to-market reference portfolios.
Feeds 31 (matched-benchmark BHAR, selection model) — resubmission strategy §2 "benchmark", "endogeneity (selection model)".

Common-stock rule (probed 2026-11-10 on g_security + KIND, recorded in INTERFACE_CARD_compustat_global_kr.md):
  tpci = '0' (dsci reads 'ORD ...'; 4,042 securities), ISIN 'KR7' + 6-digit code ending in '0' (all 2,753 KIND company codes end in 0),
  exchg in {248 KOSPI, 298 KOSDAQ}. Excluded by the rule: tpci '%' (dsci 'ETF ...', 1,275), tpci '1' (dsci 'PFD', preferred; their ISIN
  codes end in 1/2/3/6/K — the ISIN digit is NOT the preferred share's trading code), KONEX 353, foreign venues. 2,729 of the 2,731
  KIND-listed firms found in Compustat are tpci '0'.
Returns: adjprc = prccd / ajexdi * trfd (17's rule, catalog: Price-Close, Adjustment Factor (Issue), Daily Total Return Factor);
  rows with prccd <= 0, ajexdi <= 0, curcdd != KRW or zero traded volume dropped (as 17); a daily return beyond the exchange's price
  limit (+-15% before 2015-06-15, +-30% after, +1 pp tolerance; 17/18's glitch rule) is set to NaN for that day (vendor adjustment errors
  such as the 2013-09-11 +12,377% case would otherwise dominate an equal-weighted portfolio); counts recorded.
Market value: ME = prccd * cshoc on the last trading day of the month (cshoc in shares, probe P4 of 26; coverage >= 99% every year).
Fundamentals: g_funda KRW / INDL / HIST_STD; consolidated row (consol C) when present, else parent-only (N) with a flag (pre-2011
  consolidated reporting was not universal: 380 C gvkeys in 2001 vs 1,194 in 2011); amounts in millions of KRW (probe P2).
Reference portfolios: each June of year t, size quintiles on June ME and B/M quintiles on ceq (fiscal year ending in calendar t-1,
  > 0) / ME at the end of December t-1, breakpoints from the whole universe; equal-weighted daily returns July t .. June t+1 (5x5 and 3x3).
Controls (recorded in the JSON): equal-weighted universe monthly return vs the KOSPI/KOSDAQ index returns from data/raw/krx_prices
  (expected correlation >= 0.8 with KOSDAQ for the EW portfolio dominated by small KOSDAQ names); firm counts per year vs KIND today.
Outputs (data/processed/universe_*.parquet, benchmark_portfolios_daily.parquet, results/universe_build_<date>.json)
"""
import os, re, json, glob, datetime as dt, numpy as np, pandas as pd

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); RAW = f"{P}/data/raw/compustat_global_kr"; OUT = f"{P}/data/processed"; STAMP = dt.date.today().strftime("%Y%m%d")
R = {"generated": dt.datetime.now().astimezone().isoformat(timespec="seconds")}
LIMIT_CHANGE = pd.Timestamp("2015-06-15"); LIM_OLD, LIM_NEW, TOL = 0.15, 0.30, 0.01

# ---- securities
sec = pd.read_parquet(f"{RAW}/g_security_kr.parquet"); isin = sec["isin"].astype("string").fillna("")
sec["stock_code"] = np.where(isin.str.startswith("KR7"), isin.str[3:9], None)
uni = sec[(sec.tpci == "0") & sec.stock_code.notna() & sec.exchg.isin([248, 298])].copy(); uni = uni[uni.stock_code.str.endswith("0")]
uni = uni[["gvkey", "iid", "stock_code", "exchg", "secstat", "dldtei", "dsci"]].reset_index(drop=True)
R["securities"] = {"n": int(len(uni)), "gvkeys": int(uni.gvkey.nunique()), "by_exchg": uni.exchg.value_counts().to_dict(), "active": int((uni.secstat == "A").sum()),
                   "rule": "tpci='0' & ISIN KR7+code ending 0 & exchg in {248,298}", "dsci_not_starting_ORD": int((~uni.dsci.fillna("").str.upper().str.startswith("ORD")).sum())}
uni.to_parquet(f"{OUT}/universe_common_securities.parquet", index=False)
key = uni[["gvkey", "iid"]].drop_duplicates()

# ---- daily returns and month-end ME, year by year
daily_parts, me_parts, glitch = [], [], {"rows": 0, "flagged": 0, "by_year": {}}
for f in sorted(glob.glob(f"{RAW}/g_secd_kr_*.parquet")):
    y = int(re.search(r"(\d{4})", os.path.basename(f)).group(1))
    d = pd.read_parquet(f, columns=["gvkey", "iid", "datadate", "prccd", "ajexdi", "trfd", "cshtrd", "cshoc", "curcdd", "exchg"]).merge(key, on=["gvkey", "iid"])
    d = d[(d.curcdd == "KRW") & (d.prccd > 0) & (d.ajexdi > 0)]; d = d[~((d.cshtrd.notna()) & (d.cshtrd <= 0))]
    d["trfd"] = d.trfd.fillna(1.0); d["adjprc"] = d.prccd / d.ajexdi * d.trfd
    d = d.sort_values(["gvkey", "iid", "datadate"]).drop_duplicates(["gvkey", "iid", "datadate"])
    daily_parts.append(d[["gvkey", "iid", "datadate", "adjprc", "prccd", "cshoc", "exchg"]])
    glitch["by_year"][y] = int(len(d))
daily = pd.concat(daily_parts, ignore_index=True).sort_values(["gvkey", "iid", "datadate"]); del daily_parts
g = daily.groupby(["gvkey", "iid"], sort=False)
daily["ret"] = g.adjprc.pct_change(); daily["gap_days"] = g.datadate.diff().dt.days
lim = np.where(daily.datadate < LIMIT_CHANGE, LIM_OLD, LIM_NEW) + TOL
flag = daily.ret.abs() > lim
glitch.update({"rows": int(len(daily)), "flagged": int(flag.sum()), "flagged_share": round(float(flag.mean()), 6), "flagged_with_gap_gt_30d": int((flag & (daily.gap_days > 30)).sum())})
daily.loc[flag, "ret"] = np.nan
daily["me"] = daily.prccd * daily.cshoc
daily[["gvkey", "iid", "datadate", "ret", "me", "exchg"]].to_parquet(f"{OUT}/universe_daily_returns.parquet", index=False)
R["daily"] = {"rows": int(len(daily)), "first": str(daily.datadate.min().date()), "last": str(daily.datadate.max().date()), "glitch_rule": glitch,
              "securities_by_year_ge200days": {int(k): int(v) for k, v in daily.groupby(daily.datadate.dt.year).apply(lambda x: (x.groupby(["gvkey", "iid"]).size() >= 200).sum(), include_groups=False).items()}}
# month-end
daily["ym"] = daily.datadate.dt.to_period("M")
last = daily.groupby(["gvkey", "iid", "ym"], sort=False).tail(1)[["gvkey", "iid", "ym", "datadate", "me", "prccd", "exchg"]]
mret = daily.groupby(["gvkey", "iid", "ym"], sort=False).ret.apply(lambda x: float(np.prod(1 + x.dropna()) - 1) if x.notna().any() else np.nan).rename("ret_m").reset_index()
me = last.merge(mret, on=["gvkey", "iid", "ym"]); me = me[me.me > 0]
me.to_parquet(f"{OUT}/universe_month_end.parquet", index=False)
R["month_end"] = {"rows": int(len(me)), "firms_dec_by_year": {int(k): int(v) for k, v in me[me.ym.dt.month == 12].groupby(me.ym.dt.year).gvkey.nunique().items()}}

# ---- firm-year fundamentals: C preferred, N fallback
fa = pd.read_parquet(f"{RAW}/g_funda_kr.parquet"); fa = fa[(fa.curcd == "KRW") & (fa.indfmt == "INDL") & (fa.datafmt == "HIST_STD") & (fa.popsrc == "I")]
fa = fa.sort_values(["gvkey", "fyear", "consol"])  # 'C' < 'N'
fy = fa.drop_duplicates(["gvkey", "fyear"], keep="first").copy(); fy["consol_used"] = fy.consol; fy["n_fallback"] = (fy.consol == "N").astype(int)
cols = ["gvkey", "fyear", "datadate", "fyr", "consol_used", "n_fallback", "at", "lt", "ceq", "seq", "teq", "sale", "revt", "oiadp", "oibdp", "capx", "oancf", "che", "dltt", "dlc", "emp", "sich", "exchg"]
fy = fy[[c for c in cols if c in fy.columns]]; fy.to_parquet(f"{OUT}/universe_firm_year_fundamentals.parquet", index=False)
R["fundamentals"] = {"firm_years": int(len(fy)), "gvkeys": int(fy.gvkey.nunique()), "share_N_fallback_by_fyear": {int(k): round(float(v), 3) for k, v in fy.groupby("fyear").n_fallback.mean().items() if k in (2001, 2005, 2008, 2010, 2011, 2012, 2015, 2020, 2024)},
                     "ceq_positive_share": round(float((fy.ceq > 0).mean()), 3)}

# ---- size / B/M reference portfolios (June formation)
dec = me[me.ym.dt.month == 12][["gvkey", "ym", "me"]].rename(columns={"me": "me_dec"}); dec["t"] = dec.ym.dt.year + 1
jun = me[me.ym.dt.month == 6][["gvkey", "iid", "ym", "me"]].rename(columns={"me": "me_jun"}); jun["t"] = jun.ym.dt.year
be = fy[fy.ceq > 0][["gvkey", "fyear", "datadate", "ceq"]].copy(); be["t"] = be.datadate.dt.year + 1          # fiscal year ending in calendar t-1
be = be.sort_values("datadate").drop_duplicates(["gvkey", "t"], keep="last")
form = jun.merge(dec[["gvkey", "t", "me_dec"]], on=["gvkey", "t"], how="inner").merge(be[["gvkey", "t", "ceq"]], on=["gvkey", "t"], how="inner")
form["bm"] = form.ceq * 1e6 / form.me_dec            # ceq in millions of KRW (probe P2) -> KRW
form = form[(form.me_jun > 0) & (form.bm > 0)]
def qcut_safe(x, q):
    try: return pd.qcut(x, q, labels=False, duplicates="drop") + 1
    except ValueError: return pd.Series(np.nan, index=x.index)
assign = []
for t, gq in form.groupby("t"):
    gq = gq.copy(); gq["size5"] = qcut_safe(gq.me_jun, 5); gq["bm5"] = qcut_safe(gq.bm, 5); gq["size3"] = qcut_safe(gq.me_jun, 3); gq["bm3"] = qcut_safe(gq.bm, 3); assign.append(gq)
assign = pd.concat(assign, ignore_index=True); assign.to_parquet(f"{OUT}/universe_portfolio_assignments.parquet", index=False)
R["formation"] = {"firms_by_formation_year": {int(k): int(v) for k, v in assign.groupby("t").size().items()}}
# daily EW portfolio returns: assignment of year t applies to July t .. June t+1
daily["t"] = np.where(daily.datadate.dt.month >= 7, daily.datadate.dt.year, daily.datadate.dt.year - 1)
pf = daily.dropna(subset=["ret"]).merge(assign[["gvkey", "iid", "t", "size5", "bm5", "size3", "bm3"]], on=["gvkey", "iid", "t"], how="inner")
p55 = pf.groupby(["datadate", "size5", "bm5"]).ret.agg(ret_ew="mean", n="size").reset_index(); p33 = pf.groupby(["datadate", "size3", "bm3"]).ret.agg(ret_ew="mean", n="size").reset_index()
mkt = daily.dropna(subset=["ret"]).groupby("datadate").agg(ret_ew=("ret", "mean"), n=("ret", "size")).reset_index()
p55.to_parquet(f"{OUT}/benchmark_portfolios_5x5_daily.parquet", index=False); p33.to_parquet(f"{OUT}/benchmark_portfolios_3x3_daily.parquet", index=False); mkt.to_parquet(f"{OUT}/universe_ew_market_daily.parquet", index=False)
R["portfolios"] = {"5x5_rows": int(len(p55)), "5x5_median_n_per_portfolio_day": float(p55.n.median()), "5x5_min_n": int(p55.n.min()), "3x3_median_n": float(p33.n.median()), "first_day": str(p55.datadate.min().date()), "last_day": str(p55.datadate.max().date())}

# ---- controls: EW universe monthly return vs KRX indices; firm counts vs KIND
idx = {k: pd.read_csv(f, index_col=0, parse_dates=True)["종가"] for k, f in (("KOSPI", f"{P}/data/raw/krx_prices/index_1001_20000101_20261024.csv"), ("KOSDAQ", f"{P}/data/raw/krx_prices/index_2001_20000101_20261024.csv"))}
ewm = (1 + mkt.set_index("datadate").ret_ew).resample("ME").prod() - 1
ctrl = {}
for k, s in idx.items():
    im = s.resample("ME").last().pct_change(); j = pd.concat([ewm.rename("ew"), im.rename("idx")], axis=1).dropna(); j = j[(j.index >= "2001-01-31") & (j.index <= "2026-09-30")]
    ctrl[f"corr_ew_vs_{k}_monthly"] = round(float(j.ew.corr(j.idx)), 3); ctrl[f"months_{k}"] = int(len(j))
# value-weighted universe vs KOSPI (should track the cap-weighted index more closely)
dv = daily.dropna(subset=["ret"]).copy(); dv["w"] = dv.groupby(["gvkey", "iid"]).me.shift(1); dv = dv.dropna(subset=["w"])
vw = dv.groupby("datadate").apply(lambda x: float(np.average(x.ret, weights=x.w)), include_groups=False); vwm = (1 + vw).resample("ME").prod() - 1
j = pd.concat([vwm.rename("vw"), idx["KOSPI"].resample("ME").last().pct_change().rename("idx")], axis=1).dropna(); j = j[(j.index >= "2001-01-31") & (j.index <= "2026-09-30")]
ctrl["corr_vw_vs_KOSPI_monthly"] = round(float(j.vw.corr(j.idx)), 3)
kind = pd.read_csv(f"{P}/data/raw/kind_corplist_20261014.csv", dtype=str)
ctrl["firms_2026_universe_vs_KIND"] = {"universe_securities_2026_ge200days": R["daily"]["securities_by_year_ge200days"].get(2026), "KIND_listed_KOSPI_KOSDAQ": int(kind["시장구분"].isin(["유가", "코스닥"]).sum())}
ctrl["expected"] = "EW vs KOSDAQ >= 0.8; VW vs KOSPI >= 0.9; 2026 universe within ~10% of KIND KOSPI+KOSDAQ count"
ctrl["pass"] = bool(ctrl.get("corr_ew_vs_KOSDAQ_monthly", 0) >= 0.8 and ctrl["corr_vw_vs_KOSPI_monthly"] >= 0.9)
R["controls"] = ctrl
def _clean(o):
    if isinstance(o, dict): return {(k.item() if hasattr(k, "item") else (str(k) if not isinstance(k, (str, int, float, bool)) and k is not None else k)): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_clean(v) for v in o]
    if hasattr(o, "item"): return o.item()
    return o
json.dump(_clean(R), open(f"{P}/results/universe_build_{STAMP}.json", "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(_clean({k: R[k] for k in ("securities", "month_end", "fundamentals", "portfolios", "controls")}), ensure_ascii=False, indent=1, default=str)[:4000])
print("glitch:", {k: v for k, v in R["daily"]["glitch_rule"].items() if k != "by_year"}); print(f"saved universe parquets to {OUT}, results/universe_build_{STAMP}.json")
