#!/usr/bin/env python3
"""06_baseline_vs_llm.py — Gate 1: does the filing text add information beyond the numbers in the filing?

Compares, on the same clean-labelled carve-outs (v3 labels: disposed = ipo/majority/partial; retained = retained_100):
  (a) financial-only logistic regression (numbers from the filing's structured fields + parent prior-FY accounts),
      out-of-fold AUC from repeated stratified 5-fold CV and from a temporal split (train <= 2020, test >= 2021);
  (b) LLM probabilities (zero-shot, no training) — Claude, GPT, and their average;
  (c) combined model: financial features + logit(LLM average) — CV AUC increment.
Paired bootstrap CIs for AUC differences. Output: results/gate1_baseline_vs_llm_<date>.json
"""
import json, glob, os, datetime as dt, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.metrics import roc_auc_score

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
feat = {f["rcept_no"]: f for f in json.load(open(f"{P}/data/processed/baseline_features.json", encoding="utf-8"))}
v3 = {r["rcept_no"]: r for r in json.load(open(f"{P}/data/processed/carveout_disposal_tracking_v3.json", encoding="utf-8"))}
lab = {k: 1 for k, r in v3.items() if r["outcome"] in ("ipo_listed", "majority_disposed", "partial_sale")}
lab.update({k: 0 for k, r in v3.items() if r["outcome"] == "retained_100"})
llm = {}
for f in glob.glob(f"{P}/results/llm_judge/*__identified.jsonl"):
    m = "claude" if "anthropic" in f else "gpt"
    for l in open(f, encoding="utf-8"):
        r = json.loads(l); p = (r.get("parsed") or {}).get("p_disposal")
        if isinstance(p, (int, float)): llm.setdefault(r["rcept_no"], {})[m] = float(p) / 100

rows = []
for k, y in lab.items():
    f = feat.get(k); 
    if not f or k not in llm or len(llm[k]) < 2: continue
    def safe(a, b): return (a / b) if (a is not None and b not in (None, 0)) else None
    rows.append({"rcept_no": k, "y": y, "year": f["board_year"], "kosdaq": int(f["corp_cls"] == "K"),
                 "log_newco_assets": np.log1p(f["newco_assets"]) if f["newco_assets"] else None,
                 "newco_leverage": safe(f["newco_debt"], f["newco_assets"]), "newco_sales_to_assets": safe(f["newco_sales"], f["newco_assets"]),
                 "relative_size": safe(f["newco_assets"], (f["newco_assets"] or 0) + (f["parent_after_assets"] or 0)) if f["newco_assets"] and f["parent_after_assets"] else None,
                 "parent_after_leverage": safe(f["parent_after_debt"], f["parent_after_assets"]),
                 "log_parent_assets": np.log1p(f["parent_total_assets"]) if f["parent_total_assets"] else None,
                 "parent_roa": safe(f["parent_net_income"], f["parent_total_assets"]), "parent_op_margin": safe(f["parent_operating_income"], f["parent_sales"]),
                 "parent_leverage": safe(f["parent_total_debt"], f["parent_total_assets"]), "parent_current_ratio": safe(f["parent_current_assets"], f["parent_current_liabilities"]),
                 "relisting_yes": int((f.get("relisting_application") or "").strip().startswith("예")), "put_option_yes": int((f.get("put_option_contract") or "").strip().startswith("예")),
                 "sec_reg_yes": int((f.get("securities_registration") or "").strip().startswith("예")),
                 "p_claude": llm[k]["claude"], "p_gpt": llm[k]["gpt"], "p_llm": (llm[k]["claude"] + llm[k]["gpt"]) / 2})
df = pd.DataFrame(rows); y = df["y"].values
FIN = ["kosdaq", "log_newco_assets", "newco_leverage", "newco_sales_to_assets", "relative_size", "parent_after_leverage", "log_parent_assets", "parent_roa", "parent_op_margin", "parent_leverage", "parent_current_ratio", "relisting_yes", "put_option_yes", "sec_reg_yes", "year"]
X = df[FIN].copy()
for c in FIN:  # median imputation + missing indicator
    if X[c].isna().any(): X[c + "_miss"] = X[c].isna().astype(int); X[c] = X[c].fillna(X[c].median())
X = X.clip(lower=X.quantile(0.01), upper=X.quantile(0.99), axis=1)
print(f"n={len(df)} disposed={y.mean():.2f} features={X.shape[1]}")


def cv_auc(Xm, y, n_rep=50, seed=0):
    oof = np.zeros((n_rep, len(y))); rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=n_rep, random_state=seed)
    for i, (tr, te) in enumerate(rskf.split(Xm, y)):
        mdl = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)); mdl.fit(Xm.iloc[tr], y[tr]); oof[i // 5, te] = mdl.predict_proba(Xm.iloc[te])[:, 1]
    aucs = [roc_auc_score(y, oof[r]) for r in range(n_rep)]
    return float(np.mean(aucs)), float(np.std(aucs)), oof.mean(axis=0)


res = {"n": int(len(df)), "disposed_share": float(y.mean()), "features": FIN}
auc_fin, sd_fin, oof_fin = cv_auc(X, y); res["financial_cv_auc"] = {"mean": round(auc_fin, 3), "sd_over_repeats": round(sd_fin, 3)}
for m in ("p_claude", "p_gpt", "p_llm"): res[f"auc_{m}"] = round(float(roc_auc_score(y, df[m])), 3)
Xc = X.copy(); Xc["logit_llm"] = np.log(df["p_llm"].clip(0.01, 0.99) / (1 - df["p_llm"].clip(0.01, 0.99)))
auc_comb, sd_comb, oof_comb = cv_auc(Xc, y); res["combined_cv_auc"] = {"mean": round(auc_comb, 3), "sd_over_repeats": round(sd_comb, 3)}
# paired bootstrap: LLM avg vs financial OOF, combined vs financial
rng = np.random.default_rng(1); d1, d2 = [], []
for _ in range(2000):
    idx = rng.integers(0, len(y), len(y))
    if len(set(y[idx])) < 2: continue
    d1.append(roc_auc_score(y[idx], df["p_llm"].values[idx]) - roc_auc_score(y[idx], oof_fin[idx])); d2.append(roc_auc_score(y[idx], oof_comb[idx]) - roc_auc_score(y[idx], oof_fin[idx]))
res["delta_llm_minus_financial"] = {"point": round(float(roc_auc_score(y, df["p_llm"]) - auc_fin), 3), "ci95": [round(float(np.percentile(d1, 2.5)), 3), round(float(np.percentile(d1, 97.5)), 3)]}
res["delta_combined_minus_financial"] = {"point": round(auc_comb - auc_fin, 3), "ci95": [round(float(np.percentile(d2, 2.5)), 3), round(float(np.percentile(d2, 97.5)), 3)]}
# temporal split
tr, te = df["year"] <= 2020, df["year"] >= 2021
if te.sum() >= 15 and len(set(y[te])) == 2:
    mdl = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)).fit(X[tr], y[tr])
    res["temporal_split"] = {"train_n": int(tr.sum()), "test_n": int(te.sum()), "financial_auc_test": round(float(roc_auc_score(y[te], mdl.predict_proba(X[te])[:, 1])), 3), "llm_auc_test": round(float(roc_auc_score(y[te], df["p_llm"][te])), 3)}
# univariate AUCs and in-sample coefficients (direction) for transparency
uni = {}
for c in FIN:
    if X[c].nunique() > 1: uni[c] = round(float(max(roc_auc_score(y, X[c]), 1 - roc_auc_score(y, X[c]))), 3)
res["univariate_auc_abs"] = dict(sorted(uni.items(), key=lambda kv: -kv[1]))
res["corr_llm_with_features"] = {c: round(float(np.corrcoef(df["p_llm"], X[c])[0, 1]), 2) for c in FIN if X[c].nunique() > 1}
stamp = dt.date.today().strftime("%Y%m%d"); json.dump(res, open(f"{P}/results/gate1_baseline_vs_llm_{stamp}.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in res.items() if k not in ("features", "univariate_auc_abs", "corr_llm_with_features")}, ensure_ascii=False, indent=1))
print("univariate |AUC| top:", list(res["univariate_auc_abs"].items())[:6])
