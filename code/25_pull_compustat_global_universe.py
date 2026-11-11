#!/usr/bin/env python3
"""25_pull_compustat_global_universe.py — one-session WRDS pull of the Compustat Global KOREAN UNIVERSE
(company header, security master, annual fundamentals, monthly and daily security files) for the matching /
selection-model / matched-benchmark designs of RESUBMISSION_STRATEGY_20261110.md §2 (step 1 of §8).

Duo policy (steering wrds_access.md, binding): the connection is opened ONCE through wrds_connect_once.connect().
No retry, no reconnect, no second attempt of any kind. Every step is checkpointed to disk; if a query fails the
script stops where it is, writes the log and exits non-zero. A later run skips steps whose checkpoint exists and
therefore needs no WRDS connection once everything is on disk.

No-assumption policy (no_guessing_in_data_analysis.md, no_assumptions_in_experiment_code.md): library and table
names are taken from the server's own catalog (list_tables / information_schema), column lists are read from the
server (describe_table) and the WANTED lists below are INTERSECTED with them — a wanted column that does not exist is
recorded as missing, never invented. Codes (indfmt, datafmt, popsrc, consol, curcd, exchg, fic, excntry) are not
filtered on the server; their distinct values are recorded and the filtering is done, with reasons, in later steps.
Units (millions of KRW?) are NOT assumed: 26_verify_compustat_global_kr.py cross-checks `at`, `sale`, `ni` against the
DART financial statements already collected for the event parents (baseline_features.json) and writes the interface
card. Expected ranges written before the run (treat anything outside as a bug first):
  companies with a Korean flag 2,000–4,000; securities 2,500–6,000; g_funda rows 1999–2025 30k–80k (more if several
  indfmt/consol variants per firm-year); g_secm rows 300k–1.2M; g_secd rows per year 375k–750k.

Outputs: data/raw/compustat_global_kr/{dictionary_*.json, g_company_kr.parquet, g_security_kr.parquet, g_funda_kr.parquet,
         g_secm_kr.parquet, g_secd_kr_<year>.parquet, PULL_LOG.json}
"""
import os, sys, io, json, time, datetime as dt, traceback
import pandas as pd

sys.path.insert(0, "/Users/jihwanw/PhD/code")
from wrds_connect_once import connect, WRDSDuoBlocked  # the only sanctioned connector (one Duo attempt, then stop)

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = f"{P}/data/raw/compustat_global_kr"; os.makedirs(OUT, exist_ok=True)
LOG = f"{OUT}/PULL_LOG.json"
FY_FROM, FY_TO = 1999, 2025                 # fundamentals: fiscal years
SECM_FROM, SECM_TO = "1999-12-01", "2026-10-31"
SECD_YEARS = list(range(2000, 2027))        # daily: calendar years, one checkpoint each

# Wanted columns — intersected with the server's column list; missing ones are logged, not assumed.
WANT = {
 "g_company": None,   # all columns (small table)
 "g_security": None,  # all columns (small table)
 "g_funda": ["gvkey", "datadate", "fyear", "fyr", "indfmt", "datafmt", "popsrc", "consol", "curcd", "conm", "fic", "loc", "exchg", "costat", "sich",
             "at", "lt", "ceq", "seq", "teq", "pstk", "mib", "che", "act", "lct", "dltt", "dlc", "re", "invt", "rect", "ppent", "intan", "gdwl",
             "sale", "revt", "cogs", "xsga", "oibdp", "oiadp", "ebitda", "ebit", "ib", "ni", "nicon", "xint", "txt", "dp", "dvc", "dvt", "dv",
             "oancf", "capx", "sstk", "prstkc", "xrd", "csho", "cshpri", "ajex", "emp", "prcc_f", "mkvalt", "epspx", "wcap", "fincf", "ivncf"],
 "g_secm": ["gvkey", "iid", "datadate", "prccm", "prchm", "prclm", "ajexm", "trfm", "cshom", "cshtrm", "curcdm", "exchg", "isin", "dvpsxm", "secstat", "tpci"],
 "g_secd": ["gvkey", "iid", "datadate", "prccd", "prchd", "prcld", "ajexdi", "trfd", "cshtrd", "cshoc", "exchg", "curcdd"],
}

log = json.load(open(LOG)) if os.path.exists(LOG) else {"runs": []}
run = {"started": dt.datetime.now().astimezone().isoformat(timespec="seconds"), "steps": [], "status": "running"}
log["runs"].append(run)

def _clean(o):
    """JSON-safe copy: numpy/pandas scalars -> Python, non-primitive dict keys -> str (value_counts of Int64 columns gives int64 keys)."""
    if isinstance(o, dict):
        return {(k if isinstance(k, (str, int, float, bool)) or k is None else str(k)) if not hasattr(k, "item") else k.item(): _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple, set)):
        return [_clean(v) for v in o]
    if hasattr(o, "item") and not isinstance(o, (str, bytes)):
        try: return o.item()
        except Exception: return str(o)
    if isinstance(o, (pd.Timestamp, dt.date, dt.datetime)):
        return str(o)
    return o

def save_log():
    json.dump(_clean(log), open(LOG, "w"), ensure_ascii=False, indent=1, default=str)

def vc(df, col, n=10):
    return df[col].value_counts(dropna=False).head(n).to_dict() if col in df.columns else None

def step(name, **kw):
    kw["name"] = name; kw["t"] = dt.datetime.now().astimezone().isoformat(timespec="seconds"); run["steps"].append(_clean(kw)); save_log()
    print(f"[{kw['t'][11:19]}] {name}: " + "; ".join(f"{k}={v}" for k, v in kw.items() if k not in ("name", "t", "sql")), flush=True)

TYPES = {}   # table -> {column: postgres data_type}, filled from information_schema after the catalog step

def copy_df(db, sql, date_cols=(), table=None):
    """Bulk fetch with COPY (3–4x faster than row fetch, per the 2026-11 WRDS memo). One attempt; errors propagate.
    Every column is read as text and then cast from the SERVER's declared type (information_schema.data_type), so a
    code column such as tpci ('0', '%', '1', 'F') can never be inferred as int in one chunk and str in another."""
    cur = db.connection.connection.cursor(); buf = io.StringIO()
    cur.copy_expert(f"COPY ({sql}) TO STDOUT WITH CSV HEADER", buf); buf.seek(0)
    df = pd.read_csv(buf, dtype=str, keep_default_na=True, na_values=[""], low_memory=False)
    types = TYPES.get(table, {})
    for c in df.columns:
        t = types.get(c, "")
        if t in ("numeric", "double precision", "real", "integer", "bigint", "smallint"):
            df[c] = pd.to_numeric(df[c], errors="raise")
            if t in ("integer", "bigint", "smallint"): df[c] = df[c].astype("Int64")
        elif t.startswith("date") or t.startswith("timestamp") or c in date_cols:
            df[c] = pd.to_datetime(df[c], errors="raise")
        else:
            df[c] = df[c].astype("string")
    return df

def cols_of(db, lib, tables):
    """Server-side column lists from the Postgres catalog only (no EXPLAIN / count on the big tables)."""
    tl = ",".join(f"'{t}'" for t in tables)
    d = copy_df(db, f"""select table_name, column_name, data_type, ordinal_position
                        from information_schema.columns where table_schema = '{lib}' and table_name in ({tl})
                        order by table_name, ordinal_position""")
    return {t: g.sort_values("ordinal_position").to_dict(orient="records") for t, g in d.groupby("table_name")}

def main():
    t0 = time.time()
    try:
        db = connect()                                # <-- the single Duo attempt
    except WRDSDuoBlocked as e:
        run["status"] = "duo_blocked"; step("connect", result="FAILED — block file written, no retry", detail=str(e)[:500]); save_log()
        print("WRDS Duo 인증 1회 실패, 재시도하지 않음. 기록: ~/.wrds_duo_block, /Users/jihwanw/PhD/code/logs/wrds_duo_incidents.log", flush=True)
        return 2
    step("connect", seconds=round(time.time() - t0, 1))
    try:
        # ---- 0. catalog: which library holds the Compustat Global tables, and their columns
        libs = [l for l in db.list_libraries() if "comp" in l.lower()]
        lib = None
        for cand in ["comp_global_daily", "comp_global", "compg"] + sorted(libs):
            if cand in libs:
                tabs = set(db.list_tables(cand))
                if {"g_funda", "g_company", "g_security", "g_secd"} <= tabs:
                    lib = cand; have_secm = "g_secm" in tabs; break
        if lib is None:
            raise RuntimeError(f"no library with g_funda+g_company+g_security+g_secd among {libs}")
        step("catalog", library=lib, g_secm_present=have_secm, comp_libraries=libs)
        dictionary = cols_of(db, lib, ["g_company", "g_security", "g_funda", "g_secd"] + (["g_secm"] if have_secm else []))
        for t in ["g_company", "g_security", "g_funda", "g_secd"]:
            if t not in dictionary: raise RuntimeError(f"information_schema returned no columns for {lib}.{t}")
        for t, v in dictionary.items(): TYPES[t] = {r["column_name"]: r["data_type"] for r in v}
        # column comments from the Postgres catalog, if WRDS populated them (first-party dictionary)
        comments = copy_df(db, f"""select c.relname as table_name, a.attname as column_name, d.description
                                   from pg_description d join pg_class c on d.objoid = c.oid
                                   join pg_attribute a on a.attrelid = c.oid and a.attnum = d.objsubid
                                   join pg_namespace n on n.oid = c.relnamespace
                                   where n.nspname = '{lib}' and c.relname in ('g_company','g_security','g_funda','g_secd','g_secm')""")
        json.dump({"library": lib, "columns": dictionary, "catalog_comments_rows": int(len(comments)),
                   "catalog_comments": comments.to_dict(orient="records")}, open(f"{OUT}/dictionary_{lib}.json", "w"), ensure_ascii=False, indent=1)
        step("dictionary", tables={t: len(v) for t, v in dictionary.items()}, catalog_comment_rows=int(len(comments)))
        colset = {t: set(n["column_name"] for n in v) for t, v in dictionary.items()}

        def select_list(table):
            want = WANT[table]
            if want is None: return "*", []
            have = [c for c in want if c in colset[table]]; missing = [c for c in want if c not in colset[table]]
            return ", ".join(have), missing

        # ---- 1. g_security: Korean exchange country OR Korean ISIN prefix (both flags kept; neither assumed to be the definition)
        f_sec = f"{OUT}/g_security_kr.parquet"
        if not os.path.exists(f_sec):
            cond = []
            if "excntry" in colset["g_security"]: cond.append("excntry = 'KOR'")
            if "isin" in colset["g_security"]: cond.append("substr(isin, 1, 2) = 'KR'")
            if not cond: raise RuntimeError("g_security has neither excntry nor isin")
            sql = f"select * from {lib}.g_security where " + " or ".join(cond)
            sec = copy_df(db, sql, date_cols=["dldtei"], table="g_security"); sec.to_parquet(f_sec, index=False); cached = False
        else:
            sec = pd.read_parquet(f_sec); sql = None; cached = True
        step("g_security", rows=len(sec), gvkeys=sec.gvkey.nunique(), cached=cached, sql=sql, excntry_counts=vc(sec, "excntry"),
             isin_prefix_counts=sec["isin"].str[:2].value_counts(dropna=False).head(10).to_dict() if "isin" in sec.columns else None,
             exchg_counts=vc(sec, "exchg"), tpci_counts=vc(sec, "tpci"), secstat_counts=vc(sec, "secstat"),
             delisted_rows=int(sec["dldtei"].notna().sum()) if "dldtei" in sec.columns else None)
        kr_gvkeys = sorted(sec.gvkey.dropna().unique())

        # ---- 2. g_company: incorporated in Korea OR has a Korean-listed security
        f_co = f"{OUT}/g_company_kr.parquet"
        if not os.path.exists(f_co):
            parts = []
            if "fic" in colset["g_company"]:
                parts.append(copy_df(db, f"select * from {lib}.g_company where fic = 'KOR'", table="g_company"))
            for i in range(0, len(kr_gvkeys), 1000):
                ids = ",".join(f"'{g}'" for g in kr_gvkeys[i:i+1000])
                parts.append(copy_df(db, f"select * from {lib}.g_company where gvkey in ({ids})", table="g_company"))
            co = pd.concat(parts, ignore_index=True).drop_duplicates("gvkey")
            co["flag_fic_kor"] = co["fic"].eq("KOR") if "fic" in co else None
            co["flag_has_kr_security"] = co.gvkey.isin(kr_gvkeys)
            co.to_parquet(f_co, index=False)
            step("g_company", rows=len(co), fic_kor=int(co.flag_fic_kor.sum()) if "fic" in co else None, has_kr_security=int(co.flag_has_kr_security.sum()),
                 both=int((co.flag_fic_kor & co.flag_has_kr_security).sum()) if "fic" in co else None,
                 loc_counts=co["loc"].value_counts(dropna=False).head(8).to_dict() if "loc" in co else None)
        else:
            co = pd.read_parquet(f_co); step("g_company", rows=len(co), cached=True)
        all_gvkeys = sorted(set(co.gvkey) | set(kr_gvkeys))

        # ---- 3. g_funda: all format variants kept; filtered later with reasons
        f_fa = f"{OUT}/g_funda_kr.parquet"
        if not os.path.exists(f_fa):
            sel, missing = select_list("g_funda"); parts = []
            for i in range(0, len(all_gvkeys), 1000):
                ids = ",".join(f"'{g}'" for g in all_gvkeys[i:i+1000])
                parts.append(copy_df(db, f"select {sel} from {lib}.g_funda where gvkey in ({ids}) and fyear between {FY_FROM} and {FY_TO}", date_cols=["datadate"], table="g_funda"))
            fa = pd.concat(parts, ignore_index=True); fa.to_parquet(f_fa, index=False)
            step("g_funda", rows=len(fa), gvkeys=fa.gvkey.nunique(), missing_wanted_columns=missing,
                 indfmt=fa.indfmt.value_counts(dropna=False).to_dict() if "indfmt" in fa else None, datafmt=fa.datafmt.value_counts(dropna=False).to_dict() if "datafmt" in fa else None,
                 popsrc=fa.popsrc.value_counts(dropna=False).to_dict() if "popsrc" in fa else None, consol=fa.consol.value_counts(dropna=False).to_dict() if "consol" in fa else None,
                 curcd=fa.curcd.value_counts(dropna=False).head(6).to_dict() if "curcd" in fa else None,
                 fyr=fa.fyr.value_counts(dropna=False).head(6).to_dict() if "fyr" in fa else None,
                 rows_by_fyear={int(k): int(v) for k, v in fa.fyear.value_counts().sort_index().items()} if "fyear" in fa else None)
        else:
            fa = pd.read_parquet(f_fa); step("g_funda", rows=len(fa), cached=True)

        # ---- 4. g_secm: monthly prices and shares for every Korean security
        if have_secm:
            f_sm = f"{OUT}/g_secm_kr.parquet"
            if not os.path.exists(f_sm):
                sel, missing = select_list("g_secm"); parts = []
                for i in range(0, len(kr_gvkeys), 500):
                    ids = ",".join(f"'{g}'" for g in kr_gvkeys[i:i+500])
                    parts.append(copy_df(db, f"select {sel} from {lib}.g_secm where gvkey in ({ids}) and datadate between '{SECM_FROM}' and '{SECM_TO}'", date_cols=["datadate"], table="g_secm"))
                sm = pd.concat(parts, ignore_index=True); sm.to_parquet(f_sm, index=False)
                step("g_secm", rows=len(sm), securities=sm.groupby(["gvkey", "iid"]).ngroups, missing_wanted_columns=missing,
                     curcdm=sm.curcdm.value_counts(dropna=False).head(6).to_dict() if "curcdm" in sm else None,
                     exchg=sm.exchg.value_counts(dropna=False).head(8).to_dict() if "exchg" in sm else None,
                     first=str(sm.datadate.min().date()), last=str(sm.datadate.max().date()))
            else:
                step("g_secm", cached=True)

        # ---- 5. g_secd: daily, one calendar year per checkpoint (the heavy part; the connection is already open, no Duo involved)
        sel, missing = select_list("g_secd")
        for y in SECD_YEARS:
            f_sd = f"{OUT}/g_secd_kr_{y}.parquet"
            if os.path.exists(f_sd): continue
            ty = time.time(); parts = []
            for i in range(0, len(kr_gvkeys), 500):
                ids = ",".join(f"'{g}'" for g in kr_gvkeys[i:i+500])
                parts.append(copy_df(db, f"select {sel} from {lib}.g_secd where gvkey in ({ids}) and datadate between '{y}-01-01' and '{y}-12-31'", date_cols=["datadate"], table="g_secd"))
            sd = pd.concat(parts, ignore_index=True); sd.to_parquet(f_sd, index=False)
            step(f"g_secd_{y}", rows=len(sd), securities=sd.groupby(["gvkey", "iid"]).ngroups if len(sd) else 0, seconds=round(time.time() - ty, 1),
                 missing_wanted_columns=missing if y == SECD_YEARS[0] else None,
                 curcdd=sd.curcdd.value_counts(dropna=False).head(4).to_dict() if len(sd) and "curcdd" in sd else None)
        run["status"] = "completed"
    except Exception as e:
        run["status"] = "failed_no_retry"; step("ERROR", error=f"{type(e).__name__}: {e}"[:800], traceback=traceback.format_exc()[-2000:])
        print("STOP: a query failed. Per policy no reconnect/retry. Checkpoints so far are kept; see PULL_LOG.json.", flush=True)
        try: db.close()
        except Exception: pass
        return 1
    try: db.close()
    except Exception: pass
    run["finished"] = dt.datetime.now().astimezone().isoformat(timespec="seconds"); run["total_seconds"] = round(time.time() - t0, 1); save_log()
    print(f"DONE in {run['total_seconds']}s — outputs in {OUT}", flush=True)
    return 0

if __name__ == "__main__":
    sys.exit(main())
