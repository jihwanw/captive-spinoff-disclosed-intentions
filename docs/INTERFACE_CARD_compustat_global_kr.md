# INTERFACE_CARD — Compustat Global, Korean universe (WRDS `comp_global_daily`)

Generated 2026-11-10T12:11:14+09:00 by `code/26_verify_compustat_global_kr.py` from the pull of `code/25_pull_compustat_global_universe.py` (2026-11-10). Results: `results/compustat_global_kr_verification_20261110.json`. Rule: an item without a source column entry is **[UNVERIFIED]** and must not feed a reported number.

## Tables and rows

| Table | Rows | Selection | Source |
|---|---|---|---|
| g_security | 5801 | excntry = 'KOR' or ISIN starts 'KR' (both kept; neither assumed to define the universe) | PULL_LOG.json step g_security |
| g_company | 5399 | fic = 'KOR' or has a Korean security | PULL_LOG.json step g_company |
| g_funda | 52360 | gvkeys of the above, fyear 1999–2025, all indfmt/consol variants kept | PULL_LOG.json step g_funda |
| g_secm | 522159 | all Korean securities 1999-12..2026-10 (file starts 2007-01 — probe) | PULL_LOG.json step g_secm |
| g_secd | 15,287,841 KRW rows | all Korean securities, calendar years 2000–2026 | PULL_LOG.json steps g_secd_<year> |

## Column definitions used (server-side catalog comments, `pg_description`)

| Column | Definition (verbatim) | Source |
|---|---|---|
| `g_funda.at` | Assets - Total | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.lt` | Liabilities - Total | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.ceq` | Common/Ordinary Equity - Total | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.seq` | Stockholders Equity - Parent | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.sale` | Sales/Turnover (Net) | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.revt` | Revenue - Total | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.nicon` | Net Income (Loss) - Consolidated | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.ib` | Income Before Extraordinary Items | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.oiadp` | Operating Income After Depreciation | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.oancf` | Operating Activities - Net Cash Flow | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.capx` | Capital Expenditures | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.che` | Cash and Short-Term Investments | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.dltt` | Long-Term Debt - Total | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.dlc` | Debt in Current Liabilities - Total | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.cshoi` | Com Shares Outstanding - Issue | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.emp` | Employees | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.sich` | Standard Industrial Classification - Historical | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.consol` | Level of Consolidation - Company Annual Descriptor | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.indfmt` | Industry Format | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.datafmt` | Data Format | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.popsrc` | Population Source | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.fyear` | Data Year - Fiscal | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.fyr` | Fiscal Year-end Month | dictionary_comp_global_daily.json / catalog_comments |
| `g_funda.curcd` | ISO Currency Code | dictionary_comp_global_daily.json / catalog_comments |
| `g_secd.prccd` | Price - Close - Daily | dictionary_comp_global_daily.json / catalog_comments |
| `g_secd.ajexdi` | Adjustment Factor (Issue)-Cumulative by Ex-Date | dictionary_comp_global_daily.json / catalog_comments |
| `g_secd.trfd` | Daily Total Return Factor | dictionary_comp_global_daily.json / catalog_comments |
| `g_secd.cshtrd` | Trading Volume - Daily | dictionary_comp_global_daily.json / catalog_comments |
| `g_secd.cshoc` | Shares Outstanding | dictionary_comp_global_daily.json / catalog_comments |
| `g_secd.curcdd` | ISO Currency Code - Daily | dictionary_comp_global_daily.json / catalog_comments |
| `g_secm.prccm` | Price - Close - Monthly | dictionary_comp_global_daily.json / catalog_comments |
| `g_secm.ajexm` | Adjustment Factor (Company) - Cumulative by Ex-Date - Monthly | dictionary_comp_global_daily.json / catalog_comments |
| `g_secm.dvpsxm` | Dividends per Share - Ex Date - Monthly | dictionary_comp_global_daily.json / catalog_comments |
| `g_security.excntry` | Stock Exchange Country Code | dictionary_comp_global_daily.json / catalog_comments |
| `g_security.exchg` | Stock Exchange Code | dictionary_comp_global_daily.json / catalog_comments |
| `g_security.tpci` | Issue Type Code | dictionary_comp_global_daily.json / catalog_comments |
| `g_security.secstat` | Security Status Marker | dictionary_comp_global_daily.json / catalog_comments |
| `g_security.dlrsni` | Security Inactivation Code | dictionary_comp_global_daily.json / catalog_comments |
| `g_security.dldtei` | Security Inactivation Date | dictionary_comp_global_daily.json / catalog_comments |
| `g_company.fic` | Current ISO Country Code - Incorporation | dictionary_comp_global_daily.json / catalog_comments |
| `g_company.loc` | Current ISO Country Code - Headquarters | dictionary_comp_global_daily.json / catalog_comments |
| `g_company.sic` | Standard Industry Classification Code | dictionary_comp_global_daily.json / catalog_comments |
| `g_company.gind` | GIC Industries | dictionary_comp_global_daily.json / catalog_comments |
| `g_company.ipodate` | Company Initial Public Offering Date | dictionary_comp_global_daily.json / catalog_comments |
| `g_company.dldte` | Research Company Deletion Date | dictionary_comp_global_daily.json / catalog_comments |

Columns wanted but absent from `g_funda` (not invented): ni, csho, cshpri, ajex, prcc_f, mkvalt, epspx; from `g_secm`: trfm, cshom. Substitutes present: nicon (Net Income - Consolidated), ib, cshoi (Com Shares Outstanding - Issue), ajexi; prices and shares outstanding from g_secd (prccd, cshoc) / g_secm (prccm).

## Probes (independent sources on disk)

| # | Question | Result | Source |
|---|---|---|---|
| P1 | fiscal year vs datadate | rows by fyr × (datadate.year − fyear): {'1': {'0': 0, '1': 15}, '2': {'0': 0, '1': 22}, '3': {'0': 0, '1': 1351}, '4': {'0': 0, '1': 6}, '5': {'0': 0, '1': 5}, '6': {'0': 661, '1': 0}, '7': {'0': 4, '1': 0}, '8': {'0': 25, '1': 0}, '9': {'0': 349, '1': 0}, '10': {'0': 44, '1': 0}, '11': {'0': 58, '1': 0}, '12': {'0': 49820, '1': 0}} | probe P1 (g_funda itself) |
| P2 | unit of g_funda amounts (DART won / Compustat) | consol C, at: log10 counts {'6': 232}, median ratio 1e+06, within 1% of 1e6: 1.000; sale vs sale 1.000, vs revt 1.000; ni vs nicon 0.413, vs ib 0.418; eq vs seq 0.450, vs ceq 0.437 (n at = 232) | probe P2: baseline_features.json (DART fnlttSinglAcnt, 05_collect_baseline_features.py lines 84–99) × g_funda |
| P2b | which Compustat line reproduces each DART account (within 1% after the 10^6 unit) | {'at': {'n': 232, 'share_within_1pct': 1.0, 'share_within_10pct': 1.0}, 'lt': {'n': 232, 'share_within_1pct': 1.0, 'share_within_10pct': 1.0}, 'sale~sale': {'n': 227, 'share_within_1pct': 1.0, 'share_within_10pct': 1.0}, 'sale~revt': {'n': 227, 'share_within_1pct': 1.0, 'share_within_10pct': 1.0}, 'oi~oiadp': {'n': 232, 'share_within_1pct': 1.0, 'share_within_10pct': 1.0}, 'oi~oibdp': {'n': 232, 'share_within_1pct': 0.004310344827586207, 'share_within_10pct': 0.05172413793103448}, 'eq~teq': {'n': 231, 'share_within_1pct': 1.0, 'share_within_10pct': 1.0}, 'eq~seq': {'n': 231, 'share_within_1pct': 0.45021645021645024, 'share_within_10pct': 0.6926406926406926}, 'eq~ceq': {'n': 231, 'share_within_1pct': 0.43722943722943725, 'share_within_10pct': 0.6926406926406926}, 'ni~nicon': {'n': 223, 'share_within_1pct': 0.42152466367713004, 'share_within_10pct': 0.6457399103139013}, 'ni~ib': {'n': 230, 'share_within_1pct': 0.3869565217391304, 'share_within_10pct': 0.591304347826087}} (consol C, DART 연결) | probe P2 definition_agreement_after_1e6 |
| P3 | consol code vs DART CFS/OFS | {'unit_factor_used': 1000000.0, 'DART_CFS_vs_consol_C': {'n': 232, 'share_at_equal_to_0.1pct_after_unit': 1.0}, 'DART_CFS_vs_consol_N': {'n': 0, 'share_at_equal_to_0.1pct_after_unit': None}, 'DART_OFS_vs_consol_C': {'n': 0, 'share_at_equal_to_0.1pct_after_unit': None}, 'DART_OFS_vs_consol_N': {'n': 32, 'share_at_equal_to_0.1pct_after_unit': 0.96875}} | probe P3 |
| P4 | unit of g_secd.cshoc | {'n': 240, 'log10_ratio_rounded_counts': {'-1': 1, '0': 239}, 'median_ratio': 0.9999810937706521, 'share_within_1pct_of_1e6': 0.0, 'share_within_1pct_of_1e3': 0.0, 'share_within_1pct_of_1': 0.8791666666666667} — ratio = cshoc / DART-implied common shares (holder count / holder % from the largest-shareholder table, rows with >= 5%); 10^0 means cshoc is in shares | probe P4: data/raw/dart_hyslr (hyslrSttus trmend_posesn_stock_co / _qota_rt) × g_secd |
| P5 | identity with the 2026-10-24 extract | {'old_rows': 565664, 'years_compared': [2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007, 2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026], 'old_rows_in_years': 565664, 'found_in_new': 565647, 'prccd_exact_equal_share': 1.0, 'ajexdi_exact_equal_share': 0.9934731572099338, 'trfd_exact_equal_share': 0.9977389404310686} | probe P5: data/raw/compustat_g_secd_events.parquet |
| P6 | exchange codes | {'248': {'유가': 826, '코넥스': 0, '코스닥': 1}, '298': {'유가': 1, '코넥스': 1, '코스닥': 1789}, '353': {'유가': 0, '코넥스': 105, '코스닥': 0}} (n = 2723 active securities matched to KIND by stock code) | probe P6: data/raw/kind_corplist_20261014.csv 시장구분 |
| P7 | coverage by year | see JSON P7_coverage (securities with ≥ 200 KRW price days per year; g_funda KRW/INDL/C gvkeys per fyear); KIND lists 2753 firms today | probe P7 |

## Code values recorded (not interpreted beyond the probes above)

```
{
 "g_funda": {
  "indfmt": {
   "INDL": 49805,
   "FS": 2555
  },
  "datafmt": {
   "HIST_STD": 52360
  },
  "popsrc": {
   "I": 52360
  },
  "consol": {
   "C": 33368,
   "N": 18992
  },
  "curcd": {
   "KRW": 52237,
   "CNY": 56,
   "USD": 29,
   "HKD": 21,
   "JPY": 12,
   "TWD": 5
  },
  "fyr": {
   "12": 49820,
   "3": 1351,
   "6": 661,
   "9": 349,
   "11": 58,
   "10": 44,
   "8": 25,
   "2": 22,
   "1": 15,
   "4": 6,
   "5": 5,
   "7": 4
  },
  "costat": {
   "A": 42867,
   "I": 9493
  }
 },
 "g_security": {
  "excntry": {
   "KOR": 5798,
   "HKG": 2,
   "DEU": 1
  },
  "exchg": {
   "248": 3194,
   "298": 2414,
   "353": 176,
   "1": 7,
   "157": 4,
   "127": 3,
   "170": 2,
   "115": 1
  },
  "tpci": {
   "0": 4157,
   "%": 1275,
   "1": 298,
   "2": 34,
   "7": 24,
   "F": 12,
   "None": 1
  },
  "secstat": {
   "A": 4071,
   "I": 1730
  },
  "dlrsni": {
   "nan": 4071,
   "10.0": 1085,
   "20.0": 282,
   "1.0": 245,
   "9.0": 54,
   "4.0": 35,
   "2.0": 14,
   "11.0": 7,
   "3.0": 4,
   "12.0": 2,
   "5.0": 1,
   "7.0": 1
  },
  "epf": {
   "Y": 5501,
   "N": 300
  }
 },
 "g_company": {
  "fic": {
   "KOR": 5348,
   "None": 18,
   "HKG": 17,
   "CYM": 9,
   "JPN": 3,
   "SGP": 2,
   "CHN": 1,
   "GBR": 1
  },
  "loc": {
   "KOR": 5364,
   "HKG": 16,
   "CHN": 5,
   "USA": 4,
   "JPN": 4,
   "CYM": 4,
   "SGP": 1,
   "GBR": 1
  },
  "costat": {
   "A": 3939,
   "I": 1460
  },
  "dlrsn": {
   "nan": 3939,
   "10.0": 1143,
   "1.0": 212,
   "9.0": 51,
   "4.0": 35,
   "2.0": 13,
   "3.0": 4,
   "5.0": 1,
   "7.0": 1
  }
 }
}
```

## Open items — [UNVERIFIED] until a source is added

- `tpci` issue-type values ('0', '%', '1', '2', '7', 'F') and `dlrsni` inactivation codes: no value lookup in the catalog comments; do not interpret. Use the ISIN rule (KR7 + stock code) and secstat/dldtei for listing status.
- `exchg` codes other than those cross-tabulated in P6 (e.g. 1, 115, 127, 157, 170, 194, 198, 251, 264): unknown venues; exclude from the Korean-market universe unless identified.
- Compustat Global `fic`/`loc` give incorporation/headquarters country; the KOSPI/KOSDAQ listing universe is defined by `exchg` ∈ {248, 298} (P6) with a KRW price history, not by `fic`.
- DART 자본총계 is reproduced by `teq` (Stockholders Equity - Total), not by `seq`/`ceq` (parent / common equity; they exclude non-controlling interests) — see P2b. Use `ceq` only where the construct is common shareholders' book equity, and say so.
- DART 당기순이익(손실) is NOT reproduced by `nicon` or `ib` for most consolidated firm-years (P2b) although at, lt, sale, oiadp and teq are reproduced to 1%. Net-income-based Compustat variables are **[UNVERIFIED]** for Korea until a further probe pulls `mii`, `ibmii`, `ibki`, `nio`, `nit`, `ninc` and tests which combination equals the DART line (next WRDS session); until then profitability for the pre-2015 universe uses `oiadp`/`oibdp` over `at`, and net income comes from DART (FY2015+).
- Historical listed-firm counts per year (for P7 against the exchange's own statistics): not on disk; KRX market statistics to be fetched before coverage is quoted in the paper.
- Common vs preferred issues: `g_security` carries 5,620 KR7-ISIN securities for 5,616 stock codes, and 2026 shows 3,862 securities with a KRW price history against 2,753 firms on today's KIND list, so the security file includes non-common issues (preferred shares, funds). The rule "6-digit code ending in 0 = common stock" is a KRX convention that has NOT been verified from data here; before the universe is built (script 27) test it on `dsci` (Security Description) and on the KIND list, and record the result in this card.
- `g_secm` begins 2007-01-31 (PULL_LOG step g_secm: first = 2007-01-31); monthly market values for 2000–2006 must be built from `g_secd` (prccd × cshoc at month-end), not from g_secm.
- Pre-2011 fundamentals: consolidated rows (`consol = 'C'`) exist for 380 gvkeys in fyear 2001 and 1,194 in 2011 (P7 `g_funda_KRW_INDL_C_gvkeys_by_fyear`), reflecting the move to consolidated reporting; a firm-year universe for 2001–2010 needs a stated rule for using `consol = 'N'` (parent-only; reproduces DART OFS, P3) when no `C` row exists, with a flag.
- Vendor revisions: between the 2026-10-24 and 2026-11-10 extracts `prccd` is identical on all 565,647 overlapping rows but `ajexdi` differs on 0.65% and `trfd` on 0.23% (P5) — adjustment and total-return factors are revised by the vendor; all return calculations must use ONE extract (this one) and cite its pull date.

## Addendum 2026-11-10 — other sources used in step 1 (not Compustat)

| Item | Value | Source |
|---|---|---|
| KRX foreign ownership (pykrx 1.2.8 `get_exhaustion_rates_of_foreign_investment_by_ticker(date, market="ALL")`) | columns 상장주식수, 보유수량, 지분율, 한도수량, 한도소진률; 지분율 = foreign holdings / listed shares, %; needs KRX login (api_keys.ini [krx]); data reach back to 2002 (005930 on 2002-01-15: 60.0); values quantised to 16-bit floats (~0.03 pp) | pykrx docstring + probe `code/34` (snapshot vs per-ticker range call 20/20 agree) |
| DART `exctvSttus` (임원 현황) | fields nm, sexdstn, birth_ym, ofcps, rgist_exctv_at (등기임원/미등기임원), fte_at (상근/비상근), chrg_job, main_career, mxmm_shrholdr_relate, hffc_pd, tenure_end_on, stlm_dt; data from FY2014 onward (FY2005 → status 013 no data) | response read 2026-11-10 (두산건설 FY2016, 22 rows); `code/34` |
| DART `cmpDvDecsn` field `popt_ctr_atn` (stored as `appraisal_right` in dart_division_decisions_2017_2026.json) | = "풋옵션 등 계약 체결여부" (put-option CONTRACT flag; block 11 of the filing), NOT the shareholder appraisal right; '예' for 9 of 290 captive filings | filing texts (block "11. 풋옵션 등 계약 체결여부") + `code/01` mapping; `code/32` note |
| DART `cmpDvDecsn` field `dv_impef` (stored as `purpose`) | "분할의 중요영향 및 효과" text, not the stated purpose (분할의 목적) | `code/01` line 65 mapping; sample values read 2026-11-10 |
| Protection block "N. 물적분할의 경우 주주보호방안" / plan block "N. 향후 회사구조개편에 관한 계획" | present in 61 of 66 post-2022-10 captive filings, 0 of 228 earlier; the next item number must start a line or follow a sentence end (the in-text reference "상기 '10. 주식매수청구권…'" otherwise truncates the block) | `code/33` |
| Appraisal price "매수예정가격 <KRW>" in block "10. 주식매수청구권에 관한 사항" | the number must be the next token; '-' = not applicable; 40 of 48 post-reform blocks carry a price; statutory formula ≈ simple average of 2-month/1-month/1-week closes before the board date (median |diff| 0.8%) | `code/32` |
