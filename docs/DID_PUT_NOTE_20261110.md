# Equity spin-off control group DiD and the appraisal put (20261110)

Source `results/equity_did_appraisal_put_20261110.json` (`code/32_equity_did_appraisal_put.py`); per-event file `data/processed/division_announcement_cars_20261110.csv`.

Events with CARs: {('2001-2016', 'captive'): 372, ('2001-2016', 'equity'): 129, ('2017+', 'captive'): 260, ('2017+', 'equity'): 55} (status {'ok': 816, 'no_day0': 94, 'short_estimation': 15}). Identity control vs the paper's CARs: {'n_matched': 670, 'corr': 0.96, 'median_abs_diff_pp': 0.0, 'pass': True}.

Mean CAR[-1,+1] by type: {'captive': {'n': 632, 'mean_pct': 0.74, 'median_pct': 0.22, 't': 2.09}, 'equity': {'n': 184, 'mean_pct': 0.63, 'median_pct': 0.25, 't': 1.06}}; 2017+ by type × post: {'captive|0.0': {'n': 209, 'mean_pct': -0.09, 'median_pct': -0.1}, 'captive|1.0': {'n': 51, 'mean_pct': 5.51, 'median_pct': 3.4}, 'equity|0.0': {'n': 31, 'mean_pct': -0.28, 'median_pct': -1.31}, 'equity|1.0': {'n': 24, 'mean_pct': -1.3, 'median_pct': -0.87}}

## Difference-in-differences (Captive × Post(2022-10-01), year FE)

| Spec | n (captive/equity/post) | Captive (pp) | Captive×Post (pp) | p HC1 | p firm | p year |
|---|---|---|---|---|---|---|
| 2017_2026_car3_yearFE | 279 (230/49/65) | +1.00 | +5.71 ± 1.60 | 0.0 | 0.0 | 0.0 |
| 2017_2026_car3_yearFE_logme_kosdaq | 279 (230/49/65) | +0.30 | +5.45 ± 1.59 | 0.001 | 0.001 | 0.0 |
| 2017_2026_car21_yearFE_logme_kosdaq | 260 (211/49/57) | +5.37 | +2.10 ± 4.78 | 0.659 | 0.661 | 0.262 |
| 2001_2026_car3_yearFE_logme_kosdaq | 762 (589/173/65) | -0.64 | +6.52 ± 1.62 | 0.0 | 0.0 | 0.0 |
| 2001_2026_madj3_yearFE_logme_kosdaq | 762 (589/173/65) | -0.62 | +6.43 ± 1.63 | 0.0 | 0.0 | 0.0 |
| placebo_2017_2022sep_cut_2019_10 | 214 (187/27/132) | -1.14 | +2.27 ± 2.89 | 0.432 | 0.435 | 0.088 |

Event time (mean CAR % by type and year, 2015+): {"2015": {"captive": {"n": 20, "mean": 0.18}, "equity": {"n": 7, "mean": 0.48}}, "2016": {"captive": {"n": 36, "mean": -0.96}, "equity": {"n": 8, "mean": 4.81}}, "2017": {"captive": {"n": 30, "mean": 0.73}, "equity": {"n": 7, "mean": 1.94}}, "2018": {"captive": {"n": 28, "mean": 1.93}, "equity": {"n": 8, "mean": 0.16}}, "2019": {"captive": {"n": 29, "mean": 1.59}, "equity": {"n": 2, "mean": -0.76}}, "2020": {"captive": {"n": 48, "mean": -1.02}, "equity": {"n": 5, "mean": -2.71}}, "2021": {"captive": {"n": 47, "mean": -0.67}, "equity": {"n": 6, "mean": 0.04}}, "2022": {"captive": {"n": 35, "mean": -1.07}, "equity": {"n": 6, "mean": -4.43}}, "2023": {"captive": {"n": 13, "mean": 6.22}, "equity": {"n": 9, "mean": -1.4}}, "2024": {"captive": {"n": 15, "mean": 8.18}, "equity": {"n": 5, "mean": -0.01}}, "2025": {"captive": {"n": 10, "mean": 0.89}, "equity": {"n": 4, "mean": -0.53}}, "2026": {"captive": {"n": 5, "mean": 10.72}, "equity": {"n": 3, "mean": -1.3}}}

Filings with CARs by half-year and type (2017+): {"2017H1": {"captive": 22, "equity": 6}, "2017H2": {"captive": 8, "equity": 1}, "2018H1": {"captive": 10, "equity": 6}, "2018H2": {"captive": 18, "equity": 2}, "2019H1": {"captive": 13, "equity": 0}, "2019H2": {"captive": 16, "equity": 2}, "2020H1": {"captive": 27, "equity": 3}, "2020H2": {"captive": 21, "equity": 2}, "2021H1": {"captive": 26, "equity": 4}, "2021H2": {"captive": 21, "equity": 2}, "2022H1": {"captive": 20, "equity": 1}, "2022H2": {"captive": 15, "equity": 5}, "2023H1": {"captive": 7, "equity": 6}, "2023H2": {"captive": 6, "equity": 3}, "2024H1": {"captive": 5, "equity": 2}, "2024H2": {"captive": 10, "equity": 3}, "2025H1": {"captive": 8, "equity": 1}, "2025H2": {"captive": 2, "equity": 3}, "2026H1": {"captive": 2, "equity": 1}, "2026H2": {"captive": 3, "equity": 2}}

## Appraisal right as a put

{
 "post_captive_2017plus_filings_with_text": 51,
 "with_block": 48,
 "with_stated_price": 40,
 "proxy_validation": {
  "n": 26,
  "median_abs_rel_diff_pct": 0.81,
  "share_within_3pct": 0.808,
  "share_within_5pct": 0.885,
  "pass_lt_3pct": true
 },
 "moneyness_post_captive": {
  "n": 40,
  "mean_pct": 1.0,
  "median_pct": 1.55,
  "share_in_the_money": 0.6,
  "q25_q75_pct": [
   -3.95,
   4.5
  ]
 },
 "car3_on_moneyness_post_captive_stated": {
  "n": 33,
  "slope": 0.3894,
  "se": 0.2848,
  "p": 0.172,
  "spearman": 0.282,
  "spearman_p": 0.112
 },
 "car21_on_moneyness_post_captive_stated": {
  "n": 25,
  "slope": 0.4489,
  "se": 0.1846,
  "p": 0.015,
  "spearman": 0.506,
  "spearman_p": 0.01
 },
 "placebo_car3_on_proxy_pre_captive_2017_2022": {
  "n": 155,
  "slope": -0.0737,
  "se": 0.041,
  "p": 0.072,
  "spearman": -0.164,
  "spearman_p": 0.041
 },
 "placebo_car3_on_proxy_equity_2017plus": {
  "n": 20,
  "slope": -0.1649,
  "se": 0.1813,
  "p": 0.363,
  "spearman": -0.23,
  "spearman_p": 0.329
 },
 "placebo_car3_on_proxy_equity_post": {
  "n": 2
 },
 "exercise_payoff": {
  "n_with_1y": 35,
  "exercise_return_pct_median": 1.43,
  "hold_1y_return_pct_median": 0.53,
  "exercise_minus_hold_pp_median": 1.09,
  "share_exercise_beats_hold": 0.514,
  "note": "exercise return = stated appraisal price / close on day -1 (cash received ~1-2 months later, not discounted); hold = adjusted price at +250 trading days / close -1"
 }
}

## Expectation check

{'identity_pass': True, 'equity_2017plus_mean_within_3pp_of_-3.0': True, 'equity_2017plus_mean_pct': -0.74, 'did_in_[1,9]pp': True, 'placebo_within_2pp': False, 'proxy_pass': True, 'put_slope_positive': True, 'placebo_slopes_within_2se': {'placebo_car3_on_proxy_pre_captive_2017_2022': True, 'placebo_car3_on_proxy_equity_2017plus': True, 'placebo_car3_on_proxy_equity_post': None}}

## Caveats recorded

- Equity spin-off parents are the untreated group for the announcement reaction only; their later returns are not comparable (new-company shares).
- The statutory price is a VWAP average; the proxy uses simple averages of closes — validated against the stated prices above and used only for placebos.
- Exercise payoff ignores the 1–2 month delay in receiving the appraisal cash and any court revision of the price.
- The 'appraisal_right' key in dart_division_decisions_2017_2026.json is DART's put-option-contract flag (popt_ctr_atn), not the appraisal right; it was not used.
