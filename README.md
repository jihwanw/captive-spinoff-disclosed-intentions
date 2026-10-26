# Controlling Owners, Disclosed Intentions, and Minority Shareholder Returns in Korean Captive Spin-Offs

Replication archive for the manuscript of that title (single author), submitted to *Corporate Governance: An International Review*.
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23660636.svg)](https://doi.org/10.5281/zenodo.23660636)

Version DOI (release `v1.0-submission`, the submitted state): https://doi.org/10.5281/zenodo.23660636. Concept DOI (resolves to the latest version): https://doi.org/10.5281/zenodo.23660635.

## What is here

| Folder | Content |
|---|---|
| `code/` | The full pipeline, numbered in execution order: `01`–`03b` collect the division filings and texts (DART Open API); `04` has two language models read each filing (identified and anonymized conditions); `05`–`07`, `10`, `15` build the financial baseline and the Gate-1 comparison; `08` repeat-run stability; `02`, `02b`, `09a`–`09c`, `12`–`12e` trace the outcome of every carve-out in the parent's later reports (2017–2026 and 2001–2016); `13`, `16`–`19` event-time and calendar-time returns and the controlled regressions; `20`–`21` controlling-block ownership and the governance cross-section; `22` the anonymization check; `23` the 2022 reform comparison; `24` label sensitivity; `make_tables_cgir.py` generates every table and every number in the manuscript (`paper/tables/*.tex`, `numbers.tex`) from `results/`; `make_bib_from_dois.py` builds the bibliography from Crossref; `numeric_smoke_test.py` and `check_build_cgir.py` are the build checks. |
| `results/` | Every results file the manuscript reads (`*_2026102x.json`), the per-filing language-model judgments (`llm_judge*/`, `ownership_llm/`, `subsidiary_status_llm/`, JSONL with verbatim evidence quotes), and the label-reconciliation outputs. |
| `data/processed/` | Outcome labels per carve-out (`carveout_disposal_tracking_v4.json` for 2017–2026, `carveout_disposal_tracking_2001_2016.json`), the event lists, pre-announcement ownership (`ownership_pre_event_all.json`), the event-level analysis file (`bhar_controls_events_20261025.csv`) and the event-study metadata. |
| `data/raw/` | The two division-filing lists retrieved from DART (structured record 2017–2026; title-filtered list 2001–2016). |
| `data/external/` | Monthly Korean five-factor returns constructed by the author (`factors_monthly_kr_ff5.csv`) with the construction methodology and compliance notes. |
| `paper/` | LaTeX sources of the manuscript and the Supporting Information, the generated tables and the bibliography. |
| `literature/` | The literature search records and the anchor numbers transcribed from Kang & Lee (2025) with their table/footnote sources. |

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
* `v1.0-submission` — the submitted state (DOI 10.5281/zenodo.23660636); results code unchanged from `v1.0-results`. This README's DOI line was added after the release was archived.

## Licence and citation

Code: MIT License (see `LICENSE`). Results files and generated tables: CC BY 4.0. See `CITATION.cff`.
