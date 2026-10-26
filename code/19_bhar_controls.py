#!/usr/bin/env python3
"""19_bhar_controls.py — does the ex-ante disposal score's association with post-announcement returns survive controls?

The alternative a referee will state: filings that signal disposal come from parents in trouble (small, levered, poor recent returns), and it
is the trouble, not the disposal signal, that predicts the drift. This script adds those controls to the regressions of 16/18.

Sample: the pooled carve-out sample of 18 (2001–2016 Compustat panel without glitch suspects; 2017+ KRX panel), Gate-1 score, clean labels.
Controls (source in brackets; nothing inferred from a name):
  log_me        log market capitalisation at the last month-end before the event: prccd × cshoc, KRW, from the Korea-factor project's
                Compustat month-end extract (korea-ff-factors/raw_secd.parquet; cshoc is in shares — checked on Samsung 2026-08: 5.85e9)
  log_bm        log(book equity / ME): ceq (Compustat Global g_funda, millions KRW) of the latest fiscal year ending >= 6 months before
                the event, over ME in millions KRW; NaN if ceq <= 0
  mom6          market-adjusted buy-and-hold return over tau [-130, -2] (the panel of 17/13)
  kosdaq        1 if the parent's market at the event is KOSDAQ (17: exchg 298; 13: corp_cls K)
  rel_size      new company total assets / (new company + surviving company total assets), from the filing
                (2017+: baseline_features newco_assets, parent_after_assets — DART structured fields; 2001–2016: 12e text extraction
                new_company.total_assets, surviving_company_after_division.total_assets, same unit within a filing)
  surv_lev      surviving company total debt / total assets from the filing (same sources)
  relisting     1 if the filing states a (re)listing application (2017+: relisting_application starts with '예'; 2001–2016: 'yes')
  2017+ only:   parent_roa = parent_net_income / parent_total_assets, parent_lev = parent_total_debt / parent_total_assets,
                log_parent_assets (baseline_features, parent's last fiscal year before the division)
Missing controls: median imputation plus a missing indicator (as in Gate 1), so the sample does not shrink by control availability; n reported.
Outcomes: BHAR 1y [+2,+250] market-adjusted; CAR_mm 1y; within-year percentile rank of BHAR 1y (0–1; skew-robust); announcement CAR[-1,+1].
Standard errors: HC1 and clustered by event year. Also: AUC of the score for early disposal (first change <= 1 year) vs never, and vs late/never.
Output: results/bhar_controls_<date>.json
"""
import os, json, importlib.util, datetime as dt, numpy as np, pandas as pd
import statsmodels.api as sm
from sklearn.metrics import roc_auc_score

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(name):
    spec = importlib.util.spec_from_file_location(name, f"{P}/code/{name}.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
b16 = load("16_bhar_by_predicted_disposal"); b18 = load("18_bhar_pooled")
FF = "/Users/jihwanw/PhD/Finance/0_pipeline/korea-ff-factors"

B = b18.build_pooled()
co_old = B["co_old_k"][~B["co_old_k"].flag_glitch].drop(columns=["flag_glitch"]); co = pd.concat([co_old, B["co_k"]], ignore_index=True)
pan = pd.concat([B["pan_old"][B["pan_old"].rcept_no.isin(co_old.rcept_no)], B["pan_k"]], ignore_index=True)
co = b16.add_windows(co, pan); co["event_dt"] = pd.to_datetime(co.event_date); co["timing"] = co.rcept_no.map(B["timing"])
M = b16.MAIN

# ---- controls
sec = pd.read_parquet(f"{FF}/raw_secd.parquet"); sec["me"] = sec.prccd * sec.cshoc
fun = pd.read_parquet(f"{FF}/raw_funda_full.parquet"); fun["datadate"] = pd.to_datetime(fun.datadate)
mkt_k = pd.read_csv(f"{P}/data/processed/event_study_meta_compustat.csv", dtype={"rcept_no": str}).set_index("rcept_no").market
def me_bm(r):
    s = sec[(sec.gvkey == r.gvkey) & (sec.iid == r.iid) & (sec.datadate < r.event_dt)].sort_values("datadate")
    if len(s) == 0 or pd.isna(s.me.iloc[-1]) or s.me.iloc[-1] <= 0: return pd.Series({"log_me": np.nan, "log_bm": np.nan, "me_date": None})
    me = float(s.me.iloc[-1]); f = fun[(fun.gvkey == r.gvkey) & (fun.datadate <= r.event_dt - pd.Timedelta(days=180)) & fun.ceq.notna()].sort_values("datadate")
    bm = (float(f.ceq.iloc[-1]) / (me / 1e6)) if len(f) and f.ceq.iloc[-1] > 0 else np.nan
    return pd.Series({"log_me": np.log(me), "log_bm": np.log(bm) if bm and bm > 0 else np.nan, "me_date": str(s.datadate.iloc[-1].date())})
co = pd.concat([co, co.apply(me_bm, axis=1)], axis=1)
mom = pan[(pan.tau >= -130) & (pan.tau <= -2)].groupby("rcept_no").apply(lambda g: float((1 + g.ret).prod() - (1 + g.mret).prod()) if len(g) >= 100 else np.nan, include_groups=False)
co["mom6"] = co.rcept_no.map(mom)
co["kosdaq"] = np.where(co.period == "2017+", (co.corp_cls == "K").astype(float), (co.rcept_no.map(mkt_k) == "K").astype(float))
bf = {f["rcept_no"]: f for f in json.load(open(f"{P}/data/processed/baseline_features.json", encoding="utf-8"))}
fin = {}
for l in open(f"{P}/results/filing_financials_2001_2016.jsonl", encoding="utf-8"):
    r = json.loads(l); fin[r["rcept_no"]] = r.get("parsed") or {}
def num(x): return float(x) if isinstance(x, (int, float)) and not (isinstance(x, float) and np.isnan(x)) else np.nan
def filing_controls(r):
    if r.period == "2017+":
        f = bf.get(r.rcept_no, {}); na, sa, sd = num(f.get("newco_assets")), num(f.get("parent_after_assets")), num(f.get("parent_after_debt"))
        relist = 1.0 if str(f.get("relisting_application") or "").strip().startswith("예") else 0.0
        pa, pd_, ni = num(f.get("parent_total_assets")), num(f.get("parent_total_debt")), num(f.get("parent_net_income"))
        return pd.Series({"rel_size": na / (na + sa) if na > 0 and sa > 0 else np.nan, "surv_lev": sd / sa if sa > 0 and sd >= 0 else np.nan, "relisting": relist,
                          "parent_roa": ni / pa if pa > 0 else np.nan, "parent_lev": pd_ / pa if pa > 0 and pd_ >= 0 else np.nan, "log_parent_assets": np.log(pa) if pa > 0 else np.nan})
    p = fin.get(r.rcept_no, {}); nc, sv = p.get("new_company") or {}, p.get("surviving_company_after_division") or {}
    na, sa, sd = num(nc.get("total_assets")), num(sv.get("total_assets")), num(sv.get("total_debt"))
    return pd.Series({"rel_size": na / (na + sa) if na > 0 and sa > 0 else np.nan, "surv_lev": sd / sa if sa > 0 and sd >= 0 else np.nan,
                      "relisting": 1.0 if str(p.get("relisting_or_listing_application") or "").lower() == "yes" else 0.0, "parent_roa": np.nan, "parent_lev": np.nan, "log_parent_assets": np.nan})
co = pd.concat([co, co.apply(filing_controls, axis=1)], axis=1)
co["bhar1y_rank_in_year"] = co.groupby("year")[M].rank(pct=True)
co["early"] = co.timing.map({"early_le1y": 1.0, "never": 0.0, "late_ge2y": 0.0, "disposed_timing_unknown": np.nan})

def design(d, xs, impute):
    X = d[xs].astype(float).copy()
    for c in impute:
        if c in X and X[c].isna().any():
            X[c + "_miss"] = X[c].isna().astype(float); X[c] = X[c].fillna(X[c].median())
    for c in X.columns:
        if c not in ("kosdaq", "relisting") and not c.endswith("_miss"): X[c] = X[c].clip(X[c].quantile(0.01), X[c].quantile(0.99))
    return X

def reg(d, y, xs, impute=(), fe=True):
    d = d.dropna(subset=[y] + [x for x in xs if x not in impute]).copy(); X = design(d, xs, impute)
    if fe: X = pd.concat([X, pd.get_dummies(d.year, prefix="y", drop_first=True, dtype=float)], axis=1)
    X = sm.add_constant(X); yv = d[y].astype(float)
    hc = sm.OLS(yv, X).fit(cov_type="HC1"); cl = sm.OLS(yv, X).fit(cov_type="cluster", cov_kwds={"groups": d.year.astype("category").cat.codes.values})
    out = {"n": int(len(d)), "r2": round(float(hc.rsquared), 3), "n_years": int(d.year.nunique())}
    for v in xs:
        out[v] = {"coef": round(float(hc.params[v]), 4), "se_hc1": round(float(hc.bse[v]), 4), "p_hc1": round(float(hc.pvalues[v]), 3), "p_cluster_year": round(float(cl.pvalues[v]), 3)}
    return out

BASE = ["log_me", "log_bm", "mom6", "kosdaq"]; FIL = ["rel_size", "surv_lev", "relisting"]; PAR = ["parent_roa", "parent_lev", "log_parent_assets"]
IMP = ["log_me", "log_bm", "mom6", "rel_size", "surv_lev", "parent_roa", "parent_lev", "log_parent_assets"]
res = {"run_at": dt.datetime.now().isoformat(timespec="seconds"), "sample": {"n_carveouts": int(len(co)), "with_score_and_1y": int(co.dropna(subset=["p_llm", M]).shape[0]),
       "control_coverage": {c: int(co[c].notna().sum()) for c in BASE + FIL + PAR}}, "specs": {}}
d_all = co.dropna(subset=["p_llm"]); d_new = d_all[d_all.period == "2017+"]
for y, lab in ((M, "bhar1y"), ("bhar1y_rank_in_year", "bhar1y_rank"), ("car_mm_p2_p250", "carmm1y"), ("car_mm_m1_p1", "ann_car")):
    res["specs"][lab] = {
        "1_score_yearFE": reg(d_all, y, ["p_llm"]),
        "2_plus_size_bm_mom_market": reg(d_all, y, ["p_llm"] + BASE, IMP),
        "3_plus_filing_controls": reg(d_all, y, ["p_llm"] + BASE + FIL, IMP),
        "3b_old_period_only": reg(d_all[d_all.period == "2001-2016"], y, ["p_llm"] + BASE + FIL, IMP),
        "3c_new_period_only": reg(d_new, y, ["p_llm"] + BASE + FIL, IMP),
        "4_new_period_plus_parent_fundamentals": reg(d_new, y, ["p_llm"] + BASE + FIL + PAR, IMP)}
# realized early disposal, with the same controls; and both together
dl = co.dropna(subset=["early"])
res["specs"]["bhar1y_realized"] = {"early_yearFE": reg(dl, M, ["early"]), "early_plus_controls": reg(dl, M, ["early"] + BASE + FIL, IMP),
                                   "score_and_early_plus_controls": reg(dl.dropna(subset=["p_llm"]), M, ["p_llm", "early"] + BASE + FIL, IMP),
                                   "rank_early_plus_controls": reg(dl, "bhar1y_rank_in_year", ["early"] + BASE + FIL, IMP)}
# does the score predict EARLY disposal?
e = co.dropna(subset=["p_llm", "early"]); res["score_predicts_early_disposal"] = {
    "early_vs_never": {"n": int(len(e)), "share_early": round(float(e.early.mean()), 3), "auc": round(float(roc_auc_score(e.early, e.p_llm)), 3)},
    "early_vs_late_or_never": (lambda d: {"n": int(len(d)), "auc": round(float(roc_auc_score((d.timing == "early_le1y").astype(int), d.p_llm)), 3)})(co.dropna(subset=["p_llm"])[co.timing.isin(["early_le1y", "late_ge2y", "never"])]),
    "late_vs_never": (lambda d: {"n": int(len(d)), "auc": round(float(roc_auc_score((d.timing == "late_ge2y").astype(int), d.p_llm)), 3)})(co.dropna(subset=["p_llm"])[co.timing.isin(["late_ge2y", "never"])]),
    "by_period_early_vs_never": {per: {"n": int(len(g)), "auc": round(float(roc_auc_score(g.early, g.p_llm)), 3)} for per, g in e.groupby("period") if g.early.nunique() > 1}}
res["control_summary"] = co[BASE + FIL + PAR].describe().round(3).to_dict()
stamp = dt.date.today().strftime("%Y%m%d"); json.dump(res, open(f"{P}/results/bhar_controls_{stamp}.json", "w"), ensure_ascii=False, indent=1, default=float)
co.to_csv(f"{P}/data/processed/bhar_controls_events_{stamp}.csv", index=False)
print("coverage:", res["sample"]); 
for lab in ("bhar1y", "bhar1y_rank", "carmm1y", "ann_car"):
    print(f"\n== {lab}: coefficient on p_llm ==")
    for k, v in res["specs"][lab].items(): print(f"  {k:40s} n {v['n']:3d} | coef {v['p_llm']['coef']:+.4f} se {v['p_llm']['se_hc1']:.4f} p {v['p_llm']['p_hc1']:.3f} (cluster p {v['p_llm']['p_cluster_year']:.3f}) | R2 {v['r2']}")
print("\n== realized early disposal ==")
for k, v in res["specs"]["bhar1y_realized"].items(): print(f"  {k:32s} n {v['n']} | " + " | ".join(f"{x}: {v[x]['coef']:+.4f} (p {v[x]['p_hc1']:.3f})" for x in ("early", "p_llm") if x in v))
print("\nscore -> early disposal:", json.dumps(res["score_predicts_early_disposal"], ensure_ascii=False))
print("\ncontrols (spec 3, pooled bhar1y):", {k: (v["coef"], v["p_hc1"]) for k, v in res["specs"]["bhar1y"]["3_plus_filing_controls"].items() if isinstance(v, dict) and k != "p_llm"})
print(f"saved results/bhar_controls_{stamp}.json")
