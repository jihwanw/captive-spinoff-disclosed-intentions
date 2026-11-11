# The mandated shareholder-protection block: what it commits to (20261110)

Source `results/protection_block_20261110.json` (`code/33_protection_block_covenants.py`); per-filing file `data/processed/protection_block_20261110.csv` with the block text.

Coverage: {'captive_filings_2017plus': 294, 'with_text': 293, 'post_reform': 66, 'post_with_block': 61, 'pre_reform': 228, 'pre_with_block': 0}

## Post-reform filings by category (a filing can carry several)

| Category | n | mean S | mean CAR[-1,+1] % | disposed share (labelled n) |
|---|---|---|---|---|
| charter_vote | 7 | 0.5 | 6.69 | 0.333 (6) |
| no_listing_horizon | 3 | 0.343 | -2.26 | 0.0 (1) |
| unlisted_soft | 32 | 0.45 | 5.62 | 0.192 (26) |
| sale_plan | 4 | None | -2.0 | None (0) |
| payout_policy | 3 | 0.618 | 1.48 | 0.667 (3) |
| disclosure_commit | 4 | None | 5.22 | None (0) |
| consult_shareholders | 4 | 0.375 | 0.72 | 0.0 (2) |
| appraisal_only | 3 | 0.833 | 16.99 | 1.0 (2) |
| none | 15 | 0.682 | 5.6 | 0.667 (9) |

Strength index (3 charter vote / 2 horizon / 1 soft or payout / 0 none): {0: 29, 1: 27, 2: 3, 3: 7}; by strength: {"0.0": {"n": 29, "mean_S": 0.658, "mean_car3_pct": 5.94, "n_car": 14, "disposed_share": 0.615, "n_labelled": 13, "early_share": 0.545}, "1.0": {"n": 27, "mean_S": 0.437, "mean_car3_pct": 6.05, "n_car": 21, "disposed_share": 0.174, "n_labelled": 23, "early_share": 0.095}, "2.0": {"n": 3, "mean_S": 0.343, "mean_car3_pct": -2.26, "n_car": 3, "disposed_share": 0.0, "n_labelled": 1, "early_share": 0.0}, "3.0": {"n": 7, "mean_S": 0.5, "mean_car3_pct": 6.69, "n_car": 5, "disposed_share": 0.333, "n_labelled": 6, "early_share": 0.2}}

'향후 회사구조개편' block states no listing within 5 years: 22 filings.

Tests: {"spearman_strength_S": {"rho": -0.272, "p": 0.075, "n": 44}, "sale_plan_vs_rest_S": {"mean_sale_plan": null, "mean_rest": 0.51, "mw_p": null}, "spearman_strength_car3": {"rho": -0.053, "p": 0.733, "n": 43}}

## Expectation check

{'post_blocks_ge_55': True, 'pre_blocks_le_3': True, 'sale_plan_mean_S_gt_0.7': False, 'charter_vote_mean_S_lt_0.4': False}

## Dictionary

```
{
 "charter_vote": "특별결의",
 "no_listing_horizon": "[35]\\s*년[^。]{0,60}?상장[^。]{0,40}?(계획이\\s*없|신청하지\\s*않|신청할\\s*계획)",
 "unlisted_soft": "비상장(을|으로|회사로|법인으로)?\\s*(유지|하여|함으로써)",
 "sale_plan": "매각(을|할)?\\s*(예정|추진)",
 "payout_policy": "배당|자기주식|자사주|주주환원",
 "disclosure_commit": "공시하여|정보\\s*비대칭|IR\\s*활동",
 "consult_shareholders": "주주와의\\s*소통|의견을\\s*폭\\s*넓게",
 "appraisal_only": "주식매수청구권"
}
```

## Caveats recorded

- Categories are regex matches on the block text, designed after reading all 61 post-reform blocks; the per-filing CSV carries the block text so every classification can be checked by eye (and by the human coder of strategy §4-A).
- Realised outcomes for post-reform filings are young (labels to FY2025); disposal shares are not comparable with the pre-reform rate.
- A 'sale plan' in the protection block is a disclosed disposal intention, not a protection measure; it is the clearest example of the block being used to state the controller's intention.
