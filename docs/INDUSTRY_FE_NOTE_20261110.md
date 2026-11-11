# Industry fixed effects and firm clusters (20261110)

Source `results/industry_fe_firm_clusters_20261110.json` (`code/29_industry_fe_firm_clusters.py`). Sample: 576 scored return events, 459 parents (events per parent {1: 375, 2: 60, 3: 17, 4: 5, 5: 2}); GICS sectors {'45': 140, '20': 109, '25': 96, '15': 69, '50': 57, '35': 43, '30': 30, '40': 14, '10': 9, '55': 4, 'unknown': 3, '60': 2}; 61 GICS industries; 42 two-digit SIC groups. Industry = parent's current Compustat classification (limitation recorded).

Identity control (year FE + HC1 reproduces 19/Table 6): pass = True.

## Table 6 — returns on the signal (spec 3 controls)

| Outcome | FE | n | k | coef on S | p HC1 | p year-cl | p firm-cl | p two-way |
|---|---|---|---|---|---|---|---|---|
| rank_1y | yearFE_published | 559 | 37 | -0.1950 | 0.004 | 0.0 | 0.003 | 0.0 |
| rank_1y | year+gsector | 559 | 48 | -0.1937 | 0.006 | 0.0 | 0.004 | 0.0 |
| rank_1y | year+gind | 559 | 97 | -0.1670 | 0.025 | 0.001 | 0.015 | 0.001 |
| rank_1y | year+sic2 | 559 | 78 | -0.1527 | 0.031 | 0.002 | 0.02 | 0.002 |
| bhar_1y | yearFE_published | 559 | 37 | -0.1579 | 0.283 | 0.35 | 0.265 | 0.332 |
| bhar_1y | year+gsector | 559 | 48 | -0.1662 | 0.269 | 0.309 | 0.249 | 0.289 |
| bhar_1y | year+gind | 559 | 97 | -0.1976 | 0.204 | 0.165 | 0.172 | 0.143 |
| bhar_1y | year+sic2 | 559 | 78 | -0.0896 | 0.578 | 0.606 | 0.552 | 0.579 |
| carmm_1y | yearFE_published | 559 | 37 | -0.0314 | 0.832 | 0.848 | 0.825 | 0.841 |
| carmm_1y | year+gsector | 559 | 48 | -0.0785 | 0.604 | 0.639 | 0.588 | 0.621 |
| carmm_1y | year+gind | 559 | 97 | -0.1818 | 0.26 | 0.266 | 0.225 | 0.233 |
| carmm_1y | year+sic2 | 559 | 78 | +0.0043 | 0.978 | 0.978 | 0.977 | 0.977 |
| ann_car | yearFE_published | 560 | 37 | +0.0385 | 0.041 | 0.064 | 0.037 | 0.064 |
| ann_car | year+gsector | 560 | 48 | +0.0450 | 0.025 | 0.065 | 0.02 | 0.063 |
| ann_car | year+gind | 560 | 97 | +0.0367 | 0.097 | 0.147 | 0.065 | 0.113 |
| ann_car | year+sic2 | 560 | 78 | +0.0541 | 0.012 | 0.029 | 0.006 | 0.023 |

## Table 7 — realised early disposal (rank_1y)

- yearFE_published: early -0.0756 (firm-cl p 0.014, two-way p 0.026); jointly: early -0.0508 (p 0.141), S -0.1351 (p 0.114)
- year+gsector: early -0.0771 (firm-cl p 0.013, two-way p 0.016); jointly: early -0.0529 (p 0.126), S -0.1321 (p 0.12)
- year+gind: early -0.0920 (firm-cl p 0.003, two-way p 0.002); jointly: early -0.0738 (p 0.036), S -0.1025 (p 0.223)
- year+sic2: early -0.0728 (firm-cl p 0.019, two-way p 0.006); jointly: early -0.0699 (p 0.044), S -0.0164 (p 0.847)

## Table 10 — block regressions

- yearFE_published: S~block -0.118 (firm p 0.009); disposed~block -0.090 (p 0.489); early~block -0.051 (p 0.731); early~block+S: block +0.093, S +1.234; rank~block +0.152 (p 0.05); annCAR~block +0.0341 (p 0.13); rank: early -0.126, low -0.106, early×low +0.102 (p 0.084)
- year+gsector: S~block -0.095 (firm p 0.041); disposed~block -0.036 (p 0.781); early~block +0.001 (p 0.994); early~block+S: block +0.141, S +1.217; rank~block +0.143 (p 0.068); annCAR~block +0.0337 (p 0.149); rank: early -0.132, low -0.107, early×low +0.105 (p 0.076)
- year+gind: S~block -0.101 (firm p 0.042); disposed~block -0.104 (p 0.41); early~block -0.035 (p 0.813); early~block+S: block +0.073, S +1.148; rank~block +0.145 (p 0.086); annCAR~block +0.0389 (p 0.079); rank: early -0.150, low -0.107, early×low +0.111 (p 0.073)
- year+sic2: S~block -0.087 (firm p 0.056); disposed~block -0.025 (p 0.847); early~block +0.022 (p 0.883); early~block+S: block +0.103, S +1.173; rank~block +0.135 (p 0.089); annCAR~block +0.0316 (p 0.161); rank: early -0.147, low -0.112, early×low +0.147 (p 0.015)

## Gate-1 disposal logit with industry dummies (firm-clustered)

- yearFE_published: coef on logit(S) 1.398 (se 0.166, p 3.48e-16), k 16, pseudo-R² 0.215
- year+gsector: coef on logit(S) 1.442 (se 0.175, p 1.82e-15), k 27, pseudo-R² 0.229
- year+gind: coef on logit(S) 1.554 (se 0.197, p 2.12e-14), k 73, pseudo-R² 0.355
- year+sic2: coef on logit(S) 1.393 (se 0.173, p 5.39e-15), k 58, pseudo-R² 0.29
- within-sector ordering: AUC of S 0.761, of sector-demeaned S 0.761; by sector {'10': {'n': 8, 'auc': None}, '15': {'n': 58, 'auc': 0.803}, '20': {'n': 84, 'auc': 0.735}, '25': {'n': 82, 'auc': 0.827}, '30': {'n': 23, 'auc': 0.804}, '35': {'n': 37, 'auc': 0.815}, '40': {'n': 13, 'auc': None}, '45': {'n': 113, 'auc': 0.639}, '50': {'n': 50, 'auc': 0.923}, '55': {'n': 4, 'auc': None}, '60': {'n': 2, 'auc': None}, 'unknown': {'n': 105, 'auc': 0.664}}

## Expectation check

{'identity_pass': True, 'rank_S_sector_in_[-0.28,-0.12]': True, 'rank_S_firm_p<0.05': True, 'rank_S_twoway_p<0.10': True, 'anncar_S_sector_in_[0,0.06]': True, 'table7_early_negative': True, 'block_signs_kept': True, 'gate1_S_change_lt_25pct': True}

## Caveats recorded

- GICS codes are the parent's current classification (g_company header), not at the event date; firms that changed sector are classified by their later sector.
- Two-way clusters use the Cameron–Gelbach–Miller formula with HC0 components and a t(min(G_firm, G_year) − 1) reference; firm clusters use t(G_firm − 1). With 60 GICS industries and 559 events the gind specification spends ~60 degrees of freedom on dummies.
- Three events have no Compustat sector ('unknown' group).
