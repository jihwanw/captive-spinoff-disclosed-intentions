#!/usr/bin/env python3
"""17_price_panel_compustat.py — daily return panel around 회사분할결정 filings, 2001–2026, from WRDS Compustat Global (g_secd).

Why a second price source: the KRX adjusted-price endpoint used by 13_event_study_car.py returns no rows before about 2015 for most
tickers (checked 2026-10-24: 005930 2002 adjusted -> 0 rows; 004870 2005/2010 adjusted -> 0 rows; unadjusted series do exist), so the
2001–2016 events cannot be priced from it. Compustat Global's daily security file carries Korean common shares back to the 1990s,
including delisted ones (g_security.dldtei / dlrsni), with the adjustment factor (ajexdi) and total-return factor (trfd) that the
Korea FF-factor pipeline already uses (korea-ff-factors/build_factors.py: adjprc = prccd / ajexdi * trfd).

Events: 2001–2016 carve-outs from data/processed/carveout_disposal_tracking_2001_2016.json (event day = receipt date of the earliest
filing in the cluster, rcept_no[:8]; 12b_prepare_events_2001_2016.py line 10) and all 2017–2026 events from
data/raw/dart_division_decisions_2017_2026.json (event day = min(rcept_no, text_rcept_no)[:8] as in 13). Parent identified by
ISIN: Korean ISINs are 'KR7' + 6-digit stock code + 3 characters (verified on 005930 -> KR7005930003, 004870 -> KR7004870002).
Market index: KOSPI (1001) when g_secd.exchg = 248 at the event date, KOSDAQ (2001) when 298 (the codes used by the factor pipeline);
if neither, the DART corp_cls (Y/K) is used and the source recorded; otherwise the event is kept with status no_market.
Index series: data/raw/krx_prices/index_{1001,2001}_20000101_20261024.csv (pykrx; |daily return| > 12% occurs only on 2001-09-12 and in 2026).
Returns: ret = adjprc_t / adjprc_{t-1} - 1 on the security's own trading days (rows with prccd <= 0 or zero traded volume dropped,
as 13 dropped halt days); tau counts those days from the event day 0 (first trading day >= event date). Delisting inside the window
is recorded (dldtei, last price date); windows are computed by 16/18 on the days that exist (>= 90% rule), so a parent delisted
early in the year drops out of the one-year window and is counted.
Outputs: data/processed/event_returns_daily_compustat.parquet (rcept_no, tau, date, ret, mret, ar_madj, ar_mm),
         data/processed/event_study_meta_compustat.csv, results/price_coverage_compustat_<date>.json (census + KRX cross-check).
"""
import os, re, json, time, datetime as dt, configparser, builtins, getpass, numpy as np, pandas as pd

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD = f"{P}/data/processed/carveout_disposal_tracking_2001_2016.json"; NEW = f"{P}/data/raw/dart_division_decisions_2017_2026.json"
TXTIDX = f"{P}/data/processed/disclosure_text_index.json"; KRXPANEL = f"{P}/data/processed/event_returns_daily.parquet"; KRXMETA = f"{P}/data/processed/event_study_meta.csv"
IDX = {"Y": f"{P}/data/raw/krx_prices/index_1001_20000101_20261024.csv", "K": f"{P}/data/raw/krx_prices/index_2001_20000101_20261024.csv"}
RAW = f"{P}/data/raw/compustat_g_secd_events.parquet"; SEC = f"{P}/data/raw/compustat_g_security_kr.parquet"
PRE, POST = 260, 260; EXCHG = {248: "Y", 298: "K"}

# ---------------- events
old = json.load(open(OLD, encoding="utf-8")); new = json.load(open(NEW, encoding="utf-8")); tidx = json.load(open(TXTIDX, encoding="utf-8"))
ev = []
for r in old:
    code = str(r.get("stock_code") or "")
    ev.append({"rcept_no": r["rcept_no"], "period": "2001-2016", "corp_name": r["corp_name"], "corp_cls": r.get("corp_cls"), "stock_code": code if re.fullmatch(r"\d{6}", code) else None,
               "type": r.get("type"), "event_date": dt.datetime.strptime(r["rcept_no"][:8], "%Y%m%d").date().isoformat(), "division_year": r.get("division_year")})
for r in new:
    code = str(r.get("stock_code") or ""); rn = r["rcept_no"]; trn = tidx.get(rn, {}).get("text_rcept_no") or rn
    ev.append({"rcept_no": rn, "period": "2017+", "corp_name": r["corp_name"], "corp_cls": r.get("corp_cls"), "stock_code": code if re.fullmatch(r"\d{6}", code) else None,
               "type": r.get("type"), "event_date": dt.datetime.strptime(min(rn[:8], trn[:8]), "%Y%m%d").date().isoformat(), "division_year": None})
ev = pd.DataFrame(ev); ev["event_date"] = pd.to_datetime(ev.event_date)
# boundary duplicates: same parent, filings within 60 days across the two collections -> keep the 2017+ record (it carries v4 labels/features)
dup = []
for code, g in ev[ev.stock_code.notna()].groupby("stock_code"):
    a, b = g[g.period == "2001-2016"], g[g.period == "2017+"]
    for x in a.itertuples():
        close = b[(b.event_date - x.event_date).abs() <= pd.Timedelta(days=60)]
        if len(close): dup.append(x.rcept_no)
ev = ev[~ev.rcept_no.isin(dup)].copy()
print(f"events: {len(ev)} ({(ev.period=='2001-2016').sum()} old, {(ev.period=='2017+').sum()} new; {len(dup)} boundary duplicates dropped); with stock code: {ev.stock_code.notna().sum()}", flush=True)

# ---------------- WRDS pull (cached)
def wrds_conn():
    import wrds
    cfg = configparser.ConfigParser(); cfg.read("/Users/jihwanw/PhD/code/api_info/api_keys.ini")
    u, pw = cfg["wrds"]["username"], cfg["wrds"]["password"]; os.environ["PGPASSWORD"] = pw
    builtins.input = lambda p="": u; getpass.getpass = lambda p="": pw
    return wrds.Connection(wrds_username=u)

codes = sorted(ev.stock_code.dropna().unique())
if os.path.exists(SEC) and os.path.exists(RAW):
    sec = pd.read_parquet(SEC); raw = pd.read_parquet(RAW); print("using cached WRDS extracts", flush=True)
else:
    db = wrds_conn(); t0 = time.time()
    codes_sql = ",".join(f"'{c}'" for c in codes)
    sec = db.raw_sql(f"""select gvkey, iid, isin, sedol, exchg, tpci, secstat, dlrsni, dldtei, dsci, excntry
                         from comp_global_daily.g_security where substr(isin,1,3) = 'KR7' and substr(isin,4,6) in ({codes_sql})""")
    sec["stock_code"] = sec["isin"].str[3:9]; sec.to_parquet(SEC)
    print(f"g_security: {len(sec)} rows for {sec.stock_code.nunique()} of {len(codes)} codes [{time.time()-t0:.0f}s]", flush=True)
    # per security, the union of event windows it must cover
    need = ev.dropna(subset=["stock_code"]).merge(sec[["gvkey", "iid", "stock_code"]], on="stock_code")
    rng = need.groupby(["gvkey", "iid"]).event_date.agg(["min", "max"]).reset_index()
    rng["s"] = (rng["min"] - pd.Timedelta(days=int(PRE * 1.6))).dt.strftime("%Y-%m-%d"); rng["e"] = (rng["max"] + pd.Timedelta(days=int(POST * 1.6))).dt.strftime("%Y-%m-%d")
    parts = []
    for i in range(0, len(rng), 40):
        chunk = rng.iloc[i:i+40]
        cond = " or ".join(f"(gvkey='{r.gvkey}' and iid='{r.iid}' and datadate between '{r.s}' and '{r.e}')" for r in chunk.itertuples())
        parts.append(db.raw_sql(f"select gvkey, iid, datadate, prccd, ajexdi, trfd, cshtrd, exchg, curcdd from comp_global_daily.g_secd where {cond}", date_cols=["datadate"]))
        print(f"  g_secd chunk {i//40+1}/{(len(rng)+39)//40}: {sum(len(p) for p in parts):,} rows [{time.time()-t0:.0f}s]", flush=True)
    raw = pd.concat(parts, ignore_index=True); raw.to_parquet(RAW); db.close()
sec["dldtei"] = pd.to_datetime(sec.dldtei)
print(f"g_secd rows: {len(raw):,} | securities: {raw.groupby(['gvkey','iid']).ngroups} | currencies: {raw.curcdd.value_counts().to_dict()}", flush=True)

# ---------------- indices
mkt = {k: pd.read_csv(f, index_col=0, parse_dates=True)["종가"].pct_change() for k, f in IDX.items()}

# ---------------- panel
raw = raw[(raw.prccd > 0) & (raw.ajexdi > 0) & (raw.curcdd == "KRW")].copy(); raw["trfd"] = raw.trfd.fillna(1.0)
raw = raw[~((raw.cshtrd.notna()) & (raw.cshtrd <= 0))]            # zero-volume (halt) days dropped, as in the KRX panel
raw["adjprc"] = raw.prccd / raw.ajexdi * raw.trfd
raw = raw.sort_values(["gvkey", "iid", "datadate"]).drop_duplicates(["gvkey", "iid", "datadate"])
bysec = {k: g.set_index("datadate") for k, g in raw.groupby(["gvkey", "iid"])}
sec_by_code = {c: g for c, g in sec.groupby("stock_code")}
rows, meta = [], []
for e in ev.itertuples():
    m = {"rcept_no": e.rcept_no, "period": e.period, "corp_name": e.corp_name, "corp_cls": e.corp_cls, "stock_code": e.stock_code, "type": e.type, "event_date": e.event_date.date().isoformat(), "division_year": e.division_year}
    if not e.stock_code: m["status"] = "no_stock_code"; meta.append(m); continue
    cands = sec_by_code.get(e.stock_code)
    if cands is None or len(cands) == 0: m["status"] = "no_compustat_security"; meta.append(m); continue
    chosen = None
    for s in cands.itertuples():
        g = bysec.get((s.gvkey, s.iid))
        if g is None or len(g) == 0: continue
        if g.index.min() <= e.event_date + pd.Timedelta(days=10) and g.index.max() >= e.event_date - pd.Timedelta(days=10): chosen = (s, g); break
    if chosen is None:
        m["status"] = "not_traded_at_event"; m["gvkey_iid"] = ";".join(f"{s.gvkey}-{s.iid}" for s in cands.itertuples()); meta.append(m); continue
    s, g = chosen; m.update({"gvkey": s.gvkey, "iid": s.iid, "isin": s.isin, "dlrsni": s.dlrsni, "dldtei": s.dldtei.date().isoformat() if pd.notna(s.dldtei) else None, "secstat": s.secstat})
    g = g[(g.index >= e.event_date - pd.Timedelta(days=int(PRE * 1.6))) & (g.index <= e.event_date + pd.Timedelta(days=int(POST * 1.6)))]
    r = g.adjprc.pct_change().rename("ret"); td = r.index; pos = td.searchsorted(e.event_date)
    if pos >= len(td): m["status"] = "event_after_last_price"; meta.append(m); continue
    ex = g.exchg.iloc[pos] if pos < len(g) else None; mk = EXCHG.get(int(ex)) if pd.notna(ex) else None; src = "exchg"
    if mk is None and e.corp_cls in ("Y", "K"): mk, src = e.corp_cls, "corp_cls_fallback"
    m["market"], m["market_source"], m["exchg_at_event"] = mk, src, (int(ex) if pd.notna(ex) else None)
    if mk is None: m["status"] = "no_market"; meta.append(m); continue
    df = pd.DataFrame({"ret": r, "mret": mkt[mk].reindex(td)}); df["tau"] = np.arange(len(df)) - pos
    est = df[(df.tau <= -31) & (df.tau >= -250)].dropna()
    if len(est) >= 120: beta, alpha = np.polyfit(est.mret, est.ret, 1); m["alpha"], m["beta"], m["est_n"] = float(alpha), float(beta), int(len(est))
    else: alpha, beta = 0.0, 1.0; m["alpha"], m["beta"], m["est_n"] = None, None, int(len(est))
    df["ar_madj"] = df.ret - df.mret; df["ar_mm"] = df.ret - (alpha + beta * df.mret)
    w = df[(df.tau >= -PRE) & (df.tau <= POST)].dropna(subset=["ret", "mret"]).copy(); w["rcept_no"] = e.rcept_no; w["date"] = w.index
    rows.append(w[["rcept_no", "tau", "date", "ret", "mret", "ar_madj", "ar_mm"]].reset_index(drop=True))
    m["status"] = "ok"; m["n_post_days"] = int((w.tau > 0).sum()); m["n_pre_days"] = int((w.tau < 0).sum()); m["first_price"] = td.min().date().isoformat(); m["last_price"] = td.max().date().isoformat()
    m["delisted_within_1y"] = bool(pd.notna(s.dldtei) and s.dldtei <= e.event_date + pd.Timedelta(days=380)) or (m["n_post_days"] < 226 and td.max() < pd.Timestamp("2025-10-01"))
    meta.append(m)
panel = pd.concat(rows, ignore_index=True); panel.to_parquet(f"{P}/data/processed/event_returns_daily_compustat.parquet", index=False)
md = pd.DataFrame(meta); md.to_csv(f"{P}/data/processed/event_study_meta_compustat.csv", index=False)

# ---------------- coverage census + KRX cross-check
ok = md[md.status == "ok"]
cens = {"events": int(len(md)), "status": md.status.value_counts().to_dict(), "by_period_status": {p: g.status.value_counts().to_dict() for p, g in md.groupby("period")},
        "carve_outs_ok_by_period": {p: int(((g.type == "carve_out") & (g.status == "ok")).sum()) for p, g in md.groupby("period")},
        "carve_outs_ok_full_1y_by_period": {p: int(((g.type == "carve_out") & (g.status == "ok") & (g.n_post_days >= 226)).sum()) for p, g in md.groupby("period")},
        "ok_by_year": {int(k): int(v) for k, v in ok.event_date.str[:4].astype(int).value_counts().sort_index().items()},
        "ok_by_corp_cls_now": ok.corp_cls.value_counts().to_dict(), "market_source": ok.market_source.value_counts().to_dict(),
        "delisted_within_1y": int(ok.delisted_within_1y.sum()), "market_model_estimable": int(ok.alpha.notna().sum())}
krx = pd.read_parquet(KRXPANEL); kmeta = pd.read_csv(KRXMETA, dtype={"rcept_no": str, "stock_code": str})
# dates for the KRX panel: reuse the verified mapping from 16
import importlib.util
spec = importlib.util.spec_from_file_location("b16", f"{P}/code/16_bhar_by_predicted_disposal.py"); b16 = importlib.util.module_from_spec(spec); spec.loader.exec_module(b16)
co_k, pan_k, unm = b16.load_krx_2017()
j = pan_k.merge(panel, on=["rcept_no", "date"], suffixes=("_krx", "_cs"))
per = j.groupby("rcept_no").apply(lambda g: pd.Series({"n": len(g), "corr": g.ret_krx.corr(g.ret_cs) if len(g) > 10 else np.nan, "mad": (g.ret_krx - g.ret_cs).abs().mean(), "share_gt1pct": ((g.ret_krx - g.ret_cs).abs() > 0.01).mean()}), include_groups=False)
cens["krx_vs_compustat_2017plus"] = {"events_compared": int(len(per)), "days_compared": int(len(j)), "median_corr": round(float(per["corr"].median()), 4), "share_events_corr_below_0_95": round(float((per["corr"] < 0.95).mean()), 3),
                                     "median_mean_abs_diff": round(float(per.mad.median()), 6), "share_days_abs_diff_gt_1pct": round(float(j.eval("abs(ret_krx - ret_cs) > 0.01").mean()), 4),
                                     "events_corr_below_0_95": per[per["corr"] < 0.95].round(3).reset_index().to_dict(orient="records")[:20],
                                     "note": "KRX adjusted close excludes cash dividends; Compustat trfd includes them, so small differences on ex-dividend days are expected"}
stamp = dt.date.today().strftime("%Y%m%d"); json.dump(cens, open(f"{P}/results/price_coverage_compustat_{stamp}.json", "w"), ensure_ascii=False, indent=1, default=str)
print(json.dumps(cens, ensure_ascii=False, indent=1, default=str)[:3000]); print(f"saved panel ({len(panel):,} rows), meta ({len(md)}), results/price_coverage_compustat_{stamp}.json")
