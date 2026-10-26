#!/usr/bin/env python3
"""15_gate1_pooled.py — Gate 1 on the pooled carve-out sample 2001-2026.

Labels: 2017+ from carveout_disposal_tracking_v4.json (v4), 2001-2016 from carveout_disposal_tracking_2001_2016.json (12d);
clean = disposed (ipo_listed/majority_disposed/partial_sale) vs retained_100.
LLM scores: identified-condition p_disposal, mean over runs per model, two-model average (results/llm_judge/ for 2017+,
results/llm_judge_2001_2016/ for 2001-2016).
Financial baseline (filing numbers only — the parent's prior-FY accounts from fnlttSinglAcnt exist only for FY2015+):
  log(newco assets), newco leverage, newco sales/assets, relative size (newco / (newco + surviving)), surviving leverage,
  relisting application, put-option contract (2017+ only -> missing indicator), KOSDAQ parent; NO year.
  2017+: API fields (05); 2001-2016: 12e text extraction (validated 100% on 60 2017+ filings), unit-scaled to KRW.
Protocol as 10 (RepeatedStratifiedKFold 5x50, logistic C=1, median imputation + missing flags, 1-99% clipping, paired bootstrap).
Panels: pooled; by period (2001-2008, 2009-2016, 2017-2025); mature (division_year <= 2021); temporal (train <= 2016, test >= 2017).
Output: results/gate1_pooled_<date>.json
"""
import json, glob, os, re, datetime as dt, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.metrics import roc_auc_score

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISPOSED = {"ipo_listed", "majority_disposed", "partial_sale"}
UNIT = {"원": 1.0, "천원": 1e3, "백만원": 1e6, "억원": 1e8}


def scores(pattern):
    d = {}
    for f in glob.glob(pattern):
        for l in open(f, encoding="utf-8"):
            r = json.loads(l); p = (r.get("parsed") or {}).get("p_disposal")
            if isinstance(p, (int, float)): d.setdefault(r["rcept_no"], []).append(float(p) / 100)
    return {k: float(np.mean(v)) for k, v in d.items()}


rows = []
# ---- 2017+
v4 = json.load(open(f"{P}/data/processed/carveout_disposal_tracking_v4.json", encoding="utf-8"))
feat = {f["rcept_no"]: f for f in json.load(open(f"{P}/data/processed/baseline_features.json", encoding="utf-8"))}
cl = {"claude": scores(f"{P}/results/llm_judge/anthropic__identified*.jsonl"), "gpt": scores(f"{P}/results/llm_judge/openai__identified*.jsonl")}
for r in v4:
    k = r["rcept_no"]; f = feat.get(k)
    if r["outcome"] not in DISPOSED | {"retained_100"} or not f or k not in cl["claude"] or k not in cl["gpt"]: continue
    rows.append({"rcept_no": k, "period_src": "2017+", "y": int(r["outcome"] in DISPOSED), "division_year": r["division_year"], "kosdaq": int(f["corp_cls"] == "K"), "label_source": r.get("label_source"),
                 "newco_assets": f["newco_assets"], "newco_debt": f["newco_debt"], "newco_sales": f["newco_sales"], "parent_after_assets": f["parent_after_assets"], "parent_after_debt": f["parent_after_debt"],
                 "relisting_yes": int((f.get("relisting_application") or "").strip().startswith("예")), "put_option_yes": int((f.get("put_option_contract") or "").strip().startswith("예")) if f.get("put_option_contract") else None,
                 "p_claude": cl["claude"][k], "p_gpt": cl["gpt"][k]})
# ---- 2001-2016
old = json.load(open(f"{P}/data/processed/carveout_disposal_tracking_2001_2016.json", encoding="utf-8"))
fin = {}
for l in open(f"{P}/results/filing_financials_2001_2016.jsonl", encoding="utf-8"):
    r = json.loads(l); fin[r["rcept_no"]] = r.get("parsed") or {}
co = {"claude": scores(f"{P}/results/llm_judge_2001_2016/anthropic__identified*.jsonl"), "gpt": scores(f"{P}/results/llm_judge_2001_2016/openai__identified*.jsonl")}
def num(v, mult): return float(v) * mult if isinstance(v, (int, float)) and mult else None
for r in old:
    k = r["rcept_no"]; p = fin.get(k)
    if r["outcome"] not in DISPOSED | {"retained_100"} or p is None or k not in co["claude"] or k not in co["gpt"]: continue
    unit = (p.get("unit") or "").strip(); mult = next((m for u, m in UNIT.items() if unit.startswith(u)), None)
    nc, sv = p.get("new_company") or {}, p.get("surviving_company_after_division") or {}
    rows.append({"rcept_no": k, "period_src": "2001-2016", "y": int(r["outcome"] in DISPOSED), "division_year": r["division_year"], "kosdaq": int(r.get("corp_cls") == "K"), "label_source": r.get("label_source"),
                 "newco_assets": num(nc.get("total_assets"), mult), "newco_debt": num(nc.get("total_debt"), mult), "newco_sales": num(nc.get("recent_year_sales"), mult),
                 "parent_after_assets": num(sv.get("total_assets"), mult), "parent_after_debt": num(sv.get("total_debt"), mult),
                 "relisting_yes": int(p.get("relisting_or_listing_application") == "yes"), "put_option_yes": {"yes": 1, "no": 0}.get(p.get("put_option_or_similar_contract")),
                 "p_claude": co["claude"][k], "p_gpt": co["gpt"][k]})
df = pd.DataFrame(rows)
def safe(a, b): return (a / b) if (a is not None and b not in (None, 0) and not (isinstance(a, float) and np.isnan(a)) and not (isinstance(b, float) and np.isnan(b))) else None
df["log_newco_assets"] = df.newco_assets.apply(lambda v: np.log1p(v) if v and v > 0 else None)
df["newco_leverage"] = [safe(a, b) for a, b in zip(df.newco_debt, df.newco_assets)]
df["newco_sales_to_assets"] = [safe(a, b) for a, b in zip(df.newco_sales, df.newco_assets)]
df["relative_size"] = [safe(a, (a or 0) + (b or 0)) if a and b else None for a, b in zip(df.newco_assets, df.parent_after_assets)]
df["parent_after_leverage"] = [safe(a, b) for a, b in zip(df.parent_after_debt, df.parent_after_assets)]
df["p_llm"] = (df.p_claude + df.p_gpt) / 2
FIN = ["kosdaq", "log_newco_assets", "newco_leverage", "newco_sales_to_assets", "relative_size", "parent_after_leverage", "relisting_yes", "put_option_yes"]


def design(d, cols):
    X = d[cols].copy().astype(float)
    for c in cols:
        if X[c].isna().any(): X[c + "_miss"] = X[c].isna().astype(int); X[c] = X[c].fillna(X[c].median())
    X = X.loc[:, X.nunique(dropna=False) > 1]
    return X.clip(lower=X.quantile(0.01), upper=X.quantile(0.99), axis=1)


def cv_auc(Xm, y, n_rep=50, seed=0):
    oof = np.zeros((n_rep, len(y))); rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=n_rep, random_state=seed)
    for i, (tr, te) in enumerate(rskf.split(Xm, y)):
        mdl = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)).fit(Xm.iloc[tr], y[tr]); oof[i // 5, te] = mdl.predict_proba(Xm.iloc[te])[:, 1]
    avg = oof.mean(axis=0)
    # AUC of the repeat-averaged out-of-fold predictions: the same quantity the paired bootstrap uses (the mean of per-repeat AUCs
    # differs slightly and put point estimates outside their own CIs in small panels; changed 2026-10-19)
    return float(roc_auc_score(y, avg)), avg


def panel(d, name):
    y = d.y.values; X = design(d, FIN); out = {"n": int(len(d)), "disposed_share": round(float(y.mean()), 3), "n_features": int(X.shape[1])}
    auc_fin, oof_fin = cv_auc(X, y); out["financial_cv_auc"] = round(auc_fin, 3)
    for m in ("p_claude", "p_gpt", "p_llm"): out[f"auc_{m}"] = round(float(roc_auc_score(y, d[m])), 3)
    Xc = X.copy(); Xc["logit_llm"] = np.log(d.p_llm.clip(0.01, 0.99) / (1 - d.p_llm.clip(0.01, 0.99))); auc_c, oof_c = cv_auc(Xc, y); out["combined_cv_auc"] = round(auc_c, 3)
    rng = np.random.default_rng(1); d1, d2 = [], []
    for _ in range(2000):
        idx = rng.integers(0, len(y), len(y))
        if len(set(y[idx])) < 2: continue
        d1.append(roc_auc_score(y[idx], d.p_llm.values[idx]) - roc_auc_score(y[idx], oof_fin[idx])); d2.append(roc_auc_score(y[idx], oof_c[idx]) - roc_auc_score(y[idx], oof_fin[idx]))
    out["delta_llm_minus_financial"] = {"point": round(float(roc_auc_score(y, d.p_llm) - auc_fin), 3), "ci95": [round(float(np.percentile(d1, 2.5)), 3), round(float(np.percentile(d1, 97.5)), 3)]}
    out["delta_combined_minus_financial"] = {"point": round(auc_c - auc_fin, 3), "ci95": [round(float(np.percentile(d2, 2.5)), 3), round(float(np.percentile(d2, 97.5)), 3)]}
    print(f"[{name}] n={out['n']} disposed={out['disposed_share']} fin={out['financial_cv_auc']} claude={out['auc_p_claude']} gpt={out['auc_p_gpt']} llm={out['auc_p_llm']} comb={out['combined_cv_auc']} dLLM={out['delta_llm_minus_financial']['point']} {out['delta_llm_minus_financial']['ci95']} dComb={out['delta_combined_minus_financial']['point']} {out['delta_combined_minus_financial']['ci95']}", flush=True)
    return out, X


res = {"n_rows": int(len(df)), "by_source": df.period_src.value_counts().to_dict(), "feature_coverage": {c: int(df[c].notna().sum()) for c in FIN},
       "disposed_share_by_period": {k: {"n": int(len(g)), "share": round(float(g.y.mean()), 3)} for k, g in df.groupby(pd.cut(df.division_year, [2000, 2008, 2016, 2026], labels=["2001-2008", "2009-2016", "2017-2025"]), observed=True)}}
print("rows:", res["n_rows"], res["by_source"], "| coverage:", res["feature_coverage"], "| disposed by period:", res["disposed_share_by_period"])
res["pooled"], Xp = panel(df, "pooled 2001-2026")
for k, g in df.groupby(pd.cut(df.division_year, [2000, 2008, 2016, 2026], labels=["2001-2008", "2009-2016", "2017-2025"]), observed=True):
    if len(g) >= 40 and g.y.nunique() == 2: res[f"period_{k}"], _ = panel(g.reset_index(drop=True), f"period {k}")
res["mature_le2021"], _ = panel(df[df.division_year <= 2021].reset_index(drop=True), "mature <= 2021")
y = df.y.values; tr, te = df.division_year <= 2016, df.division_year >= 2017
mdl = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)).fit(Xp[tr], y[tr])
res["temporal_train_le2016_test_ge2017"] = {"train_n": int(tr.sum()), "test_n": int(te.sum()), "financial_auc_test": round(float(roc_auc_score(y[te], mdl.predict_proba(Xp[te])[:, 1])), 3), "llm_auc_test": round(float(roc_auc_score(y[te], df.p_llm[te])), 3)}
print("temporal:", res["temporal_train_le2016_test_ge2017"])
stamp = dt.date.today().strftime("%Y%m%d"); json.dump(res, open(f"{P}/results/gate1_pooled_{stamp}.json", "w"), ensure_ascii=False, indent=1); print(f"saved results/gate1_pooled_{stamp}.json")
