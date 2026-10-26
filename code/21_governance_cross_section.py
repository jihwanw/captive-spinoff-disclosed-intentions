#!/usr/bin/env python3
"""21_governance_cross_section.py — the controlling shareholder's stake and the carve-out → disposal → return chain (events 2016+).

Principal–principal reading (Kang & Lee 2025 FRL: 지배주주 지분↑ → 손실↓; Bae, Kang & Kim 2002 on tunnelling): when the controlling
block is small, the controlling shareholder bears a small share of the parent's loss from disposing of the carved-out subsidiary and
has more to gain from the disposal (listing proceeds, intragroup transfer), so disposal should be more likely and the parent's loss
larger where the block is small. Tests (all descriptive/associational; year fixed effects; HC1 and year-clustered SEs):
  T1  P(early disposal <= 1y) ~ block, with the filing score and controls (logit, average marginal effect reported as a linear-probability OLS)
  T2  score ~ block: does the filing signal more disposal where the block is small?
  T3  announcement CAR[-1,+1] ~ block, score, score x low_block
  T4  BHAR 1y (and within-year rank) ~ block; ~ early x low_block; ~ score x low_block
  T5  block terciles: disposal rate, early-disposal rate, mean/median BHAR, announcement CAR
Ownership: data/processed/largest_shareholder_pre_event.json (20): block_ex_treasury_pct at the fiscal year-end before the announcement
(filer's own 계 minus treasury rows; rowsum used when no total; the 5 rowsum/total disagreements are excluded). low_block = below the sample median.
Sample: all carve-outs with pre-event ownership (20c: DART API for 2016+ announcements; annual-report table extraction for earlier ones), returns from the pooled panel of 18, controls of 19.
Output: results/governance_cross_section_<date>.json
"""
import os, json, importlib.util, datetime as dt, numpy as np, pandas as pd
import statsmodels.api as sm
from scipy import stats

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(name):
    spec = importlib.util.spec_from_file_location(name, f"{P}/code/{name}.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
b16 = load("16_bhar_by_predicted_disposal")
co = pd.read_csv(f"{P}/data/processed/bhar_controls_events_20261025.csv", dtype={"rcept_no": str, "stock_code": str})   # pooled events with windows, score, timing, controls (19)
own = pd.DataFrame(json.load(open(f"{P}/data/processed/ownership_pre_event_all.json", encoding="utf-8")))   # 20c: API (2016+) + annual-report LLM extraction (earlier), disagreements flagged
own = own[~own.disagree.astype(bool)][["rcept_no", "block_pct", "largest_pct", "source", "basis"]].rename(columns={"block_pct": "block_ex_treasury_pct"})
d = co.merge(own, on="rcept_no", how="inner"); M = b16.MAIN
d["block"] = d.block_ex_treasury_pct / 100; d["low_block"] = (d.block < d.block.median()).astype(float)
d["early"] = d.timing.map({"early_le1y": 1.0, "never": 0.0, "late_ge2y": 0.0}); d["disposed_any"] = d.disposed
d["rank1y"] = d.groupby("year")[M].rank(pct=True)
BASE = ["log_me", "log_bm", "mom6", "kosdaq"]; FIL = ["rel_size", "surv_lev", "relisting"]; IMP = ["log_me", "log_bm", "mom6", "rel_size", "surv_lev"]

def design(dd, xs):
    X = dd[xs].astype(float).copy()
    for c in IMP:
        if c in X and X[c].isna().any(): X[c + "_miss"] = X[c].isna().astype(float); X[c] = X[c].fillna(X[c].median())
    return X
def reg(dd, y, xs, fe=True, controls=()):
    allx = list(xs) + list(controls); dd = dd.dropna(subset=[y] + [x for x in allx if x not in IMP]).copy(); X = design(dd, allx)
    if fe and dd.year.nunique() > 1: X = pd.concat([X, pd.get_dummies(dd.year, prefix="y", drop_first=True, dtype=float)], axis=1)
    X = sm.add_constant(X); yv = dd[y].astype(float)
    hc = sm.OLS(yv, X).fit(cov_type="HC1"); cl = sm.OLS(yv, X).fit(cov_type="cluster", cov_kwds={"groups": dd.year.astype("category").cat.codes.values})
    out = {"n": int(len(dd)), "r2": round(float(hc.rsquared), 3)}
    for v in xs: out[v] = {"coef": round(float(hc.params[v]), 4), "se_hc1": round(float(hc.bse[v]), 4), "p_hc1": round(float(hc.pvalues[v]), 3), "p_cluster_year": round(float(cl.pvalues[v]), 3)}
    return out

d["score_x_low"] = d.p_llm * d.low_block; d["early_x_low"] = d.early * d.low_block
res = {"run_at": dt.datetime.now().isoformat(timespec="seconds"), "sample": {"events_with_ownership": int(len(d)), "by_period": d.period.value_counts().to_dict(), "by_source": d.source.value_counts().to_dict(),
       "with_score": int(d.p_llm.notna().sum()), "with_1y": int(d[M].notna().sum()), "with_early_label": int(d.early.notna().sum()),
       "block_describe": d.block.describe().round(3).to_dict(), "largest_describe": (d.largest_pct / 100).describe().round(3).to_dict()}}
res["T1_early_disposal_on_block"] = {"block_only": reg(d, "early", ["block"]), "block_plus_score": reg(d, "early", ["block", "p_llm"]), "block_score_controls": reg(d, "early", ["block", "p_llm"], controls=BASE + FIL),
                                     "any_disposal_block_controls": reg(d, "disposed_any", ["block"], controls=BASE + FIL)}
res["T2_score_on_block"] = {"block_only": reg(d, "p_llm", ["block"]), "block_controls": reg(d, "p_llm", ["block"], controls=BASE + FIL)}
res["T3_announcement_car"] = {"block": reg(d, "car_mm_m1_p1", ["block"], controls=BASE), "score_and_low_block_interaction": reg(d, "car_mm_m1_p1", ["p_llm", "low_block", "score_x_low"], controls=BASE)}
res["T4_post_return"] = {"bhar_on_block": reg(d, M, ["block"], controls=BASE + FIL), "rank_on_block": reg(d, "rank1y", ["block"], controls=BASE + FIL),
                         "bhar_early_x_low_block": reg(d, M, ["early", "low_block", "early_x_low"], controls=BASE + FIL), "rank_early_x_low_block": reg(d, "rank1y", ["early", "low_block", "early_x_low"], controls=BASE + FIL),
                         "bhar_score_x_low_block": reg(d, M, ["p_llm", "low_block", "score_x_low"], controls=BASE + FIL), "rank_score_x_low_block": reg(d, "rank1y", ["p_llm", "low_block", "score_x_low"], controls=BASE + FIL)}
d["block_tercile"] = pd.qcut(d.block, 3, labels=["low", "mid", "high"])
T5 = {}
for t, g in d.groupby("block_tercile", observed=True):
    T5[str(t)] = {"n": int(len(g)), "block_range": [round(float(g.block.min()), 3), round(float(g.block.max()), 3)], "disposal_rate": round(float(g.disposed_any.mean()), 3) if g.disposed_any.notna().any() else None,
                  "early_disposal_rate": round(float(g.early.mean()), 3) if g.early.notna().any() else None, "mean_score": round(float(g.p_llm.mean()), 3),
                  "bhar1y": b16.summ(g[M]), "ann_car": b16.summ(g.car_mm_m1_p1)}
res["T5_block_terciles"] = T5
lo, hi = d[d.block_tercile == "low"], d[d.block_tercile == "high"]
res["T5_low_vs_high"] = {M: b16.diff_groups(lo[M], hi[M]), "car_mm_m1_p1": b16.diff_groups(lo.car_mm_m1_p1, hi.car_mm_m1_p1),
                         "early_rate_fisher_p": round(float(stats.fisher_exact(pd.crosstab(d[d.block_tercile.isin(["low", "high"])].block_tercile.astype(str), d[d.block_tercile.isin(["low", "high"])].early.fillna(-1)).loc[["low", "high"], [0.0, 1.0]].values)[1]), 3) if d.early.notna().sum() > 20 else None}
stamp = dt.date.today().strftime("%Y%m%d"); json.dump(res, open(f"{P}/results/governance_cross_section_{stamp}.json", "w"), ensure_ascii=False, indent=1, default=float)
print("sample:", res["sample"]["events_with_ownership"], res["sample"]["by_period"], "| block median", res["sample"]["block_describe"]["50%"], "| largest median", res["sample"]["largest_describe"]["50%"])
for k in ("T1_early_disposal_on_block", "T2_score_on_block", "T3_announcement_car", "T4_post_return"):
    print(f"\n== {k} ==")
    for s_, v in res[k].items(): print(f"  {s_:34s} n {v['n']:3d} | " + " | ".join(f"{x}: {v[x]['coef']:+.3f} (p {v[x]['p_hc1']}, cl {v[x]['p_cluster_year']})" for x in v if isinstance(v[x], dict)))
print("\n== T5 block terciles ==")
for t, v in T5.items(): print(f"  {t:5s} n {v['n']} block {v['block_range']} | disposal {v['disposal_rate']} early {v['early_disposal_rate']} score {v['mean_score']} | BHAR1y mean {v['bhar1y'].get('mean')} median {v['bhar1y'].get('median')} | annCAR {v['ann_car'].get('mean')}")
print("  low vs high:", {k: (v.get("diff"), v.get("welch_p"), v.get("mannwhitney_p")) if isinstance(v, dict) else v for k, v in res["T5_low_vs_high"].items()})
print(f"saved results/governance_cross_section_{stamp}.json")
