#!/usr/bin/env python3
"""24_label_sensitivity.py — do the headline results depend on the eleven definition-sensitive labels?

The cross-check of 2026-10-18 (results/label_crosscheck_tracker_20261018.json, 'disagreements') lists eleven 2017+ events where the
v3 tracker label (from 타법인출자현황 / KIND) and the annual-report reading disagree for definitional reasons: intra-group transfers,
temporary external dilution (RCPS to a PEF, later redeemed), dilution below materiality, a tracker match to the wrong entity, and three
unresolved conflicts. The clean sample keeps the tracker label (disposed). This script flips all eleven to the annual-report reading
(retained_100) — the most adverse direction for our results, since it moves events from 'disposed' to 'retained' — and recomputes:
  Gate-1 AUC (pooled 2001–2026, two-model identified score), the disposed-vs-retained and early-vs-never one-year BHAR comparisons,
  the regression of BHAR 1y / within-year rank on early disposal with controls, and the governance tercile disposal rates.
Also the opposite flip for the two intra-group transfers (KCC, 드림시큐리티) coded as 'disposed' (they already are) is moot; a third variant
drops the eleven altogether. Output: results/label_sensitivity_<date>.json
"""
import os, json, importlib.util, datetime as dt, numpy as np, pandas as pd
import statsmodels.api as sm
from sklearn.metrics import roc_auc_score

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(name):
    spec = importlib.util.spec_from_file_location(name, f"{P}/code/{name}.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
b16 = load("16_bhar_by_predicted_disposal"); M = b16.MAIN
cc = json.load(open(f"{P}/results/label_crosscheck_tracker_20261018.json", encoding="utf-8"))
flip = {r["rcept_no"]: r for r in cc["disagreements"]}; print("definition-sensitive cases:", len(flip), [r["corp_name"] for r in flip.values()])
co = pd.read_csv(f"{P}/data/processed/bhar_controls_events_20261025.csv", dtype={"rcept_no": str, "stock_code": str})
co["rank1y"] = co.groupby("year")[M].rank(pct=True)
own = pd.DataFrame(json.load(open(f"{P}/data/processed/ownership_pre_event_all.json", encoding="utf-8"))); own = own[~own.disagree.astype(bool)][["rcept_no", "block_pct"]]
co = co.merge(own, on="rcept_no", how="left")
BASE = ["log_me", "log_bm", "mom6", "kosdaq", "rel_size", "surv_lev", "relisting"]; IMP = ["log_me", "log_bm", "mom6", "rel_size", "surv_lev"]

def variant(d, mode):
    d = d.copy()
    if mode == "flip_to_retained":
        m = d.rcept_no.isin(flip); d.loc[m, "disposed"] = 0.0; d.loc[m, "timing"] = "never"; d.loc[m, "early"] = 0.0
    elif mode == "drop":
        d = d[~d.rcept_no.isin(flip)]
    return d

def reg(dd, y, xs, controls):
    allx = xs + controls; dd = dd.dropna(subset=[y] + [x for x in allx if x not in IMP]).copy(); X = dd[allx].astype(float).copy()
    for c in IMP:
        if X[c].isna().any(): X[c + "_miss"] = X[c].isna().astype(float); X[c] = X[c].fillna(X[c].median())
    X = sm.add_constant(pd.concat([X, pd.get_dummies(dd.year, prefix="y", drop_first=True, dtype=float)], axis=1)); f = sm.OLS(dd[y].astype(float), X).fit(cov_type="HC1")
    return {"n": int(len(dd)), **{v: {"coef": round(float(f.params[v]), 4), "p_hc1": round(float(f.pvalues[v]), 3)} for v in xs}}

def headline(d, label):
    s = d.dropna(subset=["p_llm", "disposed"]); e = d.dropna(subset=["early"])
    out = {"label": label, "n_clean": int(len(s)), "disposed_share": round(float(s.disposed.mean()), 3), "gate1_auc_two_model": round(float(roc_auc_score(s.disposed, s.p_llm)), 3),
           "gate1_auc_2017plus": round(float(roc_auc_score(s[s.period == "2017+"].disposed, s[s.period == "2017+"].p_llm)), 3),
           "bhar1y_disposed_vs_retained": b16.diff_groups(d[d.disposed == 1][M], d[d.disposed == 0][M]),
           "bhar1y_early_vs_never": b16.diff_groups(d[d.timing == "early_le1y"][M], d[d.timing == "never"][M]),
           "reg_bhar1y_on_early_controls": reg(e, M, ["early"], BASE), "reg_rank1y_on_early_controls": reg(e, "rank1y", ["early"], BASE)}
    g = d.dropna(subset=["block_pct"]).copy(); g["tercile"] = pd.qcut(g.block_pct, 3, labels=["low", "mid", "high"])
    out["disposal_rate_by_block_tercile"] = {str(t): round(float(x.disposed.mean()), 3) for t, x in g.dropna(subset=["disposed"]).groupby("tercile", observed=True)}
    out["early_rate_by_block_tercile"] = {str(t): round(float(x.early.mean()), 3) for t, x in g.dropna(subset=["early"]).groupby("tercile", observed=True)}
    return out

co["early"] = co.timing.map({"early_le1y": 1.0, "never": 0.0, "late_ge2y": 0.0})
res = {"run_at": dt.datetime.now().isoformat(timespec="seconds"), "cases": [{k: r.get(k) for k in ("rcept_no", "corp_name", "division_year", "v3_outcome", "llm_outcome", "category")} for r in flip.values()],
       "baseline": headline(co, "clean labels as used (tracker label kept for the eleven)"),
       "flip_to_retained": headline(variant(co, "flip_to_retained"), "eleven cases set to retained_100 / never (adverse)"),
       "drop_eleven": headline(variant(co, "drop"), "eleven cases dropped")}
stamp = dt.date.today().strftime("%Y%m%d"); json.dump(res, open(f"{P}/results/label_sensitivity_{stamp}.json", "w"), ensure_ascii=False, indent=1, default=float)
for k in ("baseline", "flip_to_retained", "drop_eleven"):
    v = res[k]; dr, en = v["bhar1y_disposed_vs_retained"], v["bhar1y_early_vs_never"]
    print(f"\n[{k}] n_clean {v['n_clean']} disposed {v['disposed_share']} | Gate-1 AUC pooled {v['gate1_auc_two_model']} (2017+ {v['gate1_auc_2017plus']})")
    print(f"  disposed−retained BHAR1y {dr['diff']:+.3f} (Welch p {dr['welch_p']}, MW p {dr['mannwhitney_p']}) | early−never {en['diff']:+.3f} (Welch p {en['welch_p']}, MW p {en['mannwhitney_p']})")
    print(f"  reg early: BHAR {v['reg_bhar1y_on_early_controls']['early']} | rank {v['reg_rank1y_on_early_controls']['early']} | disposal by block tercile {v['disposal_rate_by_block_tercile']} | early by tercile {v['early_rate_by_block_tercile']}")
print(f"\nsaved results/label_sensitivity_{stamp}.json")
