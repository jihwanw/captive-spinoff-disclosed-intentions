#!/usr/bin/env python3
"""14_calibration_decision.py — beyond AUC: are the announcement-date disposal forecasts calibrated, and what would acting on
them cost and gain?

Sample and scores as in 10_gate1_v4.py (v4 clean labels; LLM = two-run mean per model, two-model average; financial
model = out-of-fold predictions from the year-free logistic regression, 5x50 repeated CV).
  1. Calibration: reliability table by score decile (mean predicted vs observed disposal share), Brier score and its
     decomposition (reliability/resolution/uncertainty), expected calibration error; Platt-recalibrated LLM (out-of-fold).
  2. Decision analysis: for thresholds t on P(disposal), the share of carve-outs flagged, precision (share of flagged that
     were disposed), recall, and the net benefit curve (Vickers-Elkin decision curve) — net benefit = TP/N - FP/N * t/(1-t)
     — relative to "flag all" and "flag none", for LLM, financial and combined scores.
  3. Stratified by the mature sample (division_year <= 2021).
Output: results/calibration_decision_<date>.json
"""
import json, glob, os, datetime as dt, numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.metrics import roc_auc_score, brier_score_loss

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(f"{P}/code/10_gate1_v4.py", encoding="utf-8").read()
head = src.split("\ndef design(")[0]                      # data assembly identical to 10 (feat, v4, scores, rows -> df, FIN)
ns = {"__file__": os.path.abspath(f"{P}/code/10_gate1_v4.py")}; exec(head, ns)
df, FIN = ns["df"], ns["FIN"]


def design(d, cols):
    X = d[cols].copy()
    for c in cols:
        if X[c].isna().any(): X[c + "_miss"] = X[c].isna().astype(int); X[c] = X[c].fillna(X[c].median())
    X = X.loc[:, X.nunique(dropna=False) > 1]
    return X.clip(lower=X.quantile(0.01), upper=X.quantile(0.99), axis=1)


def oof_pred(Xm, y, n_rep=50, seed=0):
    oof = np.zeros((n_rep, len(y))); rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=n_rep, random_state=seed)
    for i, (tr, te) in enumerate(rskf.split(Xm, y)):
        mdl = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, max_iter=2000)).fit(Xm.iloc[tr], y[tr]); oof[i // 5, te] = mdl.predict_proba(Xm.iloc[te])[:, 1]
    return oof.mean(axis=0)


def reliability(p, y, bins=10):
    q = pd.qcut(pd.Series(p), bins, labels=False, duplicates="drop"); out = []
    for b in sorted(q.unique()):
        m = (q == b).values; out.append({"bin": int(b), "n": int(m.sum()), "mean_pred": round(float(p[m].mean()), 3), "obs_share": round(float(y[m].mean()), 3)})
    ece = sum(abs(r["mean_pred"] - r["obs_share"]) * r["n"] for r in out) / len(p)
    return out, round(float(ece), 3)


def brier_decomp(p, y, bins=10):
    base = y.mean(); q = pd.qcut(pd.Series(p), bins, labels=False, duplicates="drop").values
    rel = res_ = 0.0
    for b in np.unique(q):
        m = q == b; rel += m.sum() * (p[m].mean() - y[m].mean()) ** 2; res_ += m.sum() * (y[m].mean() - base) ** 2
    return {"brier": round(float(brier_score_loss(y, p)), 4), "reliability": round(float(rel / len(p)), 4), "resolution": round(float(res_ / len(p)), 4), "uncertainty": round(float(base * (1 - base)), 4)}


def decision_curve(p, y, thresholds=(0.3, 0.4, 0.5, 0.6, 0.7, 0.8)):
    N = len(y); out = {}
    for t in thresholds:
        flag = p >= t; tp = int((flag & (y == 1)).sum()); fp = int((flag & (y == 0)).sum()); fn = int((~flag & (y == 1)).sum())
        nb = tp / N - fp / N * t / (1 - t); nb_all = y.mean() - (1 - y.mean()) * t / (1 - t)
        out[str(t)] = {"flagged_share": round(float(flag.mean()), 3), "precision": round(tp / max(tp + fp, 1), 3), "recall": round(tp / max(tp + fn, 1), 3),
                       "net_benefit": round(float(nb), 4), "net_benefit_flag_all": round(float(nb_all), 4), "net_benefit_flag_none": 0.0}
    return out


def platt_oof(p, y, n_rep=50, seed=0):
    """Out-of-fold Platt scaling of a fixed score (logit(p) -> y) so recalibrated probabilities are not in-sample."""
    z = np.log(np.clip(p, 0.01, 0.99) / (1 - np.clip(p, 0.01, 0.99))).reshape(-1, 1); oof = np.zeros((n_rep, len(y)))
    rskf = RepeatedStratifiedKFold(n_splits=5, n_repeats=n_rep, random_state=seed)
    for i, (tr, te) in enumerate(rskf.split(z, y)):
        oof[i // 5, te] = LogisticRegression(C=1e6, max_iter=1000).fit(z[tr], y[tr]).predict_proba(z[te])[:, 1]
    return oof.mean(axis=0)


def analyse(d, name):
    y = d["y"].values; X = design(d, FIN)
    scores = {"llm_raw": d["p_llm"].values, "claude_raw": d["p_claude"].values, "gpt_raw": d["p_gpt"].values, "financial_oof": oof_pred(X, y)}
    Xc = X.copy(); Xc["logit_llm"] = np.log(d["p_llm"].clip(0.01, 0.99) / (1 - d["p_llm"].clip(0.01, 0.99))); scores["combined_oof"] = oof_pred(Xc, y)
    scores["llm_platt_oof"] = platt_oof(d["p_llm"].values, y)
    out = {"n": int(len(d)), "disposed_share": round(float(y.mean()), 3), "scores": {}}
    for k, p in scores.items():
        rel, ece = reliability(p, y)
        out["scores"][k] = {"auc": round(float(roc_auc_score(y, p)), 3), "mean_pred": round(float(p.mean()), 3), **brier_decomp(p, y), "ece": ece, "reliability_table": rel, "decision_curve": decision_curve(p, y)}
    print(f"[{name}] n={out['n']} base={out['disposed_share']} | " + " | ".join(f"{k}: AUC {v['auc']} Brier {v['brier']} ECE {v['ece']} mean_pred {v['mean_pred']}" for k, v in out["scores"].items()), flush=True)
    return out


res = {"sample": "as 10_gate1_v4.py (v4 clean labels, both-model identified scores, financial features)", "full": analyse(df, "full")}
mature = df[df.division_year <= 2021].reset_index(drop=True); res["mature_division_year_le_2021"] = analyse(mature, "mature <=2021")
stamp = dt.date.today().strftime("%Y%m%d"); json.dump(res, open(f"{P}/results/calibration_decision_{stamp}.json", "w"), ensure_ascii=False, indent=1)
print("LLM raw reliability (full):", [(r["mean_pred"], r["obs_share"], r["n"]) for r in res["full"]["scores"]["llm_raw"]["reliability_table"]])
print("decision curve LLM raw (full):", {t: (v["flagged_share"], v["precision"], v["recall"], v["net_benefit"], v["net_benefit_flag_all"]) for t, v in res["full"]["scores"]["llm_raw"]["decision_curve"].items()})
print(f"saved results/calibration_decision_{stamp}.json")
