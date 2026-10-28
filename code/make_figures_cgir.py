#!/usr/bin/env python3
"""make_figures_cgir.py — the manuscript's figures, drawn only from results files and the pooled event panel the tables use.

F1  Conceptual framework: the two steps of a captive spin-off and where H1–H4 sit (no data).
F2  (a) distribution of the disposal signal by realised outcome (never / late / early disposal) — from the pooled event file;
    (b) announcement CAR and one-year BHAR median by signal quintile with bootstrap intervals — from bhar_predicted_disposal_pooled.
F3  Mean cumulative market-model abnormal return, trading days −10 … +250, by tercile of the signal — computed from the same
    pooled daily panel and event set as Tables 4–5 (18_bhar_pooled.build_pooled, glitch screen applied); the series are written to
    results/figure_data_<date>.json so every plotted number is traceable.
F4  2022 reform by filing year: number of captive spin-off filings read by the models and the share stating shareholder-protection
    measures (majority rule, as in Table 10) — from regulation_2022.by_year.
Outputs: paper/figures/F1_framework.pdf … F4_reform.pdf (vector), results/figure_data_<date>.json.
"""
import os, sys, json, importlib, datetime as dt
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f"{P}/code")
FIG = f"{P}/paper/figures"; os.makedirs(FIG, exist_ok=True)
plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
GREY, DARK, MID, LIGHT = "#555555", "#222222", "#888888", "#bbbbbb"
out = {"generated": str(dt.datetime.now())[:19], "sources": {}}

# ------------------------------------------------------------------ F1 conceptual framework
fig, ax = plt.subplots(figsize=(6.5, 3.6)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(-0.2, 4.6)
def box(x, y, w, h, text, fs=8.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc="white", ec=DARK, lw=0.9))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=DARK)
def arrow(x1, y1, x2, y2, label=None, dy=0.18, ls="-"):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=10, lw=0.9, color=DARK, linestyle=ls))
    if label: ax.text((x1 + x2) / 2, (y1 + y2) / 2 + dy, label, ha="center", va="bottom", fontsize=8, color=GREY)
box(0.2, 2.6, 2.4, 1.0, "Controlling owner's\ncash-flow stake\n(principal–principal)")
box(3.6, 2.6, 2.8, 1.0, "Division filing\n(read by the minority\nand by counterparties)")
box(7.4, 2.6, 2.4, 1.0, "Disposal of the\nsubsidiary\n(sale, investor, listing)")
box(3.7, 0.4, 2.6, 1.0, "Announcement reaction\n(efficiency vs\nlimited attention)")
box(7.4, 0.4, 2.4, 1.0, "Minority return over\nthe following year")
arrow(2.6, 3.1, 3.6, 3.1); ax.text(3.15, 3.75, "H2: smaller stake,\nstronger signal", ha="center", fontsize=7.5, color=GREY)
arrow(6.4, 3.1, 7.4, 3.1); ax.text(6.85, 3.75, "H1: the filing\nforecasts the disposal", ha="center", fontsize=7.5, color=GREY)
arrow(5.0, 2.6, 5.0, 1.4); ax.text(5.15, 2.0, "H3a: is the signal priced?", fontsize=7.5, color=GREY, va="center")
arrow(8.6, 2.6, 8.6, 1.4); ax.text(8.75, 2.0, "H3b: the loss arrives\nwith the disposal", fontsize=7.5, color=GREY, va="center")
ax.add_patch(FancyArrowPatch((1.4, 2.6), (1.4, 0.1), arrowstyle="-", lw=0.9, color=DARK)); ax.add_patch(FancyArrowPatch((1.4, 0.1), (8.6, 0.1), arrowstyle="-", lw=0.9, color=DARK)); arrow(8.6, 0.1, 8.6, 0.4)
ax.text(5.0, -0.05, "H3c: the loss falls on minority holders of small-block parents", ha="center", va="top", fontsize=7.5, color=GREY)
ax.text(5.0, 4.45, "2022 reform (H4): mandated statements act on the filing and its reception before they act on the disposal", ha="center", fontsize=7.5, color=GREY, style="italic")
fig.savefig(f"{FIG}/F1_framework.pdf", bbox_inches="tight"); plt.close(fig)

# ------------------------------------------------------------------ data for F2/F3: the pooled event set and panel used by Tables 4-5
b18 = importlib.import_module("18_bhar_pooled")
B = b18.build_pooled()
co_old = B["co_old_k"]; co_old = co_old[~co_old.flag_glitch.astype(bool)]
co = pd.concat([co_old, B["co_k"]], ignore_index=True)
co = co[co.p_llm.notna()].copy()
ev = pd.read_csv(f"{P}/data/processed/bhar_controls_events_20261025.csv", dtype={"rcept_no": str})
co = co[co.rcept_no.isin(ev[ev.bhar_madj_p2_p250.notna()].rcept_no)].copy()   # full one-year window, as in Tables 4-5
co["timing"] = co.rcept_no.map(B["timing"])
pan = pd.concat([B["pan_old"][B["pan_old"].rcept_no.isin(co.rcept_no)], B["pan_k"][B["pan_k"].rcept_no.isin(co.rcept_no)]], ignore_index=True)
BP = json.load(open(f"{P}/results/bhar_predicted_disposal_pooled_20261028.json"))
out["sources"]["F2a_F3"] = "18_bhar_pooled.build_pooled() (same event set and daily panel as Tables 4-5; glitch-flagged 2001-2016 events excluded)"
out["sources"]["F2b"] = "results/bhar_predicted_disposal_pooled_20261028.json: by_score_quintile.q5_pooled"

# ------------------------------------------------------------------ F2
fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.5, 2.8), gridspec_kw={"width_ratios": [1, 1.25]})
groups = [("never", "Retained"), ("late_ge2y", "Disposed\nafter 2+ years"), ("early_le1y", "Disposed\nwithin a year")]
data = [co.loc[co.timing == g, "p_llm"].dropna().values for g, _ in groups]
bp = a1.boxplot(data, widths=0.55, showfliers=False, medianprops={"color": DARK, "lw": 1.2}, boxprops={"color": DARK}, whiskerprops={"color": GREY}, capprops={"color": GREY})
for i, d in enumerate(data, 1):
    a1.scatter(np.random.default_rng(1).normal(i, 0.06, len(d)), d, s=4, color=MID, alpha=0.35, lw=0)
a1.set_xticks([1, 2, 3]); a1.set_xticklabels([l for _, l in groups], fontsize=7.5); a1.set_ylabel("Disposal signal (0–1)"); a1.set_ylim(-0.02, 1.02)
a1.set_title("(a) Signal by realised outcome", fontsize=9, loc="left")
out["F2a"] = {g: {"n": int(len(d)), "median": round(float(np.median(d)), 3), "q1": round(float(np.percentile(d, 25)), 3), "q3": round(float(np.percentile(d, 75)), 3)} for (g, _), d in zip(groups, data)}
Q = BP["by_score_quintile"]["q5_pooled"]; qs = ["1", "2", "3", "4", "5"]
car = [Q[q]["car_mm_m1_p1"]["mean"] * 100 for q in qs]; car_ci = [[Q[q]["car_mm_m1_p1"]["mean_ci95_boot"][k] * 100 for q in qs] for k in (0, 1)]
med = [Q[q]["bhar_madj_p2_p250"]["median"] * 100 for q in qs]
x = np.arange(5)
a2.bar(x - 0.2, car, 0.38, color=LIGHT, ec=DARK, lw=0.6, label="Announcement CAR [−1, +1], mean (%)")
a2.errorbar(x - 0.2, car, yerr=[np.array(car) - np.array(car_ci[0]), np.array(car_ci[1]) - np.array(car)], fmt="none", ecolor=DARK, elinewidth=0.8, capsize=2)
a2.bar(x + 0.2, med, 0.38, color=DARK, lw=0, label="One-year BHAR [+2, +250], median (%)")
a2.axhline(0, color=GREY, lw=0.6); a2.set_xticks(x); a2.set_xticklabels(["Q1\nlowest", "Q2", "Q3", "Q4", "Q5\nhighest"], fontsize=8); a2.set_xlabel("Quintile of the disposal signal")
a2.set_ylabel("Percent"); a2.legend(fontsize=7, frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.42), ncol=1); a2.set_title("(b) Reaction and the year after, by quintile", fontsize=9, loc="left")
out["F2b"] = {"announcement_car_mean_pct": [round(v, 2) for v in car], "announcement_car_ci95": [[round(v, 2) for v in car_ci[0]], [round(v, 2) for v in car_ci[1]]], "bhar_median_pct": [round(v, 1) for v in med], "n": [Q[q]["bhar_madj_p2_p250"]["n"] for q in qs]}
fig.tight_layout(); fig.savefig(f"{FIG}/F2_signal_outcomes.pdf", bbox_inches="tight"); plt.close(fig)

# ------------------------------------------------------------------ F3 cumulative market-model abnormal return by signal tercile
co["tercile"] = pd.qcut(co.p_llm, 3, labels=["Bottom tercile", "Middle tercile", "Top tercile"])
win = pan[(pan.tau >= -10) & (pan.tau <= 250)].merge(co[["rcept_no", "tercile"]], on="rcept_no")
# cumulate per event from tau=-10, then average by tercile and tau over events present on that day
win = win.sort_values(["rcept_no", "tau"]); win["car"] = win.groupby("rcept_no")["ar_mm"].cumsum()
paths = win.groupby(["tercile", "tau"], observed=True).agg(mean_car=("car", "mean"), n=("car", "size")).reset_index()
fig, ax = plt.subplots(figsize=(6.5, 3.0))
styles = {"Bottom tercile": ("-", LIGHT), "Middle tercile": ("--", MID), "Top tercile": ("-", DARK)}
out["F3"] = {}
for terc, (ls, col) in styles.items():
    s = paths[paths.tercile == terc]
    ax.plot(s.tau, s.mean_car * 100, ls=ls, color=col, lw=1.4, label=f"{terc} (n = {int(s.n.max())})")
    out["F3"][terc] = {"n_events": int(s.n.max()), "tau": s.tau.tolist()[::10], "mean_car_pct": [round(v * 100, 2) for v in s.mean_car.tolist()[::10]]}
ax.axvline(0, color=GREY, lw=0.6, ls=":"); ax.axhline(0, color=GREY, lw=0.6)
ax.set_xlabel("Trading days relative to the division filing"); ax.set_ylabel("Mean cumulative market-model\nabnormal return from day −10 (%)")
ax.legend(frameon=False, fontsize=8, loc="lower left"); ax.set_xlim(-10, 250)
fig.tight_layout(); fig.savefig(f"{FIG}/F3_car_paths.pdf", bbox_inches="tight"); plt.close(fig)

# ------------------------------------------------------------------ F4 reform by year
R = json.load(open(f"{P}/results/regulation_2022_20261025.json"))["by_year"]
years = sorted(int(y) for y in R if 2017 <= int(y) <= 2026 and R[y]["n_with_llm_facts"] > 0)
n = [R[str(y)]["n_filings"] for y in years]; prot = [R[str(y)]["share_mentions_protection"] for y in years]
# Table 10 uses the majority rule per filing; by_year carries the mean of judgment-level flags. Recompute the majority-rule share per year
# from the same judgment files so the figure matches the table's definition.
import glob, collections
facts = collections.defaultdict(list)
for f in glob.glob(f"{P}/results/llm_judge*/*__identified*.jsonl"):
    for l in open(f, encoding="utf-8"):
        try: r = json.loads(l)
        except Exception: continue
        fc = (r.get("parsed") or r.get("judgment") or {}).get("facts") if isinstance(r.get("parsed") or r.get("judgment"), dict) else None
        if fc: facts[r["rcept_no"]].append(bool(fc.get("mentions_shareholder_protection_measures")))
v4 = [x for x in json.load(open(f"{P}/data/processed/carveout_disposal_tracking_v4.json", encoding="utf-8")) if x.get("type", "carve_out") in ("carve_out", "mixed")]
maj = {}
for y in years:
    ks = [x["rcept_no"] for x in v4 if int(x["rcept_no"][:4]) == y and x["rcept_no"] in facts]
    flags = [round(np.mean(facts[k])) for k in ks]
    maj[y] = (len(ks), float(np.mean(flags)) if flags else np.nan)
fig, ax = plt.subplots(figsize=(6.5, 2.8)); ax2 = ax.twinx(); ax2.spines["top"].set_visible(False)
ax.bar(years, [maj[y][0] for y in years], color=LIGHT, ec=DARK, lw=0.6, label="Filings read by the models")
ax2.plot(years, [maj[y][1] * 100 for y in years], color=DARK, marker="o", ms=3.5, lw=1.3, label="Share stating shareholder-protection measures (%)")
ax.axvline(2022.75, color=GREY, lw=0.8, ls=":"); ax.text(2022.85, max(maj[y][0] for y in years) * 0.62, "Revised form,\nOctober 2022", fontsize=7.5, color=GREY, va="top")
ax.set_ylabel("Number of filings"); ax2.set_ylabel("Percent of filings"); ax2.set_ylim(0, 105); ax.set_xticks(years); ax.set_xticklabels([str(y) for y in years], fontsize=8)
h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels(); ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=7.5, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=2)
fig.tight_layout(); fig.savefig(f"{FIG}/F4_reform.pdf", bbox_inches="tight"); plt.close(fig)
out["F4"] = {str(y): {"n_filings_read": maj[y][0], "share_protection_majority_rule_pct": round(maj[y][1] * 100, 1) if maj[y][1] == maj[y][1] else None} for y in years}
out["sources"]["F4"] = "results/regulation_2022_20261025.json by_year (years, filing counts) and the identified judgment files for the majority-rule protection flag (same rule as Table 10)"


# ------------------------------------------------------------------ F5 ROC curves (Gate-1 sample reproduced from the same files as 15_gate1_pooled.py)
from sklearn.metrics import roc_auc_score, roc_curve
import glob, collections
DISP = {"ipo_listed", "majority_disposed", "partial_sale"}
def load_scores(pattern):
    sc = collections.defaultdict(list)
    for fn in glob.glob(pattern):
        for l in open(fn, encoding="utf-8"):
            try: r = json.loads(l)
            except Exception: continue
            pj = (r.get("parsed") or r.get("judgment") or {}); pv = pj.get("p_disposal") if isinstance(pj, dict) else None
            if pv is not None: sc[r["rcept_no"]].append(float(pv) / 100)
    return {k: float(np.mean(v)) for k, v in sc.items()}
old_tr = json.load(open(f"{P}/data/processed/carveout_disposal_tracking_2001_2016.json", encoding="utf-8"))
v4_tr = json.load(open(f"{P}/data/processed/carveout_disposal_tracking_v4.json", encoding="utf-8"))
feat = {x["rcept_no"]: x for x in json.load(open(f"{P}/data/processed/baseline_features.json", encoding="utf-8"))}
fin = {}
for l in open(f"{P}/results/filing_financials_2001_2016.jsonl", encoding="utf-8"):
    r = json.loads(l); fin[r["rcept_no"]] = r.get("parsed") or {}
cA = {**load_scores(f"{P}/results/llm_judge_2001_2016/anthropic__identified*.jsonl"), **load_scores(f"{P}/results/llm_judge/anthropic__identified*.jsonl")}
cB = {**load_scores(f"{P}/results/llm_judge_2001_2016/openai__identified*.jsonl"), **load_scores(f"{P}/results/llm_judge/openai__identified*.jsonl")}
aA, aB = load_scores(f"{P}/results/llm_judge_2001_2016/anthropic__anonymized*.jsonl"), load_scores(f"{P}/results/llm_judge_2001_2016/openai__anonymized*.jsonl")
keep = {}
for r in v4_tr:
    k = r["rcept_no"]
    if r["outcome"] in DISP | {"retained_100"} and feat.get(k) and k in cA and k in cB: keep[k] = int(r["outcome"] in DISP)
for r in old_tr:
    k = r["rcept_no"]
    if r["outcome"] in DISP | {"retained_100"} and fin.get(k) is not None and k in cA and k in cB: keep[k] = int(r["outcome"] in DISP)
G1 = json.load(open(f"{P}/results/gate1_pooled_20261019.json")); AN = json.load(open(f"{P}/results/anonymized_check_20261025.json"))["by_period"]["2001-2016"]["two_model_average"]
ks = [k for k in keep if k[:4] <= "2025"]; y = np.array([keep[k] for k in ks]); s = np.array([(cA[k] + cB[k]) / 2 for k in ks])
auc_pooled = roc_auc_score(y, s)
assert len(ks) == G1["pooled"]["n"] and abs(auc_pooled - G1["pooled"]["auc_p_llm"]) < 0.0015, (len(ks), auc_pooled, G1["pooled"])
ks2 = [k for k in keep if k[:4] <= "2016" and k in aA and k in aB]; y2 = np.array([keep[k] for k in ks2])
s_id = np.array([(cA[k] + cB[k]) / 2 for k in ks2]); s_an = np.array([(aA[k] + aB[k]) / 2 for k in ks2])
assert len(ks2) == AN["n"] and abs(roc_auc_score(y2, s_id) - AN["auc_identified"]) < 0.0015 and abs(roc_auc_score(y2, s_an) - AN["auc_anonymized"]) < 0.0015
fig, (r1, r2) = plt.subplots(1, 2, figsize=(6.5, 3.1))
for ax in (r1, r2): ax.plot([0, 1], [0, 1], color=LIGHT, lw=0.8, ls=":"); ax.set_xlabel("False positive rate (retained read as disposed)"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
fpr, tpr, _ = roc_curve(y, s); r1.plot(fpr, tpr, color=DARK, lw=1.4, label=f"Two-model signal, AUC {G1['pooled']['auc_p_llm']:.3f}")
r1.text(0.55, 0.12, f"Financial baseline\n(out of sample): AUC {G1['pooled']['financial_cv_auc']:.3f}", fontsize=7.5, color=GREY)
r1.set_ylabel("True positive rate (disposed read as disposed)"); r1.set_title(f"(a) Pooled 2001–2025, n = {len(ks)}", fontsize=9, loc="left"); r1.legend(frameon=False, fontsize=7.5, loc="lower right")
f1, t1, _ = roc_curve(y2, s_id); f2, t2, _ = roc_curve(y2, s_an)
r2.plot(f1, t1, color=DARK, lw=1.4, label=f"Identified filings, AUC {AN['auc_identified']:.3f}"); r2.plot(f2, t2, color=MID, lw=1.4, ls="--", label=f"Anonymized filings, AUC {AN['auc_anonymized']:.3f}")
r2.set_title(f"(b) 2001–2016, both conditions, n = {len(ks2)}", fontsize=9, loc="left"); r2.legend(frameon=False, fontsize=7.5, loc="lower right")
fig.tight_layout(); fig.savefig(f"{FIG}/F5_roc.pdf", bbox_inches="tight"); plt.close(fig)
out["F5"] = {"pooled": {"n": len(ks), "auc": round(float(auc_pooled), 3), "financial_baseline_auc": G1["pooled"]["financial_cv_auc"]}, "old_both": {"n": len(ks2), "auc_identified": round(float(roc_auc_score(y2, s_id)), 3), "auc_anonymized": round(float(roc_auc_score(y2, s_an)), 3)}}
out["sources"]["F5"] = "scores: results/llm_judge*/ identified and anonymized judgment files; labels: tracking files; sample filter as in code/15_gate1_pooled.py (clean label, both models, filing financials present); AUCs asserted equal to gate1_pooled_20261019.json and anonymized_check_20261025.json"

# ------------------------------------------------------------------ F6 controlling-block terciles
GV = json.load(open(f"{P}/results/governance_cross_section_20261025.json"))["T5_block_terciles"]
terc = [("low", "Low block"), ("mid", "Middle"), ("high", "High block")]
fig, axes = plt.subplots(1, 4, figsize=(6.5, 2.4))
panels = [("Disposal signal (mean)", [GV[k]["mean_score"] for k, _ in terc], None), ("Disposal rate (%)", [GV[k]["disposal_rate"] * 100 for k, _ in terc], None),
          ("Early-disposal rate (%)", [GV[k]["early_disposal_rate"] * 100 for k, _ in terc], None), ("One-year BHAR, median (%)", [GV[k]["bhar1y"]["median"] * 100 for k, _ in terc], None)]
for ax, (title, vals, _) in zip(axes, panels):
    ax.bar([0, 1, 2], vals, color=[LIGHT, MID, DARK], lw=0); ax.set_xticks([0, 1, 2]); ax.set_xticklabels(["Low", "Mid", "High"], fontsize=7.5); ax.set_title(title, fontsize=8, loc="left"); ax.axhline(0, color=GREY, lw=0.6)
    for i, v in enumerate(vals):
        lab = f"{v:.2f}" if abs(v) < 2 else f"{v:.0f}"
        if v >= 0: ax.text(i, v + 0.01 * max(vals), lab, ha="center", va="bottom", fontsize=7)
        else: ax.text(i, v / 2, lab, ha="center", va="center", fontsize=7, color="white" if i == 2 else DARK)
axes[0].set_ylabel("Terciles of the controlling block", fontsize=8)
fig.tight_layout(); fig.savefig(f"{FIG}/F6_block.pdf", bbox_inches="tight"); plt.close(fig)
out["F6"] = {k: {"block_range": GV[k]["block_range"], "mean_score": GV[k]["mean_score"], "disposal_rate": GV[k]["disposal_rate"], "early_disposal_rate": GV[k]["early_disposal_rate"], "bhar1y_median": GV[k]["bhar1y"]["median"], "n": GV[k]["n"]} for k, _ in terc}
out["sources"]["F6"] = "results/governance_cross_section_20261025.json: T5_block_terciles"

stamp = dt.date.today().strftime("%Y%m%d")
json.dump(out, open(f"{P}/results/figure_data_{stamp}.json", "w"), ensure_ascii=False, indent=1)
print("figures written:", sorted(os.listdir(FIG)), "| data:", f"results/figure_data_{stamp}.json")
print("F2a medians:", {k: v["median"] for k, v in out["F2a"].items()}, "| F3 n:", {k: v["n_events"] for k, v in out["F3"].items()}, "| F4:", {y: v for y, v in list(out["F4"].items())[-3:]})
