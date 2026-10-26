#!/usr/bin/env python3
"""12c_build_tracking_2001_2016.py — tracking-format records for the 2001-2016 carve-outs.

Input : data/processed/division_events_2001_2016.json (12b: filings clustered into events + LLM-extracted fields)
Output: data/processed/carveout_events_2001_2016.json — one record per carve-out event in the format used by the 2017+
        pipeline (corp_code, corp_name, corp_cls, rcept_no, board_date, division_date, division_year, new_co, candidates,
        outcome='unknown', per_new_company=[]), plus provenance (division_type, confidence, text filing);
        data/processed/disclosure_text_index_2001_2016.json — rcept_no -> {path, corp_name, ...} for the judge (04).
Selection: division_type in {물적분할, 혼합(물적+인적)} with at least one new company allotted to the parent; 분할합병 and 인적분할 are
kept in a separate list (spin_offs_2001_2016.json) for the price study. Events whose text was unreadable keep division_type
'unknown' and are listed in unclassified_2001_2016.json.
"""
import os, re, json, collections, datetime as dt

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ev = json.load(open(f"{P}/data/processed/division_events_2001_2016.json", encoding="utf-8"))
TXTDIR = f"{P}/data/raw/disclosure_text_2001_2016"


def norm_date(s):
    if not s: return None
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", s)
    return f"{int(m.group(1))}년 {int(m.group(2)):02d}월 {int(m.group(3)):02d}일" if m else None


carve, spin, uncl, index = [], [], [], {}
for e in ev:
    llm = (e.get("llm") or {}).get("parsed") or {}
    ty = llm.get("division_type") or "unknown"
    first = e["first_filing_date"]; rn = e["event_id"]
    newcos = llm.get("new_companies") or []
    parent_allotted = [c for c in newcos if isinstance(c, dict) and c.get("shares_allotted_to") == "parent"]
    rec = {"corp_code": e["corp_code"], "corp_name": e["corp_name"], "corp_cls": e.get("corp_cls"), "stock_code": e.get("stock_code"), "rcept_no": rn,
           "board_date": norm_date(llm.get("board_date")) or f"{first[:4]}년 {first[4:6]}월 {first[6:]}일", "division_date": norm_date(llm.get("division_date")),
           "division_year": int((llm.get("division_date") or first)[:4]) if re.match(r"\d{4}", str(llm.get("division_date") or first)) else int(first[:4]),
           "type": {"물적분할": "carve_out", "혼합(물적+인적)": "mixed", "인적분할": "spin_off", "분할합병": "division_merger"}.get(ty, "unknown"),
           "division_type_llm": ty, "llm_confidence": llm.get("confidence"), "type_evidence": llm.get("type_evidence"),
           "new_co": " / ".join(c.get("name", "") for c in newcos if isinstance(c, dict)) or None,
           "candidates": [c.get("name") for c in (parent_allotted or newcos) if isinstance(c, dict) and c.get("name")],
           "new_company_listing_plan": llm.get("new_company_listing_plan"), "stated_purpose": llm.get("stated_purpose"), "appraisal_rights": llm.get("appraisal_rights"),
           "text_rcept_no": e.get("text_rcept_no"), "filings": e["filings"], "outcome": "unknown", "per_new_company": [], "kind_listings": [], "parent_event_filings": [], "merger_hits": []}
    if e.get("text_rcept_no"):
        index[rn] = {"corp_code": e["corp_code"], "corp_name": e["corp_name"], "type": rec["type"], "board_date": rec["board_date"], "division_date": rec["division_date"],
                     "path": f"data/raw/disclosure_text_2001_2016/{e['text_rcept_no']}.txt", "text_rcept_no": e["text_rcept_no"]}
    if ty in ("물적분할", "혼합(물적+인적)") and (parent_allotted or ty == "물적분할"): carve.append(rec)
    elif ty in ("인적분할", "분할합병"): spin.append(rec)
    else: uncl.append(rec)
json.dump(carve, open(f"{P}/data/processed/carveout_events_2001_2016.json", "w"), ensure_ascii=False, indent=1)
json.dump(spin, open(f"{P}/data/processed/spinoffs_2001_2016.json", "w"), ensure_ascii=False, indent=1)
json.dump(uncl, open(f"{P}/data/processed/unclassified_2001_2016.json", "w"), ensure_ascii=False, indent=1)
json.dump(index, open(f"{P}/data/processed/disclosure_text_index_2001_2016.json", "w"), ensure_ascii=False, indent=1)
print("events:", len(ev), "| carve-outs (물적/혼합):", len(carve), "| spin-offs/division-mergers:", len(spin), "| unclassified:", len(uncl))
print("carve-outs by year:", dict(sorted(collections.Counter(r["division_year"] for r in carve).items())))
print("carve-outs by corp_cls:", dict(collections.Counter(r["corp_cls"] for r in carve)), "| confidence:", dict(collections.Counter(r["llm_confidence"] for r in carve)))
print("division types (all):", dict(collections.Counter(r["division_type_llm"] for r in carve + spin + uncl)))
