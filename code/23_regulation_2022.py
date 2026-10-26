#!/usr/bin/env python3
"""23_regulation_2022.py — did the 2022 reforms change what 물적분할 filings say, what they signal, and what followed? (before/after description)

Regulatory sequence (verified 2026-10-25 on the FSC press releases, fsc.go.kr/no010101/78449 and /79125):
2022-03-07 corporate-governance-report guideline revised (shareholder-protection policy to be described on ownership-structure changes);
2022-09-05 FSC "물적분할 자회사 상장 관련 일반주주 권익 제고방안" — three measures: (1) 공시 강화: the 주요사항보고서 form (기업공시서식) to state the
division's purpose, expected effects and shareholder-protection measures, (2) appraisal rights for shareholders dissenting from a 물적분할 (Capital
Markets Act enforcement decree; notice of legislation from 9 September 2022), (3) KRX listing review of a carved-out subsidiary within five years of the
division to assess the parent's protection of general shareholders, applied also to divisions completed before the rule change if within five years;
the FSC stated that the disclosure-form and listing-rule revisions would be completed "by October [2022]". 2022-12-20: the decree amendment passed the
Cabinet, "to be promulgated within the year and take effect immediately". In the filings themselves (LLM fact mentions_shareholder_protection_measures),
every 물적분할 filing from 2022-10-17 onward states protection measures, none did before September 2022 except two in late September (한화솔루션 9/23,
누리플랜 9/29 partially), so POST = filings received on/after 2022-10-01 (CUTOFF); the appraisal right applies from late December 2022 and the
first post-cutoff quarter therefore has the disclosure rule without the appraisal right (noted in the output).
There is no control group here (the rules targeted 물적분할 itself), so this is a before/after description, not a DiD.

Series by filing year and pre/post: n; LLM facts from the identified runs (share of judgments with mentions_shareholder_protection_measures,
mentions_listing_or_ipo, mentions_sale_or_buyer; stated-purpose categories); disposal score (two-model mean); announcement CAR[-1,+1];
realized disposal and early disposal (first change <= 1 year) — only for events with at least two fiscal years of follow-up
(division year <= 2023), so post-period outcome rates are reported for 2022-10..2023 filings only and flagged as immature otherwise;
score -> early-disposal AUC pre vs post. Tests: Welch/Mann–Whitney for the score and CAR shifts; Fisher for the mention shares.
Inputs: results/llm_judge*/{anthropic,openai}__identified*.jsonl, data/processed/bhar_controls_events_20261025.csv (returns, timing),
        data/raw/dart_division_decisions_2017_2026.json (all 2017+ carve-outs for the filing-content series, incl. unlisted parents).
Output: results/regulation_2022_<date>.json
"""
import os, json, glob, collections, datetime as dt, numpy as np, pandas as pd
from scipy import stats
from sklearn.metrics import roc_auc_score

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUTOFF = "2022-10-01"
DISPOSED = {"ipo_listed", "majority_disposed", "partial_sale"}

facts = collections.defaultdict(list); score = collections.defaultdict(list)
for f in glob.glob(f"{P}/results/llm_judge*/*__identified*.jsonl"):
    for l in open(f, encoding="utf-8"):
        r = json.loads(l); p = r.get("parsed") or {}
        if isinstance(p.get("p_disposal"), (int, float)): score[r["rcept_no"]].append(float(p["p_disposal"]) / 100)
        fc = p.get("facts") or {}
        if fc: facts[r["rcept_no"]].append({"protect": bool(fc.get("mentions_shareholder_protection_measures")), "listing": bool(fc.get("mentions_listing_or_ipo")), "sale": bool(fc.get("mentions_sale_or_buyer")),
                                           "ext_inv": bool(fc.get("mentions_external_investment_or_strategic_investor")), "purposes": fc.get("stated_purpose_categories") or []})
ev = []
for r in json.load(open(f"{P}/data/processed/carveout_disposal_tracking_2001_2016.json", encoding="utf-8")): ev.append({"rcept_no": r["rcept_no"], "corp_name": r["corp_name"], "outcome": r["outcome"], "division_year": int(r["division_year"]), "fcfy": r.get("first_change_fy")})
v4 = {r["rcept_no"]: r for r in json.load(open(f"{P}/data/processed/carveout_disposal_tracking_v4.json", encoding="utf-8"))}
for r in json.load(open(f"{P}/data/raw/dart_division_decisions_2017_2026.json", encoding="utf-8")):
    if r.get("type") == "carve_out":
        v = v4.get(r["rcept_no"], {}); ev.append({"rcept_no": r["rcept_no"], "corp_name": r["corp_name"], "outcome": v.get("outcome"), "division_year": int(v["division_year"]) if v.get("division_year") else int(r["rcept_no"][:4]), "fcfy": v.get("first_change_fy")})
d = pd.DataFrame(ev).drop_duplicates("rcept_no"); d["date"] = pd.to_datetime(d.rcept_no.str[:8]); d["year"] = d.date.dt.year; d["post"] = d.date >= pd.Timestamp(CUTOFF)
d["score"] = d.rcept_no.map(lambda k: float(np.mean(score[k])) if score.get(k) else np.nan)
for key in ("protect", "listing", "sale", "ext_inv"): d[key] = d.rcept_no.map(lambda k, key=key: float(np.mean([x[key] for x in facts[k]])) if facts.get(k) else np.nan)
d["purpose_sale"] = d.rcept_no.map(lambda k: float(np.mean(["sale_or_disposal" in x["purposes"] for x in facts[k]])) if facts.get(k) else np.nan)
d["purpose_fund"] = d.rcept_no.map(lambda k: float(np.mean(["fundraising_or_investment_attraction" in x["purposes"] for x in facts[k]])) if facts.get(k) else np.nan)
d["disposed"] = d.outcome.map(lambda o: 1.0 if o in DISPOSED else (0.0 if o == "retained_100" else np.nan))
def early(r):
    if r.outcome == "retained_100": return 0.0
    if r.outcome not in DISPOSED: return np.nan
    try: return 1.0 if int(r.fcfy) - int(r.division_year) <= 1 else 0.0
    except Exception: return np.nan
d["early"] = d.apply(early, axis=1); d["mature"] = d.division_year <= 2023
co = pd.read_csv(f"{P}/data/processed/bhar_controls_events_20261025.csv", dtype={"rcept_no": str})[["rcept_no", "car_mm_m1_p1", "bhar_madj_p2_p250"]]
d = d.merge(co, on="rcept_no", how="left")

def yearly(g):
    m = g[g.mature]
    return {"n_filings": int(len(g)), "n_with_llm_facts": int(g.protect.notna().sum()), "share_mentions_protection": round(float(g.protect.mean()), 3) if g.protect.notna().any() else None,
            "share_mentions_listing": round(float(g.listing.mean()), 3) if g.listing.notna().any() else None, "share_mentions_sale": round(float(g.sale.mean()), 3) if g.sale.notna().any() else None,
            "share_purpose_sale_or_disposal": round(float(g.purpose_sale.mean()), 3) if g.purpose_sale.notna().any() else None, "share_purpose_fundraising": round(float(g.purpose_fund.mean()), 3) if g.purpose_fund.notna().any() else None,
            "mean_score": round(float(g.score.mean()), 3) if g.score.notna().any() else None, "mean_ann_car": round(float(g.car_mm_m1_p1.mean()), 4) if g.car_mm_m1_p1.notna().any() else None, "n_ann_car": int(g.car_mm_m1_p1.notna().sum()),
            "disposal_rate_mature": round(float(m.disposed.mean()), 3) if m.disposed.notna().any() else None, "n_clean_mature": int(m.disposed.notna().sum()),
            "early_disposal_rate_mature": round(float(m.early.mean()), 3) if m.early.notna().any() else None, "n_early_mature": int(m.early.notna().sum())}
res = {"run_at": dt.datetime.now().isoformat(timespec="seconds"), "cutoff_post": CUTOFF, "caveats": ["before/after only — the rules applied to all 물적분할, no untreated group", "post-period outcome rates use events with division year <= 2023 (two fiscal years of annual reports); later events are immature",
       "regulatory dates verified on FSC releases 2022-09-05 (fsc.go.kr/no010101/78449: three measures; form and listing-rule revisions to be completed by October 2022) and 2022-12-20 (fsc.go.kr/no010101/79125: appraisal-right decree passed Cabinet, promulgation and immediate effect within 2022); "
       "filings state protection measures from 2022-10-17 onward (first: 삼양패키징); the appraisal right was not yet in force for filings between 2022-10 and late 2022-12"],
       "by_year": {int(y): yearly(g) for y, g in d[d.year >= 2015].groupby("year")}, "pre_post": {}}
pre, post = d[(~d.post) & (d.year >= 2017)], d[d.post]      # same collection method (2017+ structured API) on both sides
def cmp_mean(a, b):
    a, b = a.dropna(), b.dropna()
    if len(a) < 5 or len(b) < 5: return {"n_pre": int(len(a)), "n_post": int(len(b))}
    return {"n_pre": int(len(a)), "n_post": int(len(b)), "mean_pre": round(float(a.mean()), 4), "mean_post": round(float(b.mean()), 4), "welch_p": round(float(stats.ttest_ind(a, b, equal_var=False)[1]), 3), "mannwhitney_p": round(float(stats.mannwhitneyu(a, b, alternative="two-sided")[1]), 3)}
def cmp_share(a, b):
    a, b = a.dropna(), b.dropna()
    if len(a) < 5 or len(b) < 5: return {"n_pre": int(len(a)), "n_post": int(len(b))}
    ta = [int(round(a.sum())), int(len(a) - round(a.sum()))]; tb = [int(round(b.sum())), int(len(b) - round(b.sum()))]
    return {"n_pre": int(len(a)), "n_post": int(len(b)), "share_pre": round(float(a.mean()), 3), "share_post": round(float(b.mean()), 3), "fisher_p": round(float(stats.fisher_exact([ta, tb])[1]), 3)}
res["pre_post"] = {"filings_mention_protection": cmp_share(pre.protect.round(), post.protect.round()), "filings_mention_listing": cmp_share(pre.listing.round(), post.listing.round()),
                   "purpose_sale_or_disposal": cmp_share(pre.purpose_sale.round(), post.purpose_sale.round()), "purpose_fundraising": cmp_share(pre.purpose_fund.round(), post.purpose_fund.round()),
                   "disposal_score": cmp_mean(pre.score, post.score), "announcement_car": cmp_mean(pre.car_mm_m1_p1, post.car_mm_m1_p1),
                   "disposal_rate_mature_only": cmp_share(pre[pre.mature].disposed, post[post.mature].disposed), "early_disposal_rate_mature_only": cmp_share(pre[pre.mature].early, post[post.mature].early),
                   "n_filings_per_year_pre_vs_post": {"pre_2017_to_cutoff": round(len(pre) / ((pd.Timestamp(CUTOFF) - pd.Timestamp("2017-01-01")).days / 365.25), 1), "post": round(len(post) / ((d.date.max() - pd.Timestamp(CUTOFF)).days / 365.25), 1)}}
for lab, g in (("pre", pre), ("post_mature", post[post.mature])):
    e = g.dropna(subset=["score", "early"])
    if len(e) >= 20 and e.early.nunique() > 1: res["pre_post"][f"score_to_early_auc_{lab}"] = {"n": int(len(e)), "auc": round(float(roc_auc_score(e.early, e.score)), 3)}
stamp = dt.date.today().strftime("%Y%m%d"); json.dump(res, open(f"{P}/results/regulation_2022_{stamp}.json", "w"), ensure_ascii=False, indent=1, default=float)
print("by year (2015+):")
for y, v in res["by_year"].items(): print(f"  {y}: n {v['n_filings']:3d} | protect {v['share_mentions_protection']} listing {v['share_mentions_listing']} sale-purpose {v['share_purpose_sale_or_disposal']} | score {v['mean_score']} | annCAR {v['mean_ann_car']} (n {v['n_ann_car']}) | disposal(mature) {v['disposal_rate_mature']} early {v['early_disposal_rate_mature']} (n {v['n_early_mature']})")
print("\npre/post:"); [print(f"  {k}: {v}") for k, v in res["pre_post"].items()]
print(f"saved results/regulation_2022_{stamp}.json")
