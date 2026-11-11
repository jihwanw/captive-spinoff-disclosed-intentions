#!/usr/bin/env python3
"""36_measurement_validity_bias_audit.py — "Measurement validity and bias" evidence for the LLM-read disposal signal, computed from
existing judgment files (no new API calls, no human coders; user decision 2026-11-10 21:5x: defer independent coders to R1 if asked).

Answers CGIR ground 4 ("clarify how AI bias were corrected") with four blocks:
  A  Differential discrimination and calibration by firm subgroup — AUC of S with bootstrap CIs inside each subgroup; LR tests of
     (i) S x group interaction (discrimination differs), (ii) group dummies added to y ~ logit(S) (S is mis-calibrated for some groups);
     calibration-in-the-large (mean S - mean y), Brier, recalibration slope/intercept by period.
     Subgroups: period, KOSDAQ, listed-at-event parent, parent size tercile (filing assets; market cap for listed), relative size tercile,
     text length tercile, label source, foreign-ownership tercile (listed), GICS sector (listed, via gvkey).
  B  Look-ahead / outside-knowledge audit — identified vs name-anonymized judgments (both models, both periods): paired-bootstrap
     dAUC overall and by subgroup; self-reported outside-knowledge rates by model/condition/subgroup; AUC inside the self-reported subset.
  C  Residual-bias regressions — logit(S) on the model's own extracted facts (7 purpose categories, 5 mention flags; majority vote),
     log text length and period; the residual regressed on firm characteristics (size, KOSDAQ, listed, relative size; foreign for listed),
     with and without the realised outcome y. Standardised coefficients; HC1.
  D  Two-model agreement on factual extraction (identified, run 1, both periods) — per field: prevalence per model, % agreement,
     Cohen's kappa; most_likely_path agreement/kappa; p_disposal correlation (identity check against 0.85); within-model
     identified-vs-anonymized fact agreement (anonymisation must not change extraction).
  E  External hand-coding benchmark — Kang & Lee (2025b, FRL) Table 1 Panel A (n = 525; captive spin-offs by KOSPI/KOSDAQ-listed
     parents, 2001–2021; source: literature/KangLee2025_FRL_fulltext.txt lines 229–235, read 2026-11-10): Purpose Sale 0.120,
     Efficiency 0.059, Specialization 0.891, Other 0.042, Subsidiary Listed 0.040, Subsidiary Retained 0.307. Our model-extracted
     purpose shares (majority vote) on listed-parent filings 2001–2021 under two mappings (strict: fundraising -> Other; broad:
     fundraising -> Sale), and our label shares (ipo_listed, retained_100) on clean-labelled listed-parent events 2001–2021.

Pre-registered expectations (written 2026-11-10 before the first run; outside = bug first):
  identity    n = 579, AUC(S) = 0.761 (±0.002); two-model p correlation 0.85 (±0.02) on 2017+ identified (judge summary 10-15)
  A           every subgroup AUC in [0.62, 0.86]; max-min across the levels of one grouping <= 0.15; interaction LR p: no prior;
              calibration-in-the-large: 2001-2016 gap (mean S - mean y) in [-0.30, -0.10] (base rate ~0.74 vs model mean ~0.5),
              2017+ gap in [-0.05, +0.12] (base rate ~0.49, model mean ~0.53); recalibration slope in [0.6, 1.6]
  B           overall dAUC (identified - anonymized) in [-0.03, +0.04] (2017+ ensemble: 0.767 vs 0.760); |dAUC| <= 0.06 in every
              subgroup; Claude self-reported outside knowledge 0.35-0.60, GPT <= 0.10 (2017+); a dAUC > 0.06 inside the self-reported
              subset is the leakage flag -> report and use anonymized scores there
  C           |standardised coefficient| on any firm characteristic <= 0.25 SD; larger = reportable bias (not a bug) unless the sign
              reverses when y is added
  D           mention-flag kappa in [0.35, 0.90]; purpose-category kappa in [0.25, 0.85] (multi-label, rare categories lower);
              path agreement in [0.45, 0.80], kappa in [0.25, 0.60] (GPT predicts 'retain' far more often: 127 vs 69 of ~185)
  E           specialization share within ±0.15 of 0.891; sale (strict) in [0.05, 0.30]; efficiency likely ABOVE 0.059 (our list is
              multi-label and '효율' is near-universal boilerplate) — a granularity difference, recorded, not an error;
              ipo_listed share in [0.02, 0.08] vs 0.040; retained_100 share in [0.20, 0.40] vs 0.307
Outputs: results/validity_bias_audit_<date>.json, docs/VALIDITY_BIAS_AUDIT_NOTE_<date>.md
"""
import os, re, json, glob, datetime as dt, numpy as np, pandas as pd
import statsmodels.api as sm
from sklearn.metrics import roc_auc_score, brier_score_loss, cohen_kappa_score

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAMP = dt.date.today().strftime("%Y%m%d")
rng = np.random.default_rng(20261110)
R = {"generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
     "expectations_preregistered": __doc__.split("Pre-registered expectations")[1].split("Outputs:")[0].strip()}

def logit(p): p = np.clip(np.asarray(p, float), 0.01, 0.99); return np.log(p / (1 - p))
def auc_ci(y, s, B=2000):
    y = np.asarray(y); s = np.asarray(s)
    if len(np.unique(y)) < 2 or len(y) < 8: return {"n": int(len(y)), "auc": None}
    a = roc_auc_score(y, s); i1 = np.where(y == 1)[0]; i0 = np.where(y == 0)[0]; bs = []
    for _ in range(B):
        idx = np.concatenate([rng.choice(i1, len(i1)), rng.choice(i0, len(i0))]); bs.append(roc_auc_score(y[idx], s[idx]))
    return {"n": int(len(y)), "pos": int(y.sum()), "auc": round(float(a), 3), "ci95": [round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)]}
def paired_dauc(y, s1, s2, B=2000):
    y = np.asarray(y); s1 = np.asarray(s1); s2 = np.asarray(s2)
    if len(np.unique(y)) < 2 or len(y) < 8: return {"n": int(len(y))}
    d = roc_auc_score(y, s1) - roc_auc_score(y, s2); i1 = np.where(y == 1)[0]; i0 = np.where(y == 0)[0]; bs = []
    for _ in range(B):
        idx = np.concatenate([rng.choice(i1, len(i1)), rng.choice(i0, len(i0))])
        if len(np.unique(y[idx])) < 2: continue
        bs.append(roc_auc_score(y[idx], s1[idx]) - roc_auc_score(y[idx], s2[idx]))
    return {"n": int(len(y)), "auc_1": round(float(roc_auc_score(y, s1)), 3), "auc_2": round(float(roc_auc_score(y, s2)), 3), "dauc": round(float(d), 3),
            "ci95": [round(float(np.percentile(bs, 2.5)), 3), round(float(np.percentile(bs, 97.5)), 3)]}
def lr_test(ll_small, ll_big, df):
    from scipy.stats import chi2
    stat = 2 * (ll_big - ll_small); return {"lr": round(float(stat), 2), "df": int(df), "p": round(float(chi2.sf(stat, df)), 4)}
def fit_logit(y, X):
    X = sm.add_constant(X, has_constant="add"); return sm.Logit(y, X).fit(disp=0, maxiter=200)

# ---------------- 0. Gate-1 sample (by executing 15's head — the published sample, no re-implementation)
src = open(f"{P}/code/15_gate1_pooled.py", encoding="utf-8").read(); head = src.split("\ndef panel(")[0]
ns = {"__file__": f"{P}/code/15_gate1_pooled.py", "__name__": "gate1_sample"}; exec(compile(head, "15", "exec"), ns)
df = ns["df"].copy(); FIN = ns["FIN"]
auc_S = float(roc_auc_score(df.y, df.p_llm))
R["identity_control"] = {"n": int(len(df)), "auc_S": round(auc_S, 4), "pass": bool(len(df) == 579 and abs(auc_S - 0.761) <= 0.002)}
assert R["identity_control"]["pass"], "Gate-1 sample does not reproduce Table 3 — stop"
print("identity:", R["identity_control"], flush=True)

# ---------------- 1. judgment files -> per-filing table (identified run1 / anonymized, per model) + facts
PURP = ["specialization", "efficiency", "sale_or_disposal", "fundraising_or_investment_attraction", "holding_company_or_group_restructuring", "regulatory_or_legal", "other"]
MENT = ["mentions_listing_or_ipo", "mentions_external_investment_or_strategic_investor", "mentions_sale_or_buyer", "mentions_shareholder_protection_measures", "appraisal_rights_mentioned"]
recs = []
for f in glob.glob(f"{P}/results/llm_judge/*.jsonl") + glob.glob(f"{P}/results/llm_judge_2001_2016/*.jsonl"):
    base = os.path.basename(f); model = "claude" if base.startswith("anthropic") else "gpt"; run = 2 if "run2" in base else 1
    for l in open(f, encoding="utf-8"):
        r = json.loads(l); pa = r.get("parsed") or {}
        if not isinstance(pa, dict) or pa.get("p_disposal") is None: continue
        fa = pa.get("facts") if isinstance(pa.get("facts"), dict) else {}
        row = {"rcept_no": str(r["rcept_no"]), "model": model, "condition": r["condition"], "run": run, "p": float(pa["p_disposal"]) / 100.0,
               "path": pa.get("most_likely_path"), "outside": pa.get("used_outside_knowledge"), "text_chars": r.get("text_chars"), "outcome": r.get("outcome")}
        cats = fa.get("stated_purpose_categories") or []
        for c in PURP: row[f"purp_{c}"] = int(c in cats) if isinstance(cats, list) else np.nan
        for m in MENT: row[m] = (int(bool(fa[m])) if m in fa and fa[m] is not None else np.nan)
        recs.append(row)
J = pd.DataFrame(recs); R["judgments_loaded"] = J.groupby(["condition", "model", "run"]).size().reset_index().astype(str).values.tolist()
id1 = J[(J.condition == "identified") & (J.run == 1)]; an = J[J.condition == "anonymized"]
wide = id1.pivot_table(index="rcept_no", columns="model", values="p").rename(columns=lambda c: f"p_id_{c}")
wide = wide.join(an.pivot_table(index="rcept_no", columns="model", values="p").rename(columns=lambda c: f"p_an_{c}"))
wide["S_id"] = wide[["p_id_claude", "p_id_gpt"]].mean(axis=1); wide["S_an"] = wide[["p_an_claude", "p_an_gpt"]].mean(axis=1)
wide["text_chars"] = id1.groupby("rcept_no").text_chars.first(); wide["outcome"] = id1.groupby("rcept_no").outcome.first()
for m in ("claude", "gpt"):
    wide[f"outside_id_{m}"] = id1[id1.model == m].set_index("rcept_no").outside.map(lambda v: int(bool(v)) if v is not None else np.nan)
    wide[f"outside_an_{m}"] = an[an.model == m].set_index("rcept_no").outside.map(lambda v: int(bool(v)) if v is not None else np.nan)
# majority-vote facts over all identified judgments (both models, both runs) — same rule as 27
idall = J[J.condition == "identified"]; FACT = [f"purp_{c}" for c in PURP] + MENT
maj = (idall.groupby("rcept_no")[FACT].mean() >= 0.5).astype(int)

# ---------------- 2. firm characteristics
ctl = pd.read_csv(f"{P}/data/processed/bhar_controls_events_20261025.csv", dtype={"rcept_no": str})[["rcept_no", "log_me", "log_parent_assets", "rel_size", "gvkey"]]   # kosdaq comes from the Gate-1 sample itself
gov = pd.read_csv(f"{P}/data/processed/event_governance_controls_20261110.csv", dtype={"rcept_no": str})[["rcept_no", "foreign_pct", "outside_dir_ratio"]]
gco = pd.read_parquet(f"{P}/data/raw/compustat_global_kr/g_company_kr.parquet")[["gvkey", "gsector"]]
gco["gvkey"] = gco.gvkey.astype(str); gco["gsector"] = gco.gsector.astype("string")
df["rcept_no"] = df.rcept_no.astype(str)
D = df.merge(wide, on="rcept_no", how="left").merge(ctl, on="rcept_no", how="left").merge(gov, on="rcept_no", how="left")
D["gvkey"] = D.gvkey.astype("string").str.replace(r"\.0$", "", regex=True); D = D.merge(gco, on="gvkey", how="left")
D["listed"] = D.rcept_no.isin(ctl.rcept_no).astype(int)
D["period3"] = pd.cut(D.division_year, [2000, 2008, 2016, 2030], labels=["2001-08", "2009-16", "2017+"]).astype(str)
D["log_assets_filing"] = np.log(D.parent_after_assets.where(D.parent_after_assets > 0))   # parent total assets after the division, from the filing (coverage: 4% of 2001-08, 51% of 2009-16, 100% of 2017+; no fallback — mixing newco assets in was the first run's error)
def terc(x, labels): 
    try: return pd.qcut(x, 3, labels=labels).astype(str).replace("nan", "missing")
    except Exception: return pd.Series(["missing"] * len(x), index=x.index)
D["size_terc"] = terc(D.log_assets_filing, ["small", "mid", "large"]); D["me_terc"] = terc(D.log_me, ["small", "mid", "large"]); D["newco_terc"] = terc(D.log_newco_assets, ["small", "mid", "large"])
D["relsize_terc"] = terc(D.relative_size, ["low", "mid", "high"]); D["text_terc"] = terc(D.text_chars, ["short", "mid", "long"])
D["foreign_terc"] = terc(D.foreign_pct, ["low", "mid", "high"])
sec_counts = D.gsector.value_counts(); D["sector"] = D.gsector.where(D.gsector.map(sec_counts) >= 25, other="other/small").fillna("unlisted/unknown").astype(str)
D["kosdaq_g"] = D.kosdaq.map({0: "KOSPI/other", 1: "KOSDAQ"}).fillna("missing"); D["listed_g"] = D.listed.map({1: "listed", 0: "unlisted"})
D["label_src"] = D.label_source.astype(str)
R["sample"] = {"n": int(len(D)), "listed": int(D.listed.sum()), "with_anonymized": int(D.S_an.notna().sum()), "with_text_chars": int(D.text_chars.notna().sum()),
               "with_gsector": int(D.gsector.notna().sum()), "with_foreign": int(D.foreign_pct.notna().sum())}

# ---------------- A. subgroup discrimination & calibration
GROUPS = {"period": "period3", "kosdaq": "kosdaq_g", "listed_parent": "listed_g", "parent_size_filing_2009plus": "size_terc", "market_cap_listed": "me_terc", "newco_size": "newco_terc",
          "relative_size": "relsize_terc", "text_length": "text_terc", "label_source": "label_src", "foreign_ownership_listed": "foreign_terc", "gics_sector": "sector"}
A = {}
y = D.y.values.astype(int); lS = logit(D.p_llm.values)
base = fit_logit(y, pd.DataFrame({"lS": lS}))
R["calibration_overall"] = {"mean_S": round(float(D.p_llm.mean()), 3), "mean_y": round(float(D.y.mean()), 3), "gap": round(float(D.p_llm.mean() - D.y.mean()), 3),
                            "brier": round(float(brier_score_loss(y, D.p_llm)), 3), "recal_intercept": round(float(base.params["const"]), 3), "recal_slope": round(float(base.params["lS"]), 3)}
for name, col in GROUPS.items():
    g = D[col].astype(str); levels = [l for l in g.unique() if l != "missing" and (g == l).sum() >= 15]
    sub = {}
    for l in sorted(levels):
        m = (g == l).values; r_ = auc_ci(y[m], D.p_llm.values[m])
        if r_.get("auc") is None: continue
        r_.update({"mean_S": round(float(D.p_llm.values[m].mean()), 3), "mean_y": round(float(y[m].mean()), 3), "gap": round(float(D.p_llm.values[m].mean() - y[m].mean()), 3),
                   "brier": round(float(brier_score_loss(y[m], D.p_llm.values[m])), 3)}); sub[l] = r_
    keep = g.isin(levels).values
    if len(levels) >= 2 and keep.sum() >= 40:
        Xg = pd.get_dummies(g[keep], drop_first=True).astype(float); Xg.index = range(keep.sum())
        yk = y[keep]; lk = lS[keep]; X0 = pd.DataFrame({"lS": lk}); X1 = pd.concat([X0, Xg], axis=1)
        X2 = pd.concat([X1, Xg.mul(lk, axis=0).add_prefix("lSx")], axis=1)
        try:
            m0, m1, m2 = fit_logit(yk, X0), fit_logit(yk, X1), fit_logit(yk, X2)
            tests = {"calibration_group_dummies": lr_test(m0.llf, m1.llf, X1.shape[1] - X0.shape[1]), "discrimination_interaction": lr_test(m1.llf, m2.llf, X2.shape[1] - X1.shape[1])}
        except Exception as e: tests = {"error": str(e)[:120]}
    else: tests = {"note": "fewer than 2 usable levels"}
    aucs = [v["auc"] for v in sub.values()]
    A[name] = {"levels": sub, "max_minus_min_auc": round(max(aucs) - min(aucs), 3) if len(aucs) >= 2 else None, "lr_tests": tests}
R["A_subgroups"] = A
# recalibration by period
R["calibration_by_period"] = {}
for l in ["2001-08", "2009-16", "2017+"]:
    m = (D.period3 == l).values; f = fit_logit(y[m], pd.DataFrame({"lS": lS[m]}))
    R["calibration_by_period"][l] = {"n": int(m.sum()), "mean_S": round(float(D.p_llm.values[m].mean()), 3), "mean_y": round(float(y[m].mean()), 3), "gap": round(float(D.p_llm.values[m].mean() - y[m].mean()), 3),
                                     "recal_intercept": round(float(f.params["const"]), 3), "recal_slope": round(float(f.params["lS"]), 3), "brier": round(float(brier_score_loss(y[m], D.p_llm.values[m])), 3)}
print("A done", flush=True)

# ---------------- B. identified vs anonymized
B = {}; both = D[D.S_id.notna() & D.S_an.notna()].copy()
B["overall"] = paired_dauc(both.y.values, both.S_id.values, both.S_an.values)
def pm(m): return (both[f"p_id_{m}"].notna() & both[f"p_an_{m}"].notna()).values
B["overall_by_model"] = {m: paired_dauc(both.y.values[pm(m)], both[f"p_id_{m}"].values[pm(m)], both[f"p_an_{m}"].values[pm(m)]) for m in ("claude", "gpt")}
B["mean_shift_id_minus_an"] = {m: round(float((both[f"p_id_{m}"] - both[f"p_an_{m}"]).mean()), 4) for m in ("claude", "gpt")}
B["corr_id_an"] = {m: round(float(both[f"p_id_{m}"].corr(both[f"p_an_{m}"])), 3) for m in ("claude", "gpt")}
B["by_subgroup"] = {}
for name in ["period", "listed_parent", "kosdaq", "parent_size_filing_2009plus", "market_cap_listed", "newco_size", "text_length"]:
    col = GROUPS[name]; out = {}
    for l in sorted(both[col].astype(str).unique()):
        if l == "missing": continue
        m = (both[col].astype(str) == l).values
        if m.sum() >= 30: out[l] = paired_dauc(both.y.values[m], both.S_id.values[m], both.S_an.values[m])
    B["by_subgroup"][name] = out
B["outside_knowledge_rate"] = {}
for m in ("claude", "gpt"):
    for cnd in ("id", "an"):
        c = both[f"outside_{cnd}_{m}"]; B["outside_knowledge_rate"][f"{m}_{cnd}"] = {"rate": round(float(c.mean()), 3), "n": int(c.notna().sum()),
            "by_period": {l: round(float(c[both.period3 == l].mean()), 3) for l in ["2001-08", "2009-16", "2017+"]},
            "by_listed": {l: round(float(c[both.listed_g == l].mean()), 3) for l in ["listed", "unlisted"]},
            "by_size": {l: round(float(c[both.size_terc == l].mean()), 3) for l in ["small", "mid", "large"] if (both.size_terc == l).sum() > 0}}
# inside the self-reported subset (identified condition) — does identification add accuracy where the model says it used outside knowledge?
B["self_reported_subset"] = {}
for m in ("claude", "gpt"):
    for flag, lab in ((1, "reported_outside"), (0, "no_outside")):
        mm = (both[f"outside_id_{m}"] == flag).values & pm(m)
        if mm.sum() >= 30: B["self_reported_subset"][f"{m}_{lab}"] = paired_dauc(both.y.values[mm], both[f"p_id_{m}"].values[mm], both[f"p_an_{m}"].values[mm])
R["B_anonymization"] = B; print("B done", flush=True)

# ---------------- C. residual-bias regressions
C = {}; E = D.merge(maj, left_on="rcept_no", right_index=True, how="left")
have = E[FACT].notna().all(axis=1) & E.text_chars.notna(); E = E[have].copy()
Xf = E[FACT].astype(float).copy(); Xf["log_text"] = np.log(E.text_chars.astype(float)); Xf = pd.concat([Xf, pd.get_dummies(E.period3, prefix="per", drop_first=True).astype(float)], axis=1)
Xf = Xf.loc[:, Xf.std() > 0]
m_fact = sm.OLS(logit(E.p_llm.values), sm.add_constant(Xf)).fit(cov_type="HC1"); E["u"] = m_fact.resid
C["stage1"] = {"n": int(len(E)), "r2": round(float(m_fact.rsquared), 3), "note": "logit(S) on majority-vote facts + log text length + period dummies"}
def std_ols(dep, cols, data, add_y=False):
    Z = data[cols].astype(float).copy()
    if add_y: Z["y"] = data.y.astype(float)
    Z = Z.dropna(); d = dep.loc[Z.index]
    Zs = (Z - Z.mean()) / Z.std(ddof=0); ds = (d - d.mean()) / d.std(ddof=0)
    f = sm.OLS(ds.values, sm.add_constant(Zs)).fit(cov_type="HC1")
    return {"n": int(len(Z)), "r2": round(float(f.rsquared), 3), **{c: {"beta_std": round(float(f.params[c]), 3), "p": round(float(f.pvalues[c]), 3)} for c in Zs.columns}}
E["log_me_f"] = E.log_me; E["foreign"] = E.foreign_pct / 100.0; E["err"] = E.p_llm - E.y   # error S - y: negative = under-prediction
C["all_filings"] = {"no_y": std_ols(E.u, ["log_assets_filing", "kosdaq", "listed", "relative_size"], E), "with_y": std_ols(E.u, ["log_assets_filing", "kosdaq", "listed", "relative_size"], E, add_y=True)}
EL = E[E.listed == 1]
C["listed_parents"] = {"no_y": std_ols(EL.u, ["log_me_f", "kosdaq", "relative_size", "foreign"], EL), "with_y": std_ols(EL.u, ["log_me_f", "kosdaq", "relative_size", "foreign"], EL, add_y=True)}
# direct: does the signal's error (S - y) depend on firm characteristics?
C["error_S_minus_y_on_characteristics"] = {"all": std_ols(E.err, ["log_assets_filing", "kosdaq", "listed", "relative_size"], E), "listed": std_ols(EL.err, ["log_me_f", "kosdaq", "relative_size", "foreign"], EL)}
R["C_residual_bias"] = C; print("C done", flush=True)

# ---------------- D. two-model agreement on facts (identified run1), path, p; within-model identified vs anonymized facts
Dd = {}
c1 = id1[id1.model == "claude"].set_index("rcept_no"); g1 = id1[id1.model == "gpt"].set_index("rcept_no"); common = c1.index.intersection(g1.index)
c1 = c1.loc[common]; g1 = g1.loc[common]; Dd["n_common_filings"] = int(len(common))
Dd["p_corr"] = {"pearson": round(float(np.corrcoef(c1.p, g1.p)[0, 1]), 3), "spearman": round(float(pd.Series(c1.p.values).corr(pd.Series(g1.p.values), method="spearman")), 3),
                "pearson_2017plus": round(float(np.corrcoef(c1.p[c1.index.str[:4] >= "2017"], g1.p[g1.index.str[:4] >= "2017"])[0, 1]), 3), "mean_claude": round(float(c1.p.mean()), 3), "mean_gpt": round(float(g1.p.mean()), 3)}
Dd["facts"] = {}
for f in FACT:
    a_ = c1[f]; b_ = g1[f]; ok = a_.notna() & b_.notna()
    if ok.sum() < 30: continue
    a_ = a_[ok].astype(int); b_ = b_[ok].astype(int)
    Dd["facts"][f] = {"n": int(ok.sum()), "prev_claude": round(float(a_.mean()), 3), "prev_gpt": round(float(b_.mean()), 3), "agreement": round(float((a_ == b_).mean()), 3),
                      "kappa": round(float(cohen_kappa_score(a_, b_)), 3) if (a_.nunique() > 1 or b_.nunique() > 1) else None}
okp = c1.path.notna() & g1.path.notna()
Dd["path"] = {"n": int(okp.sum()), "agreement": round(float((c1.path[okp] == g1.path[okp]).mean()), 3), "kappa": round(float(cohen_kappa_score(c1.path[okp], g1.path[okp])), 3),
              "dist_claude": c1.path[okp].value_counts().to_dict(), "dist_gpt": g1.path[okp].value_counts().to_dict(),
              "agreement_retain_vs_not": round(float(((c1.path[okp] == "retain") == (g1.path[okp] == "retain")).mean()), 3)}
Dd["within_model_identified_vs_anonymized_facts"] = {}
for m in ("claude", "gpt"):
    a_ = id1[id1.model == m].set_index("rcept_no"); b_ = an[an.model == m].set_index("rcept_no"); cm = a_.index.intersection(b_.index); out = {}
    for f in FACT:
        x = a_.loc[cm, f]; z = b_.loc[cm, f]; ok = x.notna() & z.notna()
        if ok.sum() >= 30: out[f] = round(float((x[ok].astype(int) == z[ok].astype(int)).mean()), 3)
    Dd["within_model_identified_vs_anonymized_facts"][m] = {"n": int(len(cm)), "agreement": out, "p_corr": round(float(a_.loc[cm, "p"].corr(b_.loc[cm, "p"])), 3)}
R["D_two_model_agreement"] = Dd; print("D done", flush=True)

# ---------------- E. Kang & Lee hand-coded benchmark (FRL 2025 Table 1 Panel A; n = 525; listed parents 2001–2021)
KL = {"purpose_sale": 0.120, "purpose_efficiency": 0.059, "purpose_specialization": 0.891, "purpose_other": 0.042, "subsidiary_listed": 0.040, "subsidiary_retained": 0.307,
      "source": "literature/KangLee2025_FRL_fulltext.txt lines 229-235 (Table 1 Panel A), sample lines 151-156; read 2026-11-10"}
# listed-at-event parents: events with price data in the controls file (600) — the paper's return sample definition
listed_rn = set(ctl.rcept_no.astype(str))
# year of the filing from rcept_no (DART receipt date) — division_year in the judgments
yr = idall.groupby("rcept_no").size().index.to_series().str[:4].astype(int)
M = maj.copy(); M["year"] = yr.reindex(M.index); M["listed"] = M.index.isin(listed_rn)
KLs = M[(M.year >= 2001) & (M.year <= 2021) & M.listed]
def shares(T):
    strict_other = T[["purp_fundraising_or_investment_attraction", "purp_holding_company_or_group_restructuring", "purp_regulatory_or_legal", "purp_other"]].max(axis=1)
    broad_sale = T[["purp_sale_or_disposal", "purp_fundraising_or_investment_attraction"]].max(axis=1)
    broad_other = T[["purp_holding_company_or_group_restructuring", "purp_regulatory_or_legal", "purp_other"]].max(axis=1)
    return {"n": int(len(T)), "strict": {"sale": round(float(T.purp_sale_or_disposal.mean()), 3), "efficiency": round(float(T.purp_efficiency.mean()), 3), "specialization": round(float(T.purp_specialization.mean()), 3), "other": round(float(strict_other.mean()), 3)},
            "broad_sale_incl_fundraising": {"sale": round(float(broad_sale.mean()), 3), "efficiency": round(float(T.purp_efficiency.mean()), 3), "specialization": round(float(T.purp_specialization.mean()), 3), "other": round(float(broad_other.mean()), 3)},
            "raw_7_categories": {c: round(float(T[f"purp_{c}"].mean()), 3) for c in PURP}, "mentions": {m: round(float(T[m].mean()), 3) for m in MENT}}
Ex = {"kang_lee_table1": KL, "ours_listed_2001_2021_majority_vote": shares(KLs), "ours_all_filings_with_judgments": shares(M)}
# outcome shares among clean-labelled (Gate-1) listed-parent events 2001–2021 — outcomes from the tracking files 15 itself reads
# (the judge records' 'outcome' field is the label at judge time, mostly 'unknown' — using it was the first run's error)
t16 = {r["rcept_no"]: r for r in json.load(open(f"{P}/data/processed/carveout_disposal_tracking_2001_2016.json", encoding="utf-8"))}
v4 = json.load(open(f"{P}/data/processed/carveout_disposal_tracking_v4.json", encoding="utf-8")); v4 = {r["rcept_no"]: r for r in (v4 if isinstance(v4, list) else v4.values())}
D["outcome_track"] = D.rcept_no.map(lambda rn: (t16.get(rn) or v4.get(rn) or {}).get("outcome"))
G = D[(D.division_year >= 2001) & (D.division_year <= 2021) & (D.listed == 1)].copy()
oc = G.outcome_track.value_counts(dropna=False); Ex["ours_outcomes_listed_2001_2021_gate1"] = {"n": int(len(G)), "shares": {str(k): round(float(v / len(G)), 3) for k, v in oc.items()},
    "subsidiary_listed_ipo": round(float((G.outcome_track == "ipo_listed").mean()), 3), "retained_100": round(float((G.outcome_track == "retained_100").mean()), 3),
    "retained_100_or_partial_sale_upper_bound": round(float(G.outcome_track.isin(["retained_100", "partial_sale"]).mean()), 3), "disposed_y": round(float(G.y.mean()), 3),
    "note": "K&L 'Subsidiary Listed' = eventually listed; ours = first observed change is a listing (ipo_listed). K&L 'Retained' = remained controlled and owned by the parent; ours retained_100 (strict) and retained_100+partial_sale (parent keeps control) bracket it."}
R["E_kang_lee_benchmark"] = Ex; print("E done", flush=True)

# ---------------- expectation check
sub_aucs = [v["auc"] for g in A.values() for v in g["levels"].values()]
chk = {"identity_pass": R["identity_control"]["pass"], "two_model_corr_2017plus_in_0.83_0.87": bool(0.83 <= Dd["p_corr"]["pearson_2017plus"] <= 0.87),
       "all_subgroup_auc_in_[0.62,0.86]": bool(min(sub_aucs) >= 0.62 and max(sub_aucs) <= 0.86), "min_subgroup_auc": min(sub_aucs), "max_subgroup_auc": max(sub_aucs),
       "max_spread_within_grouping_le_0.15": bool(max(g["max_minus_min_auc"] or 0 for g in A.values()) <= 0.15),
       "gap_2001_16_in_[-0.30,-0.10]": bool(all(-0.30 <= R["calibration_by_period"][l]["gap"] <= -0.10 for l in ["2001-08", "2009-16"])),
       "gap_2017plus_in_[-0.05,0.12]": bool(-0.05 <= R["calibration_by_period"]["2017+"]["gap"] <= 0.12),
       "recal_slope_in_[0.6,1.6]": bool(0.6 <= R["calibration_overall"]["recal_slope"] <= 1.6),
       "dauc_overall_in_[-0.03,0.04]": bool(-0.03 <= B["overall"]["dauc"] <= 0.04),
       "dauc_all_subgroups_abs_le_0.06": bool(all(abs(v["dauc"]) <= 0.06 for g in B["by_subgroup"].values() for v in g.values() if "dauc" in v)),
       "claude_outside_rate_2017plus_in_[0.35,0.60]": bool(0.35 <= B["outside_knowledge_rate"]["claude_id"]["by_period"]["2017+"] <= 0.60),
       "gpt_outside_rate_2017plus_le_0.10": bool(B["outside_knowledge_rate"]["gpt_id"]["by_period"]["2017+"] <= 0.10),
       "residual_bias_all_abs_le_0.25": bool(all(abs(v["beta_std"]) <= 0.25 for k, v in C["all_filings"]["no_y"].items() if isinstance(v, dict))),
       "mention_kappa_in_[0.35,0.90]": bool(all(0.35 <= v["kappa"] <= 0.90 for f, v in Dd["facts"].items() if f in MENT and v["kappa"] is not None)),
       "purpose_kappa_in_[0.25,0.85]": bool(all(0.25 <= v["kappa"] <= 0.85 for f, v in Dd["facts"].items() if f.startswith("purp_") and v["kappa"] is not None)),
       "path_agreement_in_[0.45,0.80]": bool(0.45 <= Dd["path"]["agreement"] <= 0.80), "path_kappa_in_[0.25,0.60]": bool(0.25 <= Dd["path"]["kappa"] <= 0.60),
       "KL_specialization_within_0.15": bool(abs(Ex["ours_listed_2001_2021_majority_vote"]["strict"]["specialization"] - 0.891) <= 0.15),
       "KL_sale_strict_in_[0.05,0.30]": bool(0.05 <= Ex["ours_listed_2001_2021_majority_vote"]["strict"]["sale"] <= 0.30),
       "KL_ipo_share_in_[0.02,0.08]": bool(0.02 <= Ex["ours_outcomes_listed_2001_2021_gate1"]["subsidiary_listed_ipo"] <= 0.08),
       "KL_retained_in_[0.20,0.40]": bool(0.20 <= Ex["ours_outcomes_listed_2001_2021_gate1"]["retained_100"] <= 0.40)}
R["expectation_check"] = chk
R["post_hoc_reading_added_after_run"] = {
 "first_run_bugs_fixed": ["size tercile mixed parent assets with newco assets when the parent field was missing (2001-08 coverage 4%) -> parent assets only, labelled 2009+; newco size is its own grouping",
                          "K&L outcome shares were read from the judge records' 'outcome' field (label at judge time, 69% 'unknown') -> now from the tracking files 15 reads"],
 "gap_2017plus": "expectation [-0.05, 0.12] was set from the October judge summary (2017+ base rate 0.49, n~185); the Gate-1 2017+ sample now has base rate 0.621 (n 240) after label completion, so the model under-predicts there too (gap about -0.10). Expectation mis-set from stale numbers, not a code error.",
 "subgroup_auc_range": "misses are (i) small parents by filing assets, 2009+ (AUC ~0.60; discrimination-interaction LR p < 0.01) and short/old/unlisted filings (0.64-0.69), and (ii) GICS sector 50 (n 50, AUC ~0.92, wide CI). (i) is a reportable property of the signal — weaker and more conservative for small parents, whose realised disposal rate is highest; (ii) is a small-sample extreme.",
 "kappa_misses": "mentions_listing_or_ipo (kappa ~0.01) is a field-definition split, not a reading disagreement: GPT marks True whenever the form line '재상장신청 여부: 아니오' appears, Claude only for a positive plan; both models' listing_plan_statement text says 'no plan' for the same filings (checked on the 615 GPT-True/Claude-False cases). mentions_shareholder_protection_measures (0.24) and purp_other (0.33) are the same kind of boundary ambiguity. None of these fields enters the headline signal S.",
 "K&L_purpose_granularity": "K&L dummies sum to 1.11 (near single primary purpose; specialization 0.891, efficiency 0.059); our extraction lists every stated category (efficiency 0.97, specialization 0.99 — boilerplate). Only 'sale' is comparable (ours 0.085 strict / 0.224 incl. fundraising vs 0.120). Outcome shares are like-for-like after the fix."}
json.dump(R, open(f"{P}/results/validity_bias_audit_{STAMP}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))

# ---------------- note
L = [f"# Measurement validity and bias audit — {STAMP}", "", f"Source: `results/validity_bias_audit_{STAMP}.json` (`code/36`). Sample: Gate-1 n={len(D)} (identity AUC {auc_S:.3f}).", "",
     "## A. Discrimination and calibration by subgroup", "| grouping | level | n | AUC [95% CI] | mean S | mean y | gap | Brier |", "|---|---|---|---|---|---|---|---|"]
for name, g in A.items():
    for l, v in g["levels"].items(): L.append(f"| {name} | {l} | {v['n']} | {v['auc']} [{v['ci95'][0]}, {v['ci95'][1]}] | {v['mean_S']} | {v['mean_y']} | {v['gap']} | {v['brier']} |")
L += ["", "| grouping | max−min AUC | LR calibration (group dummies) p | LR discrimination (interaction) p |", "|---|---|---|---|"]
for name, g in A.items():
    t = g["lr_tests"]; L.append(f"| {name} | {g['max_minus_min_auc']} | {t.get('calibration_group_dummies', {}).get('p', '—')} | {t.get('discrimination_interaction', {}).get('p', '—')} |")
L += ["", f"Overall calibration: mean S {R['calibration_overall']['mean_S']} vs mean y {R['calibration_overall']['mean_y']} (gap {R['calibration_overall']['gap']}); recalibration intercept {R['calibration_overall']['recal_intercept']}, slope {R['calibration_overall']['recal_slope']}; Brier {R['calibration_overall']['brier']}.",
      "By period: " + "; ".join(f"{k}: gap {v['gap']}, slope {v['recal_slope']}, intercept {v['recal_intercept']}" for k, v in R["calibration_by_period"].items()), "",
      "## B. Identified vs name-anonymized judgments", f"Overall (n={B['overall']['n']}): AUC identified {B['overall']['auc_1']} vs anonymized {B['overall']['auc_2']}, dAUC {B['overall']['dauc']} [{B['overall']['ci95'][0]}, {B['overall']['ci95'][1]}].",
      "By model: " + "; ".join(f"{m}: {v['auc_1']} vs {v['auc_2']} (d {v['dauc']} [{v['ci95'][0]}, {v['ci95'][1]}])" for m, v in B["overall_by_model"].items()),
      "Mean shift identified − anonymized: " + ", ".join(f"{m} {v:+.3f}" for m, v in B["mean_shift_id_minus_an"].items()) + "; correlation: " + ", ".join(f"{m} {v}" for m, v in B["corr_id_an"].items()), "",
      "| grouping | level | n | AUC id | AUC anon | dAUC [95% CI] |", "|---|---|---|---|---|---|"]
for name, g in B["by_subgroup"].items():
    for l, v in g.items(): L.append(f"| {name} | {l} | {v['n']} | {v['auc_1']} | {v['auc_2']} | {v['dauc']} [{v['ci95'][0]}, {v['ci95'][1]}] |")
L += ["", "Self-reported outside knowledge (share of judgments): " + "; ".join(f"{k} {v['rate']} (2017+: {v['by_period'].get('2017+')}, 2001-08: {v['by_period'].get('2001-08')})" for k, v in B["outside_knowledge_rate"].items()),
      "Inside the self-reported subset (identified vs anonymized, same filings): " + "; ".join(f"{k}: n {v['n']}, {v['auc_1']} vs {v['auc_2']} (d {v['dauc']} [{v['ci95'][0]}, {v['ci95'][1]}])" for k, v in B["self_reported_subset"].items()), "",
      "## C. Residual bias (standardised OLS, HC1)", f"Stage 1: logit(S) on majority-vote facts + log text + period: n {C['stage1']['n']}, R² {C['stage1']['r2']}.", "",
      "| sample | spec | " + " | ".join(["log size", "KOSDAQ", "listed/foreign", "relative size", "y"]) + " |", "|---|---|---|---|---|---|---|"]
def rowC(lab, spec, d, keys):
    cells = []
    for k in keys:
        v = d.get(k); cells.append(f"{v['beta_std']:+.3f} (p {v['p']})" if isinstance(v, dict) else "—")
    return f"| {lab} | {spec} (n {d['n']}) | " + " | ".join(cells) + " |"
L.append(rowC("all filings", "residual, no y", C["all_filings"]["no_y"], ["log_assets_filing", "kosdaq", "listed", "relative_size", "y"]))
L.append(rowC("all filings", "residual, with y", C["all_filings"]["with_y"], ["log_assets_filing", "kosdaq", "listed", "relative_size", "y"]))
L.append(rowC("listed parents", "residual, no y", C["listed_parents"]["no_y"], ["log_me_f", "kosdaq", "foreign", "relative_size", "y"]))
L.append(rowC("listed parents", "residual, with y", C["listed_parents"]["with_y"], ["log_me_f", "kosdaq", "foreign", "relative_size", "y"]))
L.append(rowC("all filings", "error S−y", C["error_S_minus_y_on_characteristics"]["all"], ["log_assets_filing", "kosdaq", "listed", "relative_size", "y"]))
L.append(rowC("listed parents", "error S−y", C["error_S_minus_y_on_characteristics"]["listed"], ["log_me_f", "kosdaq", "foreign", "relative_size", "y"]))
L += ["", "## D. Two-model agreement on extracted facts (identified, run 1)", f"Common filings: {Dd['n_common_filings']}; p_disposal Pearson {Dd['p_corr']['pearson']} (2017+: {Dd['p_corr']['pearson_2017plus']}), Spearman {Dd['p_corr']['spearman']}; means Claude {Dd['p_corr']['mean_claude']} / GPT {Dd['p_corr']['mean_gpt']}.", "",
      "| field | n | prev. Claude | prev. GPT | agreement | κ |", "|---|---|---|---|---|---|"]
for f, v in Dd["facts"].items(): L.append(f"| {f} | {v['n']} | {v['prev_claude']} | {v['prev_gpt']} | {v['agreement']} | {v['kappa']} |")
L += ["", f"Most-likely path: agreement {Dd['path']['agreement']}, κ {Dd['path']['kappa']}; retain-vs-not agreement {Dd['path']['agreement_retain_vs_not']}. Claude {Dd['path']['dist_claude']}; GPT {Dd['path']['dist_gpt']}.",
      "Within-model identified vs anonymized fact agreement: " + "; ".join(f"{m}: p corr {v['p_corr']}, facts min {min(v['agreement'].values()):.3f} / median {np.median(list(v['agreement'].values())):.3f}" for m, v in Dd["within_model_identified_vs_anonymized_facts"].items()), "",
      "## E. Kang & Lee (2025b, FRL) Table 1 benchmark", f"K&L n=525 listed parents 2001–2021 ({KL['source']}).", "",
      "| category | K&L hand-coded | ours strict (listed 2001–21, n " + str(Ex["ours_listed_2001_2021_majority_vote"]["n"]) + ") | ours broad (fundraising→sale) |", "|---|---|---|---|"]
for k in ["sale", "efficiency", "specialization", "other"]:
    L.append(f"| Purpose: {k} | {KL['purpose_' + k]} | {Ex['ours_listed_2001_2021_majority_vote']['strict'][k]} | {Ex['ours_listed_2001_2021_majority_vote']['broad_sale_incl_fundraising'][k]} |")
o = Ex["ours_outcomes_listed_2001_2021_gate1"]
L += [f"| Subsidiary listed | {KL['subsidiary_listed']} | {o['subsidiary_listed_ipo']} (Gate-1 listed 2001–21, n {o['n']}) | |", f"| Subsidiary retained | {KL['subsidiary_retained']} | {o['retained_100']} (retained_100; upper bound incl. partial sale {o['retained_100_or_partial_sale_upper_bound']}) | |",
      "", "Raw 7-category shares (listed 2001–21): " + ", ".join(f"{k} {v}" for k, v in Ex["ours_listed_2001_2021_majority_vote"]["raw_7_categories"].items()),
      "Mention flags (listed 2001–21): " + ", ".join(f"{k} {v}" for k, v in Ex["ours_listed_2001_2021_majority_vote"]["mentions"].items()), "",
      "## Expectation check", "```", json.dumps(chk, indent=1), "```"]
open(f"{P}/docs/VALIDITY_BIAS_AUDIT_NOTE_{STAMP}.md", "w", encoding="utf-8").write("\n".join(L))
print(json.dumps(chk, indent=1)); print("written", f"results/validity_bias_audit_{STAMP}.json")
