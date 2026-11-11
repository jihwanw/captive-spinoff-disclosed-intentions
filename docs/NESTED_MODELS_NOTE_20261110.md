# Nested models — does the signal add to Kang & Lee-type coding? (20261110)

Source: `results/nested_models_20261110.json`, produced by `code/27_nested_models_signal_decomposition.py`. Sample = the Gate-1 pooled sample rebuilt from `15_gate1_pooled.py` (identity control: n 579, AUC(S) 0.761, financial 0.587 — pass True).

## Ladder (repeated 5-fold CV, 50 repeats; AUC of repeat-averaged out-of-fold predictions)

| Model | features | CV AUC | Brier |
|---|---|---|---|
| M0_financial | 14 | 0.587 | 0.209 |
| M1_plus_purpose | 21 | 0.667 | 0.200 |
| M2_plus_mentions | 26 | 0.680 | 0.198 |
| M3_plus_signal | 27 | 0.770 | 0.170 |
| F_facts_only | 12 | 0.611 | 0.205 |
| F2_facts_plus_signal | 13 | 0.767 | 0.172 |
| K1_financial_plus_keywords | 20 | 0.590 | 0.210 |
| K2_keywords_plus_signal | 21 | 0.769 | 0.167 |
| S_signal_only_cv | 1 | 0.758 | 0.172 |

Increments (paired bootstrap, 2,000 resamples):

- M1_plus_purpose-M0_financial: +0.080 [+0.044, +0.115]
- M2_plus_mentions-M1_plus_purpose: +0.013 [-0.014, +0.038]
- M2_plus_mentions-M0_financial: +0.093 [+0.049, +0.133]
- M3_plus_signal-M2_plus_mentions: +0.091 [+0.052, +0.128]
- M3_plus_signal-M0_financial: +0.183 [+0.133, +0.232]
- F2_facts_plus_signal-F_facts_only: +0.156 [+0.107, +0.202]
- K1_financial_plus_keywords-M0_financial: +0.003 [-0.026, +0.028]
- K2_keywords_plus_signal-K1_financial_plus_keywords: +0.180 [+0.132, +0.229]
- M2_plus_mentions-K1_financial_plus_keywords: +0.090 [+0.047, +0.133]

Likelihood-ratio tests (full-sample logistic):

- M1_plus_purpose_vs_M0_financial: LR 35.01 on 7 df, p = 1.11e-05
- M2_plus_mentions_vs_M1_plus_purpose: LR 14.33 on 5 df, p = 1.36e-02
- M3_plus_signal_vs_M2_plus_mentions: LR 88.02 on 1 df, p = 6.49e-21
- K2_keywords_plus_signal_vs_K1_financial_plus_keywords: LR 120.43 on 1 df, p = 5.09e-28
- F2_facts_plus_signal_vs_F_facts_only: LR 95.17 on 1 df, p = 1.75e-22

Facts flagged by a majority of judgments: specialization 0.99, efficiency 0.96, sale_or_disposal 0.09, fundraising_or_investment_attraction 0.17, holding_company_or_group_restructuring 0.17, regulatory_or_legal 0.03, other 0.21, mentions_listing_or_ipo 0.96, mentions_external_investment_or_strategic_investor 0.30, mentions_sale_or_buyer 0.12, mentions_shareholder_protection_measures 0.31, appraisal_rights_mentioned 0.80. Kang & Lee (2025b) Table 1: sale 0.120, efficiency 0.059, specialization 0.891, other 0.042.
Keyword dictionary (no model): {"kw_sale": "매각", "kw_listing": "상장(?!폐지)", "kw_ipo": "IPO|기업공개", "kw_investment": "투자\\s*유치|투자유치|전략적\\s*투자|외부\\s*투자", "kw_efficiency": "효율", "kw_specialization": "전문화"}; hit rates {'kw_sale': 0.176, 'kw_listing': 0.965, 'kw_ipo': 0.007, 'kw_investment': 0.071, 'kw_efficiency': 0.769, 'kw_specialization': 0.563}.

## Label-permutation control (5 seeds)

Mean permuted AUC by model: {'M0_financial': 0.476, 'M2_plus_mentions': 0.498, 'M3_plus_signal': 0.502, 'F_facts_only': 0.51, 'S_raw': 0.507, 'noise10_features_real_labels': 0.521}. The pre-set threshold (max draw ≤ 0.55) was breached by two of 25 draws (0.554, 0.552 — about 2.2 SE at n = 579), so the recorded flag is pass = False; no model's mean exceeds 0.51 and M3's mean is 0.502, which is the opposite of a leakage signature (see `post_hoc_reading_added_after_run` in the JSON).

## Return ladder (within-year rank of the one-year BHAR; 19's spec 3 controls, year FE)

Sample: {'scored_events': 576, 'with_fact_dummies': 576, 'with_keyword_flags': 476}

| Spec | n | coef on S | HC1 p | year-cluster p |
|---|---|---|---|---|
| spec3_as_published | 559 | -0.1950 | 0.004 | 0.000 |
| spec3_plus_purpose | 559 | -0.2845 | 0.001 | 0.002 |
| spec3_plus_purpose_mentions | 559 | -0.2964 | 0.000 | 0.001 |
| spec3_plus_keywords_gate1_filings_only | 469 | -0.2143 | 0.006 | 0.003 |

Fact coefficients in the facts-only rank regression (no signal): d_specialization -0.142 (p 0.24), d_efficiency +0.024 (p 0.71), d_sale_or_disposal -0.082 (p 0.40), d_fundraising_or_investment_attraction +0.069 (p 0.11), d_holding_company_or_group_restructuring +0.036 (p 0.35), d_regulatory_or_legal -0.038 (p 0.59), d_other -0.006 (p 0.85), d_mentions_listing_or_ipo +0.026 (p 0.81), d_mentions_external_investment_or_strategic_investor -0.007 (p 0.86), d_mentions_sale_or_buyer +0.003 (p 0.97), d_mentions_shareholder_protection_measures -0.067 (p 0.05), d_appraisal_rights_mentioned +0.008 (p 0.83)

## Decomposition of S

OLS of S on the 12 fact dummies, log text length and a 2017+ indicator: R² 0.442; AUC of the fitted part 0.675, of the residual 0.722, of S 0.761.

## Expectation check

F_facts_only 0.611 misses the pre-registered floor 0.62 by 0.009 — the flags are nearly constant (specialization 99%, efficiency 97%, listing mentioned 96%), not a pipeline fault (permuted F averages 0.51).

{'M1_in_range': True, 'M2_in_range': True, 'M3_in_range': True, 'M3_not_above_0.80': True, 'F_in_range': False, 'keywords_weaker_than_model_facts': True, 'permutation_pass': False, 'F_floor_0.62_missed_by': True}

## Caveat recorded

The purpose and mention dummies are extracted by the same two models that produce S (identified condition, all runs, majority vote), so M2 vs M3 compares a structured extraction with a holistic probability from the same reader; the keyword ladder (K1/K2) is the model-free comparison. A hand-coded replication of Kang & Lee's purpose dummies on a stratified subsample is the human-coder task of strategy §4-A.
