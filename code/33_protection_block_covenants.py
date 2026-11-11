#!/usr/bin/env python3
"""33_protection_block_covenants.py — what the mandated "shareholder-protection" block actually commits to (strategy §1-D H-약정, §6 정보 경로).

The October 2022 form added the block "N. 물적분할의 경우 주주보호방안" to the division filing. This script cuts that block (and the block
"향후 회사구조개편에 관한 계획") out of every 2017–2026 captive spin-off filing text and classifies its content with a transparent
dictionary built after reading all 61 post-reform blocks (2026-11-10; the 66 post-reform filings of the structured record have 61 blocks,
3 texts say "해당사항 없음"/"서식변경", 2 have no block). Categories (a filing can carry several):
  charter_vote        a shareholder-meeting (special) resolution is required before any listing of the subsidiary (DB하이텍-type charter clause)
  no_listing_horizon  an explicit horizon: no listing (preliminary review) within 3 or 5 years
  unlisted_soft       "비상장을 유지하여 주주가치 희석을 차단" without horizon or sanction
  sale_plan           the block states an intended sale of the subsidiary (often to a named buyer)
  payout_policy       dividend / buyback / shareholder-return commitment
  disclosure_commit   commitment to disclose / reduce information asymmetry / IR
  consult_shareholders "주주와의 소통 … 다양한 방안을 검토" (no concrete measure)
  appraisal_only      the block only points to the statutory appraisal right
  none                no block, "해당사항 없음", form-change note, or efficiency boilerplate only
Strength index: 3 = charter_vote; 2 = no_listing_horizon; 1 = unlisted_soft or payout_policy; 0 otherwise (sale_plan is reported separately).
Associations (descriptive, n ~ 60): strength and sale_plan vs the disposal signal S, the announcement CAR (32's file), the realised early
disposal where labels exist. Pre-reform filings are scanned to confirm the block's absence (paper: protection statements in 0.5% of filings).
Pre-registered expectations (2026-11-10): blocks found in >= 55 of 66 post-reform filings and in <= 3 pre-reform filings; sale_plan filings
have the highest mean S (> 0.7) and the highest realised early-disposal share; charter_vote filings the lowest S (< 0.4); CAR by category:
no prior, recorded.
Outputs: results/protection_block_<date>.json, data/processed/protection_block_<date>.csv, docs/PROTECTION_BLOCK_NOTE_<date>.md
"""
import os, re, json, glob, datetime as dt, numpy as np, pandas as pd
from scipy import stats

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f"{P}/data/processed"; STAMP = dt.date.today().strftime("%Y%m%d")
R = {"generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "expectations_preregistered": __doc__.split("Pre-registered expectations")[1].split("Outputs:")[0].strip()}
idx = json.load(open(f"{OUT}/disclosure_text_index.json", encoding="utf-8")); dd = json.load(open(f"{P}/data/raw/dart_division_decisions_2017_2026.json", encoding="utf-8"))
NEXT = r"(?=(?:\n\s*|(?<=[.。])\s*)\d{1,2}\s*\.\s*(기타|증권신고서|향후|풋옵션|주식매수청구권|분할등기|이사회결의일|사외이사|감사|물적분할의 경우)|\Z)"   # next item must start a line or follow a sentence end; the in-text reference "상기 '10. 주식매수청구권…'" (after a quote) does not cut the block
BLK = re.compile(r"\d{1,2}\s*\.\s*물적분할의\s*경우\s*주주보호방안(.*?)" + NEXT, re.S)
PLAN = re.compile(r"\d{1,2}\s*\.\s*향후\s*회사구조개편에\s*관한\s*계획(.*?)" + NEXT, re.S)
CAT = {"charter_vote": r"특별결의", "no_listing_horizon": r"[35]\s*년[^。]{0,60}?상장[^。]{0,40}?(계획이\s*없|신청하지\s*않|신청할\s*계획)", "unlisted_soft": r"비상장(을|으로|회사로|법인으로)?\s*(유지|하여|함으로써)",
       "sale_plan": r"매각(을|할)?\s*(예정|추진)", "payout_policy": r"배당|자기주식|자사주|주주환원", "disclosure_commit": r"공시하여|정보\s*비대칭|IR\s*활동", "consult_shareholders": r"주주와의\s*소통|의견을\s*폭\s*넓게", "appraisal_only": r"주식매수청구권"}
def classify(body):
    b = re.sub(r"\s+", " ", body or "").strip()
    flags = {k: bool(re.search(p, b)) for k, p in CAT.items()}
    if not b or re.fullmatch(r"[-\s]*(해당사항이?\s*없습니다\.?|해당사항\s*없음|서식변경.*|공시서식 개정에 따른 변경)[-\s]*", b): flags = {k: False for k in CAT}; flags["none"] = True
    else: flags["none"] = not any(flags[k] for k in CAT if k != "appraisal_only") and not flags["appraisal_only"]
    if flags.get("appraisal_only") and any(flags[k] for k in CAT if k != "appraisal_only"): flags["appraisal_only"] = False   # appraisal mention beside a real measure is not "only"
    strength = 3 if flags["charter_vote"] else 2 if flags["no_listing_horizon"] else 1 if (flags["unlisted_soft"] or flags["payout_policy"]) else 0
    return flags, strength, b
rows = []
for r in dd:
    if r["type"] not in ("carve_out", "mixed"): continue
    e = idx.get(r["rcept_no"]); p = e and e.get("path"); t = open(f"{P}/{p}", encoding="utf-8", errors="replace").read() if p and os.path.exists(f"{P}/{p}") else None
    rec = {"rcept_no": r["rcept_no"], "corp_name": r["corp_name"], "corp_cls": r["corp_cls"], "date": r["rcept_no"][:8], "post": int(r["rcept_no"][:8] >= "20221001"), "has_text": t is not None}
    if t is None: rows.append(rec); continue
    m = BLK.search(t); mp = PLAN.search(t)
    rec["has_block"] = bool(m); rec["block_chars"] = len(m.group(1).strip()) if m else 0
    flags, strength, body = classify(m.group(1) if m else "")
    rec.update({f"c_{k}": int(v) for k, v in flags.items()}); rec["strength"] = strength if m else 0; rec["block_text"] = body[:1500]
    plan = re.sub(r"\s+", " ", mp.group(1)).strip() if mp else ""
    rec["plan_no_listing_5y"] = int(bool(re.search(r"5\s*년[^。]{0,60}?상장[^。]{0,40}?(않|없)", plan))); rec["plan_text"] = plan[:600]
    rows.append(rec)
df = pd.DataFrame(rows)
post = df[df.post == 1]; pre = df[df.post == 0]
cats = [f"c_{k}" for k in CAT] + ["c_none"]
R["coverage"] = {"captive_filings_2017plus": int(len(df)), "with_text": int(df.has_text.sum()), "post_reform": int(len(post)), "post_with_block": int(post.has_block.sum()), "pre_reform": int(len(pre)), "pre_with_block": int(pre.has_block.fillna(False).sum())}
R["post_reform_categories"] = {c[2:]: int(post[c].sum()) for c in cats if c in post}; R["post_reform_strength"] = {int(k): int(v) for k, v in post.strength.value_counts().sort_index().items()}
R["post_reform_plan_no_listing_5y"] = int(post.plan_no_listing_5y.sum())
# signal, CAR, outcomes
src = open(f"{P}/code/15_gate1_pooled.py", encoding="utf-8").read(); head = src.split("\ndef panel(")[0]; ns = {"__file__": f"{P}/code/15_gate1_pooled.py", "__name__": "g"}; exec(compile(head, "15", "exec"), ns)
S = {}
for pat in (f"{P}/results/llm_judge/anthropic__identified*.jsonl", f"{P}/results/llm_judge/openai__identified*.jsonl"):
    for k, v in ns["scores"](pat).items(): S.setdefault(k, []).append(v)
df["S"] = df.rcept_no.map({k: float(np.mean(v)) for k, v in S.items()})
cars = pd.read_csv(sorted(glob.glob(f"{OUT}/division_announcement_cars_*.csv"))[-1], dtype={"rcept_no": str}); df = df.merge(cars[["rcept_no", "car_mm_m1_p1", "car_mm_0_p20"]], on="rcept_no", how="left")
v4 = {r["rcept_no"]: r for r in json.load(open(f"{OUT}/carveout_disposal_tracking_v4.json", encoding="utf-8"))}
df["outcome"] = df.rcept_no.map(lambda k: (v4.get(k) or {}).get("outcome")); df["first_change_fy"] = df.rcept_no.map(lambda k: (v4.get(k) or {}).get("first_change_fy")); df["division_year"] = df.rcept_no.map(lambda k: (v4.get(k) or {}).get("division_year"))
df["disposed"] = df.outcome.isin(["ipo_listed", "majority_disposed", "partial_sale"]).astype(float).where(df.outcome.isin(["ipo_listed", "majority_disposed", "partial_sale", "retained_100"]))
df["early"] = ((df.first_change_fy - df.division_year) <= 1).astype(float).where(df.disposed.notna() & (df.first_change_fy.notna() | (df.outcome == "retained_100")))
def grp(d, col):
    out = {}
    for val, g in d.groupby(col):
        out[str(val)] = {"n": int(len(g)), "mean_S": round(float(g.S.mean()), 3) if g.S.notna().any() else None, "mean_car3_pct": round(float(g.car_mm_m1_p1.mean() * 100), 2) if g.car_mm_m1_p1.notna().any() else None, "n_car": int(g.car_mm_m1_p1.notna().sum()),
                        "disposed_share": round(float(g.disposed.mean()), 3) if g.disposed.notna().any() else None, "n_labelled": int(g.disposed.notna().sum()), "early_share": round(float(g.early.mean()), 3) if g.early.notna().any() else None}
    return out
R["post_by_strength"] = grp(post.assign(S=df.loc[post.index, "S"], car_mm_m1_p1=df.loc[post.index, "car_mm_m1_p1"], disposed=df.loc[post.index, "disposed"], early=df.loc[post.index, "early"]), "strength")
pp = df[df.post == 1]
R["post_by_category"] = {k[2:]: {"n": int(pp[k].sum()), "mean_S": round(float(pp[pp[k] == 1].S.mean()), 3) if (pp[k] == 1).any() and pp[pp[k] == 1].S.notna().any() else None, "mean_car3_pct": round(float(pp[pp[k] == 1].car_mm_m1_p1.mean() * 100), 2) if (pp[k] == 1).any() and pp[pp[k] == 1].car_mm_m1_p1.notna().any() else None,
                                "disposed_share": round(float(pp[pp[k] == 1].disposed.mean()), 3) if (pp[k] == 1).any() and pp[pp[k] == 1].disposed.notna().any() else None, "n_labelled": int(pp[pp[k] == 1].disposed.notna().sum())} for k in cats}
# S by strength: rank correlation; sale_plan vs others
d_ = pp.dropna(subset=["S"]); R["post_tests"] = {"spearman_strength_S": {"rho": round(float(stats.spearmanr(d_.strength, d_.S).statistic), 3), "p": round(float(stats.spearmanr(d_.strength, d_.S).pvalue), 3), "n": int(len(d_))},
                                                   "sale_plan_vs_rest_S": {"mean_sale_plan": round(float(d_[d_.c_sale_plan == 1].S.mean()), 3) if (d_.c_sale_plan == 1).any() else None, "mean_rest": round(float(d_[d_.c_sale_plan == 0].S.mean()), 3), "mw_p": round(float(stats.mannwhitneyu(d_[d_.c_sale_plan == 1].S, d_[d_.c_sale_plan == 0].S).pvalue), 3) if (d_.c_sale_plan == 1).sum() >= 3 else None},
                                                   "spearman_strength_car3": (lambda e: {"rho": round(float(stats.spearmanr(e.strength, e.car_mm_m1_p1).statistic), 3), "p": round(float(stats.spearmanr(e.strength, e.car_mm_m1_p1).pvalue), 3), "n": int(len(e))})(pp.dropna(subset=["car_mm_m1_p1"]))}
R["expectation_check"] = {"post_blocks_ge_55": bool(R["coverage"]["post_with_block"] >= 55), "pre_blocks_le_3": bool(R["coverage"]["pre_with_block"] <= 3),
                          "sale_plan_mean_S_gt_0.7": bool((R["post_by_category"]["sale_plan"]["mean_S"] or 0) > 0.7), "charter_vote_mean_S_lt_0.4": bool((R["post_by_category"]["charter_vote"]["mean_S"] or 1) < 0.4)}
print(json.dumps({k: R[k] for k in ("coverage", "post_reform_categories", "post_reform_strength", "post_reform_plan_no_listing_5y", "post_by_strength", "post_tests", "expectation_check")}, ensure_ascii=False, indent=1))
print("by category:", json.dumps(R["post_by_category"], ensure_ascii=False))
json.dump(R, open(f"{P}/results/protection_block_{STAMP}.json", "w"), ensure_ascii=False, indent=1, default=str)
df.to_csv(f"{OUT}/protection_block_{STAMP}.csv", index=False)
md = [f"# The mandated shareholder-protection block: what it commits to ({STAMP})", "", f"Source `results/protection_block_{STAMP}.json` (`code/33_protection_block_covenants.py`); per-filing file `data/processed/protection_block_{STAMP}.csv` with the block text.", "",
      f"Coverage: {R['coverage']}", "", "## Post-reform filings by category (a filing can carry several)", "", "| Category | n | mean S | mean CAR[-1,+1] % | disposed share (labelled n) |", "|---|---|---|---|---|"] + \
     [f"| {k} | {v['n']} | {v['mean_S']} | {v['mean_car3_pct']} | {v['disposed_share']} ({v['n_labelled']}) |" for k, v in R["post_by_category"].items()] + [
      "", f"Strength index (3 charter vote / 2 horizon / 1 soft or payout / 0 none): {R['post_reform_strength']}; by strength: {json.dumps(R['post_by_strength'], ensure_ascii=False)}", "", f"'향후 회사구조개편' block states no listing within 5 years: {R['post_reform_plan_no_listing_5y']} filings.", "",
      f"Tests: {json.dumps(R['post_tests'], ensure_ascii=False)}", "", "## Expectation check", "", str(R["expectation_check"]), "",
      "## Dictionary", "", "```", json.dumps(CAT, ensure_ascii=False, indent=1), "```", "",
      "## Caveats recorded", "", "- Categories are regex matches on the block text, designed after reading all 61 post-reform blocks; the per-filing CSV carries the block text so every classification can be checked by eye (and by the human coder of strategy §4-A).",
      "- Realised outcomes for post-reform filings are young (labels to FY2025); disposal shares are not comparable with the pre-reform rate.",
      "- A 'sale plan' in the protection block is a disclosed disposal intention, not a protection measure; it is the clearest example of the block being used to state the controller's intention."]
open(f"{P}/docs/PROTECTION_BLOCK_NOTE_{STAMP}.md", "w").write("\n".join(md) + "\n"); print(f"saved results/protection_block_{STAMP}.json, docs/PROTECTION_BLOCK_NOTE_{STAMP}.md")
