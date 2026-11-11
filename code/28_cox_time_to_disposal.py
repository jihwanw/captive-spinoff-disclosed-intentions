#!/usr/bin/env python3
"""28_cox_time_to_disposal.py — time to disposal as a survival problem (resubmission strategy §2 "data bias": label truncation).

The paper's labels are right-censored at the last annual report read (FY2025 at the latest, earlier for parents that stopped
filing) and the published tests used a clean-label filter plus an early/late split. Here the outcome is the TIME from the division
fiscal year to the first fiscal year whose annual report shows the subsidiary sold, listed or diluted (first_change_fy), with retained
subsidiaries censored at the last fiscal year observed. Durations are report years (0 = the division year itself), so ties are heavy
and the primary estimate is a discrete-time hazard model; a Cox model with Efron ties is the second, independent path.

Samples:
  A (primary)  annual-report-labelled events (label_source annual_report_llm / tracker_corrected_by_annual_report): disposed with
               first_change_fy; retained_100 censored at max(by_fiscal_year.fy). Merged-back / liquidated excluded (as in the paper).
  B            A + tracker-labelled retained events censored at the tracker's last_period, + tracker-labelled disposed events with the
               event placed at the tracker's last_period (an UPPER bound on their timing: a bounding sensitivity, not an estimate).
  C            A + merged-back / liquidated treated as censored at their first_change_fy (competing outcome as censoring).
Covariates: S = two-model identified disposal signal (the paper's score; scores() of 15_gate1_pooled.py), controlling block (pp/10,
ownership_pre_event_all.json, disagreements dropped), KOSDAQ, the Gate-1 filing financials (design() of 15: median imputation + flags)
where the event is in the Gate-1 sample, otherwise imputed with a flag; strata / dummies for period (2001–08, 2009–16, 2017+).
Pre-registered expectations (2026-11-10, before the run; outside = bug first):
  HR(S) per unit of S (0 -> 1) in [2, 20] and per SD in [1.3, 2.5]; HR(block) per 10 pp in [0.85, 1.02];
  permuted-S HR interval covers 1; AUC of S for early (T <= 1) vs never on sample A within 0.78 ± 0.04 (published 0.780);
  synthetic known-answer (true HR 4, grouped years, random censoring): Cox and cloglog both within [3.2, 5.0];
  the S effect is likely front-loaded (PH test may fail): report the hazard ratio separately for t = 0 and t >= 1.
Outputs: results/cox_time_to_disposal_<date>.json, docs/COX_NOTE_<date>.md
"""
import os, re, json, glob, datetime as dt, numpy as np, pandas as pd
import statsmodels.api as sm
from sklearn.metrics import roc_auc_score
from lifelines import CoxPHFitter, KaplanMeierFitter
from lifelines.statistics import proportional_hazard_test

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); STAMP = dt.date.today().strftime("%Y%m%d")
DISP = {"ipo_listed", "majority_disposed", "partial_sale"}; COMPETING = {"merged_back_into_parent", "liquidated"}
R = {"generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "expectations_preregistered": __doc__.split("Pre-registered expectations")[1].split("Outputs:")[0].strip()}

# ---- Gate-1 machinery (scores, FIN design) by executing 15's own head
src = open(f"{P}/code/15_gate1_pooled.py", encoding="utf-8").read(); head = src.split("\ndef panel(")[0]
ns = {"__file__": f"{P}/code/15_gate1_pooled.py", "__name__": "gate1_sample"}; exec(compile(head, "15_head", "exec"), ns)
g1, FIN, design, scores = ns["df"], ns["FIN"], ns["design"], ns["scores"]
S_all = {}
for pat_c, pat_g in ((f"{P}/results/llm_judge/anthropic__identified*.jsonl", f"{P}/results/llm_judge/openai__identified*.jsonl"), (f"{P}/results/llm_judge_2001_2016/anthropic__identified*.jsonl", f"{P}/results/llm_judge_2001_2016/openai__identified*.jsonl")):
    c, g = scores(pat_c), scores(pat_g)
    for k in set(c) & set(g): S_all[k] = (c[k] + g[k]) / 2
own = {r["rcept_no"]: r for r in json.load(open(f"{P}/data/processed/ownership_pre_event_all.json", encoding="utf-8"))}

# ---- event table
def last_fy(r):
    fys = [x["fy"] for x in (r.get("by_fiscal_year") or []) if isinstance(x.get("fy"), int)]; return max(fys) if fys else None
def tracker_last(r):
    ys = [int(re.sub(r"\D", "", p.get("last_period") or "") or 0) for p in (r.get("per_new_company") or [])]; ys = [y for y in ys if y > 1990]; return max(ys) if ys else None
rows = []
for period_src, f in (("2017+", "carveout_disposal_tracking_v4.json"), ("2001-2016", "carveout_disposal_tracking_2001_2016.json")):
    for r in json.load(open(f"{P}/data/processed/{f}", encoding="utf-8")):
        o = own.get(r["rcept_no"]) or {}
        rows.append({"rcept_no": r["rcept_no"], "corp_code": r["corp_code"], "corp_name": r["corp_name"], "period_src": period_src, "division_year": r.get("division_year"), "outcome": r["outcome"],
                     "label_source": r.get("label_source"), "first_change_fy": r.get("first_change_fy"), "last_fy": last_fy(r), "tracker_last": tracker_last(r),
                     "kosdaq": int(r.get("corp_cls") == "K"), "S": S_all.get(r["rcept_no"]),
                     "block": (o.get("block_pct") if not o.get("disagree") else None)})
ev = pd.DataFrame(rows); ev["division_year"] = pd.to_numeric(ev.division_year, errors="coerce")
ev["period"] = pd.cut(ev.division_year, [2000, 2008, 2016, 2026], labels=["2001-2008", "2009-2016", "2017-2026"]).astype(str)
ev["ar"] = ev.label_source.isin(["annual_report_llm", "tracker_corrected_by_annual_report"])
ev = ev.merge(g1[["rcept_no"] + [c for c in FIN if c != "kosdaq"]].drop_duplicates("rcept_no"), on="rcept_no", how="left")   # Gate-1 financials where present (kosdaq already from corp_cls)
ev["gate1"] = ev.rcept_no.isin(g1.rcept_no)

def build(sample):
    d = ev.copy()
    if sample == "A":
        d = d[d.ar & (d.outcome.isin(DISP) | (d.outcome == "retained_100"))].copy()
        d["event"] = d.outcome.isin(DISP).astype(int); d["T"] = np.where(d.event == 1, d.first_change_fy - d.division_year, d.last_fy - d.division_year)
    elif sample == "B":
        a = build("A")
        t = ev[(~ev.ar) & (ev.outcome.isin(DISP) | (ev.outcome == "retained_100")) & ev.tracker_last.notna()].copy()
        t["event"] = t.outcome.isin(DISP).astype(int); t["T"] = t.tracker_last - t.division_year
        d = pd.concat([a, t], ignore_index=True)
    elif sample == "C":
        a = build("A")
        c = ev[ev.ar & ev.outcome.isin(COMPETING)].copy(); c["event"] = 0; c["T"] = np.where(c.first_change_fy.notna(), c.first_change_fy - c.division_year, c.last_fy - c.division_year)
        d = pd.concat([a, c], ignore_index=True)
    d = d.dropna(subset=["T", "S"]).copy(); d = d[d["T"] >= 0]; d["T"] = d["T"].astype(int); d["T1"] = d["T"] + 1   # +1: rank-based Cox is unchanged, lifelines wants > 0
    return d.reset_index(drop=True)

def covariates(d, with_block):
    X = design(d, FIN).copy(); X.columns = [c.replace("-", "_") for c in X.columns]
    X["S"] = d.S.values
    if with_block: X["block10"] = d.block.values / 10.0; X["block10_miss"] = X.block10.isna().astype(float); X["block10"] = X.block10.fillna(X.block10.median())
    for p in ["2009-2016", "2017-2026"]: X[f"per_{p[:4]}"] = (d.period.values == p).astype(float)
    return X.loc[:, X.nunique() > 1]

def cox(d, X, strata_col=None):
    df = pd.concat([X.reset_index(drop=True), d[["T1", "event", "corp_code", "period"]].reset_index(drop=True)], axis=1)
    cols = [c for c in X.columns if not c.startswith("per_")] if strata_col else list(X.columns)
    cph = CoxPHFitter(penalizer=0.0)
    cph.fit(df[cols + ["T1", "event", "corp_code"] + ([strata_col] if strata_col else [])], duration_col="T1", event_col="event", cluster_col="corp_code", strata=[strata_col] if strata_col else None, robust=True)
    s = cph.summary
    out = {"n": int(len(df)), "events": int(df.event.sum()), "concordance": round(float(cph.concordance_index_), 3), "partial_ll": round(float(cph.log_likelihood_), 2),
           "hr": {v: {"hr": round(float(np.exp(s.loc[v, "coef"])), 3), "ci95": [round(float(np.exp(s.loc[v, "coef lower 95%"])), 3), round(float(np.exp(s.loc[v, "coef upper 95%"])), 3)], "p": float(s.loc[v, "p"])} for v in s.index}}
    try:
        ph = proportional_hazard_test(cph, df[cols + ["T1", "event", "corp_code"] + ([strata_col] if strata_col else [])], time_transform="rank")
        out["ph_test_rank"] = {v: {"stat": round(float(ph.summary.loc[v, "test_statistic"]), 2), "p": round(float(ph.summary.loc[v, "p"]), 3)} for v in ph.summary.index if v in ("S", "block10")}
    except Exception as e: out["ph_test_rank"] = f"failed: {e}"
    return out, cph

def discrete(d, X, tv=False):
    """Person-period cloglog hazard: rows t = 0..T per event; event indicator at t = T if disposed. Duration dummies t=0..4, 5+."""
    rows = []
    for i, (T, e) in enumerate(zip(d["T"].values, d.event.values)):
        for t in range(int(T) + 1): rows.append({"i": i, "t": min(t, 5), "t_raw": t, "y": int(e == 1 and t == T)})
    pp = pd.DataFrame(rows); Z = X.reset_index(drop=True).iloc[pp.i.values].reset_index(drop=True)
    D = pd.get_dummies(pp.t, prefix="t", dtype=float); Z = pd.concat([Z, D], axis=1)
    if tv: Z["S_x_tge1"] = Z.S * (pp.t_raw.values >= 1)
    groups = d.corp_code.values[pp.i.values]
    m = sm.GLM(pp.y.values, Z, family=sm.families.Binomial(link=sm.families.links.CLogLog())).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(groups)[0]}, maxiter=200)
    keep = [c for c in Z.columns if c in ("S", "S_x_tge1", "block10", "kosdaq") or c.startswith("t_")]
    out = {"person_years": int(len(pp)), "events": int(pp.y.sum()), "exp_coef": {c: {"exp_coef": round(float(np.exp(m.params[c])), 3), "ci95": [round(float(np.exp(m.conf_int().loc[c, 0])), 3), round(float(np.exp(m.conf_int().loc[c, 1])), 3)], "p": float(m.pvalues[c])} for c in keep},
           "hazard_by_year_at_mean_x": None}
    # baseline hazard by duration year at covariate means (cloglog -> hazard)
    xm = Z.mean(); hz = {}
    for t in range(6):
        x = xm.copy(); 
        for k in range(6): x[f"t_{k}"] = float(k == t)
        hz[str(t) if t < 5 else "5+"] = round(float(1 - np.exp(-np.exp((x * m.params).sum()))), 3)
    out["hazard_by_year_at_mean_x"] = hz
    return out

# ---- samples and models
R["samples"] = {}; R["models"] = {}
for smp in ("A", "B", "C"):
    d = build(smp); R["samples"][smp] = {"n": int(len(d)), "events": int(d.event.sum()), "by_period": d.groupby("period").agg(n=("event", "size"), events=("event", "sum")).to_dict(orient="index"),
                                        "T_distribution_events": {int(k): int(v) for k, v in d[d.event == 1]["T"].value_counts().sort_index().items()}, "T_distribution_censored": {int(k): int(v) for k, v in d[d.event == 0]["T"].value_counts().sort_index().items()},
                                        "with_block": int(d.block.notna().sum()), "in_gate1": int(d.gate1.sum())}
    X = covariates(d, with_block=True)
    R["models"][smp] = {"cox_strata_period": cox(d, X, strata_col="period")[0], "cloglog_period_dummies": discrete(d, X), "cloglog_time_varying_S": discrete(d, X, tv=True)}
    if smp == "A":
        R["models"]["A_no_block"] = {"cox_strata_period": cox(d, covariates(d, with_block=False), strata_col="period")[0]}
        R["models"]["A_gate1_only"] = {"n": int(d.gate1.sum()), "cox_strata_period": cox(d[d.gate1].reset_index(drop=True), covariates(d[d.gate1].reset_index(drop=True), with_block=True), strata_col="period")[0]}
    print(f"[{smp}] n={len(d)} events={int(d.event.sum())} | Cox HR(S)={R['models'][smp]['cox_strata_period']['hr']['S']} | cloglog exp(S)={R['models'][smp]['cloglog_period_dummies']['exp_coef']['S']} | block10={R['models'][smp]['cox_strata_period']['hr'].get('block10')}", flush=True)

# ---- Kaplan–Meier by signal tercile and by block tercile (sample A)
dA = build("A"); km = {}
for var, lab in (("S", "signal"), ("block", "block")):
    dd = dA.dropna(subset=[var]).copy(); dd["terc"] = pd.qcut(dd[var], 3, labels=["low", "mid", "high"])
    km[lab] = {}
    for t_, g in dd.groupby("terc", observed=True):
        kmf = KaplanMeierFitter().fit(g.T1, g.event); sf = kmf.survival_function_
        km[lab][str(t_)] = {"n": int(len(g)), "events": int(g.event.sum()), **{f"disposed_by_year_{y}": round(float(1 - sf.loc[sf.index <= y + 1].iloc[-1, 0]) if (sf.index <= y + 1).any() else np.nan, 3) for y in (0, 1, 3, 5)}, "range": [round(float(g[var].min()), 3), round(float(g[var].max()), 3)]}
R["kaplan_meier_sample_A"] = km
kmf = KaplanMeierFitter().fit(dA.T1, dA.event); sf = kmf.survival_function_
R["kaplan_meier_sample_A"]["all"] = {"n": int(len(dA)), **{f"disposed_by_year_{y}": round(float(1 - sf.loc[sf.index <= y + 1].iloc[-1, 0]), 3) for y in (0, 1, 2, 3, 5, 7)}}

# ---- controls
# (1) identity: AUC of S for early (T<=1) vs never-disposed on sample A
early = dA[(dA.event == 1) & (dA["T"] <= 1)]; never = dA[dA.event == 0]
R["control_identity_early_auc"] = {"auc": round(float(roc_auc_score(np.r_[np.ones(len(early)), np.zeros(len(never))], np.r_[early.S.values, never.S.values])), 3), "n_early": int(len(early)), "n_never": int(len(never)), "published_AUCEarlyPooled": 0.780}
# (2) permuted S
rng = np.random.default_rng(3); Xp = covariates(dA, with_block=True); Xp["S"] = rng.permutation(Xp.S.values); R["control_permuted_S"] = cox(dA, Xp, strata_col="period")[0]["hr"]["S"]
# (3) synthetic known answer: true HR 4 per unit of S, grouped years, random administrative censoring
rng = np.random.default_rng(5); n = 600; s = rng.uniform(0, 1, n); lam = 0.25 * np.exp(np.log(4) * (s - 0.5)); t_true = rng.exponential(1 / lam); cens = rng.uniform(0.5, 9, n)
T = np.floor(np.minimum(t_true, cens)).astype(int); e = (t_true <= cens).astype(int)
dsyn = pd.DataFrame({"T": T, "T1": T + 1, "event": e, "corp_code": np.arange(n), "period": "x", "S": s})
csyn = CoxPHFitter().fit(dsyn[["T1", "event", "S"]], "T1", "event"); hr_c = float(np.exp(csyn.params_["S"]))
rows = [{"i": i, "t": min(t, 5), "y": int(e[i] == 1 and t == T[i])} for i in range(n) for t in range(T[i] + 1)]; pp = pd.DataFrame(rows)
Z = pd.concat([pd.DataFrame({"S": s[pp.i.values]}), pd.get_dummies(pp.t, prefix="t", dtype=float)], axis=1)
msyn = sm.GLM(pp.y.values, Z, family=sm.families.Binomial(link=sm.families.links.CLogLog())).fit(); hr_d = float(np.exp(msyn.params["S"]))
R["control_synthetic_true_hr_4"] = {"n": n, "events": int(e.sum()), "cox_hr": round(hr_c, 3), "cloglog_exp_coef": round(hr_d, 3), "pass": bool(3.2 <= hr_c <= 5.0 and 3.2 <= hr_d <= 5.0)}

# ---- expectation check
A = R["models"]["A"]; hrS = A["cox_strata_period"]["hr"]["S"]["hr"]; sdS = float(dA.S.std()); hrB = A["cox_strata_period"]["hr"].get("block10", {}).get("hr")
R["expectation_check"] = {"HR_S_per_unit_in_[2,20]": bool(2 <= hrS <= 20), "HR_S_per_sd": round(hrS ** sdS, 3), "HR_S_per_sd_in_[1.3,2.5]": bool(1.3 <= hrS ** sdS <= 2.5),
                          "HR_block10_in_[0.85,1.02]": (bool(0.85 <= hrB <= 1.02) if hrB else None), "permuted_S_ci_covers_1": bool(R["control_permuted_S"]["ci95"][0] <= 1 <= R["control_permuted_S"]["ci95"][1]),
                          "early_auc_within_0.04_of_0.78": bool(abs(R["control_identity_early_auc"]["auc"] - 0.78) <= 0.04), "synthetic_pass": R["control_synthetic_true_hr_4"]["pass"]}
print("expectation check:", R["expectation_check"], flush=True)
json.dump(R, open(f"{P}/results/cox_time_to_disposal_{STAMP}.json", "w"), ensure_ascii=False, indent=1, default=float)

# ---- note
def hrrow(name, m, v): h = m["hr"].get(v); return f"| {name} | {v} | {h['hr']} | [{h['ci95'][0]}, {h['ci95'][1]}] | {h['p']:.3g} |" if h else ""
md = [f"# Time to disposal — survival models ({STAMP})", "", f"Source `results/cox_time_to_disposal_{STAMP}.json` (`code/28_cox_time_to_disposal.py`).", "",
      "## Samples", ""] + [f"- {k}: n {v['n']}, events {v['events']}; event-time distribution {v['T_distribution_events']}; censoring times {v['T_distribution_censored']}; with block {v['with_block']}; in Gate-1 {v['in_gate1']}" for k, v in R["samples"].items()] + [
      "", "## Hazard ratios (Cox, Efron ties, strata = period, robust SE clustered by parent)", "", "| Sample | Covariate | HR | 95% CI | p |", "|---|---|---|---|---|"] + \
     [hrrow(f"{s} ({R['models'][s]['cox_strata_period']['n']}/{R['models'][s]['cox_strata_period']['events']})", R["models"][s]["cox_strata_period"], v) for s in ("A", "B", "C") for v in ("S", "block10", "kosdaq") if hrrow("", R["models"][s]["cox_strata_period"], v)] + \
     [hrrow("A, no block", R["models"]["A_no_block"]["cox_strata_period"], "S"), hrrow(f"A, Gate-1 filings only ({R['models']['A_gate1_only']['n']})", R["models"]["A_gate1_only"]["cox_strata_period"], "S"), "",
      f"PH test (rank transform), sample A: {A['cox_strata_period'].get('ph_test_rank')}", "",
      "## Discrete-time cloglog hazard (second path; person-years with duration dummies, period dummies, cluster by parent)", "",
      f"Sample A: exp(coef) S {A['cloglog_period_dummies']['exp_coef']['S']}; block10 {A['cloglog_period_dummies']['exp_coef'].get('block10')}; baseline hazard by duration year at covariate means {A['cloglog_period_dummies']['hazard_by_year_at_mean_x']}.",
      f"Time-varying S: main (t = 0) {A['cloglog_time_varying_S']['exp_coef']['S']}, interaction S × (t ≥ 1) {A['cloglog_time_varying_S']['exp_coef'].get('S_x_tge1')} — HR for t ≥ 1 = product of the two exp(coef).", "",
      "## Kaplan–Meier, sample A", "", json.dumps(R["kaplan_meier_sample_A"], ensure_ascii=False, indent=1), "",
      "## Controls", "", f"- identity (early vs never AUC of S): {R['control_identity_early_auc']}", f"- permuted S: {R['control_permuted_S']}", f"- synthetic true HR 4: {R['control_synthetic_true_hr_4']}", "",
      "## Expectation check", "", str(R["expectation_check"]), "",
      "## Caveats recorded", "", "- Event time is the fiscal year of the first annual report showing the change (report-year granularity); a disposal completed in the division year itself has T = 0.",
      "- Tracker-labelled disposals (77 events, 2017+) have no timing and enter only sample B at the tracker's last observed period, an upper bound — B is a bounding sensitivity, not an estimate.",
      "- Merged-back and liquidated subsidiaries are competing outcomes; the paper excluded them (A) and C treats them as censoring; a cause-specific or Fine–Gray treatment is not attempted with 50-odd competing events.",
      "- Financial covariates exist only for Gate-1 filings (median imputation + flag elsewhere); the 'Gate-1 only' row shows the estimate on complete cases."]
open(f"{P}/docs/COX_NOTE_{STAMP}.md", "w").write("\n".join(md) + "\n"); print(f"saved results/cox_time_to_disposal_{STAMP}.json, docs/COX_NOTE_{STAMP}.md")
