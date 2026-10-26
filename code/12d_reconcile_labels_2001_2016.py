#!/usr/bin/env python3
"""12d_reconcile_labels_2001_2016.py — outcome labels for the 2001-2016 carve-outs from the annual-report extraction.

There is no 타법인출자현황-based tracker for these years, so the annual-report LLM extraction (09b on 09a passages) is the
only source. Acceptance uses the same evidence rules as 09c (evidence_supports; retained_100 must be visible in the latest
available report, with name tokens excluding the parent's own name). Events whose extraction is low-confidence, 'unclear',
or unsupported by per-year evidence get outcome 'unresolved'.
Input : data/processed/carveout_events_2001_2016.json, data/processed/annual_report_subsidiary_passages_2001_2016.json,
        results/subsidiary_status_llm/anthropic__status_2001_2016.jsonl
Output: data/processed/carveout_disposal_tracking_2001_2016.json, results/label_summary_2001_2016_<date>.json
"""
import os, re, json, gzip, datetime as dt, collections

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src = open(f"{P}/code/09c_reconcile_labels_v4.py", encoding="utf-8").read()
ns = {"P": P, "os": os, "json": json}
exec(src[src.index("def _name_tokens"):src.index("def latest_report_mentions")], ns)          # _name_tokens
exec(src[src.index("def evidence_supports"):src.index("DISPOSED = {")], ns)                      # evidence_supports
_name_tokens, evidence_supports = ns["_name_tokens"], ns["evidence_supports"]

events = json.load(open(f"{P}/data/processed/carveout_events_2001_2016.json", encoding="utf-8"))
passages = json.load(open(f"{P}/data/processed/annual_report_subsidiary_passages_2001_2016.json", encoding="utf-8"))
llm = {}
for l in open(f"{P}/results/subsidiary_status_llm/anthropic__status_2001_2016.jsonl", encoding="utf-8"):
    r = json.loads(l); llm[r["rcept_no"]] = r
VALID = {"retained_100", "partial_sale", "majority_disposed", "ipo_listed", "merged_back_into_parent", "liquidated", "division_cancelled"}
DISPOSED = {"ipo_listed", "majority_disposed", "partial_sale"}


def latest_report_mentions(rn, parsed, corp_name):
    reps = [p for p in passages.get(rn, {}).get("annual_reports", []) if not p.get("error")]
    if not reps: return False
    latest = max(reps, key=lambda p: p["fy"])
    byfy = {y.get("fy"): y for y in (parsed.get("by_fiscal_year") or []) if isinstance(y, dict)}
    y = byfy.get(latest["fy"])
    if y and y.get("status") == "subsidiary_100" and (y.get("evidence") or "").strip(): return True
    if latest.get("name_hits"): return True
    parent = re.sub(r"주식회사|\(주\)|㈜|\s+", "", corp_name)
    toks = [t for t in _name_tokens(parsed.get("actual_new_company_name")) if t not in parent and parent not in t]
    if not toks: return False
    try: txt = gzip.open(f"{P}/data/raw/annual_report_text/{latest['rcept_no']}.txt.gz", "rt", encoding="utf-8").read()
    except Exception: return False
    t = re.sub(r"\s+", "", txt); return any(tok in t for tok in toks)


out = []
for e in events:
    rec = dict(e); rn = e["rcept_no"]; r = llm.get(rn); p = (r or {}).get("parsed") or {}
    oc, conf = p.get("overall_outcome"), p.get("confidence")
    n_reports = len([x for x in passages.get(rn, {}).get("annual_reports", []) if not x.get("error")])
    ok = oc in VALID and conf in ("high", "medium") and evidence_supports(oc, p.get("by_fiscal_year") or [])
    if ok and oc == "retained_100" and not latest_report_mentions(rn, p, e["corp_name"]): ok = False
    if not r: rec["outcome"], rec["label_source"] = "unresolved", "no_extraction"
    elif n_reports == 0: rec["outcome"], rec["label_source"] = "unresolved", "no_annual_reports_found"
    elif ok:
        rec["outcome"], rec["label_source"], rec["label_confidence"] = oc, "annual_report_llm", conf
        rec["actual_new_company_name"] = p.get("actual_new_company_name"); rec["by_fiscal_year"] = p.get("by_fiscal_year"); rec["first_change_fy"] = p.get("first_change_fy"); rec["label_note"] = p.get("notes")
    else:
        rec["outcome"], rec["label_source"], rec["label_confidence"], rec["llm_overall_outcome"] = "unresolved", "llm_not_accepted", conf, oc
    rec["n_annual_reports"] = n_reports
    out.append(rec)
json.dump(out, open(f"{P}/data/processed/carveout_disposal_tracking_2001_2016.json", "w"), ensure_ascii=False, indent=1)
c = collections.Counter(r["outcome"] for r in out); src_c = collections.Counter(r["label_source"] for r in out)
clean = [r for r in out if r["outcome"] in DISPOSED | {"retained_100"}]
by_year = {}
for y in sorted({r["division_year"] for r in out}):
    cl = [r for r in clean if r["division_year"] == y]
    by_year[y] = {"n_all": sum(1 for r in out if r["division_year"] == y), "clean": len(cl), "disposed_share": round(sum(r["outcome"] in DISPOSED for r in cl) / len(cl), 3) if cl else None}
summary = {"date": dt.date.today().isoformat(), "n_events": len(out), "outcome_counts": dict(c), "label_source_counts": dict(src_c), "clean_labels": len(clean),
           "disposed_share_clean": round(sum(r["outcome"] in DISPOSED for r in clean) / len(clean), 3) if clean else None, "ipo_share_clean": round(sum(r["outcome"] == "ipo_listed" for r in clean) / len(clean), 3) if clean else None,
           "by_year": by_year, "listed_parent_clean": sum(1 for r in clean if r.get("corp_cls") in ("Y", "K")),
           "disposed_share_clean_listed": (lambda L: round(sum(r["outcome"] in DISPOSED for r in L) / len(L), 3) if L else None)([r for r in clean if r.get("corp_cls") in ("Y", "K")])}
stamp = dt.date.today().strftime("%Y%m%d"); json.dump(summary, open(f"{P}/results/label_summary_2001_2016_{stamp}.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in summary.items() if k != "by_year"}, ensure_ascii=False, indent=1)); print("by year:", {y: (v["clean"], v["disposed_share"]) for y, v in by_year.items()})
