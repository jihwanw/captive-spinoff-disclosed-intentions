#!/usr/bin/env python3
"""29_industry_fe_firm_clusters.py — the paper's regressions re-estimated with industry fixed effects and firm-clustered standard errors
(resubmission strategy §2 "weak and limited regression models": the CGIR editor's first design item).

Industry: GICS sector / industry codes of the parent from Compustat Global g_company (gsector 'GIC Sectors', gind 'GIC Industries' —
catalog comments in data/raw/compustat_global_kr/dictionary_comp_global_daily.json), linked by gvkey (ISIN 'KR7' + stock code, the rule
of 17_price_panel_compustat.py). g_company is a header table: the codes are the parent's CURRENT classification, not the one at the
event date — recorded as a limitation; a time-varying alternative (g_funda.sich, 84% of firm-years) is kept for a later pass.
Clusters: the parent (stock code; 459 parents for 576 scored return events — 84 parents have 2–5 events), the announcement year, and
two-way parent × year (Cameron–Gelbach–Miller: V_firm + V_year − V_white, all HC0-based so the three are comparable). The published
HC1 and year-cluster p-values are re-computed with statsmodels as the identity control (must equal Table 6 / 19_bhar_controls.py).
Re-estimated: Table 6 (returns on S, spec 3), Table 7 (returns on realised early disposal), Table 10 rows (block regressions of
21_governance_cross_section.py), and the Gate-1 disposal logit with industry dummies.
Pre-registered expectations (2026-11-10, before the run; outside = bug first):
  rank_1y coefficient on S with sector FE in [-0.28, -0.12] (published -0.195) and firm-cluster p < 0.05; two-way p < 0.10;
  ann_car coefficient on S in [0.00, 0.06] (significance may drop); Table 7 early-disposal coefficient stays negative;
  block regressions keep their signs (S on block < 0, rank on block > 0); Gate-1 logit coefficient on S changes by < 25% with sector FE.
Outputs: results/industry_fe_firm_clusters_<date>.json, docs/INDUSTRY_FE_NOTE_<date>.md
"""
import os, json, glob, datetime as dt, numpy as np, pandas as pd
import statsmodels.api as sm
from scipy import stats

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); STAMP = dt.date.today().strftime("%Y%m%d")
RAW = f"{P}/data/raw/compustat_global_kr"
R = {"generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "expectations_preregistered": __doc__.split("Pre-registered expectations")[1].split("Outputs:")[0].strip()}

# ---------------- data
co = pd.read_csv(sorted(glob.glob(f"{P}/data/processed/bhar_controls_events_*.csv"))[-1], dtype={"rcept_no": str, "stock_code": str, "gvkey": str})
gco = pd.read_parquet(f"{RAW}/g_company_kr.parquet")[["gvkey", "sic", "gsector", "ggroup", "gind", "conm"]]
co = co.merge(gco, on="gvkey", how="left")
for c in ("gsector", "gind", "sic"): co[c] = co[c].astype("string").fillna("unknown")
co["sic2"] = co.sic.str[:2]
co["firm"] = co.stock_code.fillna(co.corp_name)
own = pd.DataFrame(json.load(open(f"{P}/data/processed/ownership_pre_event_all.json", encoding="utf-8")))
own = own[~own.disagree.astype(bool)][["rcept_no", "block_pct"]]
co = co.merge(own, on="rcept_no", how="left"); co["block"] = co.block_pct / 100
M = "bhar_madj_p2_p250"; co["rank1y"] = co.groupby("year")[M].rank(pct=True)
co["early"] = co.timing.map({"early_le1y": 1.0, "never": 0.0, "late_ge2y": 0.0})
R["sample"] = {"scored_events": int(co.p_llm.notna().sum()), "parents": int(co[co.p_llm.notna()].firm.nunique()), "events_per_parent": co[co.p_llm.notna()].firm.value_counts().value_counts().sort_index().to_dict(),
               "gsector_groups": co[co.p_llm.notna()].gsector.value_counts().to_dict(), "gind_groups": int(co[co.p_llm.notna()].gind.nunique()), "sic2_groups": int(co[co.p_llm.notna()].sic2.nunique()),
               "industry_source": "Compustat Global g_company (current classification), linked by gvkey", "with_block": int(co.block.notna().sum())}
BASE = ["log_me", "log_bm", "mom6", "kosdaq"]; FIL = ["rel_size", "surv_lev", "relisting"]; IMP = ["log_me", "log_bm", "mom6", "rel_size", "surv_lev"]

# ---------------- estimation helpers
def design(d, xs):
    X = d[xs].astype(float).copy()
    for c in IMP:
        if c in X and X[c].isna().any(): X[c + "_miss"] = X[c].isna().astype(float); X[c] = X[c].fillna(X[c].median())
    for c in X.columns:
        if c not in ("kosdaq", "relisting", "early", "low_block", "early_x_low", "score_x_low") and not c.endswith("_miss"): X[c] = X[c].clip(X[c].quantile(0.01), X[c].quantile(0.99))
    return X

def sandwich(X, e, groups):
    """HC0-type cluster sandwich: (X'X)^-1 (sum_g X_g' e_g e_g' X_g) (X'X)^-1; groups=None -> White (each obs its own cluster)."""
    Xm = X.values; bread = np.linalg.pinv(Xm.T @ Xm)
    if groups is None: meat = (Xm * (e[:, None] ** 2)).T @ Xm
    else:
        meat = np.zeros((Xm.shape[1], Xm.shape[1]))
        for g in np.unique(groups):
            idx = groups == g; s = Xm[idx].T @ e[idx]; meat += np.outer(s, s)
    return bread @ meat @ bread

def reg(d, y, xs, fe_year=True, fe_ind=None, impute=IMP):
    d = d.dropna(subset=[y] + [x for x in xs if x not in impute]).copy(); X = design(d, xs)
    if fe_year: X = pd.concat([X, pd.get_dummies(d.year, prefix="y", drop_first=True, dtype=float)], axis=1)
    if fe_ind: X = pd.concat([X, pd.get_dummies(d[fe_ind], prefix=fe_ind, drop_first=True, dtype=float)], axis=1)
    X = sm.add_constant(X); X = X.loc[:, X.nunique() > 1] if "const" not in X else pd.concat([X[["const"]], X.drop(columns="const").loc[:, X.drop(columns="const").nunique() > 1]], axis=1)
    yv = d[y].astype(float).values; ols = sm.OLS(yv, X).fit(); b = ols.params; e = ols.resid.values; n, k = X.shape
    hc1 = sm.OLS(yv, X).fit(cov_type="HC1"); cly = sm.OLS(yv, X).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.year)[0]})
    firm = pd.factorize(d.firm)[0]; year = pd.factorize(d.year)[0]
    V_f = sandwich(X, e, firm); V_y = sandwich(X, e, year); V_w = sandwich(X, e, None); V_2 = V_f + V_y - V_w
    out = {"n": n, "k": k, "r2": round(float(ols.rsquared), 3), "n_firms": int(len(np.unique(firm))), "n_years": int(len(np.unique(year)))}
    for v in xs:
        if v not in X.columns: continue
        j = list(X.columns).index(v); se_f, se_2 = float(np.sqrt(V_f[j, j])), float(np.sqrt(max(V_2[j, j], 0)))
        G = len(np.unique(firm))
        out[v] = {"coef": round(float(b[v]), 4), "se_hc1": round(float(hc1.bse[v]), 4), "p_hc1": round(float(hc1.pvalues[v]), 3), "p_cluster_year_sm": round(float(cly.pvalues[v]), 3),
                  "se_firm_hc0": round(se_f, 4), "p_firm_t": round(float(2 * stats.t.sf(abs(b[v] / se_f), G - 1)), 3),
                  "se_twoway_cgm": round(se_2, 4) if se_2 > 0 else None, "p_twoway_t": (round(float(2 * stats.t.sf(abs(b[v] / se_2), min(G, len(np.unique(year))) - 1)), 3) if se_2 > 0 else None)}
    return out

FE_SETS = {"yearFE_published": dict(fe_year=True, fe_ind=None), "year+gsector": dict(fe_year=True, fe_ind="gsector"), "year+gind": dict(fe_year=True, fe_ind="gind"), "year+sic2": dict(fe_year=True, fe_ind="sic2")}
d_all = co.dropna(subset=["p_llm"]).copy()

# ---------------- Table 6: returns on the signal, spec 3 controls
R["table6_returns_on_signal"] = {}
for yv, lab in ((M, "bhar_1y"), ("rank1y", "rank_1y"), ("car_mm_p2_p250", "carmm_1y"), ("car_mm_m1_p1", "ann_car")):
    R["table6_returns_on_signal"][lab] = {fs: reg(d_all, yv, ["p_llm"] + BASE + FIL, **kw) for fs, kw in FE_SETS.items()}
    s = R["table6_returns_on_signal"][lab]; print(f"[T6 {lab}] " + " | ".join(f"{fs}: {v['p_llm']['coef']:+.4f} (hc1 p {v['p_llm']['p_hc1']}, firm p {v['p_llm']['p_firm_t']}, 2way p {v['p_llm']['p_twoway_t']}) n {v['n']} k {v['k']}" for fs, v in s.items()), flush=True)

# ---------------- Table 7: realised early disposal
dl = d_all.dropna(subset=["early"]).copy()
R["table7_realized_early_disposal"] = {}
for yv, lab in ((M, "bhar_1y"), ("rank1y", "rank_1y")):
    R["table7_realized_early_disposal"][lab] = {fs: {"early_plus_controls": reg(dl, yv, ["early"] + BASE + FIL, **kw), "score_and_early": reg(dl, yv, ["p_llm", "early"] + BASE + FIL, **kw)} for fs, kw in FE_SETS.items()}
    print(f"[T7 {lab}] " + " | ".join(f"{fs}: early {v['early_plus_controls']['early']['coef']:+.4f} (firm p {v['early_plus_controls']['early']['p_firm_t']}); joint early {v['score_and_early']['early']['coef']:+.4f} S {v['score_and_early']['p_llm']['coef']:+.4f}" for fs, v in R["table7_realized_early_disposal"][lab].items()), flush=True)

# ---------------- Table 10: block regressions (21's rows)
db = d_all.dropna(subset=["block"]).copy(); db["low_block"] = (db.block < db.block.median()).astype(float); db["score_x_low"] = db.p_llm * db.low_block; db["early_x_low"] = db.early * db.low_block
R["table10_block"] = {}
for fs, kw in FE_SETS.items():
    R["table10_block"][fs] = {"score_on_block_controls": reg(db, "p_llm", ["block"] + BASE + FIL, **kw), "disposed_on_block_controls": reg(db, "disposed", ["block"] + BASE + FIL, **kw),
                              "early_on_block_controls": reg(db.dropna(subset=["early"]), "early", ["block"] + BASE + FIL, **kw), "early_on_block_and_score": reg(db.dropna(subset=["early"]), "early", ["block", "p_llm"] + BASE + FIL, **kw),
                              "rank_on_block_controls": reg(db, "rank1y", ["block"] + BASE + FIL, **kw), "anncar_on_block_controls": reg(db, "car_mm_m1_p1", ["block"] + BASE, **kw),
                              "rank_early_x_low_block": reg(db.dropna(subset=["early"]), "rank1y", ["early", "low_block", "early_x_low"] + BASE + FIL, **kw)}
    v = R["table10_block"][fs]; print(f"[T10 {fs}] S~block {v['score_on_block_controls']['block']['coef']:+.3f} (firm p {v['score_on_block_controls']['block']['p_firm_t']}) | rank~block {v['rank_on_block_controls']['block']['coef']:+.3f} (firm p {v['rank_on_block_controls']['block']['p_firm_t']}) | early~block {v['early_on_block_controls']['block']['coef']:+.3f} | inter {v['rank_early_x_low_block']['early_x_low']['coef']:+.3f} (p {v['rank_early_x_low_block']['early_x_low']['p_firm_t']})", flush=True)

# ---------------- Gate-1 disposal logit with industry dummies (the sample of 15, by executing its head)
src = open(f"{P}/code/15_gate1_pooled.py", encoding="utf-8").read(); head = src.split("\ndef panel(")[0]
ns = {"__file__": f"{P}/code/15_gate1_pooled.py", "__name__": "gate1_sample"}; exec(compile(head, "15_head", "exec"), ns)
g1, FIN, design15 = ns["df"], ns["FIN"], ns["design"]
g1 = g1.merge(co[["rcept_no", "gsector", "gind", "sic2", "firm"]].drop_duplicates("rcept_no"), on="rcept_no", how="left")
for c in ("gsector", "gind", "sic2"): g1[c] = g1[c].astype("string").fillna("unknown")
g1["firm"] = g1.firm.fillna(g1.rcept_no)
def drop_collinear(X):
    """Remove columns that are linear combinations of earlier ones (QR with pivoting); keeps the design full rank."""
    keep = []; cur = None
    for c in X.columns:
        trial = X[keep + [c]].values.astype(float)
        if np.linalg.matrix_rank(trial) == trial.shape[1]: keep.append(c)
    return X[keep], [c for c in X.columns if c not in keep]
def logit_S(d, fe_ind):
    X = design15(d, FIN).copy(); X["logit_S"] = np.log(d.p_llm.clip(0.01, 0.99) / (1 - d.p_llm.clip(0.01, 0.99)))
    # no separate period dummy: put_option_yes_miss (field exists only 2017+) is already the 2001–2016 indicator
    if fe_ind: X = pd.concat([X, pd.get_dummies(d[fe_ind], prefix=fe_ind, drop_first=True, dtype=float)], axis=1)
    X = sm.add_constant(X.loc[:, X.nunique() > 1]); X, dropped = drop_collinear(X.astype(float))
    m = sm.Logit(d.y.values, X).fit(method="bfgs", maxiter=5000, gtol=1e-6, disp=0)
    # firm-clustered sandwich by hand: bread = inverse Hessian; meat = sum over clusters of score sums
    pr = np.asarray(m.predict(X), dtype=float); Xm = X.values.astype(float); H = (Xm * (pr * (1 - pr))[:, None]).T @ Xm; bread = np.linalg.pinv(H)
    sc = Xm * (np.asarray(d.y.values, dtype=float) - pr)[:, None]; g = pd.factorize(d.firm)[0]; meat = np.zeros_like(H)
    for gi in np.unique(g): v = sc[g == gi].sum(axis=0); meat += np.outer(v, v)
    V = bread @ meat @ bread; j = list(X.columns).index("logit_S"); se = float(np.sqrt(V[j, j])); G = len(np.unique(g))
    return {"n": int(len(d)), "k": int(X.shape[1]), "dropped_collinear": dropped, "coef_logit_S": round(float(m.params["logit_S"]), 3), "se_firm_cluster": round(se, 3),
            "p_firm_cluster": float(2 * stats.t.sf(abs(m.params["logit_S"] / se), G - 1)), "pseudo_r2": round(float(m.prsquared), 3), "converged": bool(m.mle_retvals.get("converged", True))}
R["gate1_logit_industry"] = {fs: logit_S(g1, kw["fe_ind"]) for fs, kw in FE_SETS.items()}
print("[Gate-1 logit] " + " | ".join(f"{fs}: S {v['coef_logit_S']} (firm p {v['p_firm_cluster']:.2e}) k {v['k']}" for fs, v in R["gate1_logit_industry"].items()), flush=True)
# industry-demeaned S: does the signal order disposals WITHIN sector? (AUC of S minus sector mean)
g1["S_dm"] = g1.p_llm - g1.groupby("gsector").p_llm.transform("mean")
from sklearn.metrics import roc_auc_score
R["gate1_within_sector_auc"] = {"auc_S": round(float(roc_auc_score(g1.y, g1.p_llm)), 3), "auc_S_sector_demeaned": round(float(roc_auc_score(g1.y, g1.S_dm)), 3),
                                "auc_by_sector": {str(s): {"n": int(len(g)), "auc": (round(float(roc_auc_score(g.y, g.p_llm)), 3) if g.y.nunique() == 2 and len(g) >= 20 else None)} for s, g in g1.groupby("gsector")}}

# ---------------- identity + expectation checks
pub = json.load(open(sorted(glob.glob(f"{P}/results/bhar_controls_*.json"))[-1]))["specs"]
t6 = R["table6_returns_on_signal"]
R["identity_control"] = {"rank_1y_published": pub["bhar1y_rank"]["3_plus_filing_controls"]["p_llm"], "rank_1y_here_yearFE": t6["rank_1y"]["yearFE_published"]["p_llm"],
                         "ann_car_published": pub["ann_car"]["3_plus_filing_controls"]["p_llm"], "ann_car_here_yearFE": t6["ann_car"]["yearFE_published"]["p_llm"]}
R["identity_control"]["pass"] = bool(abs(R["identity_control"]["rank_1y_published"]["coef"] - R["identity_control"]["rank_1y_here_yearFE"]["coef"]) < 1e-3 and abs(R["identity_control"]["ann_car_published"]["coef"] - R["identity_control"]["ann_car_here_yearFE"]["coef"]) < 1e-3)
rs = t6["rank_1y"]["year+gsector"]["p_llm"]; ac = t6["ann_car"]["year+gsector"]["p_llm"]; e7 = R["table7_realized_early_disposal"]["rank_1y"]["year+gsector"]["early_plus_controls"]["early"]
b10 = R["table10_block"]["year+gsector"]; gl = R["gate1_logit_industry"]
R["expectation_check"] = {"identity_pass": R["identity_control"]["pass"], "rank_S_sector_in_[-0.28,-0.12]": bool(-0.28 <= rs["coef"] <= -0.12), "rank_S_firm_p<0.05": bool(rs["p_firm_t"] < 0.05), "rank_S_twoway_p<0.10": bool(rs["p_twoway_t"] is not None and rs["p_twoway_t"] < 0.10),   # (a p of 0.0 is falsy in Python — do not use `or`)
                          "anncar_S_sector_in_[0,0.06]": bool(0 <= ac["coef"] <= 0.06), "table7_early_negative": bool(e7["coef"] < 0),
                          "block_signs_kept": bool(b10["score_on_block_controls"]["block"]["coef"] < 0 and b10["rank_on_block_controls"]["block"]["coef"] > 0),
                          "gate1_S_change_lt_25pct": bool(abs(gl["year+gsector"]["coef_logit_S"] / gl["yearFE_published"]["coef_logit_S"] - 1) < 0.25)}
print("identity:", R["identity_control"]["pass"], "| expectation check:", R["expectation_check"], flush=True)
json.dump(R, open(f"{P}/results/industry_fe_firm_clusters_{STAMP}.json", "w"), ensure_ascii=False, indent=1, default=float)

# ---------------- note
def t6row(lab, fs): v = t6[lab][fs]["p_llm"]; return f"| {lab} | {fs} | {t6[lab][fs]['n']} | {t6[lab][fs]['k']} | {v['coef']:+.4f} | {v['p_hc1']} | {v['p_cluster_year_sm']} | {v['p_firm_t']} | {v['p_twoway_t']} |"
md = [f"# Industry fixed effects and firm clusters ({STAMP})", "", f"Source `results/industry_fe_firm_clusters_{STAMP}.json` (`code/29_industry_fe_firm_clusters.py`). Sample: {R['sample']['scored_events']} scored return events, {R['sample']['parents']} parents (events per parent {R['sample']['events_per_parent']}); GICS sectors {R['sample']['gsector_groups']}; {R['sample']['gind_groups']} GICS industries; {R['sample']['sic2_groups']} two-digit SIC groups. Industry = parent's current Compustat classification (limitation recorded).", "",
      f"Identity control (year FE + HC1 reproduces 19/Table 6): pass = {R['identity_control']['pass']}.", "",
      "## Table 6 — returns on the signal (spec 3 controls)", "", "| Outcome | FE | n | k | coef on S | p HC1 | p year-cl | p firm-cl | p two-way |", "|---|---|---|---|---|---|---|---|---|"] + [t6row(lab, fs) for lab in ("rank_1y", "bhar_1y", "carmm_1y", "ann_car") for fs in FE_SETS] + [
      "", "## Table 7 — realised early disposal (rank_1y)", ""] + [f"- {fs}: early {v['early_plus_controls']['early']['coef']:+.4f} (firm-cl p {v['early_plus_controls']['early']['p_firm_t']}, two-way p {v['early_plus_controls']['early']['p_twoway_t']}); jointly: early {v['score_and_early']['early']['coef']:+.4f} (p {v['score_and_early']['early']['p_firm_t']}), S {v['score_and_early']['p_llm']['coef']:+.4f} (p {v['score_and_early']['p_llm']['p_firm_t']})" for fs, v in R["table7_realized_early_disposal"]["rank_1y"].items()] + [
      "", "## Table 10 — block regressions", ""] + [f"- {fs}: S~block {v['score_on_block_controls']['block']['coef']:+.3f} (firm p {v['score_on_block_controls']['block']['p_firm_t']}); disposed~block {v['disposed_on_block_controls']['block']['coef']:+.3f} (p {v['disposed_on_block_controls']['block']['p_firm_t']}); early~block {v['early_on_block_controls']['block']['coef']:+.3f} (p {v['early_on_block_controls']['block']['p_firm_t']}); early~block+S: block {v['early_on_block_and_score']['block']['coef']:+.3f}, S {v['early_on_block_and_score']['p_llm']['coef']:+.3f}; rank~block {v['rank_on_block_controls']['block']['coef']:+.3f} (p {v['rank_on_block_controls']['block']['p_firm_t']}); annCAR~block {v['anncar_on_block_controls']['block']['coef']:+.4f} (p {v['anncar_on_block_controls']['block']['p_firm_t']}); rank: early {v['rank_early_x_low_block']['early']['coef']:+.3f}, low {v['rank_early_x_low_block']['low_block']['coef']:+.3f}, early×low {v['rank_early_x_low_block']['early_x_low']['coef']:+.3f} (p {v['rank_early_x_low_block']['early_x_low']['p_firm_t']})" for fs, v in R["table10_block"].items()] + [
      "", "## Gate-1 disposal logit with industry dummies (firm-clustered)", ""] + [f"- {fs}: coef on logit(S) {v['coef_logit_S']} (se {v['se_firm_cluster']}, p {v['p_firm_cluster']:.2e}), k {v['k']}, pseudo-R² {v['pseudo_r2']}" for fs, v in gl.items()] + [
      f"- within-sector ordering: AUC of S {R['gate1_within_sector_auc']['auc_S']}, of sector-demeaned S {R['gate1_within_sector_auc']['auc_S_sector_demeaned']}; by sector {R['gate1_within_sector_auc']['auc_by_sector']}", "",
      "## Expectation check", "", str(R["expectation_check"]), "",
      "## Caveats recorded", "", "- GICS codes are the parent's current classification (g_company header), not at the event date; firms that changed sector are classified by their later sector.",
      "- Two-way clusters use the Cameron–Gelbach–Miller formula with HC0 components and a t(min(G_firm, G_year) − 1) reference; firm clusters use t(G_firm − 1). With 60 GICS industries and 559 events the gind specification spends ~60 degrees of freedom on dummies.",
      "- Three events have no Compustat sector ('unknown' group)."]
open(f"{P}/docs/INDUSTRY_FE_NOTE_{STAMP}.md", "w").write("\n".join(md) + "\n"); print(f"saved results/industry_fe_firm_clusters_{STAMP}.json, docs/INDUSTRY_FE_NOTE_{STAMP}.md")
