#!/usr/bin/env python3
"""make_figures_jifma.py — figures for the JIFMA manuscript.

F1_framework_jifma.pdf  the conceptual figure with the JIFMA hypothesis labels (H4 split into the three reform channels), drawn at full text width.
F2_signal_outcomes_jifma.pdf  the two panels of make_figures_cgir.F2 at full text width (same data; values asserted against results/figure_data_20261028.json).
F7_km_signal.pdf        Kaplan–Meier share disposed by tercile of the disposal signal (results/cox_time_to_disposal_20261110.json,
                        kaplan_meier_sample_A.signal — the shares at years 0, 1, 3, 5 as written by code/28; no re-estimation here).
All other figures (F2–F6) are reused unchanged from make_figures_cgir.py.
Style: greyscale, serif, uniform markers, value labels (project convention).
"""
import os, re, json
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); FIG = f"{P}/paper/figures"
plt.rcParams.update({"font.family": "serif", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42})
GREY, DARK, MID, LIGHT = "#555555", "#222222", "#888888", "#bbbbbb"

# ---- F1 (JIFMA labels; redrawn 2026-11-14 at full text width with larger boxes and fonts — the 2026-11-11 version had labels crossing box borders).
# After drawing, every label's rendered extent is checked against every box: a label that touches a box it does not belong to raises.
plt.rcParams.update({"font.family": "STIXGeneral"})   # Times-like, matches the manuscript (mathptmx); DejaVu Serif is ~20% wider and overflowed the boxes
fig, ax = plt.subplots(figsize=(7.2, 5.4)); ax.axis("off"); ax.set_xlim(0, 16.0); ax.set_ylim(-0.3, 11.1)
BOXES, LABELS, INSIDE = [], [], []
def box(x, y, w, h, text, fs=10.5, lw=1.1):
    b = ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.15", fc="white", ec=DARK, lw=lw)); BOXES.append(b)
    INSIDE.append((ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=DARK, linespacing=1.3), b))
def label(x, y, text, **kw): LABELS.append(ax.text(x, y, text, fontsize=10, color=GREY, **kw))
def arrow(x1, y1, x2, y2): ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=13, lw=1.1, color=DARK))
W, H = 4.4, 1.9; X1, X2, X3 = 0.2, 5.6, 11.0; Y1, Y2 = 5.5, 2.0
c1, c2, c3 = X1 + W / 2, X2 + W / 2, X3 + W / 2
box(X1, 9.0, X3 + W - X1, 1.9, "2022 reform (September–December 2022): revised disclosure form, appraisal right, listing review\n"
    "H4a information — the mandated statements and their reception change; the forecast does not\n"
    "H4b compensation — the appraisal right is a put, priced at the announcement\n"
    "H4c deterrence and bonding — binding commitments and the listing review separate intentions", fs=9.5, lw=0.9)
arrow(c2 + 0.9, 9.0, c2 + 0.9, Y1 + H); label(c2 + 1.05, 8.25, "H4a", va="center", ha="left")
arrow(c3, 9.0, c3, Y1 + H); label(c3 + 0.15, 8.25, "H4c", va="center", ha="left")
box(X1, Y1, W, H, "Controlling owner's\ncash-flow stake\n(principal–principal)")
box(X2, Y1, W, H, "Division filing\n(read by the minority\nand by counterparties)")
box(X3, Y1, W, H, "Disposal of the\nsubsidiary\n(sale, investor, listing)")
arrow(X1 + W, Y1 + H / 2, X2, Y1 + H / 2); label((X1 + W + X2) / 2, Y1 + H + 0.15, "H2: smaller stake,\nstronger signal", ha="center", va="bottom")
arrow(X2 + W, Y1 + H / 2, X3, Y1 + H / 2); label((X2 + W + X3) / 2, Y1 - 0.15, "H1: the filing forecasts the\ndisposal beyond its financials\nand purposes", ha="center", va="top")
box(X2, Y2, W, H, "Announcement reaction\n(efficient reading vs\nlimited attention)")
box(X3, Y2, W, H, "Minority return over\nthe following year")
arrow(c2, Y1, c2, Y2 + H); label(c2 - 0.2, (Y1 + Y2 + H) / 2, "H3a: announcement pricing;\nH4b: post-reform, rises\nwith appraisal moneyness", va="center", ha="right")
arrow(c3, Y1, c3, Y2 + H); label(c3 + 0.2, (Y1 + Y2 + H) / 2, "H3b: the loss\narrives with\nthe disposal", va="center", ha="left")
ax.plot([c1, c1], [Y1, 0.8], color=DARK, lw=1.1); ax.plot([c1, c3], [0.8, 0.8], color=DARK, lw=1.1); arrow(c3, 0.8, c3, Y2)
label((c1 + c3) / 2, 0.6, "H3c: the one-year loss is concentrated in parents with small controlling blocks", ha="center", va="top")
fig.canvas.draw(); rend = fig.canvas.get_renderer()
for t, b in INSIDE:
    tb, bb = t.get_window_extent(rend), b.get_window_extent(rend)
    assert bb.x0 <= tb.x0 and tb.x1 <= bb.x1 and bb.y0 <= tb.y0 and tb.y1 <= bb.y1, f"F1 box text overflows its box: {t.get_text()[:30]!r}"
for t in LABELS:
    tb = t.get_window_extent(rend)
    for b in BOXES:
        bb = b.get_window_extent(rend)
        assert not tb.overlaps(bb), f"F1 label overlaps a box: {t.get_text()[:30]!r}"
    xb = tb.transformed(ax.transData.inverted()); assert xb.x0 >= 0 and xb.x1 <= 16.0, f"F1 label outside the axes: {t.get_text()[:30]!r} {xb}"
fig.savefig(f"{FIG}/F1_framework_jifma.pdf", bbox_inches="tight"); plt.close(fig)
plt.rcParams.update({"font.family": "serif"})

# ---- F2 (JIFMA size): the two panels of make_figures_cgir.F2 redrawn at full text width. Panel (a) from the controls event file (the 559 listed
# parents with a signal and a full one-year window, the sample of Table 6; timing from the same file), medians asserted against figure_data F2a;
# panel (b) from the quintile summary make_figures_cgir reads (bhar_predicted_disposal_pooled_20261028.json), values asserted against figure_data F2b.
import numpy as np, pandas as pd
FD = json.load(open(f"{P}/results/figure_data_20261028.json", encoding="utf-8"))
ev = pd.read_csv(f"{P}/data/processed/bhar_controls_events_20261025.csv", dtype={"rcept_no": str})
ev = ev[ev.p_llm.notna() & ev.bhar_madj_p2_p250.notna()]
groups = [("never", "Retained"), ("late_ge2y", "Disposed after\ntwo or more years"), ("early_le1y", "Disposed\nwithin a year")]
data = [ev.loc[ev.timing == g, "p_llm"].dropna().values for g, _ in groups]
for (g, _), d in zip(groups, data):
    assert len(d) == FD["F2a"][g]["n"] and round(float(np.median(d)), 3) == FD["F2a"][g]["median"], (g, len(d), float(np.median(d)), FD["F2a"][g])
BP = json.load(open(f"{P}/results/bhar_predicted_disposal_pooled_20261028.json", encoding="utf-8")); Q = BP["by_score_quintile"]["q5_pooled"]; qs = ["1", "2", "3", "4", "5"]
car = [Q[q]["car_mm_m1_p1"]["mean"] * 100 for q in qs]; car_ci = [[Q[q]["car_mm_m1_p1"]["mean_ci95_boot"][k] * 100 for q in qs] for k in (0, 1)]
med = [Q[q]["bhar_madj_p2_p250"]["median"] * 100 for q in qs]; nq = [Q[q]["bhar_madj_p2_p250"]["n"] for q in qs]
assert [round(v, 2) for v in car] == FD["F2b"]["announcement_car_mean_pct"] and [round(v, 1) for v in med] == FD["F2b"]["bhar_median_pct"]
plt.rcParams.update({"font.size": 10.5, "font.family": "STIXGeneral"})
fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 4.6), gridspec_kw={"width_ratios": [1, 1.2]})
a1.boxplot(data, widths=0.55, showfliers=False, medianprops={"color": DARK, "lw": 1.6}, boxprops={"color": DARK, "lw": 1.1}, whiskerprops={"color": GREY, "lw": 1.0}, capprops={"color": GREY, "lw": 1.0})
for i, d in enumerate(data, 1):
    a1.scatter(np.random.default_rng(1).normal(i, 0.07, len(d)), d, s=7, color=MID, alpha=0.4, lw=0)
    a1.text(i, 1.04, f"n = {len(d)}", ha="center", va="bottom", fontsize=9, color=GREY)
a1.set_xticks([1, 2, 3]); a1.set_xticklabels([l for _, l in groups], fontsize=9.5); a1.set_ylabel("Disposal signal (0–1)", fontsize=10.5); a1.set_ylim(-0.02, 1.12); a1.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
a1.set_title("(a) Signal by realised outcome", fontsize=11, loc="left")
x = np.arange(5)
a2.bar(x - 0.2, car, 0.38, color=LIGHT, ec=DARK, lw=0.8, label="Announcement CAR [−1, +1], mean (%)")
a2.errorbar(x - 0.2, car, yerr=[np.array(car) - np.array(car_ci[0]), np.array(car_ci[1]) - np.array(car)], fmt="none", ecolor=DARK, elinewidth=1.0, capsize=3)
a2.bar(x + 0.2, med, 0.38, color=DARK, lw=0, label="One-year BHAR [+2, +250], median (%)")
for xi, v in zip(x, med): a2.text(xi + 0.2, v - 0.6, f"{v:.0f}", ha="center", va="top", fontsize=9, color=DARK)
for xi, v in zip(x, car): a2.text(xi - 0.2, max(v, 0) + 2.6, f"{v:.1f}", ha="center", va="bottom", fontsize=8.5, color=GREY)
a2.axhline(0, color=GREY, lw=0.8); a2.set_xticks(x); a2.set_xticklabels([f"Q1\nlowest\nn={nq[0]}", f"Q2\n\nn={nq[1]}", f"Q3\n\nn={nq[2]}", f"Q4\n\nn={nq[3]}", f"Q5\nhighest\nn={nq[4]}"], fontsize=9.5); a2.set_xlabel("Quintile of the disposal signal", fontsize=10.5)
a2.set_ylabel("Percent", fontsize=10.5); a2.set_ylim(-28, 5); a2.set_title("(b) Reaction and the year after, by quintile", fontsize=11, loc="left")
h, l = a2.get_legend_handles_labels(); fig.legend(h, l, fontsize=9.5, frameon=False, loc="lower center", ncol=2, bbox_to_anchor=(0.5, -0.02))
fig.tight_layout(w_pad=2.0, rect=(0, 0.07, 1, 1)); fig.savefig(f"{FIG}/F2_signal_outcomes_jifma.pdf", bbox_inches="tight"); plt.close(fig)
plt.rcParams.update({"font.size": 9, "font.family": "serif"})

# ---- F7 Kaplan–Meier by signal tercile (values from the Cox results file)
C = json.load(open(f"{P}/results/cox_time_to_disposal_20261110.json", encoding="utf-8")); KM = C["kaplan_meier_sample_A"]["signal"]
fig, ax = plt.subplots(figsize=(5.2, 3.3))
years = [0, 1, 3, 5]; styles = {"low": ("o", "-", "Low signal"), "mid": ("s", "--", "Middle"), "high": ("^", "-.", "High signal")}
for k, (mk, ls, lab) in styles.items():
    v = KM[k]; ys = [v[f"disposed_by_year_{t}"] * 100 for t in years]
    ax.plot(years, ys, marker=mk, ls=ls, color=DARK, lw=1.0, ms=4, label=f"{lab} ({v['range'][0]:.2f}–{v['range'][1]:.2f}), n={v['n']}")
    for t, y in zip(years, ys): ax.annotate(f"{y:.0f}", (t, y), textcoords="offset points", xytext=(0, 5), ha="center", fontsize=7, color=GREY)
ax.set_xlabel("Fiscal years after the division"); ax.set_ylabel("Share of subsidiaries disposed of (%)"); ax.set_xticks(years); ax.set_ylim(0, 100)
ax.legend(frameon=False, fontsize=7.5, loc="lower right"); fig.tight_layout(); fig.savefig(f"{FIG}/F7_km_signal.pdf"); plt.close(fig)
print("written F1_framework_jifma.pdf, F2_signal_outcomes_jifma.pdf, F7_km_signal.pdf")
