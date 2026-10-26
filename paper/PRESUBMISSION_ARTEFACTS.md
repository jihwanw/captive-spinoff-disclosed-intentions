# Pre-submission artefacts — Captive spin-offs paper (CGIR)

Manuscript: *Controlling Owners, Disclosed Intentions, and Minority Shareholder Returns in Korean Captive Spin-Offs*
Prepared 2026-10-26 from the results files named in each cell (`results/*_20261025.json` unless stated). Templates: `skills/mechanism_paper_artefacts.md`.
Applicability: (c) a new measure from filings/text (the disposal signal); not (a) first paper on a new episode (Kang & Lee 2025 precede us), not (b) fewer than 30 units (n = 559–758), not (d) appendix model, not (e) channel separation by proxy.

## 1. Identification table (G1, G2, G5)

| Headline coefficient | Table | Source of variation | What absorbs common shocks | Rival story and its prediction | Minimum detectable effect / precision |
|---|---|---|---|---|---|
| Two-model signal AUC 0.761 vs financial baseline 0.587 (Δ 0.174, CI [0.117, 0.235]) | T3 | Cross-sectional: filing text vs stated financials, same events | Not needed (classification, not treatment); temporal split (train ≤2016, test ≥2017) guards against within-period fitting | Model recalls company histories → anonymized condition: 0.706→0.691 (CI of gap includes 0) | Paired bootstrap CI reported |
| Announcement CAR slope on signal +0.037 (p 0.046) | T4, T6 | Cross-sectional across 560 parents | Announcement-year FE; size, B/M, momentum, market, filing controls | Signal proxies for growth purpose → coefficient positive either way; we do not separate "growth story" from "disposal read as good news" (stated as a limit) | HC1 s.e. 0.019 |
| One-year BHAR rank on signal −0.195 (p 0.004; clustered p <0.001) | T6 | Cross-sectional within announcement year | Year FE; parent condition controls (size, B/M, momentum, market), filing characteristics, parent fundamentals (2017+) | Troubled-parent story: filings that read as disposals come from declining parents → controls narrow but do not close it (stated in §6) | s.e. 0.068; equivalent to 19.5 percentiles |
| Early disposal → BHAR −0.151 (p 0.083); signal adds 0.135 (p 0.549) when both enter | T7 | Realized outcome vs signal | Year FE + controls | Reverse: price fall causes disposal? Early disposal is first ownership change within the fiscal year of the division or next; the return window starts at +2 — overlap possible, acknowledged as association | s.e. 0.087 (HC1; `bhar_controls_20261025.json: specs.bhar1y_realized.score_and_early_plus_controls.early.se_hc1` = 0.0873) |
| Signal on block −0.113 (p 0.013; clustered 0.004) | T9 | Cross-sectional ownership, measured at FY-end before the announcement year | Year FE + controls | Small-block controllers run different firms (industries, groups) → no instrument; stated as association (§4.3, §6) | s.e. 0.045 |
| Rank on block +0.142 (p 0.062) | T9 | as above | as above | as above | s.e. 0.076 |
| Reform before/after: protection statements 0.5→95.5%, CAR +0.06→+5.29%, signal 0.528→0.510 (p 0.62), early disposal 40.2→36.8% (p 1.00) | T10 | Time (Oct 2022 cutoff) | None — no untreated group; **not identified** (stated in §4.4, §5.1, §6) | Market-wide changes in 2022–26; selection of which parents still divide (filings/yr 39→16.4) | n post = 44 filings / 49 CARs; outcome n post = 19 |

## 2. Measure-decomposition note (G7, G8)

The disposal signal is a probability forecast; it is not a count that decomposes. Its components are stated in §3.3: two models × (two runs for 2017–26, one run for 2001–16) × identified/anonymized conditions. Bounds reported: between-model correlation 0.87; within-model repeat correlations 0.96 (A) and 0.99 (B) over 245 events; identified–anonymized AUC gap 0.015 (2001–16) with CI [−0.006, 0.039].
The outcome label decomposes as disposed = listed (3.3% of clean labels) + majority sold + diluted below 99.5% (partial sale); 11 of the 2017–26 labels are definition-sensitive (categories in SI Table S1); flipping all 11 to retained strengthens the headline differences (−10.3→−14.6 pp).
Name used for the measure throughout: "disposal signal" / "two-model forecast" — a forecast, never "intention" as a fact (G8).

## 3. Model check (G6)

Not applicable: no appendix model; hypotheses are derived verbally from the principal–principal arithmetic (§2.2) with premise/mechanism/boundary/rival for each. No comparative static is claimed that requires differentiation.

## 4. Rival-narrative test plan (G10)

| Rival narrative | Prediction | Test with public data | Result | Status |
|---|---|---|---|---|
| The model remembers company histories (look-ahead) | Identified AUC ≫ anonymized AUC; recognised filings score better only with names | Anonymized re-run of all filings; AUC by recognition flag (results/anonymized_check) | 0.706 vs 0.691; flagged filings 0.764 vs 0.763 | Tested; rival rejected |
| The filing is boilerplate; financials carry the information | Financial model ≈ text model | Financial logistic baseline, repeated CV; temporal split | 0.587 vs 0.761; 0.611 vs 0.813 | Tested; rival rejected |
| Troubled parents write disposal-like filings and underperform | Signal coefficient vanishes with parent controls | Size, B/M, momentum, market, filing controls, parent ROA/leverage/size (T6) | −0.191 → −0.195; 2017+ with fundamentals −0.207 | Tested; narrowed, not closed (stated) |
| Efficient reading (H3 proper) | Negative announcement slope, no drift | T4 | slope +0.037; drift negative | Tested; rejected in favour of the practitioners' rival |
| Disposal is decided on the subsidiary's merits (efficiency view) | Block unrelated to signal/disposal | T8–T9 | signal on block −0.113 (p 0.013); disposal rate 74 vs 62% | Tested; association against the rival; causal reading not claimed |
| Market-wide change explains the reform result | — | None available (no untreated group) | — | Not testable; design limit stated (§4.4, §6) |
| Low-block parents are a different industry mix | Block effect disappears with industry controls | **Not run** — industry codes not merged for 2001–16 | — | Open; stated as "controllers with small stakes may run different businesses" (§4.3, §6). R1 item. |

## 5. Claim ladder (G2, G3, G12, G14)

| Sentence (abstract / intro / conclusion) | Level | Table | Check |
|---|---|---|---|
| "Their forecast separates subsidiaries later disposed of from those retained (AUC 0.761 against 0.587)" | association (classification accuracy) | T3 | ✓ |
| "survives the masking of all names and dates" | fact | T3 | ✓ (0.706→0.691, CI includes 0) |
| "The announcement return rises with the forecast while the market-adjusted return over the following year falls with it" | association | T4, T6 | ✓ |
| "the loss is realised in parents that dispose within a year and in parents with small controlling blocks" | association | T5, T8 | ✓ |
| "the forecast falls with the block" | association | T9 | ✓ |
| "protection statements rose … the forecast and the early-disposal rate did not change" | fact (before/after), no causal verb | T10 | ✓ ("did not change" within observed horizon; §4.4 states the design limit) |
| "minority investors priced it in the wrong direction" (abstract, implications) | association, interpretive | T4 | ✓ slope +0.037 p 0.046; wording "wrong direction" tied to the sign |
| "Protection should attach to the disposal" (policy) | recommendation | — | evidence grade stated as association in §5.4 and §6 |
| No sentence contradicted by a table | — | — | checked against T3–T10 2026-10-26 |

Nulls: the reform's "did not change" sentences carry n (44 filings; 19 mature outcomes) and the Fisher/Welch p-values; the calendar-time null (t −1.68, −0.96) is reported as "point the same way without reaching conventional significance". No minimum detectable effect is computed for the reform comparison — stated as a small-sample limit rather than a power statement (R1 item: add MDE for the pre/post early-disposal share).

## 6. Proxy validity + direct measure (G11, G13)

Proxy: the disposal signal stands for "what a careful reader could infer about the controller's intention". Validity evidence: (i) predicts the realized disposal out of sample (AUC 0.761; 0.780 for early disposals); (ii) survives anonymization; (iii) stable across models and runs; (iv) three worked filings quoted verbatim (Doosan, CJ ENM/Tving, DB HiTek) show the sentences read. Limit stated (§6): the signal is a document summary, not a list of features.
Direct measure: the realized disposal itself (public annual reports) is used wherever the claim is about outcomes (T5, T7, T8, T10) — the signal is never the only evidence for a loss.

## 7. Antecedent mirroring (G4)

Table 12 (T_mirror) mirrors the eight tests of Kang & Lee (2025): announcement CAR; one-year CAR/BHAR; disposed share; long-run return by disposal; ownership and long-run return; ownership and announcement CAR; ownership and retention; the untested "investors cannot discern" sentence. All eight have a counterpart in our tables; differences in measures are stated in the note.

## 8. Chain (G16)

Theory (principal–principal: small cash-flow stake → private cost of disposal low) → measure (filing read as of its date → disposal forecast; outcome from annual reports; block from largest-shareholder table) → identification (cross-sectional associations with year FE and controls; anonymization against look-ahead; no instrument for the block; no control group for the reform) → claim (associations; the market's sign error at the announcement; disclosure reform changed statements and reception, not forecast or disposals, within horizon). Breaks acknowledged in §6: block endogeneity, troubled-parent alternative, reform design.
