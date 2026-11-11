#!/usr/bin/env python3
"""31_matched_benchmark_and_selection.py — (a) size/book-to-market matched benchmarks for the event returns and (b) a selection model
for "who announces a captive spin-off", with propensity-matched control firms as a third benchmark. Resubmission strategy §2
("benchmark", "endogeneity: selection model"), using the universe built by 30 from the Compustat Global pull (25/26).

(a) Benchmarks. Firm-side returns are the paper's own event panel (18.build_pooled: KRX 2017+, Compustat 2001–2016, glitch screen),
    window tau +2..+250 with >= 90% of days (16.add_windows). Benchmarks compounded over the SAME calendar dates:
      market index (the paper; identity control: must reproduce bhar_madj_p2_p250 of 19's event file),
      5x5 and 3x3 size/B-M equal-weighted portfolios of 30 (assignment year t = event year if month >= 7 else year-1; fallback: size-only
      quintile when the firm has no B/M assignment; none -> missing, counted),
      nearest-neighbour control firm on standardised (log June ME, log B/M) within the same assignment year, non-event parents only,
      propensity-score nearest neighbour from (b) within the same year.
    Re-estimated on each benchmark: mean/median BHAR, Spearman(S, BHAR), within-year rank regression on S with 19's spec-3 controls
    (year FE; HC1 and firm-clustered p), early-vs-never difference.
(b) Selection logit on the firm-year universe (fundamentals of fiscal year f, ME at the fiscal year-end month; outcome = captive
    spin-off announced by the firm in calendar year f+1): log assets, Q = (ME + liabilities)/assets, leverage, investment capx/at,
    cash flow oibdp/at, cash che/at, sales growth, KOSDAQ, parent-only-statement flag; year FE, GICS sector FE, firm clusters.
    Kang & Lee (2025b) Table 4 columns (13)-(15) [literature/KangLee2025_FRL_fulltext.txt] report for I(Captive Spin-off): Size + ***,
    Leverage + ***, Cash Flow − ***, Investment + (*), Q + (n.s.), KOSPI − ***. Those signs are the pre-registered expectations here
    (net income is not used: nicon/ib are UNVERIFIED for Korea, probe P2b of 26; cash flow is oibdp/at).
Pre-registered expectations (2026-11-10): identity control reproduces 19's market-adjusted BHAR to 1e-6; matched-portfolio BHAR mean in
    [-12%, +2%] with negative medians; Spearman(S, BHAR_pf) in [-0.20, -0.05]; rank coefficient on S in [-0.28, -0.08]; early-vs-never
    difference in [-25, -5] pp; selection signs as above; >= 95% of event firm-years inside the control propensity support.
Outputs: results/matched_benchmark_selection_<date>.json, data/processed/event_benchmarks_<date>.csv, docs/MATCHED_BENCHMARK_NOTE_<date>.md
"""
import os, json, glob, importlib.util, datetime as dt, numpy as np, pandas as pd
import statsmodels.api as sm
from scipy import stats

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f"{P}/data/processed"; RAW = f"{P}/data/raw/compustat_global_kr"; STAMP = dt.date.today().strftime("%Y%m%d")
R = {"generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "expectations_preregistered": __doc__.split("Pre-registered expectations")[1].split("Outputs:")[0].strip()}
def load(name):
    spec = importlib.util.spec_from_file_location(name, f"{P}/code/{name}.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
b16 = load("16_bhar_by_predicted_disposal"); b18 = load("18_bhar_pooled")

# ---------------- events and firm-side returns (the paper's panel)
B = b18.build_pooled()
co_old = B["co_old_k"][~B["co_old_k"].flag_glitch].drop(columns=["flag_glitch"]); co = pd.concat([co_old, B["co_k"]], ignore_index=True)
pan = pd.concat([B["pan_old"][B["pan_old"].rcept_no.isin(co_old.rcept_no)], B["pan_k"]], ignore_index=True); pan["date"] = pd.to_datetime(pan.date)
co = b16.add_windows(co, pan); co["event_dt"] = pd.to_datetime(co.event_date); co["timing"] = co.rcept_no.map(B["timing"]); M = b16.MAIN
ctrl19 = pd.read_csv(sorted(glob.glob(f"{OUT}/bhar_controls_events_*.csv"))[-1], dtype={"rcept_no": str, "stock_code": str, "gvkey": str})
co = co.merge(ctrl19[["rcept_no", "log_me", "log_bm", "mom6", "kosdaq", "rel_size", "surv_lev", "relisting", "year", "period", "gvkey", "iid"]].rename(columns={"gvkey": "gvkey19", "iid": "iid19"}), on="rcept_no", how="left", suffixes=("", "_19"))
for c in ("year", "period", "kosdaq"):
    if c + "_19" in co: co[c] = co[c].fillna(co[c + "_19"])
co["gvkey"] = co.get("gvkey", pd.Series(index=co.index, dtype=object)).fillna(co.gvkey19) if "gvkey" in co else co.gvkey19
co["iid"] = co.get("iid", pd.Series(index=co.index, dtype=object)).fillna(co.iid19) if "iid" in co else co.iid19
win = pan[(pan.tau >= 2) & (pan.tau <= 250)].groupby("rcept_no").agg(d0=("date", "min"), d1=("date", "max"), n=("date", "size"), firm_bhar=("ret", lambda r: float(np.prod(1 + r) - 1)), mkt_bhar=("mret", lambda r: float(np.prod(1 + r) - 1)))
co = co.join(win, on="rcept_no"); co = co[co.n >= 0.9 * 249].copy()
R["identity_control"] = {"n": int(co[M].notna().sum()), "max_abs_diff_madj": float((co[M] - (co.firm_bhar - co.mkt_bhar)).abs().max())}
R["identity_control"]["pass"] = bool(R["identity_control"]["max_abs_diff_madj"] < 1e-6)
print("identity (market-adjusted BHAR reproduced):", R["identity_control"], flush=True)

# ---------------- benchmarks from the universe of 30
assign = pd.read_parquet(f"{OUT}/universe_portfolio_assignments.parquet"); p55 = pd.read_parquet(f"{OUT}/benchmark_portfolios_5x5_daily.parquet"); p33 = pd.read_parquet(f"{OUT}/benchmark_portfolios_3x3_daily.parquet")
udaily = pd.read_parquet(f"{OUT}/universe_daily_returns.parquet", columns=["gvkey", "iid", "datadate", "ret"])
co["t_form"] = np.where(co.event_dt.dt.month >= 7, co.event_dt.dt.year, co.event_dt.dt.year - 1)
co = co.merge(assign[["gvkey", "iid", "t", "size5", "bm5", "size3", "bm3", "me_jun", "bm"]].rename(columns={"t": "t_form"}), on=["gvkey", "iid", "t_form"], how="left")
# size-only fallback: June ME quintile from the assignment table's breakpoints in that year
for q, col in ((5, "size5"), (3, "size3")):
    miss = co[col].isna() & co.gvkey.notna()
    for t, g in assign.groupby("t"):
        idx = miss & (co.t_form == t)
        if idx.any():
            mej = pd.read_parquet(f"{OUT}/universe_month_end.parquet", columns=["gvkey", "iid", "ym", "me"]) if "mej_all" not in globals() else globals()["mej_all"]; globals()["mej_all"] = mej
            m6 = mej[(mej.ym == pd.Period(f"{t}-06", "M"))].set_index(["gvkey", "iid"]).me
            vals = pd.Series([m6.get((gk, ii), np.nan) for gk, ii in zip(co.loc[idx, "gvkey"], co.loc[idx, "iid"])], index=co.index[idx])
            edges = np.quantile(g.me_jun, np.linspace(0, 1, q + 1)[1:-1]); co.loc[idx, col] = np.where(vals.notna(), np.searchsorted(edges, vals.fillna(0)) + 1, np.nan); co.loc[idx & vals.notna(), f"{col}_fallback"] = 1
def compound(ret_series, d0, d1):
    r = ret_series[(ret_series.index >= d0) & (ret_series.index <= d1)].dropna(); return (float(np.prod(1 + r) - 1), int(len(r))) if len(r) else (np.nan, 0)
p55i = {k: g.set_index("datadate").ret_ew for k, g in p55.groupby(["size5", "bm5"])}; p33i = {k: g.set_index("datadate").ret_ew for k, g in p33.groupby(["size3", "bm3"])}
p5s = {k: g.groupby("datadate").apply(lambda x: float(np.average(x.ret_ew, weights=x.n)), include_groups=False) for k, g in p55.groupby("size5")}   # size-only (B/M-pooled) portfolios
rows = []
for r in co.itertuples():
    out = {"rcept_no": r.rcept_no}
    k55 = (r.size5, r.bm5) if pd.notna(r.size5) and pd.notna(r.bm5) else None; k33 = (r.size3, r.bm3) if pd.notna(r.size3) and pd.notna(r.bm3) else None
    out["pf55_bhar"], out["pf55_n"] = compound(p55i[k55], r.d0, r.d1) if k55 in p55i else (np.nan, 0)
    out["pf33_bhar"], out["pf33_n"] = compound(p33i[k33], r.d0, r.d1) if k33 in p33i else (np.nan, 0)
    out["size5_bhar"], _ = compound(p5s[r.size5], r.d0, r.d1) if pd.notna(r.size5) and r.size5 in p5s else (np.nan, 0)
    out["bench_used"] = "pf55" if k55 in p55i else ("size5_only" if pd.notna(r.size5) else "none")
    rows.append(out)
bm = pd.DataFrame(rows); co = co.merge(bm, on="rcept_no", how="left")
co["bhar_pf55"] = co.firm_bhar - co.pf55_bhar; co["bhar_pf33"] = co.firm_bhar - co.pf33_bhar; co["bhar_size5"] = co.firm_bhar - co.size5_bhar
co["bhar_pf"] = co.bhar_pf55.fillna(co.bhar_size5)   # primary matched-portfolio BHAR with the size-only fallback

# nearest-neighbour control firm on (log June ME, log B/M), same formation year, non-event parents, with replacement
event_gvkeys = set(co.gvkey.dropna()); cand = assign[~assign.gvkey.isin(event_gvkeys)].copy(); cand["lme"] = np.log(cand.me_jun); cand["lbm"] = np.log(cand.bm)
ud_idx = udaily.set_index(["gvkey", "iid"]).sort_index()
def nn_bhar(r, used):
    if pd.isna(r.me_jun) or pd.isna(r.bm) or r.bm <= 0: return np.nan, None, 0
    c = cand[cand.t == r.t_form]
    if not len(c): return np.nan, None, 0
    z = c[["lme", "lbm"]]; sd = z.std(); dist = np.sqrt(((np.log(r.me_jun) - c.lme) / sd.lme) ** 2 + ((np.log(r.bm) - c.lbm) / sd.lbm) ** 2)
    for j in np.argsort(dist.values)[:5]:
        m = c.iloc[j]
        try: s = ud_idx.loc[(m.gvkey, m.iid)].set_index("datadate").ret
        except KeyError: continue
        v, n = compound(s, r.d0, r.d1)
        if n >= 0.9 * 249: used.append({"rcept_no": r.rcept_no, "match_gvkey": m.gvkey, "dist": float(dist.values[j])}); return v, m.gvkey, n
    return np.nan, None, 0
used = []; vals = [nn_bhar(r, used) for r in co.itertuples()]
co["mf_bhar"] = [v[0] for v in vals]; co["bhar_mf"] = co.firm_bhar - co.mf_bhar
R["benchmarks_coverage"] = {"events_with_window": int(len(co)), "pf55": int(co.bhar_pf55.notna().sum()), "size5_fallback": int(co.bhar_size5.notna().sum() - co.bhar_pf55.notna().sum()), "pf_primary": int(co.bhar_pf.notna().sum()), "pf33": int(co.bhar_pf33.notna().sum()), "matched_firm": int(co.bhar_mf.notna().sum()),
                            "no_gvkey": int(co.gvkey.isna().sum()), "median_match_distance": float(np.median([u["dist"] for u in used])) if used else None}
print("coverage:", R["benchmarks_coverage"], flush=True)

# ---------------- (b) selection model on the firm-year universe
fy = pd.read_parquet(f"{OUT}/universe_firm_year_fundamentals.parquet"); me = pd.read_parquet(f"{OUT}/universe_month_end.parquet", columns=["gvkey", "ym", "me"])
me = me.groupby(["gvkey", "ym"]).me.sum().reset_index()      # firm-level ME (one common issue per gvkey in nearly all cases)
fy["ym"] = fy.datadate.dt.to_period("M"); fy = fy.merge(me, on=["gvkey", "ym"], how="left")
fy = fy.sort_values(["gvkey", "fyear"]); fy["sale_lag"] = fy.groupby("gvkey").sale.shift(1)
fy = fy[(fy["at"] > 0) & fy.me.notna()].copy()
# fy.lt would be the DataFrame method, not the column -> fy["lt"]
fy["log_at"] = np.log(fy["at"]); fy["q"] = (fy.me / 1e6 + fy["lt"]) / fy["at"]; fy["lev"] = fy["lt"] / fy["at"]; fy["inv"] = fy.capx / fy["at"]; fy["cf"] = fy.oibdp / fy["at"]; fy["cash"] = fy.che / fy["at"]
fy["sg"] = fy.sale / fy.sale_lag - 1; fy["kosdaq"] = (fy.exchg == 298).astype(float); fy["parent_only"] = fy.n_fallback.astype(float)
uni = pd.read_parquet(f"{OUT}/universe_common_securities.parquet")[["gvkey", "stock_code"]].drop_duplicates()
ev_all = []
for f in ("carveout_disposal_tracking_v4.json", "carveout_disposal_tracking_2001_2016.json"):
    for r in json.load(open(f"{OUT}/{f}", encoding="utf-8")):
        if r.get("type") in ("carve_out", "mixed") and str(r.get("stock_code") or "").isdigit(): ev_all.append({"stock_code": str(r["stock_code"]).zfill(6), "ann_year": int(r["rcept_no"][:4])})
ev_all = pd.DataFrame(ev_all).merge(uni, on="stock_code", how="inner").drop_duplicates(["gvkey", "ann_year"])
fy["ann_year"] = fy.fyear + 1; fy = fy.merge(ev_all.assign(event=1)[["gvkey", "ann_year", "event"]], on=["gvkey", "ann_year"], how="left"); fy["event"] = fy.event.fillna(0)
gco = pd.read_parquet(f"{RAW}/g_company_kr.parquet")[["gvkey", "gsector"]]; fy = fy.merge(gco, on="gvkey", how="left"); fy["gsector"] = fy.gsector.astype("string").fillna("unknown")
fy = fy[(fy.ann_year >= 2001) & (fy.ann_year <= 2026)].copy()
XV = ["log_at", "q", "lev", "inv", "cf", "cash", "sg", "kosdaq", "parent_only"]
sel = fy.dropna(subset=["log_at", "q", "lev"]).copy()
for c in XV:
    if sel[c].isna().any(): sel[c + "_miss"] = sel[c].isna().astype(float); sel[c] = sel[c].fillna(sel[c].median())
    if c not in ("kosdaq", "parent_only"): sel[c] = sel[c].clip(sel[c].quantile(0.01), sel[c].quantile(0.99))
Xs = sel[XV + [c for c in sel.columns if c.endswith("_miss")]].astype(float)
Xs = pd.concat([Xs, pd.get_dummies(sel.ann_year, prefix="y", drop_first=True, dtype=float), pd.get_dummies(sel.gsector, prefix="g", drop_first=True, dtype=float)], axis=1); Xs = sm.add_constant(Xs.loc[:, Xs.nunique() > 1])
lg = sm.Logit(sel.event.values, Xs).fit(method="bfgs", maxiter=5000, gtol=1e-6, disp=0)
pr = np.asarray(lg.predict(Xs), float); Xm = Xs.values.astype(float); H = (Xm * (pr * (1 - pr))[:, None]).T @ Xm; bread = np.linalg.pinv(H); sc = Xm * (sel.event.values - pr)[:, None]
g = pd.factorize(sel.gvkey)[0]; meat = np.zeros_like(H)
for gi in np.unique(g): v = sc[g == gi].sum(axis=0); meat += np.outer(v, v)
V = bread @ meat @ bread; se = np.sqrt(np.diag(V)); G = len(np.unique(g))
R["selection_logit"] = {"firm_years": int(len(sel)), "events": int(sel.event.sum()), "firms": int(G), "pseudo_r2": round(float(lg.prsquared), 3),
                        "coef": {c: {"coef": round(float(lg.params[c]), 3), "se_firm": round(float(se[list(Xs.columns).index(c)]), 3), "p_firm": float(2 * stats.t.sf(abs(lg.params[c] / se[list(Xs.columns).index(c)]), G - 1))} for c in XV if c in Xs.columns},
                        "kang_lee_table4_signs": {"log_at": "+", "lev": "+", "cf": "-", "inv": "+", "q": "+ (n.s.)", "kosdaq": "+ (KOSPI -)"}}
sel["ps"] = pr
ev_ps = sel[sel.event == 1].ps; ctrl_ps = sel[sel.event == 0].ps
R["selection_logit"]["propensity"] = {"event_median": float(ev_ps.median()), "control_median": float(ctrl_ps.median()), "event_in_control_support_share": float(((ev_ps >= ctrl_ps.min()) & (ev_ps <= ctrl_ps.max())).mean()),
                                      "auc_of_ps": float(__import__("sklearn.metrics", fromlist=["roc_auc_score"]).roc_auc_score(sel.event, sel.ps))}
print("selection:", {k: (v["coef"], round(v["p_firm"], 3)) for k, v in R["selection_logit"]["coef"].items()}, "| events", R["selection_logit"]["events"], flush=True)
# PS-matched control firm per event (same announcement year, nearest PS, non-event firm-years), BHAR over the event window
sel_c = sel[sel.event == 0][["gvkey", "ann_year", "ps"]]; sel_e = sel[sel.event == 1][["gvkey", "ann_year", "ps"]].set_index(["gvkey", "ann_year"]).ps
def psm_bhar(r):
    key = (r.gvkey, int(r.event_dt.year)) if pd.notna(r.gvkey) else None
    if key is None or key not in sel_e.index: return np.nan, None
    p0 = sel_e.loc[key]; c = sel_c[sel_c.ann_year == key[1]]
    if not len(c): return np.nan, None
    order = np.argsort((c.ps - p0).abs().values)[:5]
    for j in order:
        m = c.iloc[j]; iids = uni[uni.gvkey == m.gvkey]
        try: s = ud_idx.loc[m.gvkey].reset_index().set_index("datadate").ret
        except KeyError: continue
        v, n = compound(s.sort_index(), r.d0, r.d1)
        if n >= 0.9 * 249: return v, m.gvkey
    return np.nan, None
vals = [psm_bhar(r) for r in co.itertuples()]; co["psm_bhar"] = [v[0] for v in vals]; co["bhar_psm"] = co.firm_bhar - co.psm_bhar
R["benchmarks_coverage"]["psm_control"] = int(co.bhar_psm.notna().sum())

# ---------------- re-estimation on each benchmark
co["early"] = co.timing.map({"early_le1y": 1.0, "never": 0.0, "late_ge2y": 0.0}); co["firm"] = co.stock_code.fillna(co.corp_name)
BASE = ["log_me", "log_bm", "mom6", "kosdaq"]; FIL = ["rel_size", "surv_lev", "relisting"]; IMP = ["log_me", "log_bm", "mom6", "rel_size", "surv_lev"]
def reg(d, y, xs):
    d = d.dropna(subset=[y, "p_llm"]).copy(); X = d[xs].astype(float).copy()
    for c in IMP:
        if c in X and X[c].isna().any(): X[c + "_miss"] = X[c].isna().astype(float); X[c] = X[c].fillna(X[c].median())
    for c in X.columns:
        if c not in ("kosdaq", "relisting") and not c.endswith("_miss"): X[c] = X[c].clip(X[c].quantile(0.01), X[c].quantile(0.99))
    X = pd.concat([X, pd.get_dummies(d.year, prefix="y", drop_first=True, dtype=float)], axis=1); X = sm.add_constant(X.loc[:, X.nunique() > 1])   # drop constant columns BEFORE adding the intercept (bug fixed 2026-11-10)
    hc = sm.OLS(d[y].astype(float), X).fit(cov_type="HC1"); cf = sm.OLS(d[y].astype(float), X).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.firm)[0]})
    return {"n": int(len(d)), "coef": round(float(hc.params["p_llm"]), 4), "se_hc1": round(float(hc.bse["p_llm"]), 4), "p_hc1": round(float(hc.pvalues["p_llm"]), 3), "p_firm": round(float(cf.pvalues["p_llm"]), 3)}
R["by_benchmark"] = {}
for y, lab in ((M, "market_adjusted_paper"), ("bhar_pf", "pf55_sizeBM_with_size_fallback"), ("bhar_pf55", "pf55_strict"), ("bhar_pf33", "pf33"), ("bhar_mf", "matched_firm_sizeBM"), ("bhar_psm", "psm_control_firm")):
    d = co.dropna(subset=[y, "p_llm"]).copy(); d["rank"] = d.groupby("year")[y].rank(pct=True)
    boot = np.random.default_rng(1); means = [d[y].sample(frac=1, replace=True, random_state=int(s)).mean() for s in boot.integers(0, 1e9, 2000)]
    q = pd.qcut(d.p_llm, 5, labels=False) + 1
    e = d[d.early == 1][y]; nv = d[d.early == 0][y]
    R["by_benchmark"][lab] = {"n": int(len(d)), "mean": round(float(d[y].mean()), 4), "mean_ci95": [round(float(np.percentile(means, 2.5)), 4), round(float(np.percentile(means, 97.5)), 4)], "median": round(float(d[y].median()), 4), "share_negative": round(float((d[y] < 0).mean()), 3),
                              "spearman_S": {"rho": round(float(stats.spearmanr(d.p_llm, d[y]).statistic), 4), "p": round(float(stats.spearmanr(d.p_llm, d[y]).pvalue), 4)},
                              "median_by_S_quintile": {int(k): round(float(v), 4) for k, v in d.groupby(q)[y].median().items()}, "Q5_minus_Q1_median": round(float(d[q == 5][y].median() - d[q == 1][y].median()), 4),
                              "rank_on_S_spec3": reg(d.assign(**{"rank": d["rank"]}), "rank", ["p_llm"] + BASE + FIL), "level_on_S_spec3": reg(d, y, ["p_llm"] + BASE + FIL),
                              "early_vs_never": {"n_early": int(len(e)), "n_never": int(len(nv)), "diff_mean_pp": round(float((e.mean() - nv.mean()) * 100), 2), "diff_median_pp": round(float((e.median() - nv.median()) * 100), 2), "mw_p": round(float(stats.mannwhitneyu(e, nv).pvalue), 4) if len(e) and len(nv) else None}}
    v = R["by_benchmark"][lab]; print(f"[{lab}] n {v['n']} mean {v['mean']:+.4f} {v['mean_ci95']} median {v['median']:+.4f} | Spearman {v['spearman_S']['rho']:+.3f} (p {v['spearman_S']['p']}) | rank~S {v['rank_on_S_spec3']['coef']:+.4f} (hc1 p {v['rank_on_S_spec3']['p_hc1']}, firm p {v['rank_on_S_spec3']['p_firm']}) | early−never {v['early_vs_never']['diff_mean_pp']:+.1f} pp (MW p {v['early_vs_never']['mw_p']})", flush=True)
co[["rcept_no", "corp_name", "event_date", "year", "period", "gvkey", "iid", "p_llm", "timing", "firm_bhar", "mkt_bhar", M, "pf55_bhar", "pf33_bhar", "size5_bhar", "mf_bhar", "psm_bhar", "bhar_pf", "bhar_pf55", "bhar_pf33", "bhar_mf", "bhar_psm", "bench_used", "size5", "bm5"]].to_csv(f"{OUT}/event_benchmarks_{STAMP}.csv", index=False)

# ---------------- expectation check
bb = R["by_benchmark"]["pf55_sizeBM_with_size_fallback"]; sl = R["selection_logit"]["coef"]
R["expectation_check"] = {"identity_pass": R["identity_control"]["pass"], "pf_mean_in_[-0.12,0.02]": bool(-0.12 <= bb["mean"] <= 0.02), "pf_median_negative": bool(bb["median"] < 0),
                          "spearman_in_[-0.20,-0.05]": bool(-0.20 <= bb["spearman_S"]["rho"] <= -0.05), "rank_coef_in_[-0.28,-0.08]": bool(-0.28 <= bb["rank_on_S_spec3"]["coef"] <= -0.08),
                          "early_never_in_[-25,-5]pp": bool(-25 <= bb["early_vs_never"]["diff_mean_pp"] <= -5),
                          "selection_signs": {"log_at_pos": bool(sl["log_at"]["coef"] > 0), "lev_pos": bool(sl["lev"]["coef"] > 0), "cf_neg": bool(sl["cf"]["coef"] < 0), "inv_pos": bool(sl["inv"]["coef"] > 0), "kosdaq_pos": bool(sl["kosdaq"]["coef"] > 0)},
                          "ps_support_ge_0.95": bool(R["selection_logit"]["propensity"]["event_in_control_support_share"] >= 0.95)}
print("expectation check:", R["expectation_check"], flush=True)
def _clean(o):
    if isinstance(o, dict): return {(k.item() if hasattr(k, "item") else k): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_clean(v) for v in o]
    if hasattr(o, "item"): return o.item()
    return o
json.dump(_clean(R), open(f"{P}/results/matched_benchmark_selection_{STAMP}.json", "w"), ensure_ascii=False, indent=1, default=str)
md = [f"# Matched benchmarks and the selection model ({STAMP})", "", f"Source `results/matched_benchmark_selection_{STAMP}.json` (`code/31_matched_benchmark_and_selection.py`); per-event file `data/processed/event_benchmarks_{STAMP}.csv`. Identity control (market-adjusted BHAR equals 19's): {R['identity_control']}.", "",
      f"Coverage: {R['benchmarks_coverage']}", "", "## One-year BHAR by benchmark", "", "| Benchmark | n | mean | 95% CI | median | share < 0 | Spearman(S) | rank~S coef (HC1 p / firm p) | level~S coef | early − never (pp, MW p) |", "|---|---|---|---|---|---|---|---|---|---|"] + \
     [f"| {k} | {v['n']} | {v['mean']:+.3f} | [{v['mean_ci95'][0]:+.3f}, {v['mean_ci95'][1]:+.3f}] | {v['median']:+.3f} | {v['share_negative']} | {v['spearman_S']['rho']:+.3f} (p {v['spearman_S']['p']}) | {v['rank_on_S_spec3']['coef']:+.4f} ({v['rank_on_S_spec3']['p_hc1']} / {v['rank_on_S_spec3']['p_firm']}) | {v['level_on_S_spec3']['coef']:+.3f} (p {v['level_on_S_spec3']['p_hc1']}) | {v['early_vs_never']['diff_mean_pp']:+.1f} (median {v['early_vs_never']['diff_median_pp']:+.1f}; p {v['early_vs_never']['mw_p']}) |" for k, v in R["by_benchmark"].items()] + [
      "", "Median BHAR by signal quintile: " + "; ".join(f"{k}: {v['median_by_S_quintile']}" for k, v in R["by_benchmark"].items()), "",
      "## Selection logit — who announces a captive spin-off (firm-year universe, outcome = announcement in the next calendar year)", "", f"Firm-years {R['selection_logit']['firm_years']}, events {R['selection_logit']['events']}, firms {R['selection_logit']['firms']}, pseudo-R² {R['selection_logit']['pseudo_r2']}; year FE + GICS sector FE; firm-clustered SE.", "", "| Covariate | coef | se (firm) | p | Kang & Lee (2025b) Table 4 sign |", "|---|---|---|---|---|"] + \
     [f"| {c} | {v['coef']:+.3f} | {v['se_firm']} | {v['p_firm']:.3f} | {R['selection_logit']['kang_lee_table4_signs'].get(c, '')} |" for c, v in R["selection_logit"]["coef"].items()] + [
      "", f"Propensity: {R['selection_logit']['propensity']}", "", "## Expectation check", "", str(R["expectation_check"]), "",
      "## Caveats recorded", "", "- Benchmarks are compounded over the event's own trading days (universe calendar), firm returns from the paper's panel (KRX 2017+, Compustat 2001–2016).",
      "- Size/B-M assignment is the FF June convention with all-universe breakpoints; firms without a B/M assignment (negative book equity, no December ME) get the size-only quintile; events with no Compustat security get no matched benchmark (counted).",
      "- The selection model uses operating cash flow proxied by oibdp/at because net-income lines are unverified for Korea (26 P2b); board independence, foreign ownership and chaebol affiliation of Kang & Lee's specification are not yet in the data (strategy §2, step 1).",
      "- Matched-firm and PSM benchmarks use one nearest neighbour with replacement; they are noisier than portfolio benchmarks by construction."]
open(f"{P}/docs/MATCHED_BENCHMARK_NOTE_{STAMP}.md", "w").write("\n".join(md) + "\n"); print(f"saved results/matched_benchmark_selection_{STAMP}.json, docs/MATCHED_BENCHMARK_NOTE_{STAMP}.md")
