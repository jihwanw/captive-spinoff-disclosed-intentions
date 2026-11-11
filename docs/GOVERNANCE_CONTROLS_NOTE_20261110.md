# Foreign ownership and board independence as controls (20261110)

Source `results/governance_controls_20261110.json` (`code/34_governance_controls_foreign_board.py`); per-event file `data/processed/event_governance_controls_20261110.csv`.

Foreign ownership (KRX 지분율 at day -1): {"coverage": 577, "coverage_share": 0.962, "describe_pct": {"count": 577.0, "mean": 8.17, "std": 13.08, "min": 0.0, "25%": 0.39, "50%": 2.45, "75%": 10.08, "max": 84.38}, "by_period_median": {"2001-2016": 1.44, "2017+": 3.99}, "probe_range_call_vs_snapshot": {"checked": 20, "agree_within_0.05pp": 20}, "n_failed": 22}

Board independence (DART exctvSttus, FY before the announcement, 2014+): {"eligible_fy2014plus": 285, "api_ok": 284, "with_ratio": 211, "describe_ratio": {"count": 211.0, "mean": 0.297, "std": 0.197, "min": 0.0, "25%": 0.2, "50%": 0.25, "75%": 0.5, "max": 0.667}, "n_registered_median": 5.0}

## Spec-3 regressions with the new controls (year FE; HC1 / firm-cluster p)

| Outcome | Spec | n | coef on S (firm p) | foreign (p) | outside-director ratio (p) | block (p) |
|---|---|---|---|---|---|---|
| rank_1y | spec3_published_sample | 559 | -0.1950 (0.004) |  () |  () |  () |
| rank_1y | spec3_on_foreign_sample | 540 | -0.2142 (0.001) |  () |  () |  () |
| rank_1y | spec3_plus_foreign | 540 | -0.2111 (0.002) | 0.0643 (0.671) |  () |  () |
| rank_1y | spec3_on_board_sample_2015plus | 194 | -0.1910 (0.11) |  () |  () |  () |
| rank_1y | spec3_plus_foreign_board | 194 | -0.1873 (0.119) | 0.1182 (0.677) | -0.0893 (0.569) |  () |
| rank_1y | spec3_plus_foreign_board_block | 190 | -0.1837 (0.14) | 0.0826 (0.776) | -0.0518 (0.744) | 0.0067 (0.966) |
| bhar_1y | spec3_published_sample | 559 | -0.1579 (0.281) |  () |  () |  () |
| bhar_1y | spec3_on_foreign_sample | 540 | -0.1837 (0.222) |  () |  () |  () |
| bhar_1y | spec3_plus_foreign | 540 | -0.1850 (0.222) | -0.0249 (0.933) |  () |  () |
| bhar_1y | spec3_on_board_sample_2015plus | 194 | -0.0450 (0.81) |  () |  () |  () |
| bhar_1y | spec3_plus_foreign_board | 194 | -0.0446 (0.81) | 0.4189 (0.448) | 0.199 (0.529) |  () |
| bhar_1y | spec3_plus_foreign_board_block | 190 | -0.0137 (0.945) | 0.4533 (0.486) | 0.2414 (0.433) | 0.2242 (0.541) |
| ann_car | spec3_published_sample | 560 | +0.0385 (0.043) |  () |  () |  () |
| ann_car | spec3_on_foreign_sample | 546 | +0.0393 (0.049) |  () |  () |  () |
| ann_car | spec3_plus_foreign | 546 | +0.0407 (0.044) | 0.0319 (0.306) |  () |  () |
| ann_car | spec3_on_board_sample_2015plus | 193 | +0.0252 (0.337) |  () |  () |  () |
| ann_car | spec3_plus_foreign_board | 193 | +0.0252 (0.339) | 0.0178 (0.76) | -0.0009 (0.978) |  () |
| ann_car | spec3_plus_foreign_board_block | 189 | +0.0321 (0.216) | 0.039 (0.573) | -0.0002 (0.995) | 0.0751 (0.06) |

## Block regressions with the new controls

{
 "score_on_block_plus_foreign": {
  "n": 508,
  "block": {
   "coef": -0.1426,
   "se_hc1": 0.0458,
   "p_hc1": 0.002,
   "p_firm": 0.002
  },
  "foreign": {
   "coef": -0.2222,
   "se_hc1": 0.0939,
   "p_hc1": 0.018,
   "p_firm": 0.016
  },
  "log_me": {
   "coef": 0.0231,
   "se_hc1": 0.008,
   "p_hc1": 0.004,
   "p_firm": 0.005
  },
  "log_bm": {
   "coef": -0.0047,
   "se_hc1": 0.0111,
   "p_hc1": 0.673,
   "p_firm": 0.661
  },
  "mom6": {
   "coef": -0.0078,
   "se_hc1": 0.0154,
   "p_hc1": 0.614,
   "p_firm": 0.612
  },
  "kosdaq": {
   "coef": -0.0106,
   "se_hc1": 0.0188,
   "p_hc1": 0.572,
   "p_firm": 0.583
  },
  "rel_size": {
   "coef": -0.0704,
   "se_hc1": 0.1123,
   "p_hc1": 0.531,
   "p_firm": 0.532
  },
  "surv_lev": {
   "coef": 0.2358,
   "se_hc1": 0.0626,
   "p_hc1": 0.0,
   "p_firm": 0.0
  },
  "relisting": {
   "coef": 0.0393,
   "se_hc1": 0.0531,
   "p_hc1": 0.459,
   "p_firm": 0.443
  }
 },
 "rank_on_block_plus_foreign": {
  "n": 500,
  "block": {
   "coef": 0.1455,
   "se_hc1": 0.0792,
   "p_hc1": 0.066,
   "p_firm": 0.074
  },
  "foreign": {
   "coef": 0.1067,
   "se_hc1": 0.1514,
   "p_hc1": 0.481,
   "p_firm": 0.507
  },
  "log_me": {
   "coef": 0.0201,
   "se_hc1": 0.0128,
   "p_hc1": 0.116,
   "p_firm": 0.117
  },
  "log_bm": {
   "coef": 0.0407,
   "se_hc1": 0.0179,
   "p_hc1": 0.023,
   "p_firm": 0.029
  },
  "mom6": {
   "coef": -0.021,
   "se_hc1": 0.0321,
   "p_hc1": 0.513,
   "p_firm": 0.507
  },
  "kosdaq": {
   "coef": 0.0336,
   "se_hc1": 0.0327,
   "p_hc1": 0.304,
   "p_firm": 0.306
  },
  "rel_size": {
   "coef": -0.0325,
   "se_hc1": 0.1566,
   "p_hc1": 0.836,
   "p_firm": 0.833
  },
  "surv_lev": {
   "coef": -0.0936,
   "se_hc1": 0.0936,
   "p_hc1": 0.318,
   "p_firm": 0.319
  },
  "relisting": {
   "coef": -0.2245,
   "se_hc1": 0.0971,
   "p_hc1": 0.021,
   "p_firm": 0.024
  }
 },
 "score_on_block_plus_foreign_board": {
  "n": 191,
  "block": {
   "coef": -0.2169,
   "se_hc1": 0.0925,
   "p_hc1": 0.019,
   "p_firm": 0.018
  },
  "foreign": {
   "coef": -0.0764,
   "se_hc1": 0.1574,
   "p_hc1": 0.628,
   "p_firm": 0.608
  },
  "outside_dir_ratio": {
   "coef": 0.0484,
   "se_hc1": 0.1083,
   "p_hc1": 0.655,
   "p_firm": 0.658
  },
  "log_me": {
   "coef": 0.0175,
   "se_hc1": 0.0164,
   "p_hc1": 0.288,
   "p_firm": 0.285
  },
  "log_bm": {
   "coef": -0.0023,
   "se_hc1": 0.0198,
   "p_hc1": 0.906,
   "p_firm": 0.905
  },
  "mom6": {
   "coef": -0.0343,
   "se_hc1": 0.0349,
   "p_hc1": 0.326,
   "p_firm": 0.336
  },
  "kosdaq": {
   "coef": -0.0507,
   "se_hc1": 0.0405,
   "p_hc1": 0.211,
   "p_firm": 0.221
  },
  "rel_size": {
   "coef": -0.3462,
   "se_hc1": 0.148,
   "p_hc1": 0.019,
   "p_firm": 0.021
  },
  "surv_lev": {
   "coef": 0.2034,
   "se_hc1": 0.0817,
   "p_hc1": 0.013,
   "p_firm": 0.016
  }
 },
 "rank_on_block_plus_foreign_board": {
  "n": 190,
  "block": {
   "coef": 0.0451,
   "se_hc1": 0.1551,
   "p_hc1": 0.771,
   "p_firm": 0.776
  },
  "foreign": {
   "coef": 0.1082,
   "se_hc1": 0.2516,
   "p_hc1": 0.667,
   "p_firm": 0.713
  },
  "outside_dir_ratio": {
   "coef": -0.0614,
   "se_hc1": 0.1605,
   "p_hc1": 0.702,
   "p_firm": 0.708
  },
  "log_me": {
   "coef": 0.0178,
   "se_hc1": 0.026,
   "p_hc1": 0.494,
   "p_firm": 0.527
  },
  "log_bm": {
   "coef": 0.0419,
   "se_hc1": 0.0308,
   "p_hc1": 0.174,
   "p_firm": 0.206
  },
  "mom6": {
   "coef": 0.0158,
   "se_hc1": 0.0641,
   "p_hc1": 0.806,
   "p_firm": 0.809
  },
  "kosdaq": {
   "coef": 0.0308,
   "se_hc1": 0.0606,
   "p_hc1": 0.611,
   "p_firm": 0.624
  },
  "rel_size": {
   "coef": 0.1989,
   "se_hc1": 0.2122,
   "p_hc1": 0.349,
   "p_firm": 0.347
  },
  "surv_lev": {
   "coef": 0.0511,
   "se_hc1": 0.1267,
   "p_hc1": 0.687,
   "p_firm": 0.683
  }
 }
}

## Expectation check

{'foreign_coverage_ge_0.9': True, 'probe_20_of_20': True, 'foreign_median_in_[2,12]': True, 'board_median_in_[0.2,0.5]': True, 'rank_S_with_controls_in_[-0.28,-0.10]': True}

## Caveats recorded

- Foreign share is KRX's 지분율 (foreign holdings / listed shares) at the last trading day before the announcement; pykrx returns 16-bit-float values (precision ~0.03 pp).
- Outside-director ratio = outside directors among registered executives in the DART 임원 현황 of the prior fiscal year; available for FY2014+ only, so the board-control regressions use the 2015+ announcements; Kang & Lee's board-independence definition is not reproduced.
- Chaebol (대규모기업집단) affiliation is still missing: the KFTC portal lists are not reachable by the tools; the author downloads the designation lists (egroup.go.kr) or supplies a data.go.kr key.
