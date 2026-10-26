#!/usr/bin/env python3
"""11_descriptives_v4.py — descriptive facts for proposition A (carve-out disposals were legible at announcement; the
2022-12 disclosure rule changed what filings say).

Sources: data/processed/carveout_disposal_tracking_v4.json (labels, with annual-report evidence), results/llm_judge/*
(parsed facts per filing: stated purposes, listing/IPO mentions, investor/sale mentions, shareholder-protection measures),
data/raw/dart_division_decisions_2017_2026.json (board dates). Output: results/descriptives_v4_<date>.json
"""
import json, glob, os, re, datetime as dt, collections, numpy as np

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
v4 = json.load(open(f"{P}/data/processed/carveout_disposal_tracking_v4.json", encoding="utf-8"))
ev = {e["rcept_no"]: e for e in json.load(open(f"{P}/data/raw/dart_division_decisions_2017_2026.json", encoding="utf-8"))}
DISPOSED = {"ipo_listed", "majority_disposed", "partial_sale"}; CLEAN = DISPOSED | {"retained_100"}


def kdate(s):
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", s or "")
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


res = {"n_carveouts_2017_2026": len(v4), "outcome_counts_v4": dict(collections.Counter(r["outcome"] for r in v4))}
# 1. disposal share by division year (clean labels) and the FRL-comparable window 2017-2022
by = collections.defaultdict(lambda: collections.Counter())
for r in v4: by[r["division_year"]][r["outcome"]] += 1
res["by_division_year"] = {}
for y in sorted(by):
    c = by[y]; clean = sum(c[o] for o in CLEAN); disp = sum(c[o] for o in DISPOSED)
    res["by_division_year"][y] = {"n_all": sum(c.values()), "clean": clean, "disposed": disp, "disposed_share_clean": round(disp / clean, 3) if clean else None,
                                  "ipo": c["ipo_listed"], "majority_disposed": c["majority_disposed"], "partial_sale": c["partial_sale"], "retained_100": c["retained_100"],
                                  "merged_back": c["merged_back_into_parent"], "liquidated": c["liquidated"], "unresolved": c["unmatched"] + c["majority_disposed_or_dropped"] + c["too_recent"]}
w = [r for r in v4 if 2017 <= r["division_year"] <= 2022]
clean_w = [r for r in w if r["outcome"] in CLEAN]
res["window_2017_2022"] = {"n_all": len(w), "clean": len(clean_w), "disposed_share_clean": round(sum(r["outcome"] in DISPOSED for r in clean_w) / len(clean_w), 3),
                          "ipo_share_clean": round(sum(r["outcome"] == "ipo_listed" for r in clean_w) / len(clean_w), 3),
                          "disposed_or_diluted_share_all_resolved": round(sum(r["outcome"] in DISPOSED for r in w) / sum(r["outcome"] in CLEAN | {"merged_back_into_parent", "liquidated"} for r in w), 3),
                          "benchmark_FRL_2001_2021": {"disposal_share": 0.69, "listing_share": 0.04, "source": "Kang & Lee (2025) FRL 85:107826, as recorded in docs/WINNING_MEMO_20261014.md"}}
# 2. time to first change (annual-report labels carry first_change_fy)
ttc = [r["first_change_fy"] - r["division_year"] for r in v4 if r.get("label_source") == "annual_report_llm" and isinstance(r.get("first_change_fy"), int) and r["outcome"] in DISPOSED]
res["years_to_first_change_annual_report_labels"] = {"n": len(ttc), "distribution": dict(sorted(collections.Counter(ttc).items())), "median": float(np.median(ttc)) if ttc else None}
# 3. filing content before/after the 2022-12 rule (parsed facts from the identified Claude run 1; GPT as a check)
facts = {}
for f in sorted(glob.glob(f"{P}/results/llm_judge/anthropic__identified.jsonl")):
    for l in open(f, encoding="utf-8"):
        r = json.loads(l); pr = r.get("parsed") or {}
        if pr.get("facts"): facts[r["rcept_no"]] = {"p": pr.get("p_disposal"), **pr["facts"]}
gfacts = {}
for l in open(f"{P}/results/llm_judge/openai__identified.jsonl", encoding="utf-8"):
    r = json.loads(l); pr = r.get("parsed") or {}
    if pr.get("facts"): gfacts[r["rcept_no"]] = {"p": pr.get("p_disposal"), **pr["facts"]}
CUT = dt.date(2022, 10, 17)  # EMPIRICAL cut-over (checked 2026-10-17 on the filing texts): every 회사분할결정 filing from 2022-10-17 (삼양패키징) onward
#  contains a 주주보호 section; among earlier filings only 풍산 2022-10-04 and one 한화솔루션 2022-09-23 version do. This follows the FSC's
#  2022-09 '물적분할 자회사 상장 관련 일반주주 권익 제고방안'; the exact effective date of the amended 주요사항보고서 form must be verified
#  against the FSC/금융감독원 notice before it is written in the paper.
res["filing_content_by_period"] = {}
for name, fx in (("claude", facts), ("gpt", gfacts)):
    per = {"pre_rule": [], "post_rule": []}
    for rn, d in fx.items():
        bd = kdate(ev.get(rn, {}).get("board_date")) or dt.datetime.strptime(rn[:8], "%Y%m%d").date()
        per["post_rule" if bd >= CUT else "pre_rule"].append(d)
    out = {}
    for k, rows in per.items():
        if not rows: continue
        out[k] = {"n": len(rows),
                  "share_mentions_shareholder_protection": round(float(np.mean([bool(d.get("mentions_shareholder_protection_measures")) for d in rows])), 3),
                  "share_mentions_listing_or_ipo": round(float(np.mean([bool(d.get("mentions_listing_or_ipo")) for d in rows])), 3),
                  "share_mentions_external_investor": round(float(np.mean([bool(d.get("mentions_external_investment_or_strategic_investor")) for d in rows])), 3),
                  "share_mentions_sale_or_buyer": round(float(np.mean([bool(d.get("mentions_sale_or_buyer")) for d in rows])), 3),
                  "mean_p_disposal": round(float(np.mean([d["p"] for d in rows if isinstance(d.get("p"), (int, float))])), 1),
                  "purpose_categories_top": dict(collections.Counter(c for d in rows for c in (d.get("stated_purpose_categories") or [])).most_common(6))}
    res["filing_content_by_period"][name] = out
stamp = dt.date.today().strftime("%Y%m%d"); json.dump(res, open(f"{P}/results/descriptives_v4_{stamp}.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: res[k] for k in ("window_2017_2022", "years_to_first_change_annual_report_labels")}, ensure_ascii=False, indent=1))
print("by year (clean, disposed share):", {y: (v["clean"], v["disposed_share_clean"]) for y, v in res["by_division_year"].items()})
print("filing content by period (claude):", json.dumps(res["filing_content_by_period"].get("claude"), ensure_ascii=False, indent=1))
print(f"saved results/descriptives_v4_{stamp}.json")
