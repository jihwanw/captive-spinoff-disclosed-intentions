# Matched benchmarks and the selection model (20261110)

Source `results/matched_benchmark_selection_20261110.json` (`code/31_matched_benchmark_and_selection.py`); per-event file `data/processed/event_benchmarks_20261110.csv`. Identity control (market-adjusted BHAR equals 19's): {'n': 578, 'max_abs_diff_madj': 2.220446049250313e-16, 'pass': True}.

Coverage: {'events_with_window': 578, 'pf55': 532, 'size5_fallback': 27, 'pf_primary': 559, 'pf33': 532, 'matched_firm': 523, 'no_gvkey': 0, 'median_match_distance': 0.05606086622289604, 'psm_control': 541}

## One-year BHAR by benchmark

| Benchmark | n | mean | 95% CI | median | share < 0 | Spearman(S) | rank~S coef (HC1 p / firm p) | level~S coef | early − never (pp, MW p) |
|---|---|---|---|---|---|---|---|---|---|
| market_adjusted_paper | 559 | -0.056 | [-0.111, +0.004] | -0.161 | 0.662 | -0.137 (p 0.0012) | -0.1945 (0.004 / 0.004) | -0.158 (p 0.283) | -13.6 (median -15.2; p 0.0023) |
| pf55_sizeBM_with_size_fallback | 540 | -0.082 | [-0.135, -0.022] | -0.171 | 0.706 | -0.090 (p 0.0358) | -0.1470 (0.032 / 0.031) | -0.121 (p 0.393) | -10.0 (median -7.8; p 0.0689) |
| pf55_strict | 513 | -0.077 | [-0.134, -0.015] | -0.163 | 0.7 | -0.072 (p 0.1011) | -0.1169 (0.097 / 0.095) | -0.095 (p 0.52) | -9.6 (median -6.5; p 0.118) |
| pf33 | 513 | -0.081 | [-0.138, -0.018] | -0.178 | 0.702 | -0.085 (p 0.0557) | -0.1636 (0.02 / 0.019) | -0.115 (p 0.433) | -8.8 (median -7.0; p 0.0745) |
| matched_firm_sizeBM | 504 | -0.086 | [-0.176, +0.003] | -0.036 | 0.538 | -0.026 (p 0.5553) | -0.0168 (0.818 / 0.82) | -0.134 (p 0.523) | -9.4 (median +3.4; p 0.3162) |
| psm_control_firm | 522 | -0.036 | [-0.112, +0.037] | -0.069 | 0.569 | -0.088 (p 0.0452) | -0.1243 (0.078 / 0.071) | -0.102 (p 0.626) | -15.1 (median -11.1; p 0.0265) |

Median BHAR by signal quintile: market_adjusted_paper: {1: -0.03, 2: -0.1757, 3: -0.192, 4: -0.2397, 5: -0.2297}; pf55_sizeBM_with_size_fallback: {1: -0.1042, 2: -0.1247, 3: -0.2183, 4: -0.2099, 5: -0.2152}; pf55_strict: {1: -0.1116, 2: -0.131, 3: -0.2178, 4: -0.1954, 5: -0.1893}; pf33: {1: -0.1061, 2: -0.1586, 3: -0.1924, 4: -0.2364, 5: -0.192}; matched_firm_sizeBM: {1: -0.0498, 2: -0.0274, 3: -0.0953, 4: -0.0402, 5: -0.0001}; psm_control_firm: {1: 0.0006, 2: -0.0244, 3: -0.1143, 4: -0.106, 5: -0.1084}

## Selection logit — who announces a captive spin-off (firm-year universe, outcome = announcement in the next calendar year)

Firm-years 43000, events 615, firms 3132, pseudo-R² 0.061; year FE + GICS sector FE; firm-clustered SE.

| Covariate | coef | se (firm) | p | Kang & Lee (2025b) Table 4 sign |
|---|---|---|---|---|
| log_at | +0.231 | 0.038 | 0.000 | + |
| q | +0.065 | 0.042 | 0.125 | + (n.s.) |
| lev | +0.627 | 0.243 | 0.010 | + |
| inv | +0.423 | 0.827 | 0.609 | + |
| cf | -2.963 | 0.45 | 0.000 | - |
| cash | -0.344 | 0.349 | 0.324 |  |
| sg | +0.186 | 0.06 | 0.002 |  |
| kosdaq | -0.067 | 0.113 | 0.551 | + (KOSPI -) |
| parent_only | +0.074 | 0.109 | 0.500 |  |

Propensity: {'event_median': 0.019071037941120986, 'control_median': 0.01126675587281884, 'event_in_control_support_share': 1.0, 'auc_of_ps': 0.7166451546077334}

## Expectation check

{'identity_pass': True, 'pf_mean_in_[-0.12,0.02]': True, 'pf_median_negative': True, 'spearman_in_[-0.20,-0.05]': True, 'rank_coef_in_[-0.28,-0.08]': True, 'early_never_in_[-25,-5]pp': True, 'selection_signs': {'log_at_pos': True, 'lev_pos': True, 'cf_neg': True, 'inv_pos': True, 'kosdaq_pos': False}, 'ps_support_ge_0.95': True}

## Caveats recorded

- Benchmarks are compounded over the event's own trading days (universe calendar), firm returns from the paper's panel (KRX 2017+, Compustat 2001–2016).
- Size/B-M assignment is the FF June convention with all-universe breakpoints; firms without a B/M assignment (negative book equity, no December ME) get the size-only quintile; events with no Compustat security get no matched benchmark (counted).
- The selection model uses operating cash flow proxied by oibdp/at because net-income lines are unverified for Korea (26 P2b); board independence, foreign ownership and chaebol affiliation of Kang & Lee's specification are not yet in the data (strategy §2, step 1).
- Matched-firm and PSM benchmarks use one nearest neighbour with replacement; they are noisier than portfolio benchmarks by construction.
