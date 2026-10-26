#!/usr/bin/env python3
"""09c_reconcile_labels_v4.py — v4 outcome labels = v3 tracker + annual-report evidence (09a/09b).

Rules (recorded in each v4 record under `label_source` / `label_note`):
  * events not in the audit queue keep their v3 outcome (source 'v3_tracker');
  * queued events: if the LLM extraction has confidence high or medium and an overall_outcome other than 'unclear',
    the v4 outcome is the LLM outcome (source 'annual_report_llm'), with the actual company name and per-year evidence kept;
    otherwise the v3 outcome is kept (source 'v3_tracker_unresolved');
  * 'liquidated' and 'division_cancelled' are new categories and are excluded from the clean disposed/retained labels.
Clean labels for the Gate-1 analyses: disposed = ipo_listed | majority_disposed | partial_sale ; retained = retained_100.
Output: data/processed/carveout_disposal_tracking_v4.json, results/label_reconciliation_v4_<date>.json
"""
import json, os, datetime as dt, collections

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
v3 = json.load(open(f"{P}/data/processed/carveout_disposal_tracking_v3.json", encoding="utf-8"))
v3_by_rn = {r["rcept_no"]: r for r in v3}
llm = {}
for l in open(f"{P}/results/subsidiary_status_llm/anthropic__status_merged.jsonl", encoding="utf-8"):
    r = json.loads(l); llm[r["rcept_no"]] = r          # last record per rcept_no wins (resumable appends)
queue = {q["rcept_no"] for q in json.load(open(f"{P}/results/label_audit_queue_v3.json", encoding="utf-8"))}
passages = json.load(open(f"{P}/data/processed/annual_report_subsidiary_passages_v1.json", encoding="utf-8"))
_p2 = f"{P}/data/processed/annual_report_subsidiary_passages_v2_secondpass.json"
if os.path.exists(_p2): passages.update(json.load(open(_p2, encoding="utf-8")))   # second pass: actual-name variants added (2026-10-17)


def _name_tokens(s):
    """Normalised name tokens from a (possibly multi-company, possibly '(현 …)'-annotated) name string."""
    import re
    if not s: return []
    parts = re.split(r"[,/및·]| 및 |\(|\)", s)
    toks = set()
    for x in parts:
        x = re.sub(r"분할신설회사\s*\d*\s*사?:?|현\s|구\s|주식회사|\(주\)|㈜|유한회사|\s+|\d{4}년.*", "", x).strip("·,.:;- ")
        if len(x) >= 2 and not re.fullmatch(r"[A-Za-z.,& ]+", x): toks.add(x)
    return sorted(toks, key=len, reverse=True)


def latest_report_mentions(rn, parsed):
    """retained_100 must still be visible in the LATEST available annual report: either the LLM's per-year status for the
    latest FY is subsidiary_100 with quoted evidence, or the latest report's full text contains a filing-name variant or
    the actual company name found by the LLM (filing names are often provisional, e.g. 남선인베스트먼트 -> 남선홀딩스).
    2026-10-17 audit: 휴코드홀딩스 2021 (last 100% mention FY2022, absent FY2023-25) is the case this rule excludes."""
    import re, gzip
    reps = [p for p in passages.get(rn, {}).get("annual_reports", []) if not p.get("error")]
    if not reps: return False
    latest = max(reps, key=lambda p: p["fy"])
    byfy = {y.get("fy"): y for y in (parsed.get("by_fiscal_year") or []) if isinstance(y, dict)}
    y = byfy.get(latest["fy"])
    if y and y.get("status") == "subsidiary_100" and (y.get("evidence") or "").strip(): return True
    if latest.get("name_hits"): return True
    parent = re.sub(r"주식회사|\(주\)|㈜|\s+", "", v3_by_rn[rn]["corp_name"])
    toks = [t_ for t_ in _name_tokens(parsed.get("actual_new_company_name")) if t_ not in parent and parent not in t_]   # not the parent's own name
    if not toks: return False
    try: txt = gzip.open(f"{P}/data/raw/annual_report_text/{latest['rcept_no']}.txt.gz", "rt", encoding="utf-8").read()
    except Exception: return False
    t = re.sub(r"\s+", "", txt)
    return any(tok in t for tok in toks)


VALID = {"retained_100", "partial_sale", "majority_disposed", "ipo_listed", "merged_back_into_parent", "liquidated", "division_cancelled"}


def evidence_supports(oc, byfy):
    """Accept an LLM overall outcome only if the per-fiscal-year statuses/percentages it extracted contain explicit support:
    retained_100: the last year with a mention says subsidiary_100 (or pct >= 99.5) and no year says sold/listed/merged;
    partial_sale: a year with subsidiary_partial or 50 <= pct < 99.5; majority_disposed: a year with sold_out or pct < 50;
    ipo_listed: a 'listed' year; merged_back_into_parent: a 'merged_into_parent' year; liquidated: a 'liquidated' year;
    division_cancelled: never accepted automatically (manual review)."""
    st = [(y.get("status"), y.get("ownership_pct")) for y in byfy if isinstance(y, dict)]
    mentioned = [(s_, pc) for s_, pc in st if s_ not in (None, "not_mentioned", "unclear")]
    pcts = [pc for _, pc in st if isinstance(pc, (int, float))]
    if oc == "retained_100":
        return bool(mentioned) and mentioned[-1][0] == "subsidiary_100" and not any(s_ in ("sold_out", "listed", "merged_into_parent", "liquidated") for s_, _ in st)
    if oc == "partial_sale":
        return any(s_ == "subsidiary_partial" for s_, _ in st) or any(50 <= pc < 99.5 for pc in pcts)
    if oc == "majority_disposed":
        return any(s_ == "sold_out" for s_, _ in st) or any(pc < 50 for pc in pcts)
    if oc == "ipo_listed": return any(s_ == "listed" for s_, _ in st)
    if oc == "merged_back_into_parent": return any(s_ == "merged_into_parent" for s_, _ in st)
    if oc == "liquidated": return any(s_ == "liquidated" for s_, _ in st)
    return False
DISPOSED = {"ipo_listed", "majority_disposed", "partial_sale"}

v4, changes = [], []
for r in v3:
    rec = dict(r); rn = r["rcept_no"]; rec["v3_outcome"] = r["outcome"]
    if rn in queue and rn in llm and (llm[rn].get("parsed") or {}):
        p = llm[rn]["parsed"]; oc, conf = p.get("overall_outcome"), p.get("confidence")
        ok = oc in VALID and conf in ("high", "medium") and evidence_supports(oc, p.get("by_fiscal_year") or [])
        if ok and oc == "retained_100" and not latest_report_mentions(rn, p): ok = False   # must still be visible in the latest report
        if ok:
            rec["outcome"] = oc; rec["label_source"] = "annual_report_llm"; rec["label_confidence"] = conf
            rec["actual_new_company_name"] = p.get("actual_new_company_name"); rec["by_fiscal_year"] = p.get("by_fiscal_year"); rec["first_change_fy"] = p.get("first_change_fy")
            rec["label_note"] = p.get("notes")
            if oc != r["outcome"]: changes.append({"rcept_no": rn, "corp_name": r["corp_name"], "division_year": r["division_year"], "v3": r["outcome"], "v4": oc, "confidence": conf, "name": p.get("actual_new_company_name")})
        else:
            rec["label_source"] = "v3_tracker_unresolved"; rec["label_confidence"] = conf; rec["llm_overall_outcome"] = oc
            rec["label_note"] = "LLM outcome not accepted: low confidence, 'unclear', per-year evidence does not support it, or (retained_100) the company is absent from the latest annual report"
    else:
        rec["label_source"] = "v3_tracker"
    v4.append(rec)
# Cross-check of the tracker-labelled events against the annual reports (09a/09b --events crossval_tracker_events.json;
# results/label_crosscheck_tracker_20261018.json, categories assigned 2026-10-18): apply the documented corrections and flag the
# definition-sensitive events (intra-group transfers, temporary dilutions, minority stakes, unresolved conflicts).
_cc = f"{P}/results/label_crosscheck_tracker_20261018.json"
if os.path.exists(_cc):
    for d in json.load(open(_cc, encoding="utf-8"))["disagreements"]:
        for rec in v4:
            if rec["rcept_no"] != d["rcept_no"]: continue
            rec["label_crosscheck"] = d["category"]
            if d.get("corrected_outcome"):
                rec["v3_outcome_before_crosscheck"] = rec["outcome"]; rec["outcome"] = d["corrected_outcome"]
                rec["label_source"] = "tracker_corrected_by_annual_report"; rec["label_note"] = d["note"]
json.dump(v4, open(f"{P}/data/processed/carveout_disposal_tracking_v4.json", "w"), ensure_ascii=False, indent=1)

c3 = collections.Counter(r["outcome"] for r in v3); c4 = collections.Counter(r["outcome"] for r in v4)
clean3 = sum(1 for r in v3 if r["outcome"] in DISPOSED | {"retained_100"}); clean4 = sum(1 for r in v4 if r["outcome"] in DISPOSED | {"retained_100"})
src = collections.Counter(r["label_source"] for r in v4)
trans = collections.Counter((c["v3"], c["v4"]) for c in changes)
summary = {"date": dt.date.today().isoformat(), "n_events": len(v4), "outcome_counts_v3": dict(c3), "outcome_counts_v4": dict(c4),
           "clean_labels_v3": clean3, "clean_labels_v4": clean4,
           "disposed_share_clean_v3": round(sum(1 for r in v3 if r["outcome"] in DISPOSED) / clean3, 3), "disposed_share_clean_v4": round(sum(1 for r in v4 if r["outcome"] in DISPOSED) / clean4, 3),
           "label_source_counts": dict(src), "n_changed": len(changes), "transitions_v3_to_v4": {f"{a} -> {b}": n for (a, b), n in trans.most_common()},
           "llm_confidence_counts_queue": dict(collections.Counter((llm[rn].get("parsed") or {}).get("confidence", "no_parse") for rn in queue if rn in llm)),
           "changes": changes}
stamp = dt.date.today().strftime("%Y%m%d")
json.dump(summary, open(f"{P}/results/label_reconciliation_v4_{stamp}.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in summary.items() if k != "changes"}, ensure_ascii=False, indent=1))
print("saved data/processed/carveout_disposal_tracking_v4.json and results/label_reconciliation_v4_%s.json" % stamp)
