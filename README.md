# Controlling Owners, Disclosed Intentions, and Minority Shareholder Returns in Korean Captive Spin-Offs

Replication archive for the manuscript of that title (single author). The manuscript was submitted to *Corporate Governance: An International Review* on 31 October 2026 (desk decision 10 November 2026, no external review) and is being prepared, in a substantially extended form, for submission to the *Journal of International Financial Management & Accounting* (`paper/tex_jifma/`; see "Version 2" below).
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24136702.svg)](https://doi.org/10.5281/zenodo.24136702)

Version DOI (release `v2.0-jifma`, the JIFMA manuscript state): https://doi.org/10.5281/zenodo.24136702. CGIR submission state: `v1.2-submission`, https://doi.org/10.5281/zenodo.23890412. Previous version: `v1.1-submission`, https://doi.org/10.5281/zenodo.23721406. Concept DOI (resolves to the latest version): https://doi.org/10.5281/zenodo.23660635.

## What is here

| Folder | Content |
|---|---|
| `code/` | The full pipeline, numbered in execution order: `01`–`03b` collect the division filings and texts (DART Open API); `04` has two language models read each filing (identified and anonymized conditions); `05`–`07`, `10`, `15` build the financial baseline and the Gate-1 comparison; `08` repeat-run stability; `02`, `02b`, `09a`–`09c`, `12`–`12e` trace the outcome of every carve-out in the parent's later reports (2017–2026 and 2001–2016); `13`, `16`–`19` event-time and calendar-time returns and the controlled regressions; `20`–`21` controlling-block ownership and the governance cross-section; `22` the anonymization check; `23` the 2022 reform comparison; `24` label sensitivity; `make_tables_cgir.py` generates every table and every number in the manuscript (`paper/tables/*.tex`, `numbers.tex`) from `results/`; `make_bib_from_dois.py` builds the bibliography from Crossref; `numeric_smoke_test.py` and `check_build_cgir.py` are the build checks. |
| `results/` | Every results file the manuscript reads (`*_2026102x.json`), the per-filing language-model judgments (`llm_judge*/`, `ownership_llm/`, `subsidiary_status_llm/`, JSONL with verbatim evidence quotes), and the label-reconciliation outputs. |
| `data/processed/` | Outcome labels per carve-out (`carveout_disposal_tracking_v4.json` for 2017–2026, `carveout_disposal_tracking_2001_2016.json`), the event lists, pre-announcement ownership (`ownership_pre_event_all.json`), the event-level analysis file (`bhar_controls_events_20261025.csv`) and the event-study metadata. |
| `data/raw/` | The two division-filing lists retrieved from DART (structured record 2017–2026; title-filtered list 2001–2016). |
| `data/external/` | Monthly Korean five-factor returns constructed by the author (`factors_monthly_kr_ff5.csv`) with the construction methodology and compliance notes. |
| `paper/` | LaTeX sources of the manuscript and the Supporting Information, the generated tables and figures, and the bibliography. `make_figures_cgir.py` writes the plotted numbers to `results/figure_data_<date>.json`. |
| `literature/` | The literature search records and the anchor numbers transcribed from Kang & Lee (2025) with their table/footnote sources. |


## Version 2 (JIFMA manuscript, November 2026)

The JIFMA version keeps every result of the CGIR submission and adds the design battery and the measurement audit written after the CGIR desk decision:

| Script | Adds | Results file |
|---|---|---|
| `25_pull_compustat_global_universe.py`, `26_verify_compustat_global_kr.py` | Compustat Global universe of Korean stocks (one WRDS session) and its verification against DART/KIND (`docs/INTERFACE_CARD_compustat_global_kr.md`) | `compustat_global_kr_verification_20261110.json` |
| `27_nested_models_signal_decomposition.py` | nested models M0–M3 (financials, purpose categories, mention flags, signal), keyword ladder, decomposition of the signal | `nested_models_20261110.json` |
| `28_cox_time_to_disposal.py` | Cox model of time to first disposal with period strata; Kaplan–Meier by signal tercile | `cox_time_to_disposal_20261110.json` |
| `29_industry_fe_firm_clusters.py` | year + GICS/SIC fixed effects, parent- and two-way-clustered inference | `industry_fe_firm_clusters_20261110.json` |
| `30_universe_panel.py`, `31_matched_benchmark_and_selection.py` | 5×5 / 3×3 size–B/M portfolios, matched firm, propensity-matched control; firm-year selection logit | `universe_build_20261110.json`, `matched_benchmark_selection_20261113.json` (early-vs-never comparator = retained only, corrected 2026-11-13; supersedes `_20261110` |
| `32_equity_did_appraisal_put.py` | captive × post-2022 DiD against equity spin-offs (post main effect added 2026-11-13; winsorised and median variants 2026-11-14); appraisal-price put tests | `equity_did_appraisal_put_20261114.json` (superseding `_20261110`, `_20261113`) |
| `33_protection_block_covenants.py` | classification of the mandatory shareholder-protection block | `protection_block_20261110.json` |
| `34_governance_controls_foreign_board.py` | foreign ownership (KRX) and outside-director ratio (DART) as controls | `governance_controls_20261110.json` |
| `35_coder_sample_and_codebook.py` | human-coder sample and codebook (prepared; coding deferred) | `data/coding/` |
| `36_measurement_validity_bias_audit.py` | subgroup AUC/calibration, anonymisation, residual bias, two-model agreement, Kang & Lee benchmark | `validity_bias_audit_20261111.json` |
| `make_tables_jifma.py`, `make_figures_jifma.py`, `build_submission_package_jifma.py` | tables, figures and the ScholarOne package for `paper/tex_jifma/` | `paper/tables/`, `paper/figures/` |

Reproduce the JIFMA tables: `python code/make_tables_jifma.py` (runs `make_tables_cgir.py` first), then `TEXDIR=paper/tex_jifma TABLEGEN=make_tables_jifma.py python code/numeric_smoke_test.py`, then compile `paper/tex_jifma/main.tex` and `supplement.tex`. The Compustat Global universe files (`data/processed/universe_*.parquet`, `benchmark_portfolios_*.parquet`) are not redistributed; `30_universe_panel.py` rebuilds them from `data/raw/compustat_global_kr/`, which `25_pull_compustat_global_universe.py` pulls from WRDS under the user's subscription.

## What is not here, and how to obtain it

* **Daily prices.** Korea Exchange adjusted prices (2017–2026) are downloaded by `13_event_study_car.py` through `pykrx`; Compustat Global daily security data (2001–2016) and the month-end market-value/book-value extract used for the controls are licensed through WRDS and are not redistributed. `17_price_panel_compustat.py` rebuilds the panel from a WRDS account (table names and filters are in the script).
* **Filing texts and annual reports.** Public DART documents, re-downloadable with `03_fetch_disclosure_text.py`, `09a_annual_report_subsidiary_passages.py` and `12_collect_division_filings_2001_2016.py` (a free DART Open API key is required).
* **Credentials.** The scripts read API keys from an `api_keys.ini` outside the repository (`[dart]`, `[wrds]`); set the path at the top of each script. Language-model calls use Amazon Bedrock model identifiers recorded in `04_llm_judge.py`; the judgments actually used are archived in `results/`, so the manuscript can be regenerated without any model call.

## Reproducing the manuscript tables

```
python code/make_tables_cgir.py      # results/*.json -> paper/tables/*.tex and numbers.tex
python code/numeric_smoke_test.py    # regeneration identical, every macro defined, headline values in the PDF, no typed statistics
cd paper/tex && pdflatex main && bibtex main && pdflatex main && pdflatex main
```

## Releases

* `v1.0-results` — the code and results files that produced every estimate in the submitted manuscript.
* `v1.0-submission` — first submission-state release (DOI 10.5281/zenodo.23660636).
* `v1.1-submission` — the state uploaded on 31 October 2026 (DOI 10.5281/zenodo.23721406; superseded by `v1.2-submission` after the editorial-office correction). Change to results code since v1.0: `16_bhar_by_predicted_disposal.py` builds the calendar-time portfolios from the same full-one-year-window event set as the event-time tests (previously delisted parents' partial windows entered the daily portfolio, and one Compustat adjustment artefact on 2013-09-11 moved the all-carve-out calendar-time mean from about -7% to +25% a year); `18_bhar_pooled.py` re-run → `results/bhar_predicted_disposal_pooled_20261028.json`. Adds `make_figures_cgir.py` and `paper/figures/`.

* `v1.2-submission` — the corrected submission state (DOI 10.5281/zenodo.23890412; CGIR editorial office, 2 November 2026, manuscript CORG-26-01588 returned to draft: "remove Data availability statement from your main document"). The anonymous main document no longer carries the data availability statement (it is on the title page and in the submission form; `main.tex` inputs `sec7_availability.tex` only in the author copy). Also since v1.1: the Figure 1 conceptual-framework layout in `make_figures_cgir.py` (box geometry and arrow routing only; the figure has no data), and the package builder (flat LaTeX bundle with the figure files, standalone compile test, a build failure if the anonymous PDF contains a data availability statement, fixed cover-letter date). No change to results code, results files, tables or numbers since v1.1; `results/figure_data_20261028.json` differs only in its generation timestamp.
* `v2.0-jifma` — the JIFMA manuscript state, 11 November 2026 (DOI 10.5281/zenodo.24136702): design battery (code 25–34), validity and bias audit (36), `paper/tex_jifma/` sources and package builder.
* `v2.1-jifma` — after cross-review round 1–2 (13–14 November 2026): `31` early-vs-never comparator corrected to retained-only, `32` DiD with the post main effect plus winsorised/median variants, two-model reading count 718 (parsed probabilities from both models), reform table Panel B with multi-label categories and the strength index, short-form definitions table in the main text, manuscript revisions. DOI: see the badge once minted.

## Licence and citation

Code: MIT License (see `LICENSE`). Results files and generated tables: CC BY 4.0. See `CITATION.cff`.
