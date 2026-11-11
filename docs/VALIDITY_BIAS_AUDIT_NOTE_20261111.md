# Measurement validity and bias audit — 20261111

Source: `results/validity_bias_audit_20261111.json` (`code/36`). Sample: Gate-1 n=579 (identity AUC 0.761).

## A. Discrimination and calibration by subgroup
| grouping | level | n | AUC [95% CI] | mean S | mean y | gap | Brier |
|---|---|---|---|---|---|---|---|
| period | 2001-08 | 161 | 0.639 [0.533, 0.743] | 0.54 | 0.77 | -0.23 | 0.22 |
| period | 2009-16 | 178 | 0.751 [0.661, 0.834] | 0.497 | 0.719 | -0.222 | 0.224 |
| period | 2017+ | 240 | 0.813 [0.76, 0.865] | 0.526 | 0.621 | -0.095 | 0.184 |
| kosdaq | KOSDAQ | 200 | 0.767 [0.693, 0.836] | 0.504 | 0.73 | -0.226 | 0.219 |
| kosdaq | KOSPI/other | 379 | 0.762 [0.709, 0.811] | 0.531 | 0.673 | -0.142 | 0.2 |
| listed_parent | listed | 476 | 0.785 [0.741, 0.827] | 0.527 | 0.695 | -0.169 | 0.2 |
| listed_parent | unlisted | 103 | 0.658 [0.539, 0.779] | 0.496 | 0.68 | -0.183 | 0.238 |
| parent_size_filing_2009plus | large | 112 | 0.823 [0.74, 0.898] | 0.575 | 0.607 | -0.032 | 0.167 |
| parent_size_filing_2009plus | mid | 112 | 0.846 [0.776, 0.914] | 0.48 | 0.536 | -0.056 | 0.181 |
| parent_size_filing_2009plus | small | 112 | 0.631 [0.484, 0.765] | 0.533 | 0.804 | -0.271 | 0.232 |
| market_cap_listed | large | 158 | 0.816 [0.752, 0.88] | 0.54 | 0.595 | -0.055 | 0.177 |
| market_cap_listed | mid | 157 | 0.753 [0.665, 0.831] | 0.51 | 0.675 | -0.165 | 0.211 |
| market_cap_listed | small | 158 | 0.764 [0.669, 0.85] | 0.53 | 0.816 | -0.287 | 0.213 |
| newco_size | large | 111 | 0.879 [0.812, 0.935] | 0.547 | 0.586 | -0.039 | 0.148 |
| newco_size | mid | 111 | 0.757 [0.657, 0.844] | 0.53 | 0.649 | -0.119 | 0.206 |
| newco_size | small | 111 | 0.702 [0.582, 0.815] | 0.523 | 0.739 | -0.216 | 0.225 |
| relative_size | high | 109 | 0.809 [0.719, 0.887] | 0.494 | 0.606 | -0.111 | 0.191 |
| relative_size | low | 109 | 0.738 [0.639, 0.827] | 0.532 | 0.661 | -0.129 | 0.208 |
| relative_size | mid | 109 | 0.806 [0.712, 0.89] | 0.569 | 0.688 | -0.119 | 0.181 |
| text_length | long | 193 | 0.764 [0.699, 0.824] | 0.531 | 0.622 | -0.091 | 0.197 |
| text_length | mid | 193 | 0.804 [0.729, 0.87] | 0.506 | 0.705 | -0.199 | 0.205 |
| text_length | short | 193 | 0.691 [0.602, 0.78] | 0.526 | 0.751 | -0.225 | 0.218 |
| label_source | annual_report_llm | 485 | 0.759 [0.713, 0.803] | 0.52 | 0.67 | -0.15 | 0.205 |
| label_source | v3_tracker | 90 | 0.809 [0.701, 0.906] | 0.537 | 0.844 | -0.307 | 0.217 |
| foreign_ownership_listed | high | 154 | 0.832 [0.767, 0.89] | 0.52 | 0.63 | -0.109 | 0.18 |
| foreign_ownership_listed | low | 153 | 0.642 [0.531, 0.748] | 0.55 | 0.791 | -0.24 | 0.218 |
| foreign_ownership_listed | mid | 153 | 0.79 [0.707, 0.865] | 0.511 | 0.68 | -0.169 | 0.205 |
| gics_sector | 15 | 58 | 0.803 [0.675, 0.909] | 0.522 | 0.603 | -0.082 | 0.183 |
| gics_sector | 20 | 84 | 0.735 [0.62, 0.842] | 0.514 | 0.667 | -0.153 | 0.215 |
| gics_sector | 25 | 82 | 0.827 [0.723, 0.914] | 0.536 | 0.634 | -0.099 | 0.185 |
| gics_sector | 35 | 37 | 0.815 [0.638, 0.955] | 0.536 | 0.703 | -0.166 | 0.201 |
| gics_sector | 45 | 113 | 0.639 [0.519, 0.757] | 0.542 | 0.796 | -0.255 | 0.225 |
| gics_sector | 50 | 50 | 0.923 [0.829, 0.988] | 0.548 | 0.74 | -0.192 | 0.161 |
| gics_sector | other/small | 155 | 0.731 [0.64, 0.813] | 0.49 | 0.677 | -0.187 | 0.224 |

| grouping | max−min AUC | LR calibration (group dummies) p | LR discrimination (interaction) p |
|---|---|---|---|
| period | 0.174 | 0.0097 | 0.425 |
| kosdaq | 0.005 | 0.0603 | 0.2178 |
| listed_parent | 0.127 | 0.6595 | 0.0149 |
| parent_size_filing_2009plus | 0.215 | 0.0003 | 0.0255 |
| market_cap_listed | 0.063 | 0.0003 | 0.5136 |
| newco_size | 0.177 | 0.0402 | 0.3969 |
| relative_size | 0.071 | 0.9207 | 0.253 |
| text_length | 0.113 | 0.0254 | 0.3323 |
| label_source | 0.05 | 0.0001 | 0.7063 |
| foreign_ownership_listed | 0.19 | 0.1976 | 0.2449 |
| gics_sector | 0.284 | 0.1752 | 0.0682 |

Overall calibration: mean S 0.521 vs mean y 0.693 (gap -0.171); recalibration intercept 0.926, slope 1.456; Brier 0.207.
By period: 2001-08: gap -0.23, slope 1.078, intercept 1.127; 2009-16: gap -0.222, slope 1.364, intercept 1.192; 2017+: gap -0.095, slope 1.652, intercept 0.613

## B. Identified vs name-anonymized judgments
Overall (n=579): AUC identified 0.758 vs anonymized 0.751, dAUC 0.007 [-0.007, 0.021].
By model: claude: 0.77 vs 0.763 (d 0.007 [-0.016, 0.029]); gpt: 0.734 vs 0.729 (d 0.004 [-0.01, 0.018])
Mean shift identified − anonymized: claude +0.006, gpt +0.004; correlation: claude 0.926, gpt 0.963

| grouping | level | n | AUC id | AUC anon | dAUC [95% CI] |
|---|---|---|---|---|---|
| period | 2001-08 | 161 | 0.639 | 0.645 | -0.006 [-0.038, 0.027] |
| period | 2009-16 | 178 | 0.751 | 0.729 | 0.021 [-0.014, 0.06] |
| period | 2017+ | 240 | 0.805 | 0.804 | 0.001 [-0.017, 0.018] |
| listed_parent | listed | 476 | 0.784 | 0.777 | 0.007 [-0.01, 0.024] |
| listed_parent | unlisted | 103 | 0.651 | 0.645 | 0.005 [-0.021, 0.034] |
| kosdaq | KOSDAQ | 200 | 0.763 | 0.741 | 0.022 [-0.009, 0.055] |
| kosdaq | KOSPI/other | 379 | 0.761 | 0.76 | 0.001 [-0.015, 0.017] |
| parent_size_filing_2009plus | large | 112 | 0.823 | 0.823 | 0.001 [-0.021, 0.022] |
| parent_size_filing_2009plus | mid | 112 | 0.836 | 0.843 | -0.006 [-0.036, 0.022] |
| parent_size_filing_2009plus | small | 112 | 0.614 | 0.599 | 0.014 [-0.023, 0.063] |
| market_cap_listed | large | 158 | 0.817 | 0.807 | 0.01 [-0.016, 0.035] |
| market_cap_listed | mid | 157 | 0.754 | 0.763 | -0.01 [-0.042, 0.02] |
| market_cap_listed | small | 158 | 0.76 | 0.743 | 0.018 [-0.022, 0.063] |
| newco_size | large | 111 | 0.879 | 0.886 | -0.008 [-0.03, 0.011] |
| newco_size | mid | 111 | 0.745 | 0.729 | 0.016 [-0.016, 0.052] |
| newco_size | small | 111 | 0.692 | 0.671 | 0.021 [-0.018, 0.063] |
| text_length | long | 193 | 0.758 | 0.768 | -0.01 [-0.028, 0.008] |
| text_length | mid | 193 | 0.795 | 0.785 | 0.01 [-0.016, 0.039] |
| text_length | short | 193 | 0.692 | 0.681 | 0.011 [-0.023, 0.048] |

Self-reported outside knowledge (share of judgments): claude_id 0.418 (2017+: 0.397, 2001-08: 0.398); claude_an 0.517 (2017+: 0.534, 2001-08: 0.46); gpt_id 0.038 (2017+: 0.037, 2001-08: 0.012); gpt_an 0.033 (2017+: 0.021, 2001-08: 0.025)
Inside the self-reported subset (identified vs anonymized, same filings): claude_reported_outside: n 239, 0.784 vs 0.78 (d 0.003 [-0.035, 0.038]); claude_no_outside: n 334, 0.761 vs 0.749 (d 0.012 [-0.019, 0.04]); gpt_no_outside: n 557, 0.73 vs 0.725 (d 0.005 [-0.009, 0.02])

## C. Residual bias (standardised OLS, HC1)
Stage 1: logit(S) on majority-vote facts + log text + period: n 579, R² 0.529.

| sample | spec | log size | KOSDAQ | listed/foreign | relative size | y |
|---|---|---|---|---|---|---|
| all filings | residual, no y (n 327) | +0.090 (p 0.276) | -0.052 (p 0.339) | +0.017 (p 0.819) | -0.136 (p 0.019) | — |
| all filings | residual, with y (n 327) | +0.128 (p 0.107) | -0.052 (p 0.322) | +0.038 (p 0.597) | -0.093 (p 0.071) | +0.359 (p 0.0) |
| listed parents | residual, no y (n 261) | +0.131 (p 0.148) | -0.055 (p 0.322) | +0.048 (p 0.668) | -0.125 (p 0.075) | — |
| listed parents | residual, with y (n 261) | +0.166 (p 0.05) | -0.066 (p 0.211) | +0.064 (p 0.536) | -0.100 (p 0.088) | +0.406 (p 0.0) |
| all filings | error S−y (n 327) | +0.148 (p 0.005) | -0.051 (p 0.417) | +0.090 (p 0.136) | +0.065 (p 0.241) | — |
| listed parents | error S−y (n 261) | +0.188 (p 0.039) | -0.091 (p 0.189) | -0.006 (p 0.944) | +0.028 (p 0.633) | — |

## D. Two-model agreement on extracted facts (identified, run 1)
Common filings: 715; p_disposal Pearson 0.804 (2017+: 0.867), Spearman 0.819; means Claude 0.592 / GPT 0.458.

| field | n | prev. Claude | prev. GPT | agreement | κ |
|---|---|---|---|---|---|
| purp_specialization | 715 | 0.983 | 0.976 | 0.985 | 0.613 |
| purp_efficiency | 715 | 0.962 | 0.955 | 0.987 | 0.841 |
| purp_sale_or_disposal | 715 | 0.095 | 0.084 | 0.983 | 0.897 |
| purp_fundraising_or_investment_attraction | 715 | 0.176 | 0.159 | 0.978 | 0.92 |
| purp_holding_company_or_group_restructuring | 715 | 0.169 | 0.138 | 0.958 | 0.839 |
| purp_regulatory_or_legal | 715 | 0.036 | 0.039 | 0.989 | 0.846 |
| purp_other | 715 | 0.22 | 0.076 | 0.825 | 0.333 |
| mentions_listing_or_ipo | 715 | 0.078 | 0.938 | 0.14 | 0.011 |
| mentions_external_investment_or_strategic_investor | 715 | 0.138 | 0.259 | 0.824 | 0.459 |
| mentions_sale_or_buyer | 715 | 0.102 | 0.124 | 0.964 | 0.819 |
| mentions_shareholder_protection_measures | 715 | 0.062 | 0.319 | 0.74 | 0.238 |
| appraisal_rights_mentioned | 715 | 0.68 | 0.776 | 0.903 | 0.759 |

Most-likely path: agreement 0.516, κ 0.34; retain-vs-not agreement 0.548. Claude {'sale_to_third_party': 342, 'retain': 167, 'partial_stake_sale_or_investor': 100, 'intragroup_transfer_or_merger': 92, 'ipo': 14}; GPT {'retain': 484, 'sale_to_third_party': 136, 'partial_stake_sale_or_investor': 65, 'intragroup_transfer_or_merger': 27, 'ipo': 3}.
Within-model identified vs anonymized fact agreement: claude: p corr 0.919, facts min 0.858 / median 0.985; gpt: p corr 0.965, facts min 0.881 / median 0.994

## E. Kang & Lee (2025b, FRL) Table 1 benchmark
K&L n=525 listed parents 2001–2021 (literature/KangLee2025_FRL_fulltext.txt lines 229-235 (Table 1 Panel A), sample lines 151-156; read 2026-11-10).

| category | K&L hand-coded | ours strict (listed 2001–21, n 517) | ours broad (fundraising→sale) |
|---|---|---|---|
| Purpose: sale | 0.12 | 0.085 | 0.224 |
| Purpose: efficiency | 0.059 | 0.969 | 0.969 |
| Purpose: specialization | 0.891 | 0.994 | 0.994 |
| Purpose: other | 0.042 | 0.52 | 0.391 |
| Subsidiary listed | 0.04 | 0.039 (Gate-1 listed 2001–21, n 412) | |
| Subsidiary retained | 0.307 | 0.26 (retained_100; upper bound incl. partial sale 0.403) | |

Raw 7-category shares (listed 2001–21): specialization 0.994, efficiency 0.969, sale_or_disposal 0.085, fundraising_or_investment_attraction 0.182, holding_company_or_group_restructuring 0.145, regulatory_or_legal 0.041, other 0.248
Mention flags (listed 2001–21): mentions_listing_or_ipo 0.977, mentions_external_investment_or_strategic_investor 0.286, mentions_sale_or_buyer 0.12, mentions_shareholder_protection_measures 0.261, appraisal_rights_mentioned 0.756

## Expectation check
```
{
 "identity_pass": true,
 "two_model_corr_2017plus_in_0.83_0.87": true,
 "all_subgroup_auc_in_[0.62,0.86]": false,
 "min_subgroup_auc": 0.631,
 "max_subgroup_auc": 0.923,
 "max_spread_within_grouping_le_0.15": false,
 "gap_2001_16_in_[-0.30,-0.10]": true,
 "gap_2017plus_in_[-0.05,0.12]": false,
 "recal_slope_in_[0.6,1.6]": true,
 "dauc_overall_in_[-0.03,0.04]": true,
 "dauc_all_subgroups_abs_le_0.06": true,
 "claude_outside_rate_2017plus_in_[0.35,0.60]": true,
 "gpt_outside_rate_2017plus_le_0.10": true,
 "residual_bias_all_abs_le_0.25": true,
 "mention_kappa_in_[0.35,0.90]": false,
 "purpose_kappa_in_[0.25,0.85]": false,
 "path_agreement_in_[0.45,0.80]": true,
 "path_kappa_in_[0.25,0.60]": true,
 "KL_specialization_within_0.15": true,
 "KL_sale_strict_in_[0.05,0.30]": true,
 "KL_ipo_share_in_[0.02,0.08]": true,
 "KL_retained_in_[0.20,0.40]": true
}
```