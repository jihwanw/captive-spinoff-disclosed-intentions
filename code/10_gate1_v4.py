#!/usr/bin/env python3
"""10_gate1_v4.py — Gate 1 (does the filing text add information beyond the filing's numbers?) on the v4 labels.

Differences from 06/07: labels from carveout_disposal_tracking_v4.json (v3 tracker + annual-report evidence, 09c);
LLM score = mean of the two identified runs per model when both exist (08 showed test-retest r = 0.96-0.99), else the
single run; the financial baseline EXCLUDES the board year by default (07: the year proxies label maturity); the same
CV protocol (RepeatedStratifiedKFold 5x50, seed 0; StandardScaler + LogisticRegression C=1; median imputation with
missing indicators; 1-99% clipping) and paired bootstrap (2000 draws, seed 1).
Panels: A full clean sample; B mature sample (division_year <= 2021; retained events observed >= 3 FY after division or
labelled from the annual reports, which cover FY2025); C temporal split (train <= 2020, test >= 2021); D by label source
(v3 tracker vs annual-report LLM); E anonymized-text AUC (memorization check) where available; F with-year variant for reference.
Output: results/gate1_v4_<date>.json
"""
import json, glob, os, datetime as dt, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.metrics import roc_auc_score

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
feat = {f["rcept_no"]: f for f in json.load(open(f"{P}/data/processed/baseline_features.json", encoding="utf-8"))}
v4 = {r["rcept_no"]: r for r in json.load(open(f"{P}/data/processed/carveout_disposal_tracking_v4.json", encoding="utf-8"))}
DISPOSED = {"ipo_listed", "majority_disposed", "partial_sale"}
lab = {k: 1 for k, r in v4.items() if r["outcome"] in DISPOSED}; lab.update({k: 0 for k, r in v4.items() if r["outcome"] == "retained_100"})


def load_scores(pattern):
    d = {}
    for f in glob.glob(f"{P}/results/llm_judge/{pattern}"):
        for l in open(f, encoding="utf-8"):
            r = json.loads(l); p = (r.get("parsed") or {}).get("p_disposal")
            if isinstance(p, (int, float)): d.setdefault(r["rcept_no"], []).append(float(p) / 100)
    return {k: float(np.mean(v)) for k, v in d.items()}


ident = {"claude": load_scores("anthropic__identified*.jsonl"), "gpt": load_scores("openai__identified*.jsonl")}
anon = {"claude": load_scores("anthropic__anonymized*.jsonl"), "gpt": load_scores("openai__anonymized*.jsonl")}


def follow_up_years(r):
    yrs = [int(pc["last_period"][:4]) - r["division_year"] for pc in r.get("per_new_company", []) if pc.get("last_period")]
    return max(yrs) if yrs else None


rows = []
for k, y in lab.items():
    f = feat.get(k)
    if not f or k not in ident["claude"] or k not in ident["gpt"]: continue
    def safe(a, b): return (a / b) if (a is not None and b not in (None, 0)) else None
    r = v4[k]
    rows.append({"rcept_no": k, "y": y, "year": f["board_year"], "division_year": r["division_year"], "label_source": r["label_source"],
                 "follow_up_years": follow_up_years(r), "kosdaq": int(f["corp_cls"] == "K"),
                 "log_newco_assets": np.log1p(f["newco_assets"]) if f["newco_assets"] else None,
                 "newco_leverage": safe(f["newco_debt"], f["newco_assets"]), "newco_sales_to_assets": safe(f["newco_sales"], f["newco_assets"]),
                 "relative_size": safe(f["newco_assets"], (f["newco_assets"] or 0) + (f["parent_after_assets"] or 0)) if f["newco_assets"] and f["parent_after_assets"] else None,
                 "parent_after_leverage": safe(f["parent_after_debt"], f["parent_after_assets"]),
                 "log_parent_assets": np.log1p(f["parent_total_assets"]) if f["parent_total_assets"] else None,
                 "parent_roa": safe(f["parent_net_income"], f["parent_total_assets"]), "parent_op_margin": safe(f["parent_operating_income"], f["parent_sales"]),
                 "parent_leverage": safe(f["parent_total_debt"], f["parent_total_assets"]), "parent_current_ratio": safe(f["parent_current_assets"], f["parent_current_liabilities"]),
                 "relisting_yes": int((f.get("relisting_application") or "").strip().startswith("예")), "put_option_yes": int((f.get("put_option_contract") or "").strip().startswith("예")),
                 "sec_reg_yes": int((f.get("securities_registration") or "").strip().startswith("예")),
                 "p_claude": ident["claude"][k], "p_gpt": ident["gpt"][k], "p_llm": (ident["claude"][k] + ident["gpt"][k]) / 2,
                 "p_claude_anon": anon["claude"].get(k), "p_gpt_anon": anon["gpt"].get(k)})
df = pd.DataFrame(rows); df["p_llm_anon"] = df[["p_claude_anon", "p_gpt_anon"]].mean(axis=1, skipna=False)
FIN = ["kosdaq", "log_newco_assets", "newco_leverage", "newco_sales_to_assets", "relative_size", "parent_after_leverage", "log_parent_assets", "parent_roa",
       "parent_op_margin", "parent_leverage", "parent_current_ratio", "relisting_yes", "put_option_yes", "sec_reg_yes"]


def design(d, cols):
    X = d[cols].copy()
    for c in cols:
        if X[c].isna().any(): X[c + "_miss"] = X[c].isna().astype(int); X[c] = X[c].fillna(X[c].median())
    X = X.loc[:, X.nunique(dropna=False) > 1]
    return X.clip(lower=X.quantile(0.01), upper=X.quantile(0.99), axis=1)


def cv_auc(Xm, y, n_rep=50, seed=0):
    oof = np.zeros((n_rep, len(y))); rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=n_rep, random_state=seed)
    for i, (tr, te) in enumerate(rskf.split(Xm, y)):
        mdl = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)); mdl.fit(Xm.iloc[tr], y[tr]); oof[i // 5, te] = mdl.predict_proba(Xm.iloc[te])[:, 1]
    aucs = [roc_auc_score(y, oof[r]) for r in range(n_rep)]
    avg = oof.mean(axis=0)
    # point estimate = AUC of the repeat-averaged OOF predictions (consistent with the paired bootstrap); sd = spread of per-repeat AUCs
    return float(roc_auc_score(y, avg)), float(np.std(aucs)), avg


def panel(d, cols, name):
    y = d["y"].values; X = design(d, cols)
    out = {"n": int(len(d)), "disposed_share": round(float(y.mean()), 3), "n_features": int(X.shape[1]), "year_included": "year" in cols}
    auc_fin, sd_fin, oof_fin = cv_auc(X, y); out["financial_cv_auc"] = {"mean": round(auc_fin, 3), "sd_over_repeats": round(sd_fin, 3)}
    for m in ("p_claude", "p_gpt", "p_llm"): out[f"auc_{m}"] = round(float(roc_auc_score(y, d[m])), 3)
    Xc = X.copy(); Xc["logit_llm"] = np.log(d["p_llm"].clip(0.01, 0.99) / (1 - d["p_llm"].clip(0.01, 0.99)))
    auc_comb, sd_comb, oof_comb = cv_auc(Xc, y); out["combined_cv_auc"] = {"mean": round(auc_comb, 3), "sd_over_repeats": round(sd_comb, 3)}
    rng = np.random.default_rng(1); d1, d2 = [], []
    for _ in range(2000):
        idx = rng.integers(0, len(y), len(y))
        if len(set(y[idx])) < 2: continue
        d1.append(roc_auc_score(y[idx], d["p_llm"].values[idx]) - roc_auc_score(y[idx], oof_fin[idx])); d2.append(roc_auc_score(y[idx], oof_comb[idx]) - roc_auc_score(y[idx], oof_fin[idx]))
    out["delta_llm_minus_financial"] = {"point": round(float(roc_auc_score(y, d["p_llm"]) - auc_fin), 3), "ci95": [round(float(np.percentile(d1, 2.5)), 3), round(float(np.percentile(d1, 97.5)), 3)]}
    out["delta_combined_minus_financial"] = {"point": round(auc_comb - auc_fin, 3), "ci95": [round(float(np.percentile(d2, 2.5)), 3), round(float(np.percentile(d2, 97.5)), 3)]}
    uni = {c: round(float(max(roc_auc_score(y, X[c]), 1 - roc_auc_score(y, X[c]))), 3) for c in cols if c in X and X[c].nunique() > 1}
    out["univariate_auc_abs_top6"] = dict(sorted(uni.items(), key=lambda kv: -kv[1])[:6])
    # in-sample logistic coefficients (direction only) for the financial model
    mdl = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)).fit(X, y)
    out["financial_coef_std"] = {c: round(float(b), 3) for c, b in sorted(zip(X.columns, mdl[-1].coef_[0]), key=lambda kv: -abs(kv[1]))[:8]}
    print(f"[{name}] n={out['n']} disposed={out['disposed_share']} fin={out['financial_cv_auc']['mean']} claude={out['auc_p_claude']} gpt={out['auc_p_gpt']} llm={out['auc_p_llm']} comb={out['combined_cv_auc']['mean']} "
          f"dLLM={out['delta_llm_minus_financial']['point']} {out['delta_llm_minus_financial']['ci95']} dComb={out['delta_combined_minus_financial']['point']} {out['delta_combined_minus_financial']['ci95']}", flush=True)
    return out, X


res = {"label_version": "v4 (09c)", "llm_score": "mean of identified runs per model, then two-model average", "n_rows": int(len(df)),
       "label_source_counts": df.label_source.value_counts().to_dict(),
       "disposed_share_by_division_year": {int(k): {"n": int(v["size"]), "share": round(float(v["mean"]), 3)} for k, v in df.groupby("division_year")["y"].agg(["size", "mean"]).iterrows()},
       "auc_year_alone": round(float(max(roc_auc_score(df.y, df.year), 1 - roc_auc_score(df.y, df.year))), 3)}
print("rows:", len(df), "| label sources:", res["label_source_counts"], "| disposed by year:", {k: (v["n"], v["share"]) for k, v in res["disposed_share_by_division_year"].items()}, "| AUC(year):", res["auc_year_alone"])
res["A_full_no_year"], X_A = panel(df, FIN, "A full, no year")
mature = df[(df.division_year <= 2021) & ((df.y == 1) | (df.follow_up_years.fillna(-1) >= 3) | (df.label_source == "annual_report_llm"))].reset_index(drop=True)
res["mature_rule"] = "division_year <= 2021 and (disposed or retained observed >= 3 FY after division in 타법인출자현황 or labelled from annual reports through FY2025)"
res["B_mature_no_year"], _ = panel(mature, FIN, "B mature, no year")
y = df.y.values; tr, te = df.year <= 2020, df.year >= 2021
mdl = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)).fit(X_A[tr], y[tr])
res["C_temporal_split_no_year"] = {"train_n": int(tr.sum()), "test_n": int(te.sum()), "test_disposed_share": round(float(y[te].mean()), 3),
                                   "financial_auc_test": round(float(roc_auc_score(y[te], mdl.predict_proba(X_A[te])[:, 1])), 3), "llm_auc_test": round(float(roc_auc_score(y[te], df.p_llm[te])), 3),
                                   "claude_auc_test": round(float(roc_auc_score(y[te], df.p_claude[te])), 3), "gpt_auc_test": round(float(roc_auc_score(y[te], df.p_gpt[te])), 3)}
print("C temporal:", res["C_temporal_split_no_year"])
res["D_by_label_source"] = {}
for srcname, g in df.groupby("label_source"):
    if g.y.nunique() == 2 and len(g) >= 20:
        res["D_by_label_source"][srcname] = {"n": int(len(g)), "disposed_share": round(float(g.y.mean()), 3), "auc_p_llm": round(float(roc_auc_score(g.y, g.p_llm)), 3),
                                             "auc_p_claude": round(float(roc_auc_score(g.y, g.p_claude)), 3), "auc_p_gpt": round(float(roc_auc_score(g.y, g.p_gpt)), 3)}
print("D by label source:", res["D_by_label_source"])
an = df.dropna(subset=["p_llm_anon"])
if len(an) >= 30 and an.y.nunique() == 2:
    res["E_anonymized"] = {"n": int(len(an)), "auc_identified_llm": round(float(roc_auc_score(an.y, an.p_llm)), 3), "auc_anonymized_llm": round(float(roc_auc_score(an.y, an.p_llm_anon)), 3),
                           "auc_identified_claude": round(float(roc_auc_score(an.y, an.p_claude)), 3), "auc_anonymized_claude": round(float(roc_auc_score(an.y, an.p_claude_anon)), 3),
                           "auc_identified_gpt": round(float(roc_auc_score(an.y, an.p_gpt)), 3), "auc_anonymized_gpt": round(float(roc_auc_score(an.y, an.p_gpt_anon)), 3),
                           "corr_identified_vs_anonymized_llm": round(float(np.corrcoef(an.p_llm, an.p_llm_anon)[0, 1]), 3)}
    print("E anonymized:", res["E_anonymized"])
res["F_full_with_year"], _ = panel(df, FIN + ["year"], "F full, with year (reference)")
stamp = dt.date.today().strftime("%Y%m%d"); json.dump(res, open(f"{P}/results/gate1_v4_{stamp}.json", "w"), ensure_ascii=False, indent=1)
print(f"saved results/gate1_v4_{stamp}.json")
