#!/usr/bin/env python3
"""05_collect_baseline_features.py — announcement-date numeric features for the financial-only baseline.

Sources and documented meanings (DART developer guide, read 2026-10-15):
  cmpDvDecsn (DS005 apiId 2020051): ffdtl_tast/tdbt/teqt/cpt = 분할설립회사 설립시 재무내용(자산총계/부채총계/자본총계/자본금);
    dvfcmp_nbsn_rsl = 신설사업부문 최근 사업연도 매출액; atdvfdtl_tast/tdbt/teqt/cpt = 분할 후 존속회사 재무내용;
    atdv_excmp_exbsn_rsl = 존속사업부문 최근 사업연도 매출액; dvfcmp_rlst_atn = 분할설립회사 재상장신청 여부;
    popt_ctr_atn = 풋옵션 등 계약 체결여부; rs_sm_atn = 증권신고서 제출대상 여부; od_a_at_t/b = 사외이사 참석/불참(명).
  fnlttSinglAcnt (DS003 단일회사 주요계정): account_nm (계정명), thstrm_amount (당기금액), fs_div (CFS 연결/OFS 개별),
    for the parent's fiscal year preceding the board resolution (reprt_code 11011 사업보고서).
Output: data/processed/baseline_features.json  (one record per carve-out event)
"""
import json, os, re, time, configparser, urllib.request, urllib.parse, datetime as dt, sys

P = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVENTS = f"{P}/data/raw/dart_division_decisions_2017_2026.json"
CACHE = f"{P}/data/raw/dart_cache_features.json"
OUT = f"{P}/data/processed/baseline_features.json"
cfg = configparser.ConfigParser(); cfg.read("/Users/jihwanw/PhD/code/api_info/api_keys.ini")
KEY = cfg["dart"].get("api_key") or cfg["dart"].get("key") or list(cfg["dart"].values())[0]
cache = json.load(open(CACHE, encoding="utf-8")) if os.path.exists(CACHE) else {}


def api(ep, **kw):
    q = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in kw.items())
    for a in range(3):
        try:
            with urllib.request.urlopen(f"https://opendart.fss.or.kr/api/{ep}.json?crtfc_key={KEY}&{q}", timeout=40) as r: d = json.load(r)
            if d.get("status") in ("020", "800"): print("STOP", d, flush=True); sys.exit(2)
            return d
        except Exception: time.sleep(2 + 3 * a)
    return {}


def num(s):
    if s is None: return None
    s = str(s).replace(",", "").strip()
    if s in ("", "-"): return None
    try: return float(s)
    except Exception: return None


def kdate(s):
    m = re.search(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})", s or "")
    return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None


events = [e for e in json.load(open(EVENTS, encoding="utf-8")) if e["type"] in ("carve_out", "mixed")]
out = []; t0 = time.time()
for i, e in enumerate(events, 1):
    corp, rn = e["corp_code"], e["rcept_no"]
    bd = kdate(e["board_date"])
    # Board year for the yearly cmpDvDecsn query and the parent's prior fiscal year. When 이사회결의일 is missing ('-'),
    # fall back to 분할기일, then to the receipt date: DART 접수번호 is 14 digits = 접수일자(YYYYMMDD) + 일련번호(6)
    # (DART open-API field description for rcept_no). Data check 2026-10-17 on these 294 events: all rcept_no are 14 digits,
    # the 8-digit prefix is a valid date, equal to the board date for 163/293 events and in the same year for 94%.
    # Only one event lacks a board date (무궁화인포메이션테크놀로지, rcept_no 20221214000396, 분할기일 2022-12-14).
    if bd:
        yr, yr_src = bd.year, "board_date"
    elif kdate(e.get("division_date")):
        yr, yr_src = kdate(e["division_date"]).year, "division_date"
    else:
        yr, yr_src = int(rn[:4]), "rcept_no"
    # A board year more than one year away from the receipt year is a filing typo (data check 2026-10-17: one case,
    # 두산건설 rcept_no 20200707000019 with 이사회결의일 '2000년 06월 12일'); use the receipt year instead.
    if abs(yr - int(rn[:4])) > 1:
        yr, yr_src = int(rn[:4]), f"rcept_no (board_date {e['board_date']!r} implausible)"
    # full division record (the filing's own structured fields)
    k = f"dv:{corp}:{yr}"
    if k not in cache:
        cache[k] = api("cmpDvDecsn", corp_code=corp, bgn_de=f"{yr}0101", end_de=f"{yr}1231").get("list", []) or []; time.sleep(0.05)
    rec = next((x for x in cache[k] if x.get("rcept_no") == rn), None) or next((x for x in cache[k] if x.get("dvdt") == e["division_date"]), None) or {}
    # parent's prior fiscal year key accounts (consolidated preferred, else separate)
    fy = yr - 1
    k2 = f"fs:{corp}:{fy}"
    if k2 not in cache:
        cache[k2] = api("fnlttSinglAcnt", corp_code=corp, bsns_year=fy, reprt_code="11011").get("list", []) or []; time.sleep(0.05)
    acc = {}
    for div in ("CFS", "OFS"):
        rows = [x for x in cache[k2] if x.get("fs_div") == div]
        if rows:
            for x in rows:
                nm = (x.get("account_nm") or "").replace(" ", "")
                # fnlttSinglAcnt account names as they occur in the cached responses (checked 2026-10-17 over 507 statements):
                # 자산총계, 부채총계, 자본총계, 매출액, 영업이익, 유동자산, 유동부채 appear verbatim; net income appears only as
                # "당기순이익(손실)" (twice per statement, sj_div IS, identical amounts) -> stored under the key 당기순이익.
                if nm == "당기순이익(손실)": nm = "당기순이익"
                if nm in ("자산총계", "부채총계", "자본총계", "매출액", "영업이익", "당기순이익", "유동자산", "유동부채") and nm not in acc:
                    acc[nm] = num(x.get("thstrm_amount"))
            acc["_fs_div"] = div; break
    f = {
        "rcept_no": rn, "corp_code": corp, "corp_name": e["corp_name"], "corp_cls": e["corp_cls"], "board_year": yr, "board_year_source": yr_src, "board_date": e["board_date"],
        "newco_assets": num(rec.get("ffdtl_tast")), "newco_debt": num(rec.get("ffdtl_tdbt")), "newco_equity": num(rec.get("ffdtl_teqt")), "newco_capital": num(rec.get("ffdtl_cpt")),
        "newco_sales": num(rec.get("dvfcmp_nbsn_rsl")), "parent_after_assets": num(rec.get("atdvfdtl_tast")), "parent_after_debt": num(rec.get("atdvfdtl_tdbt")),
        "parent_after_equity": num(rec.get("atdvfdtl_teqt")), "parent_after_sales": num(rec.get("atdv_excmp_exbsn_rsl")),
        "relisting_application": rec.get("dvfcmp_rlst_atn"), "put_option_contract": rec.get("popt_ctr_atn"), "securities_registration": rec.get("rs_sm_atn"),
        "outside_directors_present": num(rec.get("od_a_at_t")), "outside_directors_absent": num(rec.get("od_a_at_b")),
        "parent_fy": fy, "parent_fs_div": acc.get("_fs_div"), "parent_total_assets": acc.get("자산총계"), "parent_total_debt": acc.get("부채총계"), "parent_equity": acc.get("자본총계"),
        "parent_sales": acc.get("매출액"), "parent_operating_income": acc.get("영업이익"), "parent_net_income": acc.get("당기순이익"), "parent_current_assets": acc.get("유동자산"), "parent_current_liabilities": acc.get("유동부채"),
        "record_found": bool(rec),
    }
    out.append(f)
    if i % 50 == 0 or i == len(events):
        json.dump(cache, open(CACHE, "w"), ensure_ascii=False); json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)
        print(f"{i}/{len(events)} records_found={sum(1 for x in out if x['record_found'])} parent_fs={sum(1 for x in out if x['parent_total_assets'])} [{time.time()-t0:.0f}s]", flush=True)
print("done")
