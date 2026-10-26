#!/usr/bin/env python3
"""08_llm_repeat_stability.py — Is the LLM judge's score stable across independent runs?

Run 1: results/llm_judge/<model>__identified.jsonl (2026-10-15). Run 2: <model>__identified__run2.jsonl (2026-10-17;
same prompt, same texts, same models and effort setting, new sampling). For each model and for the two-model average:
  * Pearson / Spearman correlation and mean absolute difference of p_disposal between runs (0-1 scale)
  * agreement of most_likely_path between runs
  * AUC of run 1, run 2 and the run average against the v3 clean labels (disposed = ipo/majority/partial; retained_100)
    on (a) all clean-labelled events with both runs and (b) the Gate-1 analysis rows (clean label + financial features + both models)
Output: results/llm_repeat_stability_<date>.json
"""
import json, glob, os, datetime as dt, numpy as np, pandas as pd
from scipy.stats import pearsonr, spearmanr
from sklearn.metrics import roc_auc_score

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNS = {"claude": ("anthropic__identified.jsonl", "anthropic__identified__run2.jsonl"), "gpt": ("openai__identified.jsonl", "openai__identified__run2.jsonl")}


def load(fn):
    d = {}
    for l in open(f"{P}/results/llm_judge/{fn}", encoding="utf-8"):
        r = json.loads(l); pr = r.get("parsed") or {}
        if isinstance(pr.get("p_disposal"), (int, float)): d[r["rcept_no"]] = {"p": float(pr["p_disposal"]) / 100, "path": pr.get("most_likely_path"), "conf": pr.get("confidence")}
    return d


v3 = {r["rcept_no"]: r for r in json.load(open(f"{P}/data/processed/carveout_disposal_tracking_v3.json", encoding="utf-8"))}
lab = {k: 1 for k, r in v3.items() if r["outcome"] in ("ipo_listed", "majority_disposed", "partial_sale")}
lab.update({k: 0 for k, r in v3.items() if r["outcome"] == "retained_100"})
feat = {f["rcept_no"] for f in json.load(open(f"{P}/data/processed/baseline_features.json", encoding="utf-8"))}

runs = {m: (load(a), load(b)) for m, (a, b) in RUNS.items()}
res = {"runs": {m: {"run1_file": a, "run2_file": b, "n_run1": len(runs[m][0]), "n_run2": len(runs[m][1])} for m, (a, b) in RUNS.items()}}
common = set.intersection(*[set(r1) & set(r2) for r1, r2 in runs.values()])
res["n_events_with_both_runs_both_models"] = len(common)
rows = []
for k in sorted(common):
    rows.append({"rcept_no": k, "y": lab.get(k), "has_feat": k in feat,
                 **{f"{m}_r1": runs[m][0][k]["p"] for m in runs}, **{f"{m}_r2": runs[m][1][k]["p"] for m in runs},
                 **{f"{m}_path_same": int(runs[m][0][k]["path"] == runs[m][1][k]["path"]) for m in runs}})
df = pd.DataFrame(rows)
df["avg_r1"] = df[["claude_r1", "gpt_r1"]].mean(axis=1); df["avg_r2"] = df[["claude_r2", "gpt_r2"]].mean(axis=1)
for m in ("claude", "gpt", "avg"):
    a, b = df[f"{m}_r1"], df[f"{m}_r2"]
    res[f"stability_{m}"] = {"n": int(len(df)), "pearson": round(float(pearsonr(a, b)[0]), 3), "spearman": round(float(spearmanr(a, b)[0]), 3),
                            "mean_abs_diff": round(float((a - b).abs().mean()), 3), "share_abs_diff_gt_0.2": round(float(((a - b).abs() > 0.2).mean()), 3),
                            "mean_run1": round(float(a.mean()), 3), "mean_run2": round(float(b.mean()), 3)}
    if m != "avg": res[f"stability_{m}"]["path_agreement"] = round(float(df[f"{m}_path_same"].mean()), 3)
res["stability_between_models_run1"] = round(float(pearsonr(df.claude_r1, df.gpt_r1)[0]), 3)
res["stability_between_models_run2"] = round(float(pearsonr(df.claude_r2, df.gpt_r2)[0]), 3)


def aucs(d, name):
    y = d["y"].values; out = {"n": int(len(d)), "disposed_share": round(float(y.mean()), 3)}
    for m in ("claude", "gpt", "avg"):
        out[m] = {"run1": round(float(roc_auc_score(y, d[f"{m}_r1"])), 3), "run2": round(float(roc_auc_score(y, d[f"{m}_r2"])), 3),
                  "mean_of_runs": round(float(roc_auc_score(y, (d[f"{m}_r1"] + d[f"{m}_r2"]) / 2)), 3)}
    # paired bootstrap: AUC(run2) - AUC(run1) for the two-model average, and mean-of-runs - run1
    rng = np.random.default_rng(1); d1, d2 = [], []
    for _ in range(2000):
        idx = rng.integers(0, len(y), len(y))
        if len(set(y[idx])) < 2: continue
        d1.append(roc_auc_score(y[idx], d["avg_r2"].values[idx]) - roc_auc_score(y[idx], d["avg_r1"].values[idx]))
        d2.append(roc_auc_score(y[idx], ((d["avg_r1"] + d["avg_r2"]) / 2).values[idx]) - roc_auc_score(y[idx], d["avg_r1"].values[idx]))
    out["avg_run2_minus_run1_ci95"] = [round(float(np.percentile(d1, 2.5)), 3), round(float(np.percentile(d1, 97.5)), 3)]
    out["avg_meanruns_minus_run1_ci95"] = [round(float(np.percentile(d2, 2.5)), 3), round(float(np.percentile(d2, 97.5)), 3)]
    res[name] = out
    print(f"[{name}] n={out['n']} " + " | ".join(f"{m}: r1 {out[m]['run1']} r2 {out[m]['run2']} mean {out[m]['mean_of_runs']}" for m in ("claude", "gpt", "avg")))


clean = df.dropna(subset=["y"]).copy()
aucs(clean, "auc_clean_labels")
aucs(clean[clean.has_feat].copy(), "auc_gate1_rows")
print("stability:", {m: res[f"stability_{m}"] for m in ("claude", "gpt", "avg")})
stamp = dt.date.today().strftime("%Y%m%d")
json.dump(res, open(f"{P}/results/llm_repeat_stability_{stamp}.json", "w"), ensure_ascii=False, indent=1)
print(f"saved results/llm_repeat_stability_{stamp}.json")
