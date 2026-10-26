#!/usr/bin/env python3
"""07_gate1_maturity_check.py — Does the Gate-1 result survive removing the year effect and label immaturity?

Motivation (2026-10-17): in 06_baseline_vs_llm.py the strongest univariate predictor of the disposal label was the
board year (|AUC| 0.688). The label (disposed vs retained_100) is observed over a follow-up window that ends at FY2025
(02b_track_carveout_disposal_v3.py, LAST_FY = 2025), so recent events have had less time to be disposed: "retained_100"
for a 2024 event means "not yet disposed after one year", not "retained". A model that uses the year (or anything
correlated with it) partly predicts label maturity, not disposal.

Same data assembly, features, CV protocol (RepeatedStratifiedKFold 5 x 50, seed 0; StandardScaler + LogisticRegression
C=1; median imputation with missing indicators; 1-99% clipping) and paired bootstrap (2000 draws, seed 1) as 06.
Variants:
  V0  as in 06 (features include year)                                  - reference
  V1  year removed from the financial feature set                        - full sample
  V2  V1 on the maturity-restricted sample: division_year <= 2021 and, for retained_100 events, the matched new company
      observed at >= 3 fiscal years after the division (follow_up_years >= 3)
  V3  V2 with year included                                              - how much year still adds within mature events
  temporal split (train <= 2020 / test >= 2021) for V1
Output: results/gate1_maturity_check_<date>.json
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


def follow_up_years(r):
    """Years between the division year and the last fiscal period in which the matched new company was observed
    in the parent's holdings (per_new_company[].last_period, e.g. '2025FY' or '2023H1'); None if never observed."""
    yrs = [int(pc["last_period"][:4]) - r["division_year"] for pc in r.get("per_new_company", []) if pc.get("last_period")]
    return max(yrs) if yrs else None


rows = []
for k, y in lab.items():
    f = feat.get(k)
    if not f or k not in llm or len(llm[k]) < 2: continue
    def safe(a, b): return (a / b) if (a is not None and b not in (None, 0)) else None
    rows.append({"rcept_no": k, "y": y, "year": f["board_year"], "division_year": v3[k]["division_year"], "follow_up_years": follow_up_years(v3[k]),
                 "kosdaq": int(f["corp_cls"] == "K"),
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
df_all = pd.DataFrame(rows)
FIN_ALL = ["kosdaq", "log_newco_assets", "newco_leverage", "newco_sales_to_assets", "relative_size", "parent_after_leverage", "log_parent_assets", "parent_roa",
           "parent_op_margin", "parent_leverage", "parent_current_ratio", "relisting_yes", "put_option_yes", "sec_reg_yes", "year"]
FIN_NOYEAR = [c for c in FIN_ALL if c != "year"]


def design(df, cols):
    X = df[cols].copy()
    for c in cols:
        if X[c].isna().any(): X[c + "_miss"] = X[c].isna().astype(int); X[c] = X[c].fillna(X[c].median())
    X = X.loc[:, X.nunique(dropna=False) > 1]            # drop constant columns (an all-NaN feature would otherwise stay NaN)
    return X.clip(lower=X.quantile(0.01), upper=X.quantile(0.99), axis=1)


def cv_auc(Xm, y, n_rep=50, seed=0):
    oof = np.zeros((n_rep, len(y))); rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=n_rep, random_state=seed)
    for i, (tr, te) in enumerate(rskf.split(Xm, y)):
        mdl = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)); mdl.fit(Xm.iloc[tr], y[tr]); oof[i // 5, te] = mdl.predict_proba(Xm.iloc[te])[:, 1]
    aucs = [roc_auc_score(y, oof[r]) for r in range(n_rep)]
    return float(np.mean(aucs)), float(np.std(aucs)), oof.mean(axis=0)


def evaluate(df, cols, name):
    y = df["y"].values; X = design(df, cols)
    out = {"n": int(len(df)), "disposed_share": round(float(y.mean()), 3), "n_features": int(X.shape[1]), "year_included": "year" in cols}
    auc_fin, sd_fin, oof_fin = cv_auc(X, y); out["financial_cv_auc"] = {"mean": round(auc_fin, 3), "sd_over_repeats": round(sd_fin, 3)}
    for m in ("p_claude", "p_gpt", "p_llm"): out[f"auc_{m}"] = round(float(roc_auc_score(y, df[m])), 3)
    Xc = X.copy(); Xc["logit_llm"] = np.log(df["p_llm"].clip(0.01, 0.99) / (1 - df["p_llm"].clip(0.01, 0.99)))
    auc_comb, sd_comb, oof_comb = cv_auc(Xc, y); out["combined_cv_auc"] = {"mean": round(auc_comb, 3), "sd_over_repeats": round(sd_comb, 3)}
    rng = np.random.default_rng(1); d1, d2 = [], []
    for _ in range(2000):
        idx = rng.integers(0, len(y), len(y))
        if len(set(y[idx])) < 2: continue
        d1.append(roc_auc_score(y[idx], df["p_llm"].values[idx]) - roc_auc_score(y[idx], oof_fin[idx])); d2.append(roc_auc_score(y[idx], oof_comb[idx]) - roc_auc_score(y[idx], oof_fin[idx]))
    out["delta_llm_minus_financial"] = {"point": round(float(roc_auc_score(y, df["p_llm"]) - auc_fin), 3), "ci95": [round(float(np.percentile(d1, 2.5)), 3), round(float(np.percentile(d1, 97.5)), 3)]}
    out["delta_combined_minus_financial"] = {"point": round(auc_comb - auc_fin, 3), "ci95": [round(float(np.percentile(d2, 2.5)), 3), round(float(np.percentile(d2, 97.5)), 3)]}
    uni = {}
    for c in cols:
        if c in X and X[c].nunique() > 1: uni[c] = round(float(max(roc_auc_score(y, X[c]), 1 - roc_auc_score(y, X[c]))), 3)
    out["univariate_auc_abs_top6"] = dict(sorted(uni.items(), key=lambda kv: -kv[1])[:6])
    print(f"[{name}] n={out['n']} disposed={out['disposed_share']} fin={out['financial_cv_auc']['mean']} llm={out['auc_p_llm']} comb={out['combined_cv_auc']['mean']} "
          f"dLLM={out['delta_llm_minus_financial']['point']} {out['delta_llm_minus_financial']['ci95']} dComb={out['delta_combined_minus_financial']['point']} {out['delta_combined_minus_financial']['ci95']}", flush=True)
    return out, X


res = {"sample_n": int(len(df_all)), "note": "same assembly/protocol as 06_baseline_vs_llm.py; see module docstring"}
# --- diagnostics: label maturity ---------------------------------------------------------------------------
by_year = df_all.groupby("division_year").agg(n=("y", "size"), disposed_share=("y", "mean")).round(3)
res["disposed_share_by_division_year"] = {int(k): {"n": int(v["n"]), "disposed_share": float(v["disposed_share"])} for k, v in by_year.iterrows()}
fu = df_all.dropna(subset=["follow_up_years"])
res["follow_up_years_by_label"] = {str(int(k)): {"n": int(v["n"]), "median": float(v["median"]), "min": float(v["min"]), "max": float(v["max"])}
                                   for k, v in fu.groupby("y")["follow_up_years"].agg(["size", "median", "min", "max"]).rename(columns={"size": "n"}).iterrows()}
res["auc_year_alone"] = round(float(max(roc_auc_score(df_all.y, df_all.year), 1 - roc_auc_score(df_all.y, df_all.year))), 3)
res["auc_llm_within_year_strata"] = {}
for yr, g in df_all.groupby("division_year"):
    if g.y.nunique() == 2 and len(g) >= 8: res["auc_llm_within_year_strata"][int(yr)] = {"n": int(len(g)), "auc_p_llm": round(float(roc_auc_score(g.y, g.p_llm)), 3)}
print("disposed share by division year:", {k: (v["n"], v["disposed_share"]) for k, v in res["disposed_share_by_division_year"].items()})
print("follow-up years by label:", res["follow_up_years_by_label"], "| AUC of year alone:", res["auc_year_alone"])

# --- variants ---------------------------------------------------------------------------------------------------
res["V0_as_in_06"], _ = evaluate(df_all, FIN_ALL, "V0 as in 06 (with year)")
res["V1_no_year"], X1 = evaluate(df_all, FIN_NOYEAR, "V1 no year, full sample")
mature = df_all[(df_all.division_year <= 2021) & ((df_all.y == 1) | (df_all.follow_up_years.fillna(-1) >= 3))].reset_index(drop=True)
res["mature_sample_rule"] = "division_year <= 2021 and (disposed or retained_100 observed >= 3 fiscal years after division)"
res["V2_no_year_mature"], _ = evaluate(mature, FIN_NOYEAR, "V2 no year, mature sample")
res["V3_with_year_mature"], _ = evaluate(mature, FIN_ALL, "V3 with year, mature sample")
# temporal split for V1 (train <= 2020, test >= 2021), year not a feature
y_all = df_all["y"].values; tr, te = df_all["year"] <= 2020, df_all["year"] >= 2021
if te.sum() >= 15 and len(set(y_all[te])) == 2:
    mdl = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)).fit(X1[tr], y_all[tr])
    res["V1_temporal_split"] = {"train_n": int(tr.sum()), "test_n": int(te.sum()), "financial_auc_test": round(float(roc_auc_score(y_all[te], mdl.predict_proba(X1[te])[:, 1])), 3),
                                "llm_auc_test": round(float(roc_auc_score(y_all[te], df_all["p_llm"][te])), 3)}
    print("V1 temporal split:", res["V1_temporal_split"])
stamp = dt.date.today().strftime("%Y%m%d")
json.dump(res, open(f"{P}/results/gate1_maturity_check_{stamp}.json", "w"), ensure_ascii=False, indent=1)
print(f"saved results/gate1_maturity_check_{stamp}.json")
