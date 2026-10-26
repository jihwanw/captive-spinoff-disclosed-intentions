#!/usr/bin/env python3
"""20c_merge_ownership.py — one pre-event controlling-ownership record per carve-out event from two sources.
  API  (20): announcements 2016+, DART hyslrSttus, fiscal year-end before the announcement year ('기말' of FY-1); block = 계 minus treasury rows.
  LLM  (20b, GPT primary): announcements before 2016, annual-report table; the pre-division FY report's 기말 when cached, else the division-year
       report's 기초 (= end of the prior year). block = 계 row minus treasury when the 계 row is printed, else the sum of holder rows ex treasury.
Rows whose total and row-sum disagree by more than 1pp, or whose GPT and Claude extractions differ by more than 1pp (agreement file results/ownership_llm_agreement_<date>.json: 354/357 within 1pp), are kept with disagree=True (excluded by 21). Output: data/processed/ownership_pre_event_all.json
"""
import os, json, collections
P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
api = json.load(open(f"{P}/data/processed/largest_shareholder_pre_event.json", encoding="utf-8"))
out = []
for r in api:
    if not r["status"].startswith("ok"): continue
    out.append({"rcept_no": r["rcept_no"], "corp_name": r["corp_name"], "period": r["period"], "source": "dart_api", "basis": f"FY{r['bsns_year']} 기말", "block_pct": r["block_ex_treasury_pct"], "largest_pct": r["largest_pct"],
                "treasury_pct": r["treasury_pct"], "disagree": bool(r.get("rowsum_total_disagree")), "largest_method": r.get("largest_method")})
have = {r["rcept_no"] for r in out}
llm = [json.loads(l) for l in open(f"{P}/results/ownership_llm/openai.jsonl", encoding="utf-8")]
claude = {json.loads(l)["rcept_no"]: (json.loads(l).get("parsed") or {}) for l in open(f"{P}/results/ownership_llm/anthropic.jsonl", encoding="utf-8")}   # second extractor: cross-check only
def blk_of(p):
    t, s, tre = p.get("block_pct_total_row"), p.get("block_pct_sum_ex_treasury"), p.get("treasury_pct") or 0
    if isinstance(t, (int, float)): return t - tre
    return s if isinstance(s, (int, float)) else None
stat = collections.Counter()
for r in llm:
    p = r.get("parsed") or {}
    if r["rcept_no"] in have or not p.get("table_found"): stat["skipped"] += 1; continue
    tot, s, tre = p.get("block_pct_total_row"), p.get("block_pct_sum_ex_treasury"), p.get("treasury_pct") or 0
    num = lambda x: isinstance(x, (int, float))
    if num(tot): block = round(tot - tre, 2); dis = num(s) and abs(block - s) > 1.0
    elif num(s): block = s; dis = False
    else: stat["no_block"] += 1; continue
    cb = blk_of(claude.get(r["rcept_no"], {}))
    if cb is not None and abs(cb - block) > 1.0: dis = True; stat["cross_model_disagree"] += 1   # GPT vs Claude differ by more than 1pp
    out.append({"rcept_no": r["rcept_no"], "corp_name": r["corp_name"], "period": "2001-2016", "source": "annual_report_llm_gpt", "basis": f"FY{r['report_fy']} {r['column']}", "block_pct": block, "largest_pct": p.get("largest_pct") if num(p.get("largest_pct")) else None,
                "treasury_pct": tre, "disagree": bool(dis), "largest_method": "llm", "report_rcept_no": r["report_rcept_no"]}); stat["ok"] += 1
json.dump(out, open(f"{P}/data/processed/ownership_pre_event_all.json", "w"), ensure_ascii=False, indent=1)
print("merged:", len(out), "| llm add:", dict(stat), "| by source:", dict(collections.Counter(r["source"] for r in out)), "| disagree:", sum(1 for r in out if r["disagree"]))
