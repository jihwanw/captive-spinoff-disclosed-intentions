#!/usr/bin/env python3
"""22_anonymized_check.py — does the disposal signal survive anonymization (the memorization/look-ahead objection)?

Conditions (04_llm_judge.py): identified = filing text as filed; anonymized = parent and new-company names, group prefixes and dates masked,
and the filing date withheld. A model that "predicts" disposal by recalling what later happened to a named company loses that route under
anonymization; a model that reads the filing keeps its accuracy. Runs: 2017+ both conditions since 2026-10-15/18; 2001–2016 identified
2026-10-18 and anonymized 2026-10-25 (EC2, same 464-event set via --only-from).
Reported, per period and model and for the two-model average: AUC (clean labels: disposed vs retained_100) identified vs anonymized with a
paired bootstrap CI on the difference; Spearman correlation of the two scores; AUC within the events where the identified run admitted
outside knowledge (used_outside_knowledge) vs not. Then the pooled return tests of 18/19 with the ANONYMIZED two-model score as the regressor:
Spearman with 1-year BHAR, within-year rank regression with controls, announcement-CAR slope, early-disposal AUC.
Output: results/anonymized_check_<date>.json
"""
import os, json, glob, importlib.util, datetime as dt, numpy as np, pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score
import statsmodels.api as sm

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def load(name):
    spec = importlib.util.spec_from_file_location(name, f"{P}/code/{name}.py"); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m
b16 = load("16_bhar_by_predicted_disposal")
DISPOSED = b16.DISPOSED; RNG = np.random.default_rng(20261025)

def judgments(pattern):
    d = {}
    for f in glob.glob(pattern):
        for l in open(f, encoding="utf-8"):
            r = json.loads(l); p = (r.get("parsed") or {})
            if isinstance(p.get("p_disposal"), (int, float)): d.setdefault(r["rcept_no"], []).append((float(p["p_disposal"]) / 100, bool(p.get("used_outside_knowledge"))))
    return {k: (float(np.mean([x for x, _ in v])), any(f for _, f in v)) for k, v in d.items()}

def paired_auc_diff(y, a, b, n=5000):
    y, a, b = np.asarray(y), np.asarray(a), np.asarray(b); idx = np.arange(len(y)); out = []
    for _ in range(n):
        s = RNG.choice(idx, len(idx))
        if len(set(y[s])) < 2: continue
        out.append(roc_auc_score(y[s], a[s]) - roc_auc_score(y[s], b[s]))
    return [round(float(np.percentile(out, 2.5)), 3), round(float(np.percentile(out, 97.5)), 3)]

labels = {}
for r in json.load(open(f"{P}/data/processed/carveout_disposal_tracking_2001_2016.json", encoding="utf-8")): labels[r["rcept_no"]] = ("2001-2016", r["outcome"])
for r in json.load(open(f"{P}/data/processed/carveout_disposal_tracking_v4.json", encoding="utf-8")): labels[r["rcept_no"]] = ("2017+", r["outcome"])
res = {"run_at": dt.datetime.now().isoformat(timespec="seconds"), "by_period": {}}
anon_avg = {}
for period, folder in (("2001-2016", "llm_judge_2001_2016"), ("2017+", "llm_judge")):
    blk = {}; sc = {}
    for model, prefix in (("claude", "anthropic"), ("gpt", "openai")):
        ide = judgments(f"{P}/results/{folder}/{prefix}__identified*.jsonl"); ano = judgments(f"{P}/results/{folder}/{prefix}__anonymized*.jsonl")
        sc[model] = (ide, ano)
        keys = [k for k in ide if k in ano and labels.get(k, ("", None))[1] in DISPOSED | {"retained_100"}]
        if len(keys) < 30: blk[model] = {"n_both_conditions_clean": len(keys), "status": "anonymized run incomplete"}; continue
        y = np.array([1 if labels[k][1] in DISPOSED else 0 for k in keys]); pi = np.array([ide[k][0] for k in keys]); pa = np.array([ano[k][0] for k in keys]); flag = np.array([ide[k][1] for k in keys])
        blk[model] = {"n_both_conditions_clean": len(keys), "disposed_share": round(float(y.mean()), 3), "auc_identified": round(float(roc_auc_score(y, pi)), 3), "auc_anonymized": round(float(roc_auc_score(y, pa)), 3),
                      "auc_gap_identified_minus_anonymized": round(float(roc_auc_score(y, pi) - roc_auc_score(y, pa)), 3), "gap_ci95_paired_boot": paired_auc_diff(y, pi, pa),
                      "spearman_identified_vs_anonymized": round(float(stats.spearmanr(pi, pa)[0]), 3), "mean_abs_score_change": round(float(np.abs(pi - pa).mean()), 3),
                      "used_outside_knowledge_share_identified": round(float(flag.mean()), 3),
                      "auc_identified_flagged": round(float(roc_auc_score(y[flag], pi[flag])), 3) if flag.sum() > 10 and len(set(y[flag])) > 1 else None,
                      "auc_anonymized_flagged": round(float(roc_auc_score(y[flag], pa[flag])), 3) if flag.sum() > 10 and len(set(y[flag])) > 1 else None,
                      "auc_identified_unflagged": round(float(roc_auc_score(y[~flag], pi[~flag])), 3) if (~flag).sum() > 10 else None,
                      "auc_anonymized_unflagged": round(float(roc_auc_score(y[~flag], pa[~flag])), 3) if (~flag).sum() > 10 else None}
    # two-model averages where both models have both conditions
    ks = [k for k in sc["claude"][0] if k in sc["claude"][1] and k in sc["gpt"][0] and k in sc["gpt"][1]]
    for k in ks: anon_avg[k] = float(np.mean([sc["claude"][1][k][0], sc["gpt"][1][k][0]]))
    kc = [k for k in ks if labels.get(k, ("", None))[1] in DISPOSED | {"retained_100"}]
    if len(kc) >= 30:
        y = np.array([1 if labels[k][1] in DISPOSED else 0 for k in kc]); pi = np.array([np.mean([sc["claude"][0][k][0], sc["gpt"][0][k][0]]) for k in kc]); pa = np.array([anon_avg[k] for k in kc])
        blk["two_model_average"] = {"n": len(kc), "auc_identified": round(float(roc_auc_score(y, pi)), 3), "auc_anonymized": round(float(roc_auc_score(y, pa)), 3), "gap_ci95_paired_boot": paired_auc_diff(y, pi, pa), "spearman": round(float(stats.spearmanr(pi, pa)[0]), 3)}
    else: blk["two_model_average"] = {"n": len(kc), "status": "incomplete"}
    res["by_period"][period] = blk

# return tests with the anonymized two-model score
co = pd.read_csv(f"{P}/data/processed/bhar_controls_events_20261025.csv", dtype={"rcept_no": str, "stock_code": str}); M = b16.MAIN
co["p_anon"] = co.rcept_no.map(anon_avg); d = co.dropna(subset=["p_anon", M]).copy(); d["rank1y"] = d.groupby("year")[M].rank(pct=True)
def reg(dd, y, xs, controls=()):
    allx = list(xs) + list(controls); dd = dd.dropna(subset=[y] + [x for x in allx if x not in ("log_me", "log_bm", "mom6", "rel_size", "surv_lev")]).copy(); X = dd[allx].astype(float).copy()
    for c in ("log_me", "log_bm", "mom6", "rel_size", "surv_lev"):
        if c in X and X[c].isna().any(): X[c + "_miss"] = X[c].isna().astype(float); X[c] = X[c].fillna(X[c].median())
    X = sm.add_constant(pd.concat([X, pd.get_dummies(dd.year, prefix="y", drop_first=True, dtype=float)], axis=1)); hc = sm.OLS(dd[y].astype(float), X).fit(cov_type="HC1")
    cl = sm.OLS(dd[y].astype(float), X).fit(cov_type="cluster", cov_kwds={"groups": dd.year.astype("category").cat.codes.values})
    return {"n": int(len(dd)), **{v: {"coef": round(float(hc.params[v]), 4), "p_hc1": round(float(hc.pvalues[v]), 3), "p_cluster_year": round(float(cl.pvalues[v]), 3)} for v in xs}}
CTR = ["log_me", "log_bm", "mom6", "kosdaq", "rel_size", "surv_lev", "relisting"]
rt = {"n_with_anonymized_score_and_1y": int(len(d)), "by_period": d.period.value_counts().to_dict(),
      "spearman_anon_score_vs_bhar1y": dict(zip(("rho", "p"), [round(float(x), 3) for x in stats.spearmanr(d.p_anon, d[M])])),
      "spearman_identified_score_vs_bhar1y_same_events": dict(zip(("rho", "p"), [round(float(x), 3) for x in stats.spearmanr(d.p_llm, d[M])])),
      "rank1y_on_anon_score_controls_yearFE": reg(d, "rank1y", ["p_anon"], CTR), "bhar1y_on_anon_score_controls_yearFE": reg(d, M, ["p_anon"], CTR),
      "ann_car_on_anon_score_yearFE": reg(co.dropna(subset=["p_anon"]), "car_mm_m1_p1", ["p_anon"])}
e = co.dropna(subset=["p_anon"]); e = e[e.timing.isin(["early_le1y", "never"])]
if len(e) > 30: rt["anon_score_predicts_early_disposal_auc"] = {"n": int(len(e)), "auc": round(float(roc_auc_score((e.timing == "early_le1y").astype(int), e.p_anon)), 3)}
for per, g in d.groupby("period"):
    rt[f"spearman_anon_{per}"] = dict(zip(("rho", "p", "n"), [round(float(x), 3) for x in stats.spearmanr(g.p_anon, g[M])] + [int(len(g))]))
res["return_tests_with_anonymized_score"] = rt
stamp = dt.date.today().strftime("%Y%m%d"); json.dump(res, open(f"{P}/results/anonymized_check_{stamp}.json", "w"), ensure_ascii=False, indent=1, default=float)
print(json.dumps(res, ensure_ascii=False, indent=1, default=str)); print(f"saved results/anonymized_check_{stamp}.json")
