#!/usr/bin/env python3
"""13_event_study_car.py — market reaction to 회사분할결정 filings, 2017-2026 (listed parents).

Data: parent daily adjusted close from KRX via pykrx 1.2.8 (stock.get_market_ohlcv_by_date(adjusted=True); columns
시가/고가/저가/종가/거래량/등락률, index = trading dates; checked 2026-10-18 on 현대퓨처넷 126560), market index from
stock.get_index_ohlcv_by_date — KOSPI "1001" for corp_cls Y, KOSDAQ "2001" for K. Credentials: api_keys.ini [krx].
Event day 0 = receipt date of the ORIGINAL 회사분할결정 filing (text_rcept_no from 03b when the collected rcept_no is a
correction, else the collected rcept_no; the 8-digit prefix of DART 접수번호 is the receipt date). Day indices count
trading days of the parent's own price series.
Abnormal returns: (i) market-adjusted r_i - r_m; (ii) market model with (alpha, beta) estimated on [-250, -31] (>= 120 obs).
Windows: [-1,+1], [0,+1], [-5,+5], [0,+20], [0,+60], [0,+120], [0,+250] (CAR = sum of daily ARs; BHAR for the long window).
Cross-section: mean, t (cross-sectional), median, N — by division type (carve_out 물적 vs spin_off 인적 vs mixed), and for
carve-outs by v4 outcome (disposed vs retained_100) and by LLM-predicted disposal probability tercile.
Outputs: data/processed/event_returns_daily.parquet (panel), results/event_study_car_<date>.json
"""
import os, re, json, glob, time, configparser, datetime as dt, numpy as np, pandas as pd

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cfg = configparser.ConfigParser(); cfg.read("/Users/jihwanw/PhD/code/api_info/api_keys.ini")
os.environ["KRX_ID"] = cfg["krx"]["krx_id"]; os.environ["KRX_PW"] = cfg["krx"]["krx_pw"]
from pykrx import stock  # noqa: E402

EVENTS = f"{P}/data/raw/dart_division_decisions_2017_2026.json"
INDEX = f"{P}/data/processed/disclosure_text_index.json"
V4 = f"{P}/data/processed/carveout_disposal_tracking_v4.json"
PXCACHE = f"{P}/data/raw/krx_prices"; os.makedirs(PXCACHE, exist_ok=True)
PANEL = f"{P}/data/processed/event_returns_daily.parquet"
WINDOWS = {"m1_p1": (-1, 1), "p0_p1": (0, 1), "m5_p5": (-5, 5), "p0_p20": (0, 20), "p0_p60": (0, 60), "p0_p120": (0, 120), "p0_p250": (0, 250)}
PRE, POST = 260, 260


def kdate(s):
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", s or "")
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


def get_px(ticker, start, end):
    f = f"{PXCACHE}/{ticker}_{start}_{end}.csv"
    if os.path.exists(f): return pd.read_csv(f, index_col=0, parse_dates=True)
    for a in range(3):
        try:
            px = stock.get_market_ohlcv_by_date(start, end, ticker, adjusted=True); time.sleep(0.35)
            px.to_csv(f); return px
        except Exception: time.sleep(2 + 3 * a)
    return None


def get_index(code, start, end):
    f = f"{PXCACHE}/index_{code}_{start}_{end}.csv"
    if os.path.exists(f): return pd.read_csv(f, index_col=0, parse_dates=True)
    ix = stock.get_index_ohlcv_by_date(start, end, code); time.sleep(0.35); ix.to_csv(f); return ix


ev = json.load(open(EVENTS, encoding="utf-8")); idx = json.load(open(INDEX, encoding="utf-8"))
v4 = {r["rcept_no"]: r for r in json.load(open(V4, encoding="utf-8"))}
llm = {}
for f in glob.glob(f"{P}/results/llm_judge/*__identified*.jsonl"):
    for l in open(f, encoding="utf-8"):
        r = json.loads(l); p = (r.get("parsed") or {}).get("p_disposal")
        if isinstance(p, (int, float)): llm.setdefault(r["rcept_no"], []).append(p / 100)
TODAY = dt.date.today().strftime("%Y%m%d")
mkt = {"Y": get_index("1001", "20151201", TODAY), "K": get_index("2001", "20151201", TODAY)}
mret = {k: v["종가"].pct_change() for k, v in mkt.items()}

rows, meta, t0 = [], [], time.time()
listed = [e for e in ev if e.get("corp_cls") in ("Y", "K") and re.fullmatch(r"\d{6}", str(e.get("stock_code") or ""))]
print(f"events: {len(ev)} | listed parents (Y/K with 6-digit code): {len(listed)}", flush=True)
for i, e in enumerate(listed, 1):
    rn = e["rcept_no"]; trn = idx.get(rn, {}).get("text_rcept_no") or rn
    d0 = dt.datetime.strptime(min(rn[:8], trn[:8]), "%Y%m%d").date()
    start = (d0 - dt.timedelta(days=int(PRE * 1.6))).strftime("%Y%m%d"); end = min(d0 + dt.timedelta(days=int(POST * 1.6)), dt.date.today()).strftime("%Y%m%d")
    px = get_px(e["stock_code"], start, end)
    m = {"rcept_no": rn, "corp_name": e["corp_name"], "corp_cls": e["corp_cls"], "stock_code": e["stock_code"], "type": e["type"], "event_date": d0.isoformat(),
         "v4_outcome": v4.get(rn, {}).get("outcome"), "p_llm": float(np.mean(llm[rn])) if rn in llm else None}
    if px is None or len(px) < 60 or (px["종가"] <= 0).all():
        m["status"] = "no_price_data"; meta.append(m); continue
    # Trading-halt days (spin-off 재상장 suspensions) appear as rows with 시가 0 / 거래량 0 and a stale close; drop them so that
    # tau counts actual trading days. Verified on BGF (halt 2017-10-30..12-07, relisted 12-08): the KRX adjusted close before the
    # halt already carries the 존속비율 adjustment (40,750 vs ~110,000 unadjusted) and equals the relisting reference price, so the
    # first post-relisting return (-29.9%) is a genuine market move, not a mechanical break; 등락률 agrees with close-to-close returns.
    px = px[(px["거래량"].notna()) & (px["거래량"] > 0) & (px["시가"] > 0)]; r = px["종가"].pct_change().rename("ret")
    td = r.index; pos = td.searchsorted(pd.Timestamp(d0))          # first trading day >= event date
    if pos >= len(td): m["status"] = "event_after_last_price"; meta.append(m); continue
    rm = mret[e["corp_cls"]].reindex(td)
    df = pd.DataFrame({"ret": r, "mret": rm}); df["tau"] = np.arange(len(df)) - pos
    est = df[(df.tau <= -31) & (df.tau >= -250)].dropna()
    if len(est) >= 120:
        beta, alpha = np.polyfit(est.mret, est.ret, 1); m["alpha"], m["beta"], m["est_n"] = float(alpha), float(beta), int(len(est))
    else:
        alpha, beta = 0.0, 1.0; m["alpha"], m["beta"], m["est_n"] = None, None, int(len(est))
    df["ar_madj"] = df.ret - df.mret; df["ar_mm"] = df.ret - (alpha + beta * df.mret)
    w = df[(df.tau >= -PRE) & (df.tau <= POST)].dropna(subset=["ret", "mret"]).copy(); w["rcept_no"] = rn
    rows.append(w[["rcept_no", "tau", "ret", "mret", "ar_madj", "ar_mm"]])
    for name, (a, b) in WINDOWS.items():
        s = w[(w.tau >= a) & (w.tau <= b)]
        if len(s) >= (b - a + 1) * 0.9:
            m[f"car_madj_{name}"] = float(s.ar_madj.sum()); m[f"car_mm_{name}"] = float(s.ar_mm.sum())
            m[f"bhar_madj_{name}"] = float((1 + s.ret).prod() - (1 + s.mret).prod())
    m["status"] = "ok"; m["n_post_days"] = int((w.tau > 0).sum()); meta.append(m)
    if i % 25 == 0: print(f"{i}/{len(listed)} ok={sum(1 for x in meta if x['status']=='ok')} [{time.time()-t0:.0f}s]", flush=True)
panel = pd.concat(rows, ignore_index=True); panel.to_parquet(PANEL, index=False)
md = pd.DataFrame(meta); md.to_csv(f"{P}/data/processed/event_study_meta.csv", index=False)
ok = md[md.status == "ok"].copy()


def summarize(d, cols):
    out = {}
    for c in cols:
        x = d[c].dropna()
        if len(x) >= 5:
            xw = x.clip(lower=x.quantile(0.02), upper=x.quantile(0.98))   # 2% winsorised mean for heavy tails in long windows
            out[c] = {"n": int(len(x)), "mean": round(float(x.mean()), 4), "mean_winsor2": round(float(xw.mean()), 4), "median": round(float(x.median()), 4),
                      "t": round(float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x)))), 2), "t_winsor2": round(float(xw.mean() / (xw.std(ddof=1) / np.sqrt(len(xw)))), 2), "share_negative": round(float((x < 0).mean()), 3)}
    return out


carcols = [c for c in ok.columns if c.startswith(("car_madj_", "car_mm_", "bhar_madj_"))]
res = {"n_events_listed": int(len(listed)), "n_ok": int(len(ok)), "status_counts": md.status.value_counts().to_dict(), "event_day_definition": "receipt date of the original 회사분할결정 filing",
       "by_type": {t: summarize(ok[ok.type == t], carcols) for t in ("carve_out", "spin_off", "mixed") if (ok.type == t).sum() >= 5}}
co = ok[ok.type == "carve_out"].copy(); co["disposed"] = co.v4_outcome.map({"ipo_listed": 1, "majority_disposed": 1, "partial_sale": 1, "retained_100": 0})
res["carveout_by_v4_outcome"] = {k: summarize(co[co.disposed == v], carcols) for k, v in (("disposed", 1), ("retained_100", 0))}
cl = co.dropna(subset=["p_llm"]).copy()
if len(cl) >= 30:
    cl["p_tercile"] = pd.qcut(cl.p_llm, 3, labels=["low", "mid", "high"])
    res["carveout_by_llm_tercile"] = {str(k): summarize(g, carcols) for k, g in cl.groupby("p_tercile", observed=True)}
    # does the announcement reaction differ by predicted disposal? OLS of CAR on p_llm (HC1), per window
    import statsmodels.api as sm
    res["car_on_p_llm"] = {}
    for c in [f"car_mm_{k}" for k in WINDOWS] + [f"bhar_madj_{k}" for k in ("p0_p120", "p0_p250")]:
        d = cl.dropna(subset=[c])
        if len(d) >= 30:
            mdl = sm.OLS(d[c], sm.add_constant(d.p_llm)).fit(cov_type="HC1")
            res["car_on_p_llm"][c] = {"n": int(len(d)), "coef_p_llm": round(float(mdl.params["p_llm"]), 4), "se": round(float(mdl.bse["p_llm"]), 4), "p": round(float(mdl.pvalues["p_llm"]), 3)}
    # realized outcome: long-run returns disposed vs retained (difference in means, Welch t)
    from scipy import stats
    res["longrun_disposed_vs_retained"] = {}
    for c in ("car_mm_p0_p250", "bhar_madj_p0_p250", "car_mm_p0_p120"):
        a, b = co[(co.disposed == 1)][c].dropna(), co[(co.disposed == 0)][c].dropna()
        if len(a) >= 10 and len(b) >= 10:
            t, p = stats.ttest_ind(a, b, equal_var=False); res["longrun_disposed_vs_retained"][c] = {"n_disposed": int(len(a)), "n_retained": int(len(b)), "mean_disposed": round(float(a.mean()), 4), "mean_retained": round(float(b.mean()), 4), "diff": round(float(a.mean() - b.mean()), 4), "welch_t": round(float(t), 2), "p": round(float(p), 3)}
stamp = dt.date.today().strftime("%Y%m%d"); json.dump(res, open(f"{P}/results/event_study_car_{stamp}.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({"n_ok": res["n_ok"], "status": res["status_counts"]}, ensure_ascii=False))
for t, d in res["by_type"].items(): print(t, {k: (v["n"], v["mean"], v["t"]) for k, v in d.items() if k.startswith("car_mm_")})
print("carve-out by outcome:", {k: {w: (v[w]["n"], v[w]["mean"], v[w]["t"]) for w in ("car_mm_m1_p1", "car_mm_p0_p250") if w in v} for k, v in res["carveout_by_v4_outcome"].items()})
print("CAR on p_llm:", res.get("car_on_p_llm")); print("long-run disposed vs retained:", res.get("longrun_disposed_vs_retained"))
print(f"saved results/event_study_car_{stamp}.json")
