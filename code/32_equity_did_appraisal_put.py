#!/usr/bin/env python3
"""32_equity_did_appraisal_put.py — (a) the 2022 reform with EQUITY spin-offs as the control group (difference-in-differences on the
announcement reaction) and (b) the appraisal right as a put option (announcement reaction vs the put's moneyness), plus the ex-post
payoff of exercising. Resubmission strategy §1-D (H-대조군 DiD, H-풋옵션) and §6 (보상 경로).

(a) The September–December 2022 package (revised disclosure form 2022-10-18, listing review 2022-09-28, appraisal right late December
    2022; FSC press releases cited in the manuscript) applied to captive spin-offs only. Equity spin-offs by listed parents are the
    untreated group. Announcement CAR[-1,+1] and CAR[0,+20] for EVERY division announcement by a listed parent, 2001–2026, from one
    source: the Compustat Global universe daily panel of 30 (adjprc returns) with the KOSPI/KOSDAQ index files of the project and the
    paper's market-model window [-250, -31] (>= 120 days) and day 0 = first trading day on or after the receipt date of the original
    filing (13's rule; 2017+: min(rcept_no, text_rcept_no) date). Event types: 2017+ from the structured record (carve_out/mixed = captive,
    spin_off = equity; 'other' dropped); 2001–2016 from the LLM-extracted division_type of 12b (물적분할/혼합 = captive, 인적분할 = equity;
    분할합병/unclear dropped). Identity control: the captive events' CARs must track the paper's (event_study_meta*.csv) with r >= 0.95.
    DiD: CAR = a + b1 Captive + b2 Captive x Post(>= 2022-10-01) + year FE + log ME (previous month-end) + KOSDAQ; HC1, firm- and
    year-clustered SE; samples 2017–2026 (structured era) and 2001–2026; event-time table of yearly mean CAR by type; placebo cutoff
    2019-10-01 inside the pre-period. Filing counts by type and half-year are reported descriptively (no denominator for a count DiD).
(b) The revised form has a block "10. 주식매수청구권에 관한 사항 … 매수예정가격 <KRW>" (seen in the raw texts 2026-11-10). The stated price is read
    by regex from the filing text (listed parents, post-reform captive spin-offs); moneyness m = P_app / close(day -1) - 1.
    The statutory formula (mean of the 2-month, 1-month and 1-week volume-weighted average prices before the board resolution; manuscript
    §2.1 fn.) is approximated with simple averages of closes over the same windows and VALIDATED against the stated prices (median |diff|);
    only if the proxy is close is it used for placebos (pre-reform captive filings; equity spin-offs, which carry no appraisal right).
    Tests: CAR[-1,+1] on m (post-reform captive); placebo slopes; ex-post payoff = (P_app/close(-1) - 1) - (one-year holding return).
Note on a misnamed field: dart_division_decisions_2017_2026.json 'appraisal_right' is DART's popt_ctr_atn = "풋옵션 등 계약 체결여부" (put-option
    CONTRACT flag; 9 '예'), not the shareholder appraisal right — it is not used here.
Pre-registered expectations (2026-11-10): identity r >= 0.95; equity-spin-off mean CAR 2017+ within ±3 pp of the paper's -3.0%;
    DiD Captive x Post in [+1, +9] pp (paper: captive +0.06% -> +5.29%); placebo DiD within ±2 pp of 0; proxy median |diff| < 3%;
    put slope > 0 for post-reform captive filings, placebo slopes within ±1 SE of 0; exercise payoff distribution: recorded, no prior.
Outputs: results/equity_did_appraisal_put_<date>.json, data/processed/division_announcement_cars_<date>.csv, docs/DID_PUT_NOTE_<date>.md
"""
import os, re, json, glob, datetime as dt, numpy as np, pandas as pd
import statsmodels.api as sm
from scipy import stats

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f"{P}/data/processed"; RAW = f"{P}/data/raw/compustat_global_kr"; STAMP = dt.date.today().strftime("%Y%m%d")
R = {"generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "expectations_preregistered": __doc__.split("Pre-registered expectations")[1].split("Outputs:")[0].strip()}
CUT = pd.Timestamp("2022-10-01"); PLACEBO_CUT = pd.Timestamp("2019-10-01")

# ---------------- events (all division announcements by listed parents)
uni = pd.read_parquet(f"{OUT}/universe_common_securities.parquet")[["gvkey", "iid", "stock_code"]]
idx_new = json.load(open(f"{OUT}/disclosure_text_index.json", encoding="utf-8"))
ev = []
for r in json.load(open(f"{P}/data/raw/dart_division_decisions_2017_2026.json", encoding="utf-8")):
    typ = {"carve_out": "captive", "mixed": "captive", "spin_off": "equity"}.get(r["type"])
    if not typ: continue
    rn = r["rcept_no"]; trn = (idx_new.get(rn) or {}).get("text_rcept_no") or rn
    ev.append({"rcept_no": rn, "corp_name": r["corp_name"], "corp_cls": r["corp_cls"], "stock_code": str(r.get("stock_code") or "").zfill(6), "type": typ, "src": "2017+", "event_date": pd.Timestamp(min(rn[:8], trn[:8])), "board_date": r.get("board_date")})
for r in json.load(open(f"{OUT}/division_events_2001_2016.json", encoding="utf-8")):
    dtp = ((r.get("llm") or {}).get("parsed") or {}).get("division_type"); typ = {"물적분할": "captive", "혼합(물적+인적)": "captive", "인적분할": "equity"}.get(dtp)
    if not typ or not str(r.get("stock_code") or "").isdigit(): continue
    rn = r["filings"][0]["rcept_no"] if r.get("filings") else r.get("text_rcept_no")
    ev.append({"rcept_no": rn, "corp_name": r["corp_name"], "corp_cls": r["corp_cls"], "stock_code": str(r["stock_code"]).zfill(6), "type": typ, "src": "2001-2016", "event_date": pd.Timestamp(str(r["first_filing_date"])), "board_date": ((r.get("llm") or {}).get("parsed") or {}).get("board_date")})
ev = pd.DataFrame(ev); ev = ev[ev.stock_code.str.fullmatch(r"\d{6}")].merge(uni, on="stock_code", how="inner")
# boundary duplicates across the two collections (same firm within 60 days): keep the 2017+ record (17's rule)
ev = ev.sort_values(["stock_code", "event_date"]); drop = []
for code, g in ev.groupby("stock_code"):
    a, b = g[g.src == "2001-2016"], g[g.src == "2017+"]
    for x in a.itertuples():
        if len(b) and (b.event_date - x.event_date).abs().min() <= pd.Timedelta(days=60): drop.append(x.rcept_no)
ev = ev[~ev.rcept_no.isin(drop)].drop_duplicates("rcept_no").reset_index(drop=True)
R["events"] = {"n": int(len(ev)), "by_type_src": ev.groupby(["src", "type"]).size().to_dict(), "boundary_dups_dropped": len(drop)}

# ---------------- CARs from the universe panel
ud = pd.read_parquet(f"{OUT}/universe_daily_returns.parquet", columns=["gvkey", "iid", "datadate", "ret", "me", "exchg"]); ud = ud[ud.gvkey.isin(ev.gvkey)]
idx = {248: pd.read_csv(f"{P}/data/raw/krx_prices/index_1001_20000101_20261024.csv", index_col=0, parse_dates=True)["종가"].pct_change(), 298: pd.read_csv(f"{P}/data/raw/krx_prices/index_2001_20000101_20261024.csv", index_col=0, parse_dates=True)["종가"].pct_change()}
bysec = {k: g.set_index("datadate").sort_index() for k, g in ud.groupby(["gvkey", "iid"])}
rows = []
for e in ev.itertuples():
    g = bysec.get((e.gvkey, e.iid))
    if g is None: rows.append({"rcept_no": e.rcept_no, "status": "no_prices"}); continue
    td = g.index; pos = td.searchsorted(e.event_date)
    if pos >= len(td) or pos < 60 or (td[pos] - e.event_date).days > 10: rows.append({"rcept_no": e.rcept_no, "status": "no_day0"}); continue
    ex = g.exchg.iloc[pos]; mk = idx.get(int(ex)) if pd.notna(ex) else None
    if mk is None: rows.append({"rcept_no": e.rcept_no, "status": "no_market"}); continue
    df = pd.DataFrame({"ret": g.ret, "mret": mk.reindex(td)}); df["tau"] = np.arange(len(df)) - pos
    est = df[(df.tau <= -31) & (df.tau >= -250)].dropna()
    if len(est) < 120: rows.append({"rcept_no": e.rcept_no, "status": "short_estimation"}); continue
    beta, alpha = np.polyfit(est.mret, est.ret, 1); df["ar_mm"] = df.ret - (alpha + beta * df.mret); df["ar_madj"] = df.ret - df.mret
    w3 = df[(df.tau >= -1) & (df.tau <= 1)].dropna(); w21 = df[(df.tau >= 0) & (df.tau <= 20)].dropna()
    me_prev = g[g.index < e.event_date - pd.Timedelta(days=20)].me.dropna()
    rows.append({"rcept_no": e.rcept_no, "status": "ok", "car_mm_m1_p1": float(w3.ar_mm.sum()) if len(w3) == 3 else np.nan, "car_madj_m1_p1": float(w3.ar_madj.sum()) if len(w3) == 3 else np.nan,
                 "car_mm_0_p20": float(w21.ar_mm.sum()) if len(w21) >= 19 else np.nan, "kosdaq": int(ex == 298), "log_me": float(np.log(me_prev.iloc[-1])) if len(me_prev) and me_prev.iloc[-1] > 0 else np.nan,
                 "close_m1": np.nan, "day0": td[pos]})
cars = ev.merge(pd.DataFrame(rows), on="rcept_no", how="left"); ok = cars[cars.status == "ok"].copy(); ok["year"] = ok.event_date.dt.year; ok["post"] = (ok.event_date >= CUT).astype(float); ok["captive"] = (ok.type == "captive").astype(float)
R["cars"] = {"status": cars.status.value_counts().to_dict(), "ok_by_type_src": ok.groupby(["src", "type"]).size().to_dict(),
             "mean_car_by_type": {t: {"n": int(len(g)), "mean_pct": round(float(g.car_mm_m1_p1.mean() * 100), 2), "median_pct": round(float(g.car_mm_m1_p1.median() * 100), 2), "t": round(float(stats.ttest_1samp(g.car_mm_m1_p1.dropna(), 0).statistic), 2)} for t, g in ok.groupby("type")},
             "mean_car_by_type_period": {f"{t}|{p}": {"n": int(len(g)), "mean_pct": round(float(g.car_mm_m1_p1.mean() * 100), 2), "median_pct": round(float(g.car_mm_m1_p1.median() * 100), 2)} for (t, p), g in ok[ok.src == "2017+"].groupby(["type", "post"])}}
# identity control vs the paper's CARs for captive events
pan_cs = pd.read_parquet(f"{OUT}/event_returns_daily_compustat.parquet", columns=["rcept_no", "tau", "ar_mm"])   # the paper's 2001–2016 panel (17): CAR[-1,+1] = sum of ar_mm over tau -1..1
cs3 = pan_cs[(pan_cs.tau >= -1) & (pan_cs.tau <= 1)].groupby("rcept_no").ar_mm.agg(["sum", "size"]); cs3 = cs3[cs3["size"] == 3]["sum"].rename("car_mm_m1_p1").reset_index()
pm = pd.concat([pd.read_csv(f"{OUT}/event_study_meta.csv", dtype={"rcept_no": str})[["rcept_no", "car_mm_m1_p1"]], cs3]).dropna().drop_duplicates("rcept_no").rename(columns={"car_mm_m1_p1": "car_paper"})
j = ok.merge(pm, on="rcept_no", how="inner")
R["identity_control"] = {"n_matched": int(len(j)), "corr": round(float(j.car_mm_m1_p1.corr(j.car_paper)), 4), "median_abs_diff_pp": round(float((j.car_mm_m1_p1 - j.car_paper).abs().median() * 100), 3), "pass": bool(j.car_mm_m1_p1.corr(j.car_paper) >= 0.95)}
print("identity:", R["identity_control"], "| cars by type:", R["cars"]["mean_car_by_type"], flush=True)

# ---------------- DiD
def did(d, y, post_col="post", extra=()):
    d = d.dropna(subset=[y]).copy(); d["cxp"] = d.captive * d[post_col]
    X = pd.concat([d[["captive", "cxp"] + list(extra)].astype(float), pd.get_dummies(d.year, prefix="y", drop_first=True, dtype=float)], axis=1)
    if d[post_col].nunique() > 1 and "y_" + str(int(d.year.max())) not in X: X[post_col] = d[post_col]
    X = sm.add_constant(X.loc[:, X.nunique() > 1]); X["log_me"] = d.log_me.fillna(d.log_me.median()) if "log_me" in extra else X.get("log_me", 0)
    if "log_me" not in extra and "log_me" in X: X = X.drop(columns="log_me")
    yv = d[y].astype(float)
    hc = sm.OLS(yv, X).fit(cov_type="HC1"); cf = sm.OLS(yv, X).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.stock_code)[0]}); cy = sm.OLS(yv, X).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.year)[0]})
    o = {"n": int(len(d)), "n_captive": int(d.captive.sum()), "n_equity": int((1 - d.captive).sum()), "n_post": int(d[post_col].sum())}
    for v in ("captive", "cxp"):
        o[v] = {"coef_pp": round(float(hc.params[v] * 100), 3), "se_hc1_pp": round(float(hc.bse[v] * 100), 3), "p_hc1": round(float(hc.pvalues[v]), 3), "p_firm": round(float(cf.pvalues[v]), 3), "p_year": round(float(cy.pvalues[v]), 3)}
    return o
d17 = ok[ok.src == "2017+"].copy(); dall = ok.copy()
R["did"] = {"2017_2026_car3_yearFE": did(d17, "car_mm_m1_p1"), "2017_2026_car3_yearFE_logme_kosdaq": did(d17, "car_mm_m1_p1", extra=("log_me", "kosdaq")), "2017_2026_car21_yearFE_logme_kosdaq": did(d17, "car_mm_0_p20", extra=("log_me", "kosdaq")),
            "2001_2026_car3_yearFE_logme_kosdaq": did(dall, "car_mm_m1_p1", extra=("log_me", "kosdaq")), "2001_2026_madj3_yearFE_logme_kosdaq": did(dall, "car_madj_m1_p1", extra=("log_me", "kosdaq"))}
pre = d17[d17.event_date < CUT].copy(); pre["post_fake"] = (pre.event_date >= PLACEBO_CUT).astype(float)
R["did"]["placebo_2017_2022sep_cut_2019_10"] = did(pre, "car_mm_m1_p1", post_col="post_fake", extra=("log_me", "kosdaq"))
R["event_time_mean_car_pct_by_type_year"] = {int(y): {t: {"n": int(len(g)), "mean": round(float(g.car_mm_m1_p1.mean() * 100), 2)} for t, g in gy.groupby("type")} for y, gy in ok[ok.year >= 2015].groupby("year")}
R["filings_by_halfyear_type"] = {f"{p}": c.to_dict() for p, c in ok.assign(h=ok.event_date.dt.year.astype(str) + "H" + ((ok.event_date.dt.month > 6) + 1).astype(str)).groupby("h").type.value_counts().unstack(fill_value=0).iterrows() if p >= "2017H1"}
for k, v in R["did"].items(): print(f"[DiD {k}] n {v['n']} (captive {v['n_captive']}, equity {v['n_equity']}, post {v['n_post']}) | captive {v['captive']['coef_pp']:+.2f} pp | captive×post {v['cxp']['coef_pp']:+.2f} pp (hc1 p {v['cxp']['p_hc1']}, firm p {v['cxp']['p_firm']}, year p {v['cxp']['p_year']})", flush=True)

# ---------------- appraisal put
pat = re.compile(r"매수\s*예정\s*가격\s*([\d,]{3,})")   # the price must be the next token; a "-" (not applicable) yields no price
def read_text(rn):
    e = idx_new.get(rn); p = e and e.get("path")
    return open(f"{P}/{p}", encoding="utf-8", errors="replace").read() if p and os.path.exists(f"{P}/{p}") else None
app = []
for e in ok[(ok.src == "2017+") & (ok.type == "captive")].itertuples():
    t = read_text(e.rcept_no)
    if not t: continue
    has = ("매수예정가격" in t) or ("매수 예정 가격" in t); m = pat.search(t) if has else None
    app.append({"rcept_no": e.rcept_no, "has_block": bool(has), "p_app": float(m.group(1).replace(",", "")) if m else np.nan})
app = pd.DataFrame(app); ok = ok.merge(app, on="rcept_no", how="left")
# closes (unadjusted) around the event and simple-average proxies of the statutory formula
need = ok[ok.p_app.notna() | ((ok.type == "captive") & (ok.src == "2017+")) | (ok.type == "equity")]
years = sorted(set(need.event_date.dt.year) | set(need.event_date.dt.year - 1))
px = pd.concat([pd.read_parquet(f"{RAW}/g_secd_kr_{y}.parquet", columns=["gvkey", "iid", "datadate", "prccd", "ajexdi", "trfd"]).query("gvkey in @need.gvkey") for y in years if os.path.exists(f"{RAW}/g_secd_kr_{y}.parquet")])
pxi = {k: g.set_index("datadate").sort_index() for k, g in px.groupby(["gvkey", "iid"])}
def board_ts(e):
    b = e.board_date
    if isinstance(b, str):
        m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", b)
        if m: return pd.Timestamp(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return e.event_date
vals = []
for e in ok.itertuples():
    g = pxi.get((e.gvkey, e.iid)); 
    if g is None: vals.append({"rcept_no": e.rcept_no}); continue
    bd = board_ts(e)
    if not (pd.Timedelta(days=0) <= (e.event_date - bd) <= pd.Timedelta(days=30)): bd = None   # proxy only when the board resolution is within 30 days before the filing
    if bd is not None:
        pre_px = g[(g.index < bd)].prccd
        w2 = pre_px[pre_px.index >= bd - pd.DateOffset(months=2)]; w1 = pre_px[pre_px.index >= bd - pd.DateOffset(months=1)]; w7 = pre_px[pre_px.index >= bd - pd.Timedelta(days=7)]
        proxy = float(np.mean([w2.mean(), w1.mean(), w7.mean()])) if len(w2) >= 20 and len(w7) >= 2 else np.nan
    else: proxy = np.nan
    c_m1 = g[g.index < e.day0].prccd; adj = (g.prccd / g.ajexdi * g.trfd.fillna(1.0))
    a_m1 = adj[adj.index < e.day0]; a_250 = adj[adj.index >= e.day0]
    hold = float(a_250.iloc[min(250, len(a_250) - 1)] / a_m1.iloc[-1] - 1) if len(a_m1) and len(a_250) >= 200 else np.nan
    vals.append({"rcept_no": e.rcept_no, "close_m1": float(c_m1.iloc[-1]) if len(c_m1) else np.nan, "p_formula_proxy": proxy, "hold_1y_from_m1": hold, "board_ts": bd})
ok = ok.drop(columns=["close_m1"]).merge(pd.DataFrame(vals), on="rcept_no", how="left")
ok["m_app"] = ok.p_app / ok.close_m1 - 1; ok["m_proxy"] = ok.p_formula_proxy / ok.close_m1 - 1
post_cap = ok[(ok.type == "captive") & (ok.post == 1) & ok.p_app.notna() & ok.close_m1.notna()].copy()
val = post_cap.dropna(subset=["p_formula_proxy"]); rel = (val.p_formula_proxy / val.p_app - 1)
R["appraisal"] = {"post_captive_2017plus_filings_with_text": int(ok[(ok.type == "captive") & (ok.post == 1)].has_block.notna().sum()), "with_block": int(ok[(ok.type == "captive") & (ok.post == 1)].has_block.sum()), "with_stated_price": int(post_cap.shape[0]),
                  "proxy_validation": {"n": int(len(val)), "median_abs_rel_diff_pct": round(float(rel.abs().median() * 100), 2), "share_within_3pct": round(float((rel.abs() <= 0.03).mean()), 3), "share_within_5pct": round(float((rel.abs() <= 0.05).mean()), 3), "pass_lt_3pct": bool(rel.abs().median() < 0.03)},
                  "moneyness_post_captive": {"n": int(post_cap.m_app.notna().sum()), "mean_pct": round(float(post_cap.m_app.mean() * 100), 2), "median_pct": round(float(post_cap.m_app.median() * 100), 2), "share_in_the_money": round(float((post_cap.m_app > 0).mean()), 3), "q25_q75_pct": [round(float(post_cap.m_app.quantile(.25) * 100), 2), round(float(post_cap.m_app.quantile(.75) * 100), 2)]}}
def slope(d, x, y="car_mm_m1_p1"):
    d = d.dropna(subset=[x, y]); d = d[d[x].abs() <= 0.5]      # |moneyness| > 50% can only be a misaligned window or a parse error
    if len(d) < 8: return {"n": int(len(d))}
    X = sm.add_constant(d[[x]].astype(float)); m = sm.OLS(d[y].astype(float), X).fit(cov_type="HC1")
    return {"n": int(len(d)), "slope": round(float(m.params[x]), 4), "se": round(float(m.bse[x]), 4), "p": round(float(m.pvalues[x]), 3), "spearman": round(float(stats.spearmanr(d[x], d[y]).statistic), 3), "spearman_p": round(float(stats.spearmanr(d[x], d[y]).pvalue), 3)}
R["appraisal"]["car3_on_moneyness_post_captive_stated"] = slope(post_cap, "m_app")
R["appraisal"]["car21_on_moneyness_post_captive_stated"] = slope(post_cap, "m_app", "car_mm_0_p20")
R["appraisal"]["placebo_car3_on_proxy_pre_captive_2017_2022"] = slope(ok[(ok.type == "captive") & (ok.post == 0) & (ok.src == "2017+")], "m_proxy")
R["appraisal"]["placebo_car3_on_proxy_equity_2017plus"] = slope(ok[(ok.type == "equity") & (ok.src == "2017+")], "m_proxy")
R["appraisal"]["placebo_car3_on_proxy_equity_post"] = slope(ok[(ok.type == "equity") & (ok.post == 1)], "m_proxy")
pay = post_cap.dropna(subset=["hold_1y_from_m1"]).copy(); pay["exercise_minus_hold_pp"] = (pay.m_app - pay.hold_1y_from_m1) * 100
R["appraisal"]["exercise_payoff"] = {"n_with_1y": int(len(pay)), "exercise_return_pct_median": round(float(pay.m_app.median() * 100), 2), "hold_1y_return_pct_median": round(float(pay.hold_1y_from_m1.median() * 100), 2),
                                     "exercise_minus_hold_pp_median": round(float(pay.exercise_minus_hold_pp.median()), 2), "share_exercise_beats_hold": round(float((pay.exercise_minus_hold_pp > 0).mean()), 3), "note": "exercise return = stated appraisal price / close on day -1 (cash received ~1-2 months later, not discounted); hold = adjusted price at +250 trading days / close -1"}
print("appraisal:", json.dumps({k: v for k, v in R["appraisal"].items() if k != "exercise_payoff"}, ensure_ascii=False)[:1500], flush=True); print("payoff:", R["appraisal"]["exercise_payoff"], flush=True)

# ---------------- checks and outputs
eq17 = ok[(ok.src == "2017+") & (ok.type == "equity")].car_mm_m1_p1
D = R["did"]["2017_2026_car3_yearFE_logme_kosdaq"]["cxp"]["coef_pp"]; PL = R["did"]["placebo_2017_2022sep_cut_2019_10"]["cxp"]["coef_pp"]; sl = R["appraisal"]["car3_on_moneyness_post_captive_stated"]
R["expectation_check"] = {"identity_pass": R["identity_control"]["pass"], "equity_2017plus_mean_within_3pp_of_-3.0": bool(abs(eq17.mean() * 100 + 3.0) <= 3.0), "equity_2017plus_mean_pct": round(float(eq17.mean() * 100), 2),
                          "did_in_[1,9]pp": bool(1 <= D <= 9), "placebo_within_2pp": bool(abs(PL) <= 2), "proxy_pass": R["appraisal"]["proxy_validation"]["pass_lt_3pct"], "put_slope_positive": bool(sl.get("slope", 0) > 0),
                          "placebo_slopes_within_2se": {k: (bool(abs(v["slope"]) <= 2 * v["se"]) if "slope" in v else None) for k, v in R["appraisal"].items() if k.startswith("placebo")}}
print("expectation check:", R["expectation_check"], flush=True)
def _clean(o):
    if isinstance(o, dict): return {(k.item() if hasattr(k, "item") else (str(k) if not isinstance(k, (str, int, float, bool)) and k is not None else k)): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [_clean(v) for v in o]
    if hasattr(o, "item"): return o.item()
    if isinstance(o, (pd.Timestamp, dt.date)): return str(o)
    return o
json.dump(_clean(R), open(f"{P}/results/equity_did_appraisal_put_{STAMP}.json", "w"), ensure_ascii=False, indent=1, default=str)
ok.drop(columns=[c for c in ("board_ts",) if c in ok]).to_csv(f"{OUT}/division_announcement_cars_{STAMP}.csv", index=False)
md = [f"# Equity spin-off control group DiD and the appraisal put ({STAMP})", "", f"Source `results/equity_did_appraisal_put_{STAMP}.json` (`code/32_equity_did_appraisal_put.py`); per-event file `data/processed/division_announcement_cars_{STAMP}.csv`.", "",
      f"Events with CARs: {R['cars']['ok_by_type_src']} (status {R['cars']['status']}). Identity control vs the paper's CARs: {R['identity_control']}.", "", f"Mean CAR[-1,+1] by type: {R['cars']['mean_car_by_type']}; 2017+ by type × post: {R['cars']['mean_car_by_type_period']}", "",
      "## Difference-in-differences (Captive × Post(2022-10-01), year FE)", "", "| Spec | n (captive/equity/post) | Captive (pp) | Captive×Post (pp) | p HC1 | p firm | p year |", "|---|---|---|---|---|---|---|"] + \
     [f"| {k} | {v['n']} ({v['n_captive']}/{v['n_equity']}/{v['n_post']}) | {v['captive']['coef_pp']:+.2f} | {v['cxp']['coef_pp']:+.2f} ± {v['cxp']['se_hc1_pp']:.2f} | {v['cxp']['p_hc1']} | {v['cxp']['p_firm']} | {v['cxp']['p_year']} |" for k, v in R["did"].items()] + [
      "", "Event time (mean CAR % by type and year, 2015+): " + json.dumps(R["event_time_mean_car_pct_by_type_year"], ensure_ascii=False), "", "Filings with CARs by half-year and type (2017+): " + json.dumps(R["filings_by_halfyear_type"], ensure_ascii=False), "",
      "## Appraisal right as a put", "", json.dumps(R["appraisal"], ensure_ascii=False, indent=1), "", "## Expectation check", "", str(R["expectation_check"]), "",
      "## Caveats recorded", "", "- Equity spin-off parents are the untreated group for the announcement reaction only; their later returns are not comparable (new-company shares).",
      "- The statutory price is a VWAP average; the proxy uses simple averages of closes — validated against the stated prices above and used only for placebos.",
      "- Exercise payoff ignores the 1–2 month delay in receiving the appraisal cash and any court revision of the price.",
      "- The 'appraisal_right' key in dart_division_decisions_2017_2026.json is DART's put-option-contract flag (popt_ctr_atn), not the appraisal right; it was not used."]
open(f"{P}/docs/DID_PUT_NOTE_{STAMP}.md", "w").write("\n".join(md) + "\n"); print(f"saved results/equity_did_appraisal_put_{STAMP}.json, docs/DID_PUT_NOTE_{STAMP}.md")
