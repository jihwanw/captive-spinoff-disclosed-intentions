#!/usr/bin/env python3
"""34_governance_controls_foreign_board.py — two Kang & Lee (2025b) controls not yet in the data: foreign ownership and board independence
(resubmission strategy §2 "omitted variables"), collected for every event with a disposal signal, with interface checks, then added to the
paper's spec-3 regressions.

Foreign ownership — KRX via pykrx 1.2.8 `get_exhaustion_rates_of_foreign_investment_by_ticker(date, market="ALL")` (one snapshot per
  trading day; needs the KRX login in api_keys.ini [krx], as 13_event_study_car.py). Columns returned (pykrx docstring, read 2026-11-10):
  상장주식수, 보유수량, 지분율, 한도수량, 한도소진률. We use 지분율 = foreign holdings / listed shares in percent, at the last trading day before
  the announcement (day -1 of 32's CAR file; the snapshot date is that day). Probe 2026-11-10: Samsung 005930 on 2002-01-15 returned
  지분율 60.0 (data reach back to 2002); values are quantised (e.g. 53.96875) — pykrx casts to a 16-bit float, so precision is ~0.03 pp.
  Interface check in this script: for 20 random events, the per-ticker range call (`get_exhaustion_rates_of_foreign_investment(d, d, ticker)`)
  must return the same 지분율 as the snapshot.
Board independence — DART `exctvSttus` (임원 현황 of the annual report, reprt_code 11011) for the fiscal year before the announcement year.
  Fields (response read 2026-11-10): nm, ofcps (직위), rgist_exctv_at ('등기임원'/'미등기임원'), fte_at ('상근'/'비상근'), chrg_job, ...
  outside_dir_ratio = #(rgist_exctv_at == '등기임원' and '사외이사' in ofcps) / #(rgist_exctv_at == '등기임원'). The API returned no data for
  FY2005 and data for FY2014+ in the probe (두산건설), so the control exists for announcements from 2015 onward; earlier events are missing
  (flag). Kang & Lee's "Board Independence" (mean 0.168, median 0) is defined differently (not stated in detail); we do not call ours theirs.
Re-estimation: 19's spec 3 (year FE, HC1 + firm cluster) with foreign ownership added (all events with the control) and with foreign ownership
  + outside director ratio (2015+ events); the block regressions of 21 likewise.
Pre-registered expectations (2026-11-10): foreign ownership coverage >= 90% of listed-parent events; probe agreement 20/20; median foreign
  share in [2%, 12%] (Kang & Lee: mean 7.8%, median 2.1%); outside-director ratio median in [0.2, 0.5] for listed parents; the coefficient on S
  in the rank regression stays in [-0.28, -0.10] with the controls; foreign ownership coefficient on the one-year rank: no prior.
Outputs: data/processed/event_governance_controls_<date>.csv, results/governance_controls_<date>.json, docs/GOVERNANCE_CONTROLS_NOTE_<date>.md
"""
import os, json, glob, time, signal, datetime as dt, configparser, urllib.request, urllib.parse, numpy as np, pandas as pd
import statsmodels.api as sm

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f"{P}/data/processed"; STAMP = dt.date.today().strftime("%Y%m%d")
CACHE_F = f"{P}/data/raw/krx_foreign"; CACHE_D = f"{P}/data/raw/dart_exctv"; os.makedirs(CACHE_F, exist_ok=True); os.makedirs(CACHE_D, exist_ok=True)
cfg = configparser.ConfigParser(); cfg.read("/Users/jihwanw/PhD/code/api_info/api_keys.ini"); os.environ["KRX_ID"] = cfg["krx"]["krx_id"]; os.environ["KRX_PW"] = cfg["krx"]["krx_pw"]; KEY = cfg["dart"]["api_key"]
from pykrx import stock
R = {"generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "expectations_preregistered": __doc__.split("Pre-registered expectations")[1].split("Outputs:")[0].strip()}

# ---------------- events: the return sample (CAR file of 32 has day0 for all division announcements) ∩ scored captive events
cars = pd.read_csv(sorted(glob.glob(f"{OUT}/division_announcement_cars_*.csv"))[-1], dtype={"rcept_no": str, "stock_code": str}, parse_dates=["event_date", "day0"])
ret = pd.read_csv(sorted(glob.glob(f"{OUT}/bhar_controls_events_*.csv"))[-1], dtype={"rcept_no": str, "stock_code": str})
ev = ret[["rcept_no", "corp_name", "stock_code", "event_date", "year", "period", "p_llm"]].merge(cars[["rcept_no", "day0", "gvkey", "iid"]], on="rcept_no", how="left")
ev["event_date"] = pd.to_datetime(ev.event_date); ev = ev.dropna(subset=["stock_code"]).copy()
# day -1 = last trading day before day0 from the universe calendar
cal = np.sort(pd.read_parquet(f"{OUT}/universe_ew_market_daily.parquet", columns=["datadate"]).datadate.unique())
def day_m1(d0):
    i = np.searchsorted(cal, np.datetime64(d0)); return pd.Timestamp(cal[i - 1]) if i > 0 else pd.NaT
ev["day_m1"] = [day_m1(d) if pd.notna(d) else pd.NaT for d in ev.day0.fillna(ev.event_date)]
R["events"] = {"n": int(len(ev)), "distinct_day_m1": int(ev.day_m1.nunique())}

# ---------------- foreign ownership snapshots (cached per date)
def alarm(s, f): raise TimeoutError()
signal.signal(signal.SIGALRM, alarm)
def snapshot(d):
    f = f"{CACHE_F}/{d:%Y%m%d}.parquet"
    if os.path.exists(f): return pd.read_parquet(f)
    signal.alarm(60)
    try:
        s = stock.get_exhaustion_rates_of_foreign_investment_by_ticker(f"{d:%Y%m%d}", market="ALL"); signal.alarm(0)
        s = s.reset_index().rename(columns={"티커": "ticker"}); s["ticker"] = s.ticker.astype(str).str.zfill(6)
        for c in ("상장주식수", "보유수량", "지분율", "한도수량", "한도소진률"):
            if c in s: s[c] = pd.to_numeric(s[c], errors="coerce").astype("float64")
        s.to_parquet(f, index=False); time.sleep(1.1); return s
    except Exception as e:
        signal.alarm(0); time.sleep(3); return None
t0 = time.time(); fo = {}; fails = []
for i, d in enumerate(sorted(ev.day_m1.dropna().unique())):
    s = snapshot(pd.Timestamp(d))
    if s is None: fails.append(str(pd.Timestamp(d).date())); continue
    fo[pd.Timestamp(d)] = s.set_index("ticker")
    if i % 50 == 0: print(f"  snapshots {i}/{ev.day_m1.nunique()} [{time.time()-t0:.0f}s] fails {len(fails)}", flush=True)
ev["foreign_pct"] = [float(fo[d].loc[c, "지분율"]) if (pd.notna(d) and d in fo and c in fo[d].index) else np.nan for d, c in zip(ev.day_m1, ev.stock_code)]
ev["foreign_limit_pct"] = [float(fo[d].loc[c, "한도소진률"]) if (pd.notna(d) and d in fo and c in fo[d].index) else np.nan for d, c in zip(ev.day_m1, ev.stock_code)]
R["foreign"] = {"snapshot_dates": len(fo), "failed_dates": fails[:20], "n_failed": len(fails), "coverage": int(ev.foreign_pct.notna().sum()), "coverage_share": round(float(ev.foreign_pct.notna().mean()), 3),
                "describe_pct": {k: round(float(v), 2) for k, v in ev.foreign_pct.describe().items()}, "by_period_median": {k: round(float(g.foreign_pct.median()), 2) for k, g in ev.groupby("period")}}
# interface check: per-ticker range call vs snapshot on 20 random events
rng = np.random.default_rng(0); chk = ev.dropna(subset=["foreign_pct"]).sample(20, random_state=0); agree = 0; checked = 0
for r in chk.itertuples():
    signal.alarm(60)
    try:
        x = stock.get_exhaustion_rates_of_foreign_investment(f"{r.day_m1:%Y%m%d}", f"{r.day_m1:%Y%m%d}", r.stock_code); signal.alarm(0); time.sleep(1.1)
        if len(x): checked += 1; agree += int(abs(float(x["지분율"].iloc[0]) - r.foreign_pct) < 0.05)
    except Exception: signal.alarm(0); time.sleep(3)
R["foreign"]["probe_range_call_vs_snapshot"] = {"checked": checked, "agree_within_0.05pp": agree}
print("foreign:", {k: R["foreign"][k] for k in ("coverage", "coverage_share", "n_failed", "probe_range_call_vs_snapshot")}, flush=True)

# ---------------- board independence (DART exctvSttus, FY before the announcement year)
dd = json.load(open(f"{P}/data/raw/dart_division_decisions_2017_2026.json", encoding="utf-8")); old = json.load(open(f"{OUT}/division_events_2001_2016.json", encoding="utf-8"))
corp_of = {r["rcept_no"]: r["corp_code"] for r in dd}
for r in old:
    for f in r.get("filings") or []: corp_of[f["rcept_no"]] = r["corp_code"]
    if r.get("text_rcept_no"): corp_of[r["text_rcept_no"]] = r["corp_code"]
ev["corp_code"] = ev.rcept_no.map(corp_of)
def api(ep, **kw):
    q = urllib.parse.urlencode(kw)
    with urllib.request.urlopen(f"https://opendart.fss.or.kr/api/{ep}.json?crtfc_key={KEY}&{q}", timeout=40) as r: return json.load(r)
def board(corp, fy):
    f = f"{CACHE_D}/{corp}_{fy}.json"
    if os.path.exists(f): d = json.load(open(f))
    else:
        try: d = api("exctvSttus", corp_code=corp, bsns_year=str(fy), reprt_code="11011"); json.dump(d, open(f, "w"), ensure_ascii=False); time.sleep(0.25)
        except Exception as e: return {"status": "error", "err": str(e)[:80]}
    rows = d.get("list") or []
    reg = [x for x in rows if (x.get("rgist_exctv_at") or "").replace(" ", "") == "등기임원"]
    outside = [x for x in reg if "사외이사" in (x.get("ofcps") or "")]
    return {"status": d.get("status"), "n_rows": len(rows), "n_registered": len(reg), "n_outside": len(outside), "ratio": (len(outside) / len(reg)) if reg else np.nan}
ev["fy_before"] = ev.event_date.dt.year - 1
res = []
for i, r in enumerate(ev.itertuples()):
    if pd.isna(r.corp_code) or r.fy_before < 2014: res.append({}); continue
    res.append(board(r.corp_code, int(r.fy_before)))
    if i % 100 == 0: print(f"  DART exctvSttus {i}/{len(ev)}", flush=True)
bd = pd.DataFrame(res); ev["outside_dir_ratio"] = bd.get("ratio"); ev["n_registered_exec"] = bd.get("n_registered"); ev["n_outside_dir"] = bd.get("n_outside"); ev["board_status"] = bd.get("status")
R["board"] = {"eligible_fy2014plus": int((ev.fy_before >= 2014).sum()), "api_ok": int((ev.board_status == "000").sum()), "with_ratio": int(ev.outside_dir_ratio.notna().sum()),
              "describe_ratio": {k: round(float(v), 3) for k, v in ev.outside_dir_ratio.describe().items()}, "n_registered_median": float(ev.n_registered_exec.median()) if ev.n_registered_exec.notna().any() else None,
              "status_counts": ev.board_status.value_counts(dropna=False).astype(str).to_dict()}
print("board:", {k: R["board"][k] for k in ("eligible_fy2014plus", "api_ok", "with_ratio", "describe_ratio")}, flush=True)
ev.to_csv(f"{OUT}/event_governance_controls_{STAMP}.csv", index=False)

# ---------------- re-estimation with the new controls
co = ret.merge(ev[["rcept_no", "foreign_pct", "outside_dir_ratio"]], on="rcept_no", how="left"); co["firm"] = co.stock_code.fillna(co.corp_name)
own = pd.DataFrame(json.load(open(f"{OUT}/ownership_pre_event_all.json", encoding="utf-8"))); own = own[~own.disagree.astype(bool)][["rcept_no", "block_pct"]]; co = co.merge(own, on="rcept_no", how="left"); co["block"] = co.block_pct / 100
M = "bhar_madj_p2_p250"; co["rank1y"] = co["bhar1y_rank_in_year"]; co["foreign"] = co.foreign_pct / 100   # the rank stored by 19 (computed over all 600 events), so the published row reproduces Table 6 exactly
BASE = ["log_me", "log_bm", "mom6", "kosdaq"]; FIL = ["rel_size", "surv_lev", "relisting"]; IMP = ["log_me", "log_bm", "mom6", "rel_size", "surv_lev"]
def reg(d, y, xs):
    d = d.dropna(subset=[y] + [x for x in xs if x not in IMP]).copy(); X = d[xs].astype(float).copy()
    for c in IMP:
        if c in X and X[c].isna().any(): X[c + "_miss"] = X[c].isna().astype(float); X[c] = X[c].fillna(X[c].median())
    for c in X.columns:
        if c not in ("kosdaq", "relisting") and not c.endswith("_miss"): X[c] = X[c].clip(X[c].quantile(0.01), X[c].quantile(0.99))
    X = pd.concat([X, pd.get_dummies(d.year, prefix="y", drop_first=True, dtype=float)], axis=1); X = sm.add_constant(X.loc[:, X.nunique() > 1])   # drop constant columns BEFORE adding the intercept (a post-add filter removed the intercept — bug found 2026-11-10)
    hc = sm.OLS(d[y].astype(float), X).fit(cov_type="HC1"); cf = sm.OLS(d[y].astype(float), X).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.firm)[0]})
    return {"n": int(len(d)), **{v: {"coef": round(float(hc.params[v]), 4), "se_hc1": round(float(hc.bse[v]), 4), "p_hc1": round(float(hc.pvalues[v]), 3), "p_firm": round(float(cf.pvalues[v]), 3)} for v in xs if v in X}}
d_all = co.dropna(subset=["p_llm"]); d_f = d_all.dropna(subset=["foreign"]); d_fb = d_f.dropna(subset=["outside_dir_ratio"])
R["regressions"] = {}
for y, lab in (("rank1y", "rank_1y"), (M, "bhar_1y"), ("car_mm_m1_p1", "ann_car")):
    R["regressions"][lab] = {"spec3_published_sample": reg(d_all, y, ["p_llm"] + BASE + FIL), "spec3_on_foreign_sample": reg(d_f, y, ["p_llm"] + BASE + FIL), "spec3_plus_foreign": reg(d_f, y, ["p_llm", "foreign"] + BASE + FIL),
                            "spec3_on_board_sample_2015plus": reg(d_fb, y, ["p_llm"] + BASE + FIL), "spec3_plus_foreign_board": reg(d_fb, y, ["p_llm", "foreign", "outside_dir_ratio"] + BASE + FIL),
                            "spec3_plus_foreign_board_block": reg(d_fb.dropna(subset=["block"]), y, ["p_llm", "foreign", "outside_dir_ratio", "block"] + BASE + FIL)}
    s = R["regressions"][lab]; print(f"[{lab}] S: published {s['spec3_published_sample']['p_llm']['coef']:+.4f} (n {s['spec3_published_sample']['n']}) | +foreign {s['spec3_plus_foreign']['p_llm']['coef']:+.4f} (p {s['spec3_plus_foreign']['p_llm']['p_firm']}, n {s['spec3_plus_foreign']['n']}; foreign {s['spec3_plus_foreign']['foreign']['coef']:+.4f} p {s['spec3_plus_foreign']['foreign']['p_firm']}) | +board {s['spec3_plus_foreign_board']['p_llm']['coef']:+.4f} (p {s['spec3_plus_foreign_board']['p_llm']['p_firm']}, n {s['spec3_plus_foreign_board']['n']}; board {s['spec3_plus_foreign_board']['outside_dir_ratio']['coef']:+.4f} p {s['spec3_plus_foreign_board']['outside_dir_ratio']['p_firm']})", flush=True)
# block regressions (21) with the new controls
db = d_f.dropna(subset=["block"]).copy()
R["block_regressions"] = {"score_on_block_plus_foreign": reg(db, "p_llm", ["block", "foreign"] + BASE + FIL), "rank_on_block_plus_foreign": reg(db, "rank1y", ["block", "foreign"] + BASE + FIL),
                          "score_on_block_plus_foreign_board": reg(db.dropna(subset=["outside_dir_ratio"]), "p_llm", ["block", "foreign", "outside_dir_ratio"] + BASE + FIL), "rank_on_block_plus_foreign_board": reg(db.dropna(subset=["outside_dir_ratio"]), "rank1y", ["block", "foreign", "outside_dir_ratio"] + BASE + FIL)}
rs = R["regressions"]["rank_1y"]
R["expectation_check"] = {"foreign_coverage_ge_0.9": bool(R["foreign"]["coverage_share"] >= 0.9), "probe_20_of_20": bool(R["foreign"]["probe_range_call_vs_snapshot"]["agree_within_0.05pp"] == R["foreign"]["probe_range_call_vs_snapshot"]["checked"] == 20),
                          "foreign_median_in_[2,12]": bool(2 <= R["foreign"]["describe_pct"].get("50%", -1) <= 12), "board_median_in_[0.2,0.5]": bool(0.2 <= R["board"]["describe_ratio"].get("50%", -1) <= 0.5),
                          "rank_S_with_controls_in_[-0.28,-0.10]": bool(-0.28 <= rs["spec3_plus_foreign_board"]["p_llm"]["coef"] <= -0.10)}
print("expectation check:", R["expectation_check"], flush=True)
json.dump(R, open(f"{P}/results/governance_controls_{STAMP}.json", "w"), ensure_ascii=False, indent=1, default=str)
md = [f"# Foreign ownership and board independence as controls ({STAMP})", "", f"Source `results/governance_controls_{STAMP}.json` (`code/34_governance_controls_foreign_board.py`); per-event file `data/processed/event_governance_controls_{STAMP}.csv`.", "",
      f"Foreign ownership (KRX 지분율 at day -1): {json.dumps({k: R['foreign'][k] for k in ('coverage', 'coverage_share', 'describe_pct', 'by_period_median', 'probe_range_call_vs_snapshot', 'n_failed')}, ensure_ascii=False)}", "",
      f"Board independence (DART exctvSttus, FY before the announcement, 2014+): {json.dumps({k: R['board'][k] for k in ('eligible_fy2014plus', 'api_ok', 'with_ratio', 'describe_ratio', 'n_registered_median')}, ensure_ascii=False)}", "",
      "## Spec-3 regressions with the new controls (year FE; HC1 / firm-cluster p)", "", "| Outcome | Spec | n | coef on S (firm p) | foreign (p) | outside-director ratio (p) | block (p) |", "|---|---|---|---|---|---|---|"] + \
     [f"| {lab} | {k} | {v['n']} | {v['p_llm']['coef']:+.4f} ({v['p_llm']['p_firm']}) | {v.get('foreign', {}).get('coef', '')} ({v.get('foreign', {}).get('p_firm', '')}) | {v.get('outside_dir_ratio', {}).get('coef', '')} ({v.get('outside_dir_ratio', {}).get('p_firm', '')}) | {v.get('block', {}).get('coef', '')} ({v.get('block', {}).get('p_firm', '')}) |" for lab, s in R["regressions"].items() for k, v in s.items()] + [
      "", "## Block regressions with the new controls", "", json.dumps(R["block_regressions"], ensure_ascii=False, indent=1), "", "## Expectation check", "", str(R["expectation_check"]), "",
      "## Caveats recorded", "", "- Foreign share is KRX's 지분율 (foreign holdings / listed shares) at the last trading day before the announcement; pykrx returns 16-bit-float values (precision ~0.03 pp).",
      "- Outside-director ratio = outside directors among registered executives in the DART 임원 현황 of the prior fiscal year; available for FY2014+ only, so the board-control regressions use the 2015+ announcements; Kang & Lee's board-independence definition is not reproduced.",
      "- Chaebol (대규모기업집단) affiliation is still missing: the KFTC portal lists are not reachable by the tools; the author downloads the designation lists (egroup.go.kr) or supplies a data.go.kr key."]
open(f"{P}/docs/GOVERNANCE_CONTROLS_NOTE_{STAMP}.md", "w").write("\n".join(md) + "\n"); print(f"saved results/governance_controls_{STAMP}.json, docs/GOVERNANCE_CONTROLS_NOTE_{STAMP}.md")
