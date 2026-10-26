#!/usr/bin/env python3
"""16_bhar_by_predicted_disposal.py — did the market price the disposal signal that is readable in the 회사분할결정 filing?

Question (venue review 2026-10-24, experiment ①): if investors read the filing as the LLM does, parents whose filings signal a
likely disposal should react at announcement and show no further drift; if they do not, the drift after the announcement should
be more negative the higher the ex-ante signal. The realized-outcome sort (disposed vs retained) is the FRL 2025 comparison.

Module layout (2026-10-24 23:30): `load_krx_2017()` builds (co, pan_d) from the 13-script KRX panel; `analyze(co, pan_d, tag)` runs
every test and writes results/bhar_predicted_disposal_<tag>_<date>.json and docs/BHAR_NOTE_<tag>_<date>.md. 18_bhar_pooled.py
imports both and runs the same tests on the Compustat Global panel (2001–2026). Run as a script = the 2017+ KRX analysis.

Inputs for the 2017+ KRX run (all produced earlier; nothing is re-fetched):
  data/processed/event_returns_daily.parquet   daily panel from 13_event_study_car.py: rcept_no, tau (trading days from the event
                                               day 0 = first trading day >= receipt date of the ORIGINAL filing), ret (parent, KRX
                                               adjusted close, halt days removed), mret (KOSPI 1001 / KOSDAQ 2001 by corp_cls),
                                               ar_madj = ret - mret, ar_mm = market-model AR (alpha, beta on [-250,-31])
  data/processed/event_study_meta.csv          one row per listed-parent event: type, corp_cls, stock_code, event_date, v4_outcome, status
  data/raw/krx_prices/<ticker>_<start>_<end>.csv  cached price series, used only to map tau back to calendar dates (verified event by event)
  results/llm_judge/{anthropic,openai}__identified*.jsonl   LLM disposal probabilities; score = mean over identified runs per model,
                                               then the two-model average (the Gate-1 definition in 15_gate1_pooled.py)
  data/processed/carveout_disposal_tracking_v4.json   outcome labels; clean = disposed {ipo_listed, majority_disposed, partial_sale} vs retained_100
  /Users/jihwanw/PhD/Finance/0_pipeline/korea-ff-factors/factors_monthly_kr_ff5.csv   Korea FF5 monthly factors in percent
                                               (METHODOLOGY.md line 93: "% 단위"; RF = CD91 monthly), for the calendar-time alpha
Sample: carve-outs (물적분할) with status ok. Windows start at tau = +2 so the two-day announcement return is excluded:
  post windows [+2,+60], [+2,+126], [+2,+250] (trading days; a window is used only if >= 90% of its days exist), announcement [-1,+1].
"""
import os, re, json, glob, datetime as dt, numpy as np, pandas as pd
from scipy import stats
import statsmodels.api as sm

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PANEL = f"{P}/data/processed/event_returns_daily.parquet"; META = f"{P}/data/processed/event_study_meta.csv"
V4 = f"{P}/data/processed/carveout_disposal_tracking_v4.json"; PXCACHE = f"{P}/data/raw/krx_prices"
FF5 = "/Users/jihwanw/PhD/Finance/0_pipeline/korea-ff-factors/factors_monthly_kr_ff5.csv"
DISPOSED = {"ipo_listed", "majority_disposed", "partial_sale"}
POST = {"p2_p60": (2, 60), "p2_p126": (2, 126), "p2_p250": (2, 250)}; ANN = (-1, 1)
MAIN = "bhar_madj_p2_p250"
RNG = np.random.default_rng(20261024); NBOOT = 10000


def scores(pattern):
    d = {}
    for f in glob.glob(pattern):
        for l in open(f, encoding="utf-8"):
            r = json.loads(l); p = (r.get("parsed") or {}).get("p_disposal")
            if isinstance(p, (int, float)): d.setdefault(r["rcept_no"], []).append(float(p) / 100)
    return {k: float(np.mean(v)) for k, v in d.items()}


def two_model_score(claude, gpt, keys):
    return [np.mean([claude[k], gpt[k]]) if k in claude and k in gpt else np.nan for k in keys]


def boot_ci(x, stat=np.mean, n=NBOOT):
    x = np.asarray(x, float); idx = RNG.integers(0, len(x), (n, len(x))); b = stat(x[idx], axis=1)
    return [round(float(np.percentile(b, 2.5)), 4), round(float(np.percentile(b, 97.5)), 4)]


def summ(x):
    x = pd.Series(x).dropna()
    if len(x) < 5: return {"n": int(len(x))}
    xw = x.clip(lower=x.quantile(0.02), upper=x.quantile(0.98)); neg = int((x < 0).sum())
    return {"n": int(len(x)), "mean": round(float(x.mean()), 4), "mean_ci95_boot": boot_ci(x), "mean_winsor2": round(float(xw.mean()), 4),
            "median": round(float(x.median()), 4), "t": round(float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))), 2),
            "t_winsor2": round(float(xw.mean() / (xw.std(ddof=1) / np.sqrt(len(xw)))), 2),
            "share_negative": round(neg / len(x), 3), "sign_test_p": round(float(stats.binomtest(neg, len(x), 0.5).pvalue), 3)}


def diff_groups(a, b):
    a, b = pd.Series(a).dropna(), pd.Series(b).dropna()
    if len(a) < 5 or len(b) < 5: return {"n_a": int(len(a)), "n_b": int(len(b))}
    t, p = stats.ttest_ind(a, b, equal_var=False)
    ia = RNG.integers(0, len(a), (NBOOT, len(a))); ib = RNG.integers(0, len(b), (NBOOT, len(b))); d = a.values[ia].mean(1) - b.values[ib].mean(1)
    return {"n_a": int(len(a)), "n_b": int(len(b)), "mean_a": round(float(a.mean()), 4), "mean_b": round(float(b.mean()), 4), "diff": round(float(a.mean() - b.mean()), 4),
            "diff_ci95_boot": [round(float(np.percentile(d, 2.5)), 4), round(float(np.percentile(d, 97.5)), 4)], "welch_t": round(float(t), 2), "welch_p": round(float(p), 3),
            "median_a": round(float(a.median()), 4), "median_b": round(float(b.median()), 4), "mannwhitney_p": round(float(stats.mannwhitneyu(a, b, alternative="two-sided").pvalue), 3)}


def ols(df, y, xs, fe_year=True):
    d = df.dropna(subset=[y] + xs).copy(); X = d[xs].astype(float)
    if fe_year: X = pd.concat([X, pd.get_dummies(d.year, prefix="y", drop_first=True, dtype=float)], axis=1)
    X = sm.add_constant(X); out = {"n": int(len(d)), "year_fe": fe_year}
    hc = sm.OLS(d[y].astype(float), X).fit(cov_type="HC1")
    cl = sm.OLS(d[y].astype(float), X).fit(cov_type="cluster", cov_kwds={"groups": d.year.astype("category").cat.codes.values})
    for v in xs:
        out[v] = {"coef": round(float(hc.params[v]), 4), "se_hc1": round(float(hc.bse[v]), 4), "p_hc1": round(float(hc.pvalues[v]), 3),
                  "se_cluster_year": round(float(cl.bse[v]), 4), "p_cluster_year": round(float(cl.pvalues[v]), 3)}
    out["n_year_clusters"] = int(d.year.nunique()); out["r2"] = round(float(hc.rsquared), 3)
    return out


def window_stats(g, a, b):
    s = g[(g.tau >= a) & (g.tau <= b)]
    if len(s) < 0.9 * (b - a + 1): return (np.nan, np.nan, np.nan, int(len(s)))
    return (float((1 + s.ret).prod() - (1 + s.mret).prod()), float(s.ar_madj.sum()), float(s.ar_mm.sum()), int(len(s)))


def add_windows(co, pan):
    W = {}
    for k, g in pan.groupby("rcept_no"):
        row = {}
        for name, (a, b) in POST.items():
            bh, cm, cmm, n = window_stats(g, a, b); row[f"bhar_madj_{name}"] = bh; row[f"car_madj_{name}"] = cm; row[f"car_mm_{name}"] = cmm; row[f"ndays_{name}"] = n
        bh, cm, cmm, n = window_stats(g, *ANN); row["car_mm_m1_p1"] = cmm; row["car_madj_m1_p1"] = cm
        W[k] = row
    return co.join(pd.DataFrame.from_dict(W, orient="index"), on="rcept_no")


# ---------------- 2017+ KRX panel -> (co, pan_d)
def load_krx_2017():
    panel = pd.read_parquet(PANEL); meta = pd.read_csv(META, dtype={"stock_code": str, "rcept_no": str})
    v4 = {r["rcept_no"]: r for r in json.load(open(V4, encoding="utf-8"))}
    sc = {"claude": scores(f"{P}/results/llm_judge/anthropic__identified*.jsonl"), "gpt": scores(f"{P}/results/llm_judge/openai__identified*.jsonl")}
    co = meta[(meta.type == "carve_out") & (meta.status == "ok")]
    co = co[[c for c in co.columns if not c.startswith(("car_", "bhar_"))]].copy()   # the meta carries the 13-script windows (from tau 0); every window is recomputed from the panel
    co["p_llm"] = two_model_score(sc["claude"], sc["gpt"], co.rcept_no)
    co["outcome"] = co.rcept_no.map(lambda k: v4.get(k, {}).get("outcome"))
    co["disposed"] = co.outcome.map(lambda o: 1.0 if o in DISPOSED else (0.0 if o == "retained_100" else np.nan))
    co["year"] = co.event_date.str[:4].astype(int); co["period"] = "2017+"
    pan = panel[panel.rcept_no.isin(co.rcept_no)]

    def dates_for(e):   # calendar dates for each (event, tau) from the cached price files, verified against the panel's returns
        files = sorted(glob.glob(f"{PXCACHE}/{e.stock_code}_*.csv")); d0 = pd.Timestamp(e.event_date)
        for f in files:
            m = re.search(r"_(\d{8})_(\d{8})\.csv$", f); s_, t_ = pd.Timestamp(m.group(1)), pd.Timestamp(m.group(2))
            if not (s_ <= d0 <= t_): continue
            px = pd.read_csv(f, index_col=0, parse_dates=True); px = px[(px["거래량"].notna()) & (px["거래량"] > 0) & (px["시가"] > 0)]
            r = px["종가"].pct_change(); pos = r.index.searchsorted(d0)
            if pos >= len(r): continue
            m2 = pd.DataFrame({"tau": np.arange(len(r)) - pos, "ret_chk": r.values, "date": r.index})
            g = pan[pan.rcept_no == e.rcept_no].merge(m2, on="tau", how="left"); ok = g.dropna(subset=["ret_chk"])
            if len(ok) and np.nanmax(np.abs(ok.ret - ok.ret_chk)) < 1e-9: return g[["tau", "date"]]
        return None
    cal, unmapped = [], []
    for e in co.itertuples():
        d = dates_for(e)
        if d is None: unmapped.append(e.rcept_no); continue
        cal.append(d.assign(rcept_no=e.rcept_no))
    pan_d = pan.merge(pd.concat(cal, ignore_index=True), on=["rcept_no", "tau"], how="inner")
    return co, pan_d, unmapped


# ---------------- all tests on a (co, pan_d) pair
def analyze(co, pan_d, tag, unmapped=(), sample_note=""):
    co = add_windows(co.copy(), pan_d)
    res = {"run_at": dt.datetime.now().isoformat(timespec="seconds"), "tag": tag, "sample_note": sample_note, "definitions": {
        "event_day": "first trading day >= receipt date of the original 회사분할결정 filing",
        "score": "LLM p_disposal, identified condition, mean over runs per model, two-model average (Gate-1 definition)",
        "bhar_madj": "prod(1+ret) - prod(1+mret) over the window; mret = KOSPI or KOSDAQ index return by the parent's market",
        "car_mm": "sum of market-model abnormal returns (alpha, beta from [-250,-31])",
        "post_windows_start_at_tau_2": "the announcement days 0 and +1 are excluded from every post window",
        "clean_labels": "disposed = ipo_listed/majority_disposed/partial_sale; retained = retained_100; other outcomes excluded from realized-outcome tests",
        "winsor2": "means also reported after clipping at the 2nd/98th percentiles", "boot": f"{NBOOT} percentile-bootstrap resamples (seed 20261024)"}}
    res["sample"] = {"carve_outs_ok": int(len(co)), "with_score": int(co.p_llm.notna().sum()), "with_clean_label": int(co.disposed.notna().sum()),
                     "with_full_1y_window": int(co[MAIN].notna().sum()), "with_score_and_1y": int(co.dropna(subset=["p_llm", MAIN]).shape[0]),
                     "with_label_and_1y": int(co.dropna(subset=["disposed", MAIN]).shape[0]), "by_year_1y": {int(k): int(v) for k, v in co.dropna(subset=[MAIN]).year.value_counts().sort_index().items()},
                     "by_period_1y": {str(k): int(v) for k, v in co.dropna(subset=[MAIN]).period.value_counts().items()} if "period" in co else {}, "date_mapping_unverified_events": list(unmapped)}
    cols = [f"bhar_madj_{k}" for k in POST] + [f"car_madj_{k}" for k in POST] + [f"car_mm_{k}" for k in POST]
    res["all_carveouts_post_drift"] = {c: summ(co[c]) for c in cols}
    res["announcement_car_mm_m1_p1"] = summ(co.car_mm_m1_p1)

    S = co.dropna(subset=["p_llm", MAIN]).copy()
    S["q5_pooled"] = pd.qcut(S.p_llm, 5, labels=[1, 2, 3, 4, 5]).astype(int)
    S["pct_in_year"] = S.groupby("year").p_llm.rank(pct=True, method="average")
    S["q5_within_year"] = pd.qcut(S.pct_in_year, 5, labels=[1, 2, 3, 4, 5]).astype(int)
    S["t3_pooled"] = pd.qcut(S.p_llm, 3, labels=[1, 2, 3]).astype(int)
    res["score_describe"] = S.p_llm.describe().round(3).to_dict()
    res["by_score_quintile"] = {}
    for scheme in ("q5_pooled", "q5_within_year"):
        blk = {str(q): {c: summ(g[c]) for c in (MAIN, "bhar_madj_p2_p126", "car_mm_p2_p250", "car_mm_m1_p1")} for q, g in S.groupby(scheme)}
        blk["Q5_minus_Q1"] = {c: diff_groups(S[S[scheme] == 5][c], S[S[scheme] == 1][c]) for c in (MAIN, "bhar_madj_p2_p126", "car_mm_p2_p250", "car_mm_m1_p1")}
        res["by_score_quintile"][scheme] = blk
    res["spearman_score_vs_return"] = {}
    for c in (MAIN, "bhar_madj_p2_p126", "bhar_madj_p2_p60", "car_mm_p2_p250", "car_mm_m1_p1"):
        d = co.dropna(subset=["p_llm", c]); rho, p = stats.spearmanr(d.p_llm, d[c])
        dy = d.assign(rk=d.groupby("year").p_llm.rank(pct=True), ry=d.groupby("year")[c].rank(pct=True)); rho_y, p_y = stats.spearmanr(dy.rk, dy.ry)
        res["spearman_score_vs_return"][c] = {"n": int(len(d)), "rho": round(float(rho), 3), "p": round(float(p), 3), "rho_within_year_ranks": round(float(rho_y), 3), "p_within_year_ranks": round(float(p_y), 3)}
    res["regressions"] = {
        "bhar_1y_on_score": ols(co, MAIN, ["p_llm"], fe_year=False), "bhar_1y_on_score_yearFE": ols(co, MAIN, ["p_llm"]),
        "car_mm_1y_on_score_yearFE": ols(co, "car_mm_p2_p250", ["p_llm"]), "bhar_6m_on_score_yearFE": ols(co, "bhar_madj_p2_p126", ["p_llm"]),
        "announcement_car_on_score_yearFE": ols(co, "car_mm_m1_p1", ["p_llm"]),
        "bhar_1y_on_disposed_yearFE": ols(co, MAIN, ["disposed"]), "bhar_1y_on_score_and_disposed_yearFE": ols(co, MAIN, ["p_llm", "disposed"]),
        "car_mm_1y_on_disposed_yearFE": ols(co, "car_mm_p2_p250", ["disposed"])}
    L = co.dropna(subset=["disposed"])
    res["by_realized_outcome"] = {c: diff_groups(L[L.disposed == 1][c], L[L.disposed == 0][c]) for c in (MAIN, "bhar_madj_p2_p126", "car_mm_p2_p250", "car_mm_m1_p1")}
    res["by_realized_outcome"]["groups"] = {"disposed": {c: summ(L[L.disposed == 1][c]) for c in (MAIN, "car_mm_p2_p250")}, "retained_100": {c: summ(L[L.disposed == 0][c]) for c in (MAIN, "car_mm_p2_p250")}}
    res["score_within_realized"] = {}
    for g, name in ((1, "disposed"), (0, "retained_100")):
        d = L[L.disposed == g].dropna(subset=["p_llm", MAIN])
        if len(d) >= 20:
            hi, lo = d[d.p_llm >= d.p_llm.median()], d[d.p_llm < d.p_llm.median()]
            res["score_within_realized"][name] = {"n": int(len(d)), "above_median_score_vs_below": diff_groups(hi[MAIN], lo[MAIN]), "spearman": [round(float(x), 3) for x in stats.spearmanr(d.p_llm, d[MAIN])]}
    if "period" in co and co.period.nunique() > 1:   # pooled runs: the headline comparisons by period
        res["by_period"] = {}
        for per, g in co.groupby("period"):
            Sg = g.dropna(subset=["p_llm", MAIN]); Lg = g.dropna(subset=["disposed"])
            blk = {"n_score_1y": int(len(Sg)), "n_label_1y": int(Lg[MAIN].notna().sum()), "drift_all": summ(g[MAIN]), "disposed_vs_retained": diff_groups(Lg[Lg.disposed == 1][MAIN], Lg[Lg.disposed == 0][MAIN])}
            if len(Sg) >= 30:
                q = pd.qcut(Sg.p_llm, 5, labels=[1, 2, 3, 4, 5]).astype(int); blk["Q5_minus_Q1"] = diff_groups(Sg[q == 5][MAIN], Sg[q == 1][MAIN])
                rho, p = stats.spearmanr(Sg.p_llm, Sg[MAIN]); blk["spearman"] = {"rho": round(float(rho), 3), "p": round(float(p), 3)}
                blk["announcement_car_on_score"] = ols(g, "car_mm_m1_p1", ["p_llm"], fe_year=g.year.nunique() > 1)
            res["by_period"][str(per)] = blk

    # calendar-time portfolios (daily, market-adjusted): cross-correlation-robust inference
    pd_ = pan_d.merge(co[["rcept_no", "p_llm", "disposed", "year"]], on="rcept_no").merge(S[["rcept_no", "t3_pooled"]], on="rcept_no", how="left")
    win = pd_[(pd_.tau >= 2) & (pd_.tau <= 250)].copy()
    def ct_series(d, minn=5):
        g = d.groupby("date").ar_madj.agg(["mean", "size"]); g = g[g["size"] >= minn]; return g["mean"], g["size"]
    def ct_stats(s, label):
        if len(s) < 60: return {"label": label, "n_days": int(len(s))}
        f = sm.OLS(s.values, np.ones((len(s), 1))).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
        return {"label": label, "n_days": int(len(s)), "mean_daily_ar": round(float(s.mean()), 6), "annualized_x250": round(float(s.mean() * 250), 4),
                "t_newey_west_lag5": round(float(f.tvalues[0]), 2), "p": round(float(f.pvalues[0]), 3), "first_day": str(s.index.min().date()), "last_day": str(s.index.max().date())}
    ct = {}
    s_all, n_all = ct_series(win); ct["all_carveouts"] = dict(ct_stats(s_all, "all carve-outs, tau 2..250"), avg_portfolio_size=round(float(n_all.mean()), 1))
    s_hi, _ = ct_series(win[win.t3_pooled == 3]); s_lo, _ = ct_series(win[win.t3_pooled == 1])
    ct["high_score_tercile"] = ct_stats(s_hi, "top score tercile"); ct["low_score_tercile"] = ct_stats(s_lo, "bottom score tercile")
    both = pd.concat([s_hi.rename("hi"), s_lo.rename("lo")], axis=1).dropna(); ct["high_minus_low"] = ct_stats(both.hi - both.lo, "top minus bottom score tercile (days with both)")
    s_d, _ = ct_series(win[win.disposed == 1]); s_r, _ = ct_series(win[win.disposed == 0])
    ct["disposed"] = ct_stats(s_d, "realized disposed"); ct["retained_100"] = ct_stats(s_r, "realized retained_100")
    both2 = pd.concat([s_d.rename("d"), s_r.rename("r")], axis=1).dropna(); ct["disposed_minus_retained"] = ct_stats(both2.d - both2.r, "disposed minus retained (days with both)")
    res["calendar_time_daily_madj"] = ct

    # calendar-time monthly FF5 alpha (Korea factors, percent units -> decimals)
    ff = pd.read_csv(FF5); ff["month"] = pd.PeriodIndex(ff.month, freq="M"); ff = ff.set_index("month")
    for c in ("MKT_RF", "SMB", "HML", "RMW", "CMA", "RF"): ff[c] = pd.to_numeric(ff[c], errors="coerce") / 100
    win["month"] = win.date.dt.to_period("M")
    def monthly_port(d, minn=5):
        em = d.groupby(["rcept_no", "month"]).ret.apply(lambda r: float(np.prod(1 + r) - 1)).reset_index()
        g = em.groupby("month").ret.agg(["mean", "size"]); g = g[g["size"] >= minn]; return g["mean"], g["size"]
    def ff_alpha(rp, label, excess=True):
        d = pd.concat([rp.rename("rp"), ff[["MKT_RF", "SMB", "HML", "RMW", "CMA", "RF"]]], axis=1).dropna()
        if len(d) < 24: return {"label": label, "n_months": int(len(d))}
        y = d.rp - d.RF if excess else d.rp
        f = sm.OLS(y, sm.add_constant(d[["MKT_RF", "SMB", "HML", "RMW", "CMA"]])).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
        f3 = sm.OLS(y, sm.add_constant(d[["MKT_RF", "SMB", "HML"]])).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
        return {"label": label, "n_months": int(len(d)), "first_month": str(d.index.min()), "last_month": str(d.index.max()),
                "alpha_ff5_monthly": round(float(f.params["const"]), 4), "alpha_ff5_t_nw3": round(float(f.tvalues["const"]), 2), "alpha_ff5_p": round(float(f.pvalues["const"]), 3),
                "beta_mkt": round(float(f.params["MKT_RF"]), 3), "alpha_ff3_monthly": round(float(f3.params["const"]), 4), "alpha_ff3_t_nw3": round(float(f3.tvalues["const"]), 2),
                "mean_excess_monthly": round(float(y.mean()), 4)}
    mp = {}
    r_all, n_m = monthly_port(win); mp["all_carveouts"] = dict(ff_alpha(r_all, "all carve-outs, tau 2..250"), avg_events_per_month=round(float(n_m.mean()), 1))
    r_hi, _ = monthly_port(win[win.t3_pooled == 3]); r_lo, _ = monthly_port(win[win.t3_pooled == 1])
    mp["high_score_tercile"] = ff_alpha(r_hi, "top score tercile"); mp["low_score_tercile"] = ff_alpha(r_lo, "bottom score tercile")
    b = pd.concat([r_hi.rename("h"), r_lo.rename("l")], axis=1).dropna(); mp["high_minus_low"] = ff_alpha(b.h - b.l, "top minus bottom score tercile", excess=False)
    r_d, _ = monthly_port(win[win.disposed == 1]); r_r, _ = monthly_port(win[win.disposed == 0])
    mp["disposed"] = ff_alpha(r_d, "realized disposed"); mp["retained_100"] = ff_alpha(r_r, "realized retained_100")
    b2 = pd.concat([r_d.rename("d"), r_r.rename("r")], axis=1).dropna(); mp["disposed_minus_retained"] = ff_alpha(b2.d - b2.r, "disposed minus retained", excess=False)
    res["calendar_time_monthly_ff5"] = mp

    stamp = dt.date.today().strftime("%Y%m%d"); base = f"bhar_predicted_disposal_{tag}_{stamp}"
    json.dump(res, open(f"{P}/results/{base}.json", "w"), ensure_ascii=False, indent=1, default=float)
    co.to_csv(f"{P}/data/processed/{base}_events.csv", index=False)
    write_note(res, f"{P}/docs/BHAR_NOTE_{tag}_{stamp}.md", base)
    return res, co


def write_note(res, path, base):
    """Every number below is read from `res`."""
    def f4(x): return f"{x*100:+.1f}%" if isinstance(x, (int, float)) and not (isinstance(x, float) and np.isnan(x)) else "—"
    A = res["all_carveouts_post_drift"][MAIN]; Q = res["by_score_quintile"]; R = res["regressions"]; O = res["by_realized_outcome"]; C = res["calendar_time_daily_madj"]; M = res["calendar_time_monthly_ff5"]; SP = res["spearman_score_vs_return"][MAIN]
    smp = res["sample"]
    lines = [f"# BHAR after 물적분할 announcements by ex-ante disposal score — {res['tag']} — {res['run_at'][:10]}", "",
             f"Generated by `code/16_bhar_by_predicted_disposal.py` (`analyze`) from `results/{base}.json`. {res['sample_note']} Sample: {smp['carve_outs_ok']} carve-outs with prices; "
             f"{smp['with_score_and_1y']} with an LLM score and a full one-year post window (tau +2..+250); {smp['with_label_and_1y']} with a clean realized label and the window; by period {smp.get('by_period_1y')}.", "",
             "## 1. Drift after the announcement (all carve-outs)", "",
             f"Market-adjusted BHAR [+2,+250]: mean {f4(A['mean'])} (bootstrap 95% CI {f4(A['mean_ci95_boot'][0])} to {f4(A['mean_ci95_boot'][1])}), winsorised mean {f4(A['mean_winsor2'])}, median {f4(A['median'])}, "
             f"share negative {A['share_negative']:.0%} (sign test p {A['sign_test_p']}), n {A['n']}. Calendar-time daily portfolio: {f4(C['all_carveouts'].get('annualized_x250'))} per year, "
             f"Newey–West t {C['all_carveouts'].get('t_newey_west_lag5')} over {C['all_carveouts'].get('n_days')} days (avg {C['all_carveouts'].get('avg_portfolio_size')} firms). "
             f"FF5 monthly alpha {M['all_carveouts'].get('alpha_ff5_monthly', float('nan'))*100:+.2f}%/month (t {M['all_carveouts'].get('alpha_ff5_t_nw3')}, {M['all_carveouts'].get('n_months')} months).", "",
             "## 2. By ex-ante LLM disposal score", "", "| quintile (pooled) | n | mean BHAR 1y | median | mean CAR_mm 1y | announcement CAR[-1,+1] |", "|---|---|---|---|---|---|"]
    for q in ("1", "2", "3", "4", "5"):
        b = Q["q5_pooled"][q]; lines.append(f"| Q{q} | {b[MAIN]['n']} | {f4(b[MAIN]['mean'])} | {f4(b[MAIN]['median'])} | {f4(b['car_mm_p2_p250']['mean'])} | {f4(b['car_mm_m1_p1']['mean'])} |")
    d5 = Q["q5_pooled"]["Q5_minus_Q1"][MAIN]; d5y = Q["q5_within_year"]["Q5_minus_Q1"][MAIN]
    lines += ["", f"Q5 − Q1 (pooled): {f4(d5['diff'])} (bootstrap CI {f4(d5['diff_ci95_boot'][0])} to {f4(d5['diff_ci95_boot'][1])}, Welch t {d5['welch_t']}, Mann–Whitney p {d5['mannwhitney_p']}); within-year quintiles: {f4(d5y['diff'])} (Welch t {d5y['welch_t']}).",
              f"Spearman(score, BHAR 1y) = {SP['rho']} (p {SP['p']}); within-year ranks {SP['rho_within_year_ranks']} (p {SP['p_within_year_ranks']}).",
              f"OLS BHAR 1y on score with year FE: {R['bhar_1y_on_score_yearFE']['p_llm']['coef']:+.3f} per unit of probability (HC1 p {R['bhar_1y_on_score_yearFE']['p_llm']['p_hc1']}; year-cluster p {R['bhar_1y_on_score_yearFE']['p_llm']['p_cluster_year']}, {R['bhar_1y_on_score_yearFE']['n_year_clusters']} clusters). "
              f"Announcement CAR[-1,+1] on score (year FE): {R['announcement_car_on_score_yearFE']['p_llm']['coef']:+.4f} (HC1 p {R['announcement_car_on_score_yearFE']['p_llm']['p_hc1']}).",
              f"Calendar-time: top tercile {f4(C['high_score_tercile'].get('annualized_x250'))}/yr (t {C['high_score_tercile'].get('t_newey_west_lag5')}), bottom tercile {f4(C['low_score_tercile'].get('annualized_x250'))}/yr (t {C['low_score_tercile'].get('t_newey_west_lag5')}), "
              f"top − bottom {f4(C['high_minus_low'].get('annualized_x250'))}/yr (t {C['high_minus_low'].get('t_newey_west_lag5')}); FF5 alpha top − bottom {M['high_minus_low'].get('alpha_ff5_monthly', float('nan'))*100:+.2f}%/month (t {M['high_minus_low'].get('alpha_ff5_t_nw3')}).", "",
              "## 3. By realized outcome (FRL comparison)", "",
              f"Disposed (n {O[MAIN]['n_a']}) mean BHAR 1y {f4(O[MAIN]['mean_a'])}, median {f4(O[MAIN]['median_a'])}; retained (n {O[MAIN]['n_b']}) mean {f4(O[MAIN]['mean_b'])}, median {f4(O[MAIN]['median_b'])}; "
              f"difference {f4(O[MAIN]['diff'])} (bootstrap CI {f4(O[MAIN]['diff_ci95_boot'][0])} to {f4(O[MAIN]['diff_ci95_boot'][1])}, Welch t {O[MAIN]['welch_t']}, Mann–Whitney p {O[MAIN]['mannwhitney_p']}). "
              f"Year-FE regression on disposed: {R['bhar_1y_on_disposed_yearFE']['disposed']['coef']:+.3f} (HC1 p {R['bhar_1y_on_disposed_yearFE']['disposed']['p_hc1']}); with the score added: disposed {R['bhar_1y_on_score_and_disposed_yearFE']['disposed']['coef']:+.3f}, score {R['bhar_1y_on_score_and_disposed_yearFE']['p_llm']['coef']:+.3f}. "
              f"Calendar-time disposed − retained {f4(C['disposed_minus_retained'].get('annualized_x250'))}/yr (t {C['disposed_minus_retained'].get('t_newey_west_lag5')}); FF5 alpha {M['disposed_minus_retained'].get('alpha_ff5_monthly', float('nan'))*100:+.2f}%/month (t {M['disposed_minus_retained'].get('alpha_ff5_t_nw3')})."]
    if res.get("by_period"):
        lines += ["", "## 4. By period", "", "| period | n (score, 1y) | drift mean / median | Q5−Q1 (CI) | Spearman | disposed − retained (Welch p) | announcement CAR on score |", "|---|---|---|---|---|---|---|"]
        for per, b in res["by_period"].items():
            q = b.get("Q5_minus_Q1", {}); sp = b.get("spearman", {}); dr = b["disposed_vs_retained"]; ac = b.get("announcement_car_on_score", {}).get("p_llm", {})
            lines.append(f"| {per} | {b['n_score_1y']} | {f4(b['drift_all'].get('mean'))} / {f4(b['drift_all'].get('median'))} | {f4(q.get('diff'))} ({f4(q.get('diff_ci95_boot', [None, None])[0]) if q.get('diff_ci95_boot') else '—'} to {f4(q.get('diff_ci95_boot', [None, None])[1]) if q.get('diff_ci95_boot') else '—'}) | {sp.get('rho', '—')} (p {sp.get('p', '—')}) | {f4(dr.get('diff'))} (p {dr.get('welch_p', '—')}) | {ac.get('coef', '—')} (p {ac.get('p_hc1', '—')}) |")
    lines += ["", "## Reading", "", "The numbers answer whether the post-announcement drift is more negative where the filing signals a disposal; the verdict is written in the memo by the author after reading them. "
              "Limits: one-year horizon; market-adjusted benchmark (no size/B-M matching); events cluster in time, hence the year fixed effects and the calendar-time tests."]
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")


if __name__ == "__main__":
    co, pan_d, unmapped = load_krx_2017()
    res, _ = analyze(co, pan_d, "krx2017", unmapped, "2017–2026 listed parents, KRX adjusted prices (13-script panel).")
    M_ = MAIN; A = res["all_carveouts_post_drift"][M_]
    print(json.dumps({"sample": res["sample"], "all_1y": A, "Q5-Q1": res["by_score_quintile"]["q5_pooled"]["Q5_minus_Q1"][M_], "spearman": res["spearman_score_vs_return"][M_],
                      "reg_score_yearFE": res["regressions"]["bhar_1y_on_score_yearFE"]["p_llm"], "ann_car_on_score": res["regressions"]["announcement_car_on_score_yearFE"]["p_llm"],
                      "disposed_vs_retained": res["by_realized_outcome"][M_], "ct_hi_lo": res["calendar_time_daily_madj"]["high_minus_low"], "ct_d_r": res["calendar_time_daily_madj"]["disposed_minus_retained"],
                      "ff5_d_r": res["calendar_time_monthly_ff5"]["disposed_minus_retained"]}, ensure_ascii=False, indent=1, default=str))
