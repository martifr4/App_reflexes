# valuer

Personal asset-based value-investing research system. For a US-listed company it estimates
assets minus liabilities line by line, compares that with the market value of the equity, and
gives a BUY / WATCH / PASS verdict with a margin of safety.

Status: the deterministic pipeline (ingestion, point-in-time fact store, valuation, memo,
checker, journal) runs end to end. The LLM agents are not built yet.

## Quick start

```bash
uv venv && uv pip install -e ".[dev]"
```

```bash
export SEC_USER_AGENT="Your Name you@example.com"   # SEC requires a contact string
```

```bash
valuer ingest LECO                     # SEC filings index + XBRL facts -> data/store
valuer prices LECO --source bloomberg  # or: --source csv --csv closes.csv | --source yahoo
valuer value LECO --price-source bloomberg [--as-of 2026-03-01] [--params params/v001]
valuer decide <run_id> pass --note "why"
valuer journal
```

`valuer value` writes `data/runs/<run_id>/` (memo.md, valuation.json, params.json, check.json,
meta.json), runs the checker, and exits non-zero if the checker fails. `VALUER_HOME` moves `data/`.

Price sources: `bloomberg` needs the Terminal running on the same machine and
`uv pip install blpapi`. `csv` takes a file with `date,close` columns. `yahoo` is an unofficial
free fallback with split-adjusted closes.

## Rules the code enforces

- **Code owns every number.** The valuation is a pure function of (fact store, ticker, as-of
  date, price source, parameters). The checker recomputes each saved run and compares.
- **Point in time.** Facts carry the filing they came from and its filing date. A run as of date
  D sees only filings with `filed <= D`; a restatement replaces the original only from the day
  it was filed. Stored prices are never overwritten.
- **Every assumption is a named parameter** in `params/<version>/params.yaml`, as low / base /
  high. The loader rejects unknown or missing names. Each run records the version, a hash of
  the resolved values, and a full copy.
- **Lines add up.** Asset and liability lines always sum to the reported totals; whatever is
  not mapped sits in a residual line. Mapping a concept twice fails the run.
- **The memo is checked.** Every number, date and identifier in a memo must trace to the
  valuation, the parameters or the store. One stray figure fails the run, and a decision can
  only be recorded on a run that passed.

## Method in brief

Two equity values, each low / base / high (all assumptions conservative together in low):

- **Liquidation value** = tangible assets at sale haircuts - liabilities - tax on liquidation gains.
- **Reproduction value** = tangible assets at rebuild cost + intangibles - liabilities.

Goodwill and book intangibles are set to zero and replaced by three estimates that are shown
side by side and never averaged: capitalised investment, replacement cost, relief from royalty.
`intangible.selection` names which one enters each scenario.

Verdict: BUY if market cap <= (1 - margin of safety) x base reproduction value and
<= low liquidation value; WATCH if <= base reproduction value; otherwise PASS.

## Layout

```
params/v001/params.yaml       assumptions (copy to v002 to change; never edit a used version)
src/valuer/edgar/             SEC client and JSON -> fact rows
src/valuer/store/             Parquet + DuckDB point-in-time store
src/valuer/mapping/           XBRL concept -> line item (line_items.yaml)
src/valuer/valuation/         assets, intangibles, liabilities, engine (decision, sensitivity)
src/valuer/market/            price sources
src/valuer/memo/              memo renderer and checker
src/valuer/journal.py         run archive and decision journal
tests/                        offline tests on recorded Lincoln Electric data
```

## Known limits

- Facts come from the SEC companyfacts API, which has no dimensional data. Missing as a
  result: fair-value levels of securities, option and award tables (dilution uses the company's
  reported figure), pension obligations where only reported by plan, convertibles. Each run
  lists what it could not measure under "Gaps".
- Flows (R&D, SG&A, revenue) use the last full fiscal year, not trailing twelve months.
- US domestic filers (10-K / 10-Q) reporting in USD only. Financial companies are refused.
- Parameter values in v001 are draft judgments, not calibrated.
