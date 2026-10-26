#!/usr/bin/env python3
"""18_bhar_pooled.py — the experiment of 16 on the pooled 2001–2026 carve-out sample (power extension).

Price sources (why two): 2017+ events use the KRX adjusted-price panel of 13 (halt days removed, corporate-action adjustment verified on
BGF; see 13's header); 2001–2016 events use the Compustat Global panel of 17, because the KRX adjusted endpoint has no history there.
On the 2017+ overlap the two sources agree (233 events, median daily-return correlation 0.9998, 0.2% of days differ by more than 1pp;
results/price_coverage_compustat_<date>.json), except for a few corporate-action days where Compustat's adjustment factor is missing
(e.g. a +97% day where KRX shows a halt, a -60% day on a spin-off re-listing). Such days exceed the KRX daily price limit (15% before
2015-06-15, 30% after), which a genuine trading day cannot, unless the stock is in delisting proceedings. Screen for 2001–2016 events:
an event is FLAGGED when a day in [-1,+250] has |ret| > limit + 1pp and the parent was not delisted within the window; flagged events
are excluded from the main pooled run and included in a sensitivity run (tag pooled_incl_flagged).
Scores: results/llm_judge_2001_2016/{anthropic,openai}__identified.jsonl (one identified run per model for 2001–2016), Gate-1 two-model
average, as in 15_gate1_pooled.py. Labels: data/processed/carveout_disposal_tracking_2001_2016.json, clean = disposed vs retained_100.
Disposal timing: first_change_fy (first fiscal year whose annual report shows the new company sold/listed/diluted) minus the division year.
`build_pooled()` is imported by 19_bhar_controls.py. Runs as a script: pooled (main), compustat2001_2016, pooled_incl_flagged.
"""
import os, json, importlib.util, datetime as dt, numpy as np, pandas as pd

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("b16", f"{P}/code/16_bhar_by_predicted_disposal.py"); b16 = importlib.util.module_from_spec(spec); spec.loader.exec_module(b16)
KEEP = ["rcept_no", "corp_name", "corp_cls", "stock_code", "event_date", "p_llm", "outcome", "disposed", "year", "period"]


def build_pooled():
    """2001–2016 Compustat carve-outs (with flag_glitch) and 2017+ KRX carve-outs, both with the Gate-1 score, clean labels, year, period."""
    cs = pd.read_parquet(f"{P}/data/processed/event_returns_daily_compustat.parquet")
    for c in ("ret", "mret", "ar_madj", "ar_mm"): cs[c] = cs[c].astype("float64")   # the WRDS extract arrives as pandas nullable floats
    cs["tau"] = cs.tau.astype(int)
    md = pd.read_csv(f"{P}/data/processed/event_study_meta_compustat.csv", dtype={"rcept_no": str, "stock_code": str, "gvkey": str})
    old = {r["rcept_no"]: r for r in json.load(open(f"{P}/data/processed/carveout_disposal_tracking_2001_2016.json", encoding="utf-8"))}
    v4 = {r["rcept_no"]: r for r in json.load(open(f"{P}/data/processed/carveout_disposal_tracking_v4.json", encoding="utf-8"))}
    sc = {"claude": b16.scores(f"{P}/results/llm_judge_2001_2016/anthropic__identified*.jsonl"), "gpt": b16.scores(f"{P}/results/llm_judge_2001_2016/openai__identified*.jsonl")}
    co_old = md[(md.period == "2001-2016") & (md.type == "carve_out") & (md.status == "ok")].copy()
    co_old["p_llm"] = b16.two_model_score(sc["claude"], sc["gpt"], co_old.rcept_no)
    co_old["outcome"] = co_old.rcept_no.map(lambda k: old.get(k, {}).get("outcome"))
    co_old["disposed"] = co_old.outcome.map(lambda o: 1.0 if o in b16.DISPOSED else (0.0 if o == "retained_100" else np.nan))
    co_old["year"] = co_old.event_date.str[:4].astype(int)
    cs["limit"] = np.where(cs.date < pd.Timestamp("2015-06-15"), 0.16, 0.31)
    w = cs[(cs.tau >= -1) & (cs.tau <= 250)]
    bad = w[w.ret.abs() > w.limit].groupby("rcept_no").agg(n_beyond_limit=("ret", "size"), worst_abs_ret=("ret", lambda s: float(s.abs().max())))
    co_old = co_old.merge(bad, left_on="rcept_no", right_index=True, how="left")
    co_old["flag_glitch"] = co_old.n_beyond_limit.notna() & ~co_old.delisted_within_1y.astype(bool)
    pan_old = cs[cs.rcept_no.isin(co_old.rcept_no)][["rcept_no", "tau", "date", "ret", "mret", "ar_madj", "ar_mm"]]
    screen = {"carve_outs_2001_2016_ok": int(len(co_old)), "with_beyond_limit_day": int(co_old.n_beyond_limit.notna().sum()),
              "of_which_delisted_within_1y": int((co_old.n_beyond_limit.notna() & co_old.delisted_within_1y.astype(bool)).sum()),
              "flagged_as_suspected_adjustment_glitch": int(co_old.flag_glitch.sum()),
              "flagged_events": co_old[co_old.flag_glitch][["rcept_no", "corp_name", "event_date", "n_beyond_limit", "worst_abs_ret"]].to_dict(orient="records")}
    co_k, pan_k, unmapped = b16.load_krx_2017()
    co_k = co_k[KEEP].copy(); co_old_k = co_old[KEEP + ["flag_glitch", "gvkey", "iid"]].copy()
    pan_k = pan_k[["rcept_no", "tau", "date", "ret", "mret", "ar_madj", "ar_mm"]]
    cs_meta = md.set_index("rcept_no")[["gvkey", "iid"]]
    co_k = co_k.join(cs_meta, on="rcept_no")   # Compustat identifiers for the 2017+ events too (size / book equity controls)

    def timing(rn):
        r = old.get(rn) or v4.get(rn) or {}
        if r.get("outcome") == "retained_100": return "never"
        if r.get("outcome") not in b16.DISPOSED: return None
        try: lag = int(r["first_change_fy"]) - int(r["division_year"])
        except Exception: return "disposed_timing_unknown"
        return "early_le1y" if lag <= 1 else "late_ge2y"
    return {"co_old_k": co_old_k, "pan_old": pan_old, "co_k": co_k, "pan_k": pan_k, "screen": screen, "timing": timing, "unmapped": unmapped}


def run(co, pan, tag, note, B):
    res, co_out = b16.analyze(co.reset_index(drop=True), pan.reset_index(drop=True), tag, B["unmapped"], note)
    co_out["disposal_timing"] = co_out.rcept_no.map(B["timing"]); M = b16.MAIN
    tb = {g: b16.summ(d[M]) for g, d in co_out.dropna(subset=[M]).groupby("disposal_timing")}
    cmp = {f"{a}_vs_never": b16.diff_groups(co_out[co_out.disposal_timing == a][M], co_out[co_out.disposal_timing == "never"][M]) for a in ("early_le1y", "late_ge2y", "disposed_timing_unknown")}
    res["by_disposal_timing"] = {"definition": "early = first ownership change recorded in the division FY or the next (lag <= 1), late = lag >= 2, never = retained_100; timing unknown = disposed but no first_change_fy (v3-tracker labels)", "groups": tb, "comparisons": cmp}
    stamp = dt.date.today().strftime("%Y%m%d"); json.dump(res, open(f"{P}/results/bhar_predicted_disposal_{tag}_{stamp}.json", "w"), ensure_ascii=False, indent=1, default=float)
    q = res["by_score_quintile"]["q5_pooled"]["Q5_minus_Q1"][M]; qy = res["by_score_quintile"]["q5_within_year"]["Q5_minus_Q1"][M]; r = res["regressions"]; c = res["calendar_time_daily_madj"]; f = res["calendar_time_monthly_ff5"]; o = res["by_realized_outcome"][M]
    print(f"\n[{tag}] n score+1y {res['sample']['with_score_and_1y']} | label+1y {res['sample']['with_label_and_1y']} | by period {res['sample'].get('by_period_1y')}")
    print(f"  drift all: mean {res['all_carveouts_post_drift'][M]['mean']:+.3f} CI {res['all_carveouts_post_drift'][M]['mean_ci95_boot']} median {res['all_carveouts_post_drift'][M]['median']:+.3f} | CT all {c['all_carveouts'].get('annualized_x250')} t {c['all_carveouts'].get('t_newey_west_lag5')} | FF5 alpha {f['all_carveouts'].get('alpha_ff5_monthly')} t {f['all_carveouts'].get('alpha_ff5_t_nw3')}")
    print(f"  Q5-Q1 pooled {q['diff']:+.3f} CI {q['diff_ci95_boot']} p {q['welch_p']} | within-year {qy['diff']:+.3f} CI {qy['diff_ci95_boot']} p {qy['welch_p']} | Spearman {res['spearman_score_vs_return'][M]['rho']} p {res['spearman_score_vs_return'][M]['p']} (within-year {res['spearman_score_vs_return'][M]['rho_within_year_ranks']} p {res['spearman_score_vs_return'][M]['p_within_year_ranks']})")
    print(f"  BHAR1y on score yearFE {r['bhar_1y_on_score_yearFE']['p_llm']['coef']:+.3f} p {r['bhar_1y_on_score_yearFE']['p_llm']['p_hc1']} (cl {r['bhar_1y_on_score_yearFE']['p_llm']['p_cluster_year']}) | ann CAR on score {r['announcement_car_on_score_yearFE']['p_llm']['coef']:+.4f} se {r['announcement_car_on_score_yearFE']['p_llm']['se_hc1']} p {r['announcement_car_on_score_yearFE']['p_llm']['p_hc1']}")
    print(f"  CT hi-lo {c['high_minus_low'].get('annualized_x250')} t {c['high_minus_low'].get('t_newey_west_lag5')} | FF5 hi-lo {f['high_minus_low'].get('alpha_ff5_monthly')} t {f['high_minus_low'].get('alpha_ff5_t_nw3')}")
    print(f"  disposed vs retained: {o['mean_a']:+.3f} vs {o['mean_b']:+.3f} diff {o['diff']:+.3f} CI {o['diff_ci95_boot']} Welch p {o['welch_p']} MW p {o['mannwhitney_p']} | CT d-r {c['disposed_minus_retained'].get('annualized_x250')} t {c['disposed_minus_retained'].get('t_newey_west_lag5')} | FF5 d-r {f['disposed_minus_retained'].get('alpha_ff5_monthly')} t {f['disposed_minus_retained'].get('alpha_ff5_t_nw3')}")
    print("  timing groups: " + " | ".join(f"{g}: n {v['n']} mean {v.get('mean')} median {v.get('median')}" for g, v in tb.items()))
    for k, v in cmp.items(): print(f"    {k}: diff {v.get('diff')} CI {v.get('diff_ci95_boot')} Welch p {v.get('welch_p')} MW p {v.get('mannwhitney_p')}")
    if res.get("by_period"):
        for per, b in res["by_period"].items():
            qq = b.get("Q5_minus_Q1", {}); print(f"  period {per}: n {b['n_score_1y']} | Q5-Q1 {qq.get('diff')} CI {qq.get('diff_ci95_boot')} | Spearman {b.get('spearman')} | d-r {b['disposed_vs_retained'].get('diff')} p {b['disposed_vs_retained'].get('welch_p')} | annCAR on score {b.get('announcement_car_on_score', {}).get('p_llm')}")
    return res


if __name__ == "__main__":
    B = build_pooled(); co_old_k, pan_old, co_k, pan_k, screen = B["co_old_k"], B["pan_old"], B["co_k"], B["pan_k"], B["screen"]
    print("screen:", {k: v for k, v in screen.items() if k != "flagged_events"}, flush=True)
    main_old = co_old_k[~co_old_k.flag_glitch].drop(columns=["flag_glitch"])
    run(pd.concat([main_old, co_k]), pd.concat([pan_old[pan_old.rcept_no.isin(main_old.rcept_no)], pan_k]), "pooled",
        "Pooled 2001–2026: 2001–2016 carve-outs from Compustat Global daily (adjustment-glitch suspects excluded), 2017+ from the verified KRX panel.", B)
    run(main_old, pan_old[pan_old.rcept_no.isin(main_old.rcept_no)], "compustat2001_2016", "2001–2016 carve-outs alone, Compustat Global daily, glitch suspects excluded.", B)
    run(pd.concat([co_old_k.drop(columns=["flag_glitch"]), co_k]), pd.concat([pan_old, pan_k]), "pooled_incl_flagged", "Sensitivity: pooled including the flagged 2001–2016 events.", B)
    stamp = dt.date.today().strftime("%Y%m%d"); json.dump(screen, open(f"{P}/results/bhar_pooled_glitch_screen_{stamp}.json", "w"), ensure_ascii=False, indent=1, default=str)
    print("\nsaved screen ->", f"results/bhar_pooled_glitch_screen_{stamp}.json")
