# valuer

Personal asset-based value-investing research system. For a US-listed company it estimates
assets minus liabilities line by line, compares that with the market value of the equity, and
gives a BUY / WATCH / PASS verdict with a margin of safety.

Status: runs end to end. The deterministic pipeline values a company from its XBRL data, three
Claude agents fill gaps from the filing text and attack the result, and a checker reconciles
the memo against the store and the raw filings. See `examples/LECO-agent-run/` for a real run.

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
valuer value LECO --price-source bloomberg [--as-of 2026-03-01] [--params params/v001]   # code only
valuer analyse LECO --price-source bloomberg [--model claude-opus-5-5]                  # with agents
valuer decide <run_id> pass --note "why"
valuer journal
```

`valuer value` writes `data/runs/<run_id>/` (memo.md, valuation.json, params.json, check.json,
meta.json), runs the checker, and exits non-zero if the checker fails. `VALUER_HOME` moves `data/`.

Price sources: `bloomberg` needs the Terminal running on the same machine and
`uv pip install blpapi`. `csv` takes a file with `date,close` columns. `yahoo` is an unofficial
free fallback with split-adjusted closes.

`valuer analyse` needs Claude Code credentials (`ANTHROPIC_API_KEY`, or a logged-in Claude
Code) because it runs agents through the Claude Agent SDK. A run costs roughly one dollar.

## Where the data comes from

Everything is fetched from SEC EDGAR's public endpoints, with the `SEC_USER_AGENT` header
SEC requires and at most five requests per second:

| What | URL | Used for |
|---|---|---|
| Ticker to CIK map | `https://www.sec.gov/files/company_tickers.json` | finding the company's SEC id |
| Filing index and profile | `https://data.sec.gov/submissions/CIK##########.json` | SIC code (financials are refused), list of 10-K and 10-Q filings with filing dates |
| XBRL company facts | `https://data.sec.gov/api/xbrl/companyfacts/CIK##########.json` | every tagged figure the company has filed; this is the fact store |
| Filing documents | `https://www.sec.gov/Archives/edgar/data/<cik>/<accession>/<doc>.htm` | the latest 10-K and later 10-Qs, which the agents read |

Prices come from the source you pick (`bloomberg`, `csv` or `yahoo`).

## Raw files: one folder per company

Every downloaded document is kept unchanged under `data/raw/<TICKER>/` so you can open
what the system used:

```
data/raw/LECO/
  SOURCES.md          index: each file, what it is, source URL, fetch time, SHA-256
  manifest.json       the same, machine-readable
  sec/                submissions.<date>.json, companyfacts.<date>.json
  filings/<accession>/<name>.htm   the filing exactly as filed
  filings/<accession>/<name>.txt   plain text made from it by code; line N = paragraph N
  prices/<source>.csv the closes stored from that source
```

Memo quotes cite `LECO/filings/<accession>/<name>.txt:<line>`; open that file at that line to
see the passage. The `.htm` beside it is the original. Each run also saves `sources.json` with
the hash of every filing it used, and the checker fails if a file has changed since.

## Agents

`valuer analyse` runs three agents (Claude Agent SDK, no built-in tools: no shell, files or web).
Their only tools are read-only functions over the current filings' text and the fact store.

1. The engine values the company from XBRL facts and lists what it could not measure.
2. An **asset analyst** and a **liabilities analyst** read the filings in parallel. They return
   figures the XBRL data lacks (options, unvested awards, pension obligation, reasonably
   possible losses, guarantees, purchase obligations) and observations, each with a quote.
3. Code verifies every item: the quote must be in the cited paragraph verbatim, the figure
   must be inside the quote, its scale needs its own quote, the size must be plausible, and
   the agent's own words must contain no digits. Accepted figures become tier-2 facts in the
   store; rejected items are kept in `findings.json` with the reason.
4. The engine values the company again with the tier-2 facts.
5. A **bear-case agent**, which never sees the analysts' work, attacks the result with
   cited claims and may propose parameter changes. Code applies the accepted changes and
   reruns the engine as a bear scenario. Decision rules cannot be overridden.

Agents never produce a number that reaches the valuation. The memo shows their statements as
opinion, and every quote in it is checked against the raw filing.

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
src/valuer/agents/            agent tools, prompts, output schemas, verification, pipeline
src/valuer/raw.py             per-company raw document archive
src/valuer/journal.py         run archive and decision journal
tests/                        offline tests on recorded Lincoln Electric data
```

## Known limits

- Facts come from the SEC companyfacts API, which has no dimensional data. The agents fill
  some of the holes from the filing text; still missing: fair-value levels of securities and
  convertibles. Each run lists what it could not measure under "Gaps".
- An agent's "not disclosed" is recorded but cannot be verified by code; the memo says so.
- Tier-2 facts are bitemporal: a run records the moment it learned them, so re-running an
  old as-of date gives the same answer as before.
- Flows (R&D, SG&A, revenue) use the last full fiscal year, not trailing twelve months.
- US domestic filers (10-K / 10-Q) reporting in USD only. Financial companies are refused.
- Parameter values in v001 are draft judgments, not calibrated.
