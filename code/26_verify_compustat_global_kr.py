#!/usr/bin/env python3
"""26_verify_compustat_global_kr.py — interface verification of the Compustat Global Korean universe pulled by 25 (OFFLINE; no WRDS).

Every fact about the pulled tables that later scripts will rely on is established here by a probe against an independent
source already on disk, or read from the server's own column comments (dictionary_comp_global_daily.json), and written to
results/compustat_global_kr_verification_<date>.json and docs/INTERFACE_CARD_compustat_global_kr.md. Nothing is taken from
variable names or from memory of how Compustat North America works.

Pre-registered expectations (written 2026-11-10 before the first run; a result outside them is a bug until shown otherwise):
  P1 fiscal-year convention  : for fyr = 12, datadate.year == fyear for ~100% of rows; for fyr <= 5 the year differs by 1.
  P2 unit of g_funda amounts : DART thstrm_amount (won) / Compustat at should sit at ONE power of ten for nearly all matched
                               firm-years (10^6 if Compustat Global reports millions, 10^3 thousands, 10^0 won). Mixed powers = bug.
  P3 consolidation code      : DART CFS (연결) should agree with Compustat consol = 'C' and OFS (개별) with 'N' far better than crosswise.
  P4 shares outstanding unit : g_secd.cshoc at fiscal year-end / DART-implied common shares at ONE power of ten.
  P5 price identity          : the new g_secd rows equal the 2026-10-24 event-firm extract on the overlap (>= 99% exact).
  P6 exchange codes          : 248 <-> 유가(KOSPI), 298 <-> 코스닥 with ~0 crossings on currently listed firms; 353 tested against 코넥스.
  P7 coverage                : securities with a KRW daily price history per year 1,000–2,800 (KIND lists 2,753 listed firms today).
"""
import os, re, json, glob, datetime as dt, numpy as np, pandas as pd

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = f"{P}/data/raw/compustat_global_kr"; STAMP = dt.date.today().strftime("%Y%m%d")
OUT_JSON = f"{P}/results/compustat_global_kr_verification_{STAMP}.json"; OUT_MD = f"{P}/docs/INTERFACE_CARD_compustat_global_kr.md"
R = {"generated": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "probes": {}}

def j(x):
    if isinstance(x, dict): return {str(k): j(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [j(v) for v in x]
    if hasattr(x, "item"): return x.item()
    if isinstance(x, (pd.Timestamp, dt.date)): return str(x)
    return x

# ---------------- load
dic = json.load(open(f"{RAW}/dictionary_comp_global_daily.json")); comments = pd.DataFrame(dic["catalog_comments"])
def desc(table, col):
    s = comments[(comments.table_name == table) & (comments.column_name == col)].description
    return s.iloc[0] if len(s) else None
sec = pd.read_parquet(f"{RAW}/g_security_kr.parquet"); co = pd.read_parquet(f"{RAW}/g_company_kr.parquet"); fa = pd.read_parquet(f"{RAW}/g_funda_kr.parquet")
sm = pd.read_parquet(f"{RAW}/g_secm_kr.parquet") if os.path.exists(f"{RAW}/g_secm_kr.parquet") else None
sd_files = sorted(glob.glob(f"{RAW}/g_secd_kr_*.parquet")); years = [int(re.search(r"(\d{4})", os.path.basename(f)).group(1)) for f in sd_files]
R["inputs"] = {"g_security_rows": len(sec), "g_company_rows": len(co), "g_funda_rows": len(fa), "g_secm_rows": None if sm is None else len(sm), "g_secd_years": years}

# Korean ISIN -> 6-digit stock code (rule verified in 17_price_panel_compustat.py on 005930 -> KR7005930003, 004870 -> KR7004870002)
isin_s = sec["isin"].astype("string").fillna("")   # .isin is a DataFrame method name; use column access
sec["stock_code"] = np.where(isin_s.str.startswith("KR7"), isin_s.str[3:9], None)
link = sec.dropna(subset=["stock_code"])[["gvkey", "iid", "isin", "stock_code", "exchg", "tpci", "secstat", "dldtei"]].copy()
R["link"] = {"kr7_isin_securities": int(len(link)), "distinct_stock_codes": int(link.stock_code.nunique()),
             "stock_codes_with_several_gvkeys": int((link.groupby("stock_code").gvkey.nunique() > 1).sum()),
             "stock_codes_with_several_iids_same_gvkey": int((link.groupby(["stock_code", "gvkey"]).iid.nunique() > 1).sum())}

# ---------------- P1 fiscal-year convention (from the data itself)
fa["dd_year"] = fa.datadate.dt.year
p1 = fa.assign(diff=fa.dd_year - fa.fyear.astype("Int64")).groupby("fyr")["diff"].value_counts().unstack(fill_value=0)
R["probes"]["P1_fyear_convention"] = {"rows_by_fyr_and_(datadate_year - fyear)": j({int(k): v.to_dict() for k, v in p1.iterrows()}),
                                     "reading": "see table: for each fiscal-year-end month, how many rows have datadate.year - fyear = 0 / 1"}

# ---------------- DART event parents -> gvkey
base = json.load(open(f"{P}/data/processed/baseline_features.json")); dd = json.load(open(f"{P}/data/raw/dart_division_decisions_2017_2026.json"))
code_of = {r["corp_code"]: str(r.get("stock_code") or "") for r in dd}
ev = pd.DataFrame([{"rcept_no": r["rcept_no"], "corp_code": r["corp_code"], "corp_name": r["corp_name"], "stock_code": code_of.get(r["corp_code"], ""), "fy": r.get("parent_fy"), "fs_div": r.get("parent_fs_div"),
                    "dart_at": r.get("parent_total_assets"), "dart_lt": r.get("parent_total_debt"), "dart_eq": r.get("parent_equity"), "dart_sale": r.get("parent_sales"), "dart_ni": r.get("parent_net_income"), "dart_oi": r.get("parent_operating_income")}
                   for r in base if r.get("parent_total_assets") and r.get("parent_fy")])
ev = ev[ev.stock_code.str.fullmatch(r"\d{6}")]
ev = ev.merge(link[["stock_code", "gvkey"]].drop_duplicates(), on="stock_code", how="left")
R["dart_parents"] = {"with_dart_financials": int(len(ev)), "linked_to_gvkey": int(ev.gvkey.notna().sum()), "fs_div": ev.fs_div.value_counts(dropna=False).to_dict()}

# ---------------- P2/P3 unit and consolidation probes
fa_k = fa[(fa.curcd == "KRW") & (fa.indfmt == "INDL") & (fa.datafmt == "HIST_STD") & (fa.popsrc == "I")]
m = ev.dropna(subset=["gvkey"]).merge(fa_k[["gvkey", "fyear", "consol", "datadate", "at", "lt", "ceq", "seq", "teq", "sale", "revt", "nicon", "ib", "oiadp", "oibdp"]], left_on=["gvkey", "fy"], right_on=["gvkey", "fyear"], how="inner")
R["probes"]["P2_P3_matched_firm_years"] = int(len(m))
def power_table(num, den):
    r = (num / den).replace([np.inf, -np.inf], np.nan).dropna(); r = r[r > 0]
    lp = np.round(np.log10(r)).astype(int)
    return {"n": int(len(r)), "log10_ratio_rounded_counts": j(lp.value_counts().sort_index().to_dict()), "median_ratio": float(r.median()),
            "share_within_1pct_of_1e6": float(((r / 1e6 - 1).abs() <= 0.01).mean()), "share_within_1pct_of_1e3": float(((r / 1e3 - 1).abs() <= 0.01).mean()), "share_within_1pct_of_1": float(((r - 1).abs() <= 0.01).mean())}
p2 = {}
for cons in ["C", "N"]:
    g = m[m.consol == cons]
    p2[f"consol_{cons}"] = {"n_rows": int(len(g)), "by_dart_fs_div": g.fs_div.value_counts(dropna=False).to_dict(),
                            "at": power_table(g.dart_at, g["at"]), "lt": power_table(g.dart_lt, g["lt"]), "sale_vs_sale": power_table(g.dart_sale, g["sale"]), "sale_vs_revt": power_table(g.dart_sale, g["revt"]),
                            "ni_vs_nicon": power_table(g.dart_ni.where(g.dart_ni > 0), g.nicon.where(g.nicon > 0)), "ni_vs_ib": power_table(g.dart_ni.where(g.dart_ni > 0), g.ib.where(g.ib > 0)),
                            "eq_vs_seq": power_table(g.dart_eq, g.seq), "eq_vs_ceq": power_table(g.dart_eq, g.ceq), "eq_vs_teq": power_table(g.dart_eq, g.teq), "oi_vs_oiadp": power_table(g.dart_oi.where(g.dart_oi > 0), g.oiadp.where(g.oiadp > 0))}
# P3: which consol matches each DART statement type best (|log10 ratio - mode| small AND exact to 0.1% after the unit factor)
def agree(g, factor):
    r = g.dart_at / (g["at"] * factor); return float(((r - 1).abs() <= 0.001).mean()) if len(g) else None
# unit factor = the dominant power of ten over all matched rows
allr = (m.dart_at / m["at"]).replace([np.inf, -np.inf], np.nan).dropna(); allr = allr[allr > 0]
factor = float(10 ** int(np.round(np.log10(allr)).mode().iloc[0])) if len(allr) else None
p3 = {"unit_factor_used": factor}
for fsd in ["CFS", "OFS"]:
    for cons in ["C", "N"]:
        g = m[(m.fs_div == fsd) & (m.consol == cons)]
        p3[f"DART_{fsd}_vs_consol_{cons}"] = {"n": int(len(g)), "share_at_equal_to_0.1pct_after_unit": agree(g, factor) if factor else None}
for cons in ["C", "N"]:
    g = m[m.consol == cons]
    def within1(num, den): r = (num / (den * 1e6)).replace([np.inf, -np.inf], np.nan).dropna(); return {"n": int(len(r)), "share_within_1pct": float(((r - 1).abs() <= 0.01).mean()) if len(r) else None, "share_within_10pct": float(((r - 1).abs() <= 0.10).mean()) if len(r) else None}
    p2[f"consol_{cons}"]["definition_agreement_after_1e6"] = {"at": within1(g.dart_at, g["at"]), "lt": within1(g.dart_lt, g["lt"]), "sale~sale": within1(g.dart_sale, g.sale), "sale~revt": within1(g.dart_sale, g.revt),
        "oi~oiadp": within1(g.dart_oi, g.oiadp), "oi~oibdp": within1(g.dart_oi, g.oibdp), "eq~teq": within1(g.dart_eq, g.teq), "eq~seq": within1(g.dart_eq, g.seq), "eq~ceq": within1(g.dart_eq, g.ceq), "ni~nicon": within1(g.dart_ni, g.nicon), "ni~ib": within1(g.dart_ni, g.ib)}
R["probes"]["P2_units"] = p2; R["probes"]["P3_consolidation"] = p3

# ---------------- P4 shares outstanding (g_secd.cshoc at FY end vs DART largest-shareholder table implied total common shares)
p4 = {"n": 0}
if sd_files:
    hy = []
    for f in glob.glob(f"{P}/data/raw/dart_hyslr/*.json"):
        d = json.load(open(f)); rows = d.get("list") if isinstance(d, dict) else d
        if not rows: continue
        corp = os.path.basename(f).split("_")[0]
        for x in rows:
            if x.get("stock_knd") != "보통주": continue
            cnt = pd.to_numeric(str(x.get("trmend_posesn_stock_co", "")).replace(",", ""), errors="coerce"); pct = pd.to_numeric(x.get("trmend_posesn_stock_qota_rt"), errors="coerce")
            if pd.notna(cnt) and pd.notna(pct) and pct >= 5 and cnt > 0: hy.append({"corp_code": corp, "stlm_dt": x.get("stlm_dt"), "implied_total": cnt / pct * 100})
    hy = pd.DataFrame(hy)
    if len(hy):
        hy = hy.groupby(["corp_code", "stlm_dt"]).implied_total.median().reset_index(); hy["stock_code"] = hy.corp_code.map(code_of); hy["stlm_dt"] = pd.to_datetime(hy.stlm_dt, errors="coerce")
        hy = hy.dropna(subset=["stlm_dt"]).merge(link[["stock_code", "gvkey", "iid"]], on="stock_code", how="inner")
        yrs_needed = sorted(set(hy.stlm_dt.dt.year) & set(years)); parts = []
        for y in yrs_needed:
            s = pd.read_parquet(f"{RAW}/g_secd_kr_{y}.parquet", columns=["gvkey", "iid", "datadate", "cshoc", "prccd", "curcdd"]); parts.append(s[s.gvkey.isin(hy.gvkey)])
        sdd = pd.concat(parts) if parts else pd.DataFrame(columns=["gvkey", "iid", "datadate", "cshoc", "prccd", "curcdd"])
        rows = []
        for r in (hy.itertuples() if len(sdd) else []):
            g = sdd[(sdd.gvkey == r.gvkey) & (sdd.iid == r.iid) & (sdd.datadate <= r.stlm_dt) & (sdd.datadate >= r.stlm_dt - pd.Timedelta(days=10))].dropna(subset=["cshoc"])
            if len(g): rows.append({"gvkey": r.gvkey, "iid": r.iid, "stlm_dt": r.stlm_dt, "implied_total": r.implied_total, "cshoc": float(g.sort_values("datadate").cshoc.iloc[-1])})
        pp = pd.DataFrame(rows)
        if len(pp):
            p4 = {"n": int(len(pp)), **power_table(pp.cshoc, pp.implied_total), "note": "ratio = cshoc / DART-implied common shares (holder count / holder % from the largest-shareholder table, rows with >= 5%); 10^0 means cshoc is in shares"}
R["probes"]["P4_shares_outstanding_unit"] = p4

# ---------------- P5 identity with the 2026-10-24 event-firm extract (same vendor table, pulled 17 days earlier)
old = pd.read_parquet(f"{P}/data/raw/compustat_g_secd_events.parquet"); old["datadate"] = pd.to_datetime(old.datadate)
p5 = {"old_rows": int(len(old))}
if sd_files:
    yrs = sorted(set(old.datadate.dt.year) & set(years)); parts = []
    for y in yrs:
        s = pd.read_parquet(f"{RAW}/g_secd_kr_{y}.parquet", columns=["gvkey", "iid", "datadate", "prccd", "ajexdi", "trfd", "cshtrd"]); parts.append(s[s.gvkey.isin(old.gvkey.unique())])
    new = pd.concat(parts) if parts else pd.DataFrame(columns=["gvkey", "iid", "datadate", "prccd", "ajexdi", "trfd", "cshtrd"])
    jn = old[old.datadate.dt.year.isin(yrs)].merge(new, on=["gvkey", "iid", "datadate"], suffixes=("_old", "_new"), how="left")
    p5.update({"years_compared": yrs, "old_rows_in_years": int(len(jn)), "found_in_new": int(jn.prccd_new.notna().sum()),
               "prccd_exact_equal_share": float(np.isclose(jn.prccd_old, jn.prccd_new, rtol=1e-9, atol=1e-9, equal_nan=True).mean()),
               "ajexdi_exact_equal_share": float(np.isclose(jn.ajexdi_old, jn.ajexdi_new, rtol=1e-9, atol=1e-12, equal_nan=True).mean()),
               "trfd_exact_equal_share": float(np.isclose(jn.trfd_old.astype(float), jn.trfd_new.astype(float), rtol=1e-9, atol=1e-12, equal_nan=True).mean())})
R["probes"]["P5_identity_with_oct24_extract"] = p5

# ---------------- P6 exchange codes vs KIND market classification (currently listed firms)
kind = pd.read_csv(f"{P}/data/raw/kind_corplist_20261014.csv", dtype=str); kind["stock_code"] = kind["종목코드"].str.zfill(6)
act = link[link.secstat == "A"].merge(kind[["stock_code", "시장구분"]], on="stock_code", how="inner")
ct = pd.crosstab(act.exchg.astype("Int64"), act["시장구분"])
R["probes"]["P6_exchg_vs_KIND_market"] = {"crosstab_exchg_x_market": j({str(k): v.to_dict() for k, v in ct.iterrows()}), "n_active_matched": int(len(act)),
                                           "catalog_definition_exchg": desc("g_security", "exchg"), "note": "KIND 시장구분 values are the exchange's own labels (유가 = KOSPI main board, 코스닥, 코넥스)"}

# ---------------- P7 coverage by year
cov = {}
for f, y in zip(sd_files, years):
    s = pd.read_parquet(f, columns=["gvkey", "iid", "prccd", "curcdd", "cshtrd"]); s = s[(s.curcdd == "KRW") & (s.prccd > 0)]
    n = s.groupby(["gvkey", "iid"]).size(); cov[y] = {"securities_with_>=200_KRW_price_days": int((n >= 200).sum()), "securities_any": int(len(n)), "rows": int(len(s))}
fa_c = fa_k[fa_k.consol == "C"]; cov_f = fa_c.groupby("fyear").gvkey.nunique().to_dict()
R["probes"]["P7_coverage"] = {"daily_by_year": j(cov), "g_funda_KRW_INDL_C_gvkeys_by_fyear": j({int(k): int(v) for k, v in cov_f.items()}), "KIND_listed_today": int(len(kind)), "KIND_by_market": kind["시장구분"].value_counts().to_dict()}

# ---------------- code distributions (recorded, not interpreted)
R["code_values"] = {"g_funda": {c: j(fa[c].value_counts(dropna=False).head(12).to_dict()) for c in ["indfmt", "datafmt", "popsrc", "consol", "curcd", "fyr", "costat"] if c in fa},
                    "g_security": {c: j(sec[c].value_counts(dropna=False).head(12).to_dict()) for c in ["excntry", "exchg", "tpci", "secstat", "dlrsni", "epf"] if c in sec},
                    "g_company": {c: j(co[c].value_counts(dropna=False).head(12).to_dict()) for c in ["fic", "loc", "costat", "dlrsn"] if c in co}}
R["missing_wanted_columns"] = {"g_funda": ["ni", "csho", "cshpri", "ajex", "prcc_f", "mkvalt", "epspx"], "g_secm": ["trfm", "cshom"],
                               "substitutes_present_with_catalog_definition": {c: desc("g_funda", c) for c in ["nicon", "ib", "cshoi", "cshpria", "ajexi"]} | {"g_secd.cshoc": desc("g_secd", "cshoc"), "g_secd.prccd": desc("g_secd", "prccd"), "g_secm.prccm": desc("g_secm", "prccm")}}
json.dump(j(R), open(OUT_JSON, "w"), ensure_ascii=False, indent=1)

# ---------------- interface card (every row cites its source: catalog comment, probe key, or script)
def row(*cells): return "| " + " | ".join(str(c) for c in cells) + " |"
pr = R["probes"]; u = pr["P2_units"]
lines = [f"# INTERFACE_CARD — Compustat Global, Korean universe (WRDS `comp_global_daily`)", "",
         f"Generated {R['generated']} by `code/26_verify_compustat_global_kr.py` from the pull of `code/25_pull_compustat_global_universe.py` (2026-11-10). Results: `results/{os.path.basename(OUT_JSON)}`. "
         "Rule: an item without a source column entry is **[UNVERIFIED]** and must not feed a reported number.", "",
         "## Tables and rows", "", "| Table | Rows | Selection | Source |", "|---|---|---|---|",
         row("g_security", len(sec), "excntry = 'KOR' or ISIN starts 'KR' (both kept; neither assumed to define the universe)", "PULL_LOG.json step g_security"),
         row("g_company", len(co), "fic = 'KOR' or has a Korean security", "PULL_LOG.json step g_company"),
         row("g_funda", len(fa), f"gvkeys of the above, fyear 1999–2025, all indfmt/consol variants kept", "PULL_LOG.json step g_funda"),
         row("g_secm", R["inputs"]["g_secm_rows"], "all Korean securities 1999-12..2026-10 (file starts 2007-01 — probe)", "PULL_LOG.json step g_secm"),
         row("g_secd", f"{sum(v['rows'] for v in cov.values()):,} KRW rows", f"all Korean securities, calendar years {years[0] if years else '–'}–{years[-1] if years else '–'}", "PULL_LOG.json steps g_secd_<year>"), "",
         "## Column definitions used (server-side catalog comments, `pg_description`)", "", "| Column | Definition (verbatim) | Source |", "|---|---|---|"]
for t, c in [("g_funda", "at"), ("g_funda", "lt"), ("g_funda", "ceq"), ("g_funda", "seq"), ("g_funda", "sale"), ("g_funda", "revt"), ("g_funda", "nicon"), ("g_funda", "ib"), ("g_funda", "oiadp"), ("g_funda", "oancf"), ("g_funda", "capx"), ("g_funda", "che"), ("g_funda", "dltt"), ("g_funda", "dlc"), ("g_funda", "cshoi"), ("g_funda", "emp"), ("g_funda", "sich"), ("g_funda", "consol"), ("g_funda", "indfmt"), ("g_funda", "datafmt"), ("g_funda", "popsrc"), ("g_funda", "fyear"), ("g_funda", "fyr"), ("g_funda", "curcd"),
             ("g_secd", "prccd"), ("g_secd", "ajexdi"), ("g_secd", "trfd"), ("g_secd", "cshtrd"), ("g_secd", "cshoc"), ("g_secd", "curcdd"), ("g_secm", "prccm"), ("g_secm", "ajexm"), ("g_secm", "dvpsxm"), ("g_security", "excntry"), ("g_security", "exchg"), ("g_security", "tpci"), ("g_security", "secstat"), ("g_security", "dlrsni"), ("g_security", "dldtei"), ("g_company", "fic"), ("g_company", "loc"), ("g_company", "sic"), ("g_company", "gind"), ("g_company", "ipodate"), ("g_company", "dldte")]:
    lines.append(row(f"`{t}.{c}`", desc(t, c) or "**[no catalog comment]**", "dictionary_comp_global_daily.json / catalog_comments"))
lines += ["", "Columns wanted but absent from `g_funda` (not invented): " + ", ".join(R["missing_wanted_columns"]["g_funda"]) + "; from `g_secm`: " + ", ".join(R["missing_wanted_columns"]["g_secm"]) +
          ". Substitutes present: nicon (Net Income - Consolidated), ib, cshoi (Com Shares Outstanding - Issue), ajexi; prices and shares outstanding from g_secd (prccd, cshoc) / g_secm (prccm).", "",
          "## Probes (independent sources on disk)", "", "| # | Question | Result | Source |", "|---|---|---|---|",
          row("P1", "fiscal year vs datadate", f"rows by fyr × (datadate.year − fyear): {pr['P1_fyear_convention']['rows_by_fyr_and_(datadate_year - fyear)']}", "probe P1 (g_funda itself)"),
          row("P2", "unit of g_funda amounts (DART won / Compustat)", f"consol C, at: log10 counts {u['consol_C']['at']['log10_ratio_rounded_counts']}, median ratio {u['consol_C']['at']['median_ratio']:.6g}, within 1% of 1e6: {u['consol_C']['at']['share_within_1pct_of_1e6']:.3f}; sale vs sale {u['consol_C']['sale_vs_sale']['share_within_1pct_of_1e6']:.3f}, vs revt {u['consol_C']['sale_vs_revt']['share_within_1pct_of_1e6']:.3f}; ni vs nicon {u['consol_C']['ni_vs_nicon']['share_within_1pct_of_1e6']:.3f}, vs ib {u['consol_C']['ni_vs_ib']['share_within_1pct_of_1e6']:.3f}; eq vs seq {u['consol_C']['eq_vs_seq']['share_within_1pct_of_1e6']:.3f}, vs ceq {u['consol_C']['eq_vs_ceq']['share_within_1pct_of_1e6']:.3f} (n at = {u['consol_C']['at']['n']})", "probe P2: baseline_features.json (DART fnlttSinglAcnt, 05_collect_baseline_features.py lines 84–99) × g_funda"),
          row("P2b", "which Compustat line reproduces each DART account (within 1% after the 10^6 unit)", str(u["consol_C"]["definition_agreement_after_1e6"]) + " (consol C, DART 연결)", "probe P2 definition_agreement_after_1e6"),
          row("P3", "consol code vs DART CFS/OFS", str(pr["P3_consolidation"]), "probe P3"),
          row("P4", "unit of g_secd.cshoc", str({k: v for k, v in pr["P4_shares_outstanding_unit"].items() if k != "note"}) + " — " + pr["P4_shares_outstanding_unit"].get("note", ""), "probe P4: data/raw/dart_hyslr (hyslrSttus trmend_posesn_stock_co / _qota_rt) × g_secd"),
          row("P5", "identity with the 2026-10-24 extract", str(pr["P5_identity_with_oct24_extract"]), "probe P5: data/raw/compustat_g_secd_events.parquet"),
          row("P6", "exchange codes", str(pr["P6_exchg_vs_KIND_market"]["crosstab_exchg_x_market"]) + f" (n = {pr['P6_exchg_vs_KIND_market']['n_active_matched']} active securities matched to KIND by stock code)", "probe P6: data/raw/kind_corplist_20261014.csv 시장구분"),
          row("P7", "coverage by year", "see JSON P7_coverage (securities with ≥ 200 KRW price days per year; g_funda KRW/INDL/C gvkeys per fyear); KIND lists " + str(len(kind)) + " firms today", "probe P7"), "",
          "## Code values recorded (not interpreted beyond the probes above)", "", "```", json.dumps(j(R["code_values"]), ensure_ascii=False, indent=1), "```", "",
          "## Open items — [UNVERIFIED] until a source is added", "",
          "- `tpci` issue-type values ('0', '%', '1', '2', '7', 'F') and `dlrsni` inactivation codes: no value lookup in the catalog comments; do not interpret. Use the ISIN rule (KR7 + stock code) and secstat/dldtei for listing status.",
          "- `exchg` codes other than those cross-tabulated in P6 (e.g. 1, 115, 127, 157, 170, 194, 198, 251, 264): unknown venues; exclude from the Korean-market universe unless identified.",
          "- Compustat Global `fic`/`loc` give incorporation/headquarters country; the KOSPI/KOSDAQ listing universe is defined by `exchg` ∈ {248, 298} (P6) with a KRW price history, not by `fic`.",
          "- DART 자본총계 is reproduced by `teq` (Stockholders Equity - Total), not by `seq`/`ceq` (parent / common equity; they exclude non-controlling interests) — see P2b. Use `ceq` only where the construct is common shareholders' book equity, and say so.",
          "- DART 당기순이익(손실) is NOT reproduced by `nicon` or `ib` for most consolidated firm-years (P2b) although at, lt, sale, oiadp and teq are reproduced to 1%. Net-income-based Compustat variables are **[UNVERIFIED]** for Korea until a further probe pulls `mii`, `ibmii`, `ibki`, `nio`, `nit`, `ninc` and tests which combination equals the DART line (next WRDS session); until then profitability for the pre-2015 universe uses `oiadp`/`oibdp` over `at`, and net income comes from DART (FY2015+).",
          "- Historical listed-firm counts per year (for P7 against the exchange's own statistics): not on disk; KRX market statistics to be fetched before coverage is quoted in the paper."]
open(OUT_MD, "w").write("\n".join(lines) + "\n")
print(json.dumps(j({k: R[k] for k in ("inputs", "link", "dart_parents")}), ensure_ascii=False, indent=1))
print(json.dumps(j(pr), ensure_ascii=False, indent=1)[:6000]); print(f"\nwrote {OUT_JSON}\nwrote {OUT_MD}")
