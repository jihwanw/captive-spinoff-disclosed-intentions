#!/usr/bin/env python3
"""make_figures_jifma.py — figures for the JIFMA manuscript.

F1_framework_jifma.pdf  the conceptual figure of make_figures_cgir.py with the hypothesis labels of the JIFMA version
                        (H4 split into the three channels of the 2022 reform: information, compensation, deterrence/bonding).
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

# ---- F1 (JIFMA labels)
fig, ax = plt.subplots(figsize=(6.5, 4.4)); ax.axis("off"); ax.set_xlim(0, 13.4); ax.set_ylim(-0.7, 5.9)
def box(x, y, w, h, text, fs=8.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.1", fc="white", ec=DARK, lw=0.9))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=DARK, linespacing=1.25)
def arrow(x1, y1, x2, y2): ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=10, lw=0.9, color=DARK))
W = 3.7; X1, X2, X3 = 0.2, 4.6, 9.0
box(X1, 3.3, W, 1.5, "Controlling owner's\ncash-flow stake\n(principal–principal)")
box(X2, 3.3, W, 1.5, "Division filing\n(read by the minority\nand by counterparties)")
box(X3, 3.3, W, 1.5, "Disposal of the\nsubsidiary\n(sale, investor, listing)")
box(X2, 0.5, W, 1.5, "Announcement\nreaction (efficiency\nvs limited attention)")
box(X3, 0.5, W, 1.5, "Minority return over\nthe following year")
arrow(X1 + W, 4.05, X2, 4.05); ax.text((X1 + W + X2) / 2, 5.15, "H2: smaller stake,\nstronger signal", ha="center", va="center", fontsize=7.5, color=GREY)
arrow(X2 + W, 4.05, X3, 4.05); ax.text((X2 + W + X3) / 2, 5.15, "H1: the filing forecasts\nthe disposal beyond\nits financials and purposes", ha="center", va="center", fontsize=7.5, color=GREY)
c2, c3 = X2 + W / 2, X3 + W / 2
arrow(c2, 3.3, c2, 2.0); ax.text(c2 - 0.15, 2.65, "H3a: is the\nsignal priced?", fontsize=7.5, color=GREY, va="center", ha="right")
arrow(c3, 3.3, c3, 2.0); ax.text(c3 + 0.15, 2.65, "H3b: the loss\narrives with\nthe disposal", fontsize=7.5, color=GREY, va="center", ha="left")
c1 = X1 + W / 2
ax.plot([c1, c1], [3.3, -0.1], color=DARK, lw=0.9); ax.plot([c1, c3], [-0.1, -0.1], color=DARK, lw=0.9); arrow(c3, -0.1, c3, 0.5)
ax.text((c1 + c3) / 2, -0.25, "H3c: the loss falls on minority holders of small-block parents", ha="center", va="top", fontsize=7.5, color=GREY)
ax.text(6.7, 5.75, "2022 reform: H4a information (mandated statements), H4b compensation (appraisal put), H4c deterrence and bonding (listing review, commitments)", ha="center", va="center", fontsize=7.0, color=GREY, style="italic")
fig.savefig(f"{FIG}/F1_framework_jifma.pdf", bbox_inches="tight"); plt.close(fig)

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
print("written F1_framework_jifma.pdf, F7_km_signal.pdf")
