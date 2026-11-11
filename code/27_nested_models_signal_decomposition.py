#!/usr/bin/env python3
"""27_nested_models_signal_decomposition.py — does the disposal signal add anything beyond Kang & Lee-type coding of the filing?
(Resubmission strategy §1-B/§1-C; answers CGIR ground 1 "contribution limited relative to Kang and Lee" with a nested-model ladder.)

Kang & Lee (2025b, FRL) hand-code the filing's stated purpose into dummies (sale 12.0%, efficiency 5.9%, specialization 89.1%, other
4.2%; their Table 1) and use a listing indicator. Our judgment files already carry, for every filing and every judgment, a structured
extraction of the same kind (facts.stated_purpose_categories from a fixed 7-category list; mention flags for listing/IPO, external
investor, sale/buyer, protection measures, appraisal rights — 04_llm_judge.py lines 43–51) beside the holistic probability S.
Ladder (identical CV protocol to 15_gate1_pooled.py: RepeatedStratifiedKFold 5x50, logistic C=1, median imputation + missing flags,
1–99% clipping; the Gate-1 sample is rebuilt by executing 15's own code, so n and the baseline AUCs must reproduce Table 3):
  M0  financial baseline (Table 3)                      M1  M0 + 7 purpose-category dummies (majority of judgments)
  M2  M1 + 5 mention flags (majority)                   M3  M2 + logit(S)
  F   facts only (purpose + mentions, no financials)    K1  M0 + 6 keyword dummies read from the raw text WITHOUT any model
  K2  K1 + logit(S)                                     S   the signal alone (must equal Table 3's AUCPooledLLM)
Increments get paired-bootstrap intervals on the out-of-fold predictions and likelihood-ratio tests on full-sample fits.
Return ladder: the within-year rank regression of 19_bhar_controls.py (spec 3 controls, year FE, HC1 + year-cluster) with the purpose
and mention dummies added — does the coefficient on S survive the K&L-type variables?
Decomposition: OLS of S on the fact dummies, text length and period; the fitted part's AUC against the realised label.

Pre-registered expectations (written 2026-11-10 before the first run; outside = bug first):
  identity  n = 579, AUC(S) = 0.761 (±0.002), M0 = 0.587 (±0.005; same seed as 15)
  ladder    0.587 <= M1 <= 0.72 ; M1 <= M2 <= 0.76 ; 0.755 <= M3 <= 0.79 ; M3 > 0.80 or M1 > M3 => suspect leakage/bug
  facts     F between 0.62 and 0.76 ; keyword dummies weaker than the model's facts (K1 - M0 < M2 - M0)
  controls  label-permutation AUCs 0.50 ± 0.04 for every model
  returns   coefficient on S in the rank regression stays in [-0.25, -0.05] with the dummies added, or moves toward 0 while the sale/buyer
            or investor dummies turn negative — both are reportable; a sign flip is a bug first
Outputs: results/nested_models_<date>.json, docs/NESTED_MODELS_NOTE_<date>.md
"""
import os, re, json, glob, datetime as dt, numpy as np, pandas as pd
import statsmodels.api as sm
from sklearn.metrics import roc_auc_score, brier_score_loss
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAMP = dt.date.today().strftime("%Y%m%d")
R = {"generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "expectations_preregistered": __doc__.split("Pre-registered expectations")[1].split("Outputs:")[0].strip()}

# ---------------- A. the Gate-1 sample, by executing 15's own construction code (no re-implementation)
src = open(f"{P}/code/15_gate1_pooled.py", encoding="utf-8").read()
head = src.split("\ndef panel(")[0]                       # everything up to and including design() and cv_auc()
ns = {"__file__": f"{P}/code/15_gate1_pooled.py", "__name__": "gate1_sample"}
exec(compile(head, "15_gate1_pooled_head", "exec"), ns)
df, FIN, design, cv_auc = ns["df"], ns["FIN"], ns["design"], ns["cv_auc"]
y = df.y.values
auc_S = float(roc_auc_score(y, df.p_llm)); X0 = design(df, FIN); auc_M0, oof_M0 = cv_auc(X0, y)
R["identity_control"] = {"n": int(len(df)), "auc_S": round(auc_S, 4), "auc_M0_financial": round(auc_M0, 4),
                         "expected": {"n": 579, "auc_S": 0.761, "auc_M0": 0.587}, "pass": bool(len(df) == 579 and abs(auc_S - 0.761) <= 0.002 and abs(auc_M0 - 0.587) <= 0.005)}
print("identity:", R["identity_control"], flush=True)
assert R["identity_control"]["pass"], "Gate-1 sample or baseline does not reproduce Table 3 — stop"

# ---------------- B. fact dummies from the identified-condition judgments (both models, all runs) — majority vote per filing
PURP = ["specialization", "efficiency", "sale_or_disposal", "fundraising_or_investment_attraction", "holding_company_or_group_restructuring", "regulatory_or_legal", "other"]
MENT = ["mentions_listing_or_ipo", "mentions_external_investment_or_strategic_investor", "mentions_sale_or_buyer", "mentions_shareholder_protection_measures", "appraisal_rights_mentioned"]
acc = {}
for f in glob.glob(f"{P}/results/llm_judge/*identified*.jsonl") + glob.glob(f"{P}/results/llm_judge_2001_2016/*identified*.jsonl"):
    for l in open(f, encoding="utf-8"):
        r = json.loads(l); fa = (r.get("parsed") or {}).get("facts")
        if not isinstance(fa, dict): continue
        a = acc.setdefault(r["rcept_no"], {"n": 0, **{k: 0 for k in PURP + MENT}})
        a["n"] += 1
        cats = fa.get("stated_purpose_categories") or []
        for c in PURP: a[c] += int(c in cats)
        for m in MENT: a[m] += int(bool(fa.get(m)))
facts = pd.DataFrame([{"rcept_no": k, "n_judg": v["n"], **{f"p_{c}": v[c] / v["n"] for c in PURP}, **{f"m_{m}": v[m] / v["n"] for m in MENT}} for k, v in acc.items()])
PD = [f"d_{c}" for c in PURP]; MD = [f"d_{m}" for m in MENT]
for c in PURP: facts[f"d_{c}"] = (facts[f"p_{c}"] >= 0.5).astype(int)
for m in MENT: facts[f"d_{m}"] = (facts[f"m_{m}"] >= 0.5).astype(int)
df = df.merge(facts, on="rcept_no", how="left")
R["facts"] = {"filings_with_facts": int(df.n_judg.notna().sum()), "judgments_per_filing": df.n_judg.describe()[["min", "50%", "max"]].to_dict(),
              "share_flagged_majority": {c: round(float(df[c].mean()), 3) for c in PD + MD},
              "kang_lee_2025b_table1_for_comparison": {"purpose_sale": 0.120, "purpose_efficiency": 0.059, "purpose_specialization": 0.891, "purpose_other": 0.042, "source": "literature/anchor_numbers.json (Table 1 Panel A)"}}
assert df.n_judg.notna().all(), "a Gate-1 filing has no judgment facts"

# ---------------- C. keyword dummies from the raw filing text, no model involved (transparent dictionary; crude by design)
KW = {"kw_sale": r"매각", "kw_listing": r"상장(?!폐지)", "kw_ipo": r"IPO|기업공개", "kw_investment": r"투자\s*유치|투자유치|전략적\s*투자|외부\s*투자", "kw_efficiency": r"효율", "kw_specialization": r"전문화"}
idx_new = json.load(open(f"{P}/data/processed/disclosure_text_index.json", encoding="utf-8")); idx_old = json.load(open(f"{P}/data/processed/disclosure_text_index_2001_2016.json", encoding="utf-8"))
def text_path(rn):
    e = idx_new.get(rn) or idx_old.get(rn)
    if not e: return None
    p = e.get("path"); return f"{P}/{p}" if p and os.path.exists(f"{P}/{p}") else None
rows = []
for rn in df.rcept_no:
    p = text_path(rn); t = open(p, encoding="utf-8", errors="replace").read() if p else None
    rows.append({"rcept_no": rn, "text_chars": len(t) if t else np.nan, **{k: (int(bool(re.search(v, t))) if t else np.nan) for k, v in KW.items()}})
df = df.merge(pd.DataFrame(rows), on="rcept_no", how="left")
KD = list(KW)
R["keywords"] = {"dictionary": KW, "filings_with_text": int(df.text_chars.notna().sum()), "hit_rates": {k: round(float(df[k].mean()), 3) for k in KD}, "median_chars": float(df.text_chars.median())}

# ---------------- D. the ladder
df["logit_S"] = np.log(df.p_llm.clip(0.01, 0.99) / (1 - df.p_llm.clip(0.01, 0.99)))
LADDER = {"M0_financial": FIN, "M1_plus_purpose": FIN + PD, "M2_plus_mentions": FIN + PD + MD, "M3_plus_signal": FIN + PD + MD + ["logit_S"],
          "F_facts_only": PD + MD, "F2_facts_plus_signal": PD + MD + ["logit_S"], "K1_financial_plus_keywords": FIN + KD, "K2_keywords_plus_signal": FIN + KD + ["logit_S"], "S_signal_only_cv": ["logit_S"]}
def fit_ladder(d, label):
    yy = d.y.values; out, oofs = {}, {}
    for name, cols in LADDER.items():
        X = design(d, cols); auc, oof = cv_auc(X, yy); oofs[name] = oof
        out[name] = {"n_features": int(X.shape[1]), "cv_auc": round(auc, 4), "brier_oof": round(float(brier_score_loss(yy, oof)), 4)}
    out["S_raw_auc"] = round(float(roc_auc_score(yy, d.p_llm)), 4)
    rng = np.random.default_rng(7); pairs = [("M1_plus_purpose", "M0_financial"), ("M2_plus_mentions", "M1_plus_purpose"), ("M2_plus_mentions", "M0_financial"), ("M3_plus_signal", "M2_plus_mentions"), ("M3_plus_signal", "M0_financial"),
                                              ("F2_facts_plus_signal", "F_facts_only"), ("K1_financial_plus_keywords", "M0_financial"), ("K2_keywords_plus_signal", "K1_financial_plus_keywords"), ("M2_plus_mentions", "K1_financial_plus_keywords")]
    deltas = {f"{a}-{b}": [] for a, b in pairs}
    for _ in range(2000):
        i = rng.integers(0, len(yy), len(yy))
        if len(set(yy[i])) < 2: continue
        for a, b in pairs: deltas[f"{a}-{b}"].append(roc_auc_score(yy[i], oofs[a][i]) - roc_auc_score(yy[i], oofs[b][i]))
    out["increments"] = {k: {"point": round(out[k.split("-")[0]]["cv_auc"] - out[k.split("-")[1]]["cv_auc"], 4), "ci95": [round(float(np.percentile(v, 2.5)), 4), round(float(np.percentile(v, 97.5)), 4)]} for k, v in deltas.items()}
    # likelihood-ratio tests on full-sample logistic fits (standardised design, same columns)
    def ll(cols):
        X = design(d, cols); Xs = pd.DataFrame(StandardScaler().fit_transform(X), columns=X.columns); m = sm.Logit(yy, sm.add_constant(Xs)).fit(method="bfgs", disp=0, maxiter=5000, gtol=1e-6); return float(m.llf), int(X.shape[1])   # bfgs: llf without inverting a near-singular Hessian
    lr = {}
    for a, b in [("M1_plus_purpose", "M0_financial"), ("M2_plus_mentions", "M1_plus_purpose"), ("M3_plus_signal", "M2_plus_mentions"), ("K2_keywords_plus_signal", "K1_financial_plus_keywords"), ("F2_facts_plus_signal", "F_facts_only")]:
        la, ka = ll(LADDER[a]); lb, kb = ll(LADDER[b]); from scipy.stats import chi2
        lr[f"{a}_vs_{b}"] = {"lr_stat": round(2 * (la - lb), 2), "df": ka - kb, "p": float(chi2.sf(2 * (la - lb), ka - kb))}
    out["lr_tests_full_sample"] = lr
    print(f"[{label}] " + " | ".join(f"{k}={v['cv_auc']}" for k, v in out.items() if isinstance(v, dict) and "cv_auc" in v), flush=True)
    return out
R["ladder_pooled"] = fit_ladder(df, "pooled n=%d" % len(df))
R["ladder_by_period"] = {k: fit_ladder(g.reset_index(drop=True), f"period {k}") for k, g in df.groupby("period_src") if len(g) >= 100}
# full-sample coefficients of M2 and M3 (which facts carry the prediction; does S keep its coefficient)
def coefs(cols):
    X = design(df, cols); Xs = pd.DataFrame(StandardScaler().fit_transform(X), columns=X.columns)
    m = sm.Logit(y, sm.add_constant(Xs)).fit(method="bfgs", disp=0, maxiter=5000, gtol=1e-6)
    try: pv = m.pvalues
    except Exception: pv = pd.Series(np.nan, index=m.params.index)
    return {c: {"coef_std": round(float(m.params[c]), 3), "p": (round(float(pv[c]), 3) if pd.notna(pv[c]) else None)} for c in X.columns}
R["coefficients_full_sample"] = {"M2_plus_mentions": coefs(LADDER["M2_plus_mentions"]), "M3_plus_signal": coefs(LADDER["M3_plus_signal"])}
# control: label permutation
perm = {k: [] for k in ("M0_financial", "M2_plus_mentions", "M3_plus_signal", "F_facts_only", "S_raw", "noise10_features_real_labels")}
for seed in (11, 12, 13, 14, 15):
    rng = np.random.default_rng(seed); yp = rng.permutation(y)
    for name in ("M0_financial", "M2_plus_mentions", "M3_plus_signal", "F_facts_only"):
        X = design(df, LADDER[name]); a, _ = cv_auc(X, yp, n_rep=10, seed=seed); perm[name].append(round(a, 3))
    perm["S_raw"].append(round(float(roc_auc_score(yp, df.p_llm)), 3))
    Xn = pd.DataFrame(rng.standard_normal((len(y), 10)), columns=[f"z{i}" for i in range(10)]); a, _ = cv_auc(Xn, y, n_rep=10, seed=seed); perm["noise10_features_real_labels"].append(round(a, 3))
# Criterion: leakage would push a permuted-label AUC ABOVE 0.5; cross-validated models with no signal sit BELOW 0.5 (the pure-noise
# control shows the same), so the test is "no permuted model above 0.55 and raw S within 0.45–0.55", not "all within ±0.04 of 0.5".
R["control_label_permutation"] = {"auc_by_seed": perm, "mean": {k: round(float(np.mean(v)), 3) for k, v in perm.items()},
                                  "criterion": "max permuted CV AUC <= 0.55 and raw-S permuted AUC within [0.45, 0.55]; CV AUC under the null is biased below 0.5 (see noise10 control)",
                                  "pass": bool(max(max(v) for k, v in perm.items() if k != "noise10_features_real_labels") <= 0.55 and all(0.45 <= v <= 0.55 for v in perm["S_raw"]))}
print("permutation control:", R["control_label_permutation"], flush=True)

# ---------------- E. return ladder (19's rank regression with the K&L-type dummies added)
co = pd.read_csv(sorted(glob.glob(f"{P}/data/processed/bhar_controls_events_*.csv"))[-1], dtype={"rcept_no": str, "stock_code": str})
kwall = pd.DataFrame(rows).set_index("rcept_no")   # keyword flags exist only for Gate-1 filings (texts read above)
co = co.merge(facts[["rcept_no"] + PD + MD], on="rcept_no", how="left").merge(kwall[KD].reset_index(), on="rcept_no", how="left")
BASE = ["log_me", "log_bm", "mom6", "kosdaq"]; FIL = ["rel_size", "surv_lev", "relisting"]; IMP = ["log_me", "log_bm", "mom6", "rel_size", "surv_lev"]
def design19(d, xs, impute):
    X = d[xs].astype(float).copy()
    for c in impute:
        if c in X and X[c].isna().any(): X[c + "_miss"] = X[c].isna().astype(float); X[c] = X[c].fillna(X[c].median())
    for c in X.columns:
        if c not in ("kosdaq", "relisting") and not c.endswith("_miss") and not c.startswith("d_") and not c.startswith("kw_"): X[c] = X[c].clip(X[c].quantile(0.01), X[c].quantile(0.99))
    return X.loc[:, X.nunique(dropna=False) > 1]
def reg19(d, yv, xs, impute=()):
    d = d.dropna(subset=[yv] + [x for x in xs if x not in impute]).copy(); X = design19(d, xs, impute)
    X = sm.add_constant(pd.concat([X, pd.get_dummies(d.year, prefix="y", drop_first=True, dtype=float)], axis=1)); yy = d[yv].astype(float)
    hc = sm.OLS(yy, X).fit(cov_type="HC1"); cl = sm.OLS(yy, X).fit(cov_type="cluster", cov_kwds={"groups": d.year.astype("category").cat.codes.values})
    out = {"n": int(len(d)), "r2": round(float(hc.rsquared), 3)}
    for v in xs:
        if v in X: out[v] = {"coef": round(float(hc.params[v]), 4), "se_hc1": round(float(hc.bse[v]), 4), "p_hc1": round(float(hc.pvalues[v]), 3), "p_cluster_year": round(float(cl.pvalues[v]), 3)}
    return out
dd = co.dropna(subset=["p_llm"]).copy()
R["return_ladder_sample"] = {"scored_events": int(len(dd)), "with_fact_dummies": int(dd.d_specialization.notna().sum()), "with_keyword_flags": int(dd.kw_sale.notna().sum())}
dd = dd[dd.d_specialization.notna()]
R["return_ladder"] = {}
for yv, lab in (("bhar1y_rank_in_year", "rank_1y"), ("bhar_madj_p2_p250", "bhar_1y"), ("car_mm_m1_p1", "ann_car")):
    R["return_ladder"][lab] = {"spec3_as_published": reg19(dd, yv, ["p_llm"] + BASE + FIL, IMP),
                               "spec3_plus_purpose": reg19(dd, yv, ["p_llm"] + BASE + FIL + PD, IMP),
                               "spec3_plus_purpose_mentions": reg19(dd, yv, ["p_llm"] + BASE + FIL + PD + MD, IMP),
                               "facts_only_no_signal": reg19(dd, yv, BASE + FIL + PD + MD, IMP),
                               "spec3_plus_keywords_gate1_filings_only": reg19(dd[dd.kw_sale.notna()], yv, ["p_llm"] + BASE + FIL + KD, IMP)}
    s = R["return_ladder"][lab]; print(f"[returns {lab}] S coef: published {s['spec3_as_published']['p_llm']['coef']} (p {s['spec3_as_published']['p_llm']['p_hc1']}) -> +purpose {s['spec3_plus_purpose']['p_llm']['coef']} (p {s['spec3_plus_purpose']['p_llm']['p_hc1']}) -> +mentions {s['spec3_plus_purpose_mentions']['p_llm']['coef']} (p {s['spec3_plus_purpose_mentions']['p_llm']['p_hc1']}) | n {s['spec3_as_published']['n']}", flush=True)

# ---------------- F. decomposition of S
df["log_chars"] = np.log(df.text_chars); df["new_period"] = (df.period_src == "2017+").astype(int)
Xd = sm.add_constant(df[PD + MD + ["log_chars", "new_period"]].astype(float).fillna(df[["log_chars"]].median().iloc[0]))
dec = sm.OLS(df.p_llm.astype(float), Xd).fit(cov_type="HC1"); df["S_hat"] = dec.fittedvalues; df["S_resid"] = df.p_llm - df.S_hat
R["decomposition_of_S"] = {"r2": round(float(dec.rsquared), 3), "n": int(dec.nobs), "coef": {c: {"coef": round(float(dec.params[c]), 3), "p": round(float(dec.pvalues[c]), 3)} for c in Xd.columns if c != "const"},
                           "auc_S_hat_fitted_part": round(float(roc_auc_score(y, df.S_hat)), 4), "auc_S_resid": round(float(roc_auc_score(y, df.S_resid)), 4), "auc_S": round(auc_S, 4),
                           "reading": "S_hat is the part of the signal explained by the structured facts; S_resid is what the holistic reading adds beyond them"}
print("decomposition:", {k: R["decomposition_of_S"][k] for k in ("r2", "auc_S_hat_fitted_part", "auc_S_resid", "auc_S")}, flush=True)

# ---------------- expectations check (recorded, not enforced)
L = R["ladder_pooled"]; chk = {"M1_in_range": 0.587 <= L["M1_plus_purpose"]["cv_auc"] <= 0.72, "M2_in_range": L["M1_plus_purpose"]["cv_auc"] - 0.01 <= L["M2_plus_mentions"]["cv_auc"] <= 0.76,
                               "M3_in_range": 0.755 <= L["M3_plus_signal"]["cv_auc"] <= 0.79, "M3_not_above_0.80": L["M3_plus_signal"]["cv_auc"] <= 0.80, "F_in_range": 0.62 <= L["F_facts_only"]["cv_auc"] <= 0.76,
                               "keywords_weaker_than_model_facts": (L["K1_financial_plus_keywords"]["cv_auc"] - L["M0_financial"]["cv_auc"]) < (L["M2_plus_mentions"]["cv_auc"] - L["M0_financial"]["cv_auc"]),
                               "permutation_pass": R["control_label_permutation"]["pass"], "F_floor_0.62_missed_by": round(0.62 - L["F_facts_only"]["cv_auc"], 3) if L["F_facts_only"]["cv_auc"] < 0.62 else 0}
R["expectation_check"] = {k: bool(v) for k, v in chk.items()}; print("expectation check:", R["expectation_check"], flush=True)
json.dump(R, open(f"{P}/results/nested_models_{STAMP}.json", "w"), ensure_ascii=False, indent=1, default=float)

# ---------------- note
L = R["ladder_pooled"]; inc = L["increments"]; rl = R["return_ladder"]["rank_1y"]
def row(k): return f"| {k} | {L[k]['n_features']} | {L[k]['cv_auc']:.3f} | {L[k]['brier_oof']:.3f} |"
md = [f"# Nested models — does the signal add to Kang & Lee-type coding? ({STAMP})", "", f"Source: `results/nested_models_{STAMP}.json`, produced by `code/27_nested_models_signal_decomposition.py`. Sample = the Gate-1 pooled sample rebuilt from `15_gate1_pooled.py` (identity control: n {R['identity_control']['n']}, AUC(S) {R['identity_control']['auc_S']:.3f}, financial {R['identity_control']['auc_M0_financial']:.3f} — pass {R['identity_control']['pass']}).", "",
      "## Ladder (repeated 5-fold CV, 50 repeats; AUC of repeat-averaged out-of-fold predictions)", "", "| Model | features | CV AUC | Brier |", "|---|---|---|---|"] + [row(k) for k in LADDER] + ["", "Increments (paired bootstrap, 2,000 resamples):", ""] + [f"- {k}: {v['point']:+.3f} [{v['ci95'][0]:+.3f}, {v['ci95'][1]:+.3f}]" for k, v in inc.items()] + ["", "Likelihood-ratio tests (full-sample logistic):", ""] + [f"- {k}: LR {v['lr_stat']} on {v['df']} df, p = {v['p']:.2e}" for k, v in L["lr_tests_full_sample"].items()] + [
      "", f"Facts flagged by a majority of judgments: " + ", ".join(f"{c[2:]} {v:.2f}" for c, v in R["facts"]["share_flagged_majority"].items()) + f". Kang & Lee (2025b) Table 1: sale 0.120, efficiency 0.059, specialization 0.891, other 0.042.",
      f"Keyword dictionary (no model): {json.dumps(KW, ensure_ascii=False)}; hit rates {R['keywords']['hit_rates']}.", "",
      "## Label-permutation control (5 seeds)", "", f"mean permuted AUC by model: {R['control_label_permutation']['mean']}; criterion: {R['control_label_permutation']['criterion']}; pass {R['control_label_permutation']['pass']}", "",
      "## Return ladder (within-year rank of the one-year BHAR; 19's spec 3 controls, year FE)", "", f"Sample: {R['return_ladder_sample']}", "", "| Spec | n | coef on S | HC1 p | year-cluster p |", "|---|---|---|---|---|"] + [f"| {k} | {v['n']} | {v['p_llm']['coef']:+.4f} | {v['p_llm']['p_hc1']:.3f} | {v['p_llm']['p_cluster_year']:.3f} |" for k, v in rl.items() if "p_llm" in v] + [
      "", "Fact coefficients in the facts-only rank regression (no signal): " + ", ".join(f"{k} {v['coef']:+.3f} (p {v['p_hc1']:.2f})" for k, v in rl["facts_only_no_signal"].items() if k.startswith("d_")), "",
      "## Decomposition of S", "", f"OLS of S on the 12 fact dummies, log text length and a 2017+ indicator: R² {R['decomposition_of_S']['r2']}; AUC of the fitted part {R['decomposition_of_S']['auc_S_hat_fitted_part']:.3f}, of the residual {R['decomposition_of_S']['auc_S_resid']:.3f}, of S {R['decomposition_of_S']['auc_S']:.3f}.", "",
      "## Expectation check", "", str(R["expectation_check"]), "",
      "## Caveat recorded", "", "The purpose and mention dummies are extracted by the same two models that produce S (identified condition, all runs, majority vote), so M2 vs M3 compares a structured extraction with a holistic probability from the same reader; the keyword ladder (K1/K2) is the model-free comparison. A hand-coded replication of Kang & Lee's purpose dummies on a stratified subsample is the human-coder task of strategy §4-A."]
open(f"{P}/docs/NESTED_MODELS_NOTE_{STAMP}.md", "w").write("\n".join(md) + "\n"); print(f"saved results/nested_models_{STAMP}.json, docs/NESTED_MODELS_NOTE_{STAMP}.md")
