"""Command line: ingest -> prices -> value (runs the checker) -> decide."""
from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

from . import config
from .journal import Journal
from .memo.checker import check_run
from .memo.render import render_memo, usd_m
from .params import load_params
from .store.store import FactStore


def _date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def cmd_ingest(a) -> int:
    from .edgar.client import EdgarClient
    from .edgar.ingest import ingest

    home = config.home()
    info = ingest(FactStore(home), EdgarClient(home / "raw" / "edgar"), a.ticker.upper())
    print(f"{a.ticker.upper()}: {info['name']} (CIK {info['cik']}, SIC {info['sic']}), {info['facts']:,} facts stored")
    return 0


def cmd_prices(a) -> int:
    from .market import prices

    ticker, end = a.ticker.upper(), a.end or dt.date.today()
    start = a.start or end - dt.timedelta(days=30)
    if a.source == "csv":
        if not a.csv:
            sys.exit("--csv PATH is required with --source csv")
        closes = prices.from_csv(a.csv)
    elif a.source == "bloomberg":
        closes = prices.from_bloomberg(ticker, start, end)
    else:
        closes = prices.from_yahoo(ticker, start, end)
    n = FactStore(config.home()).add_prices(ticker, a.source, closes)
    print(f"{ticker}: {n} new {a.source} closes stored")
    return 0


def cmd_value(a) -> int:
    home = config.home()
    store, journal = FactStore(home), Journal(home)
    ticker, as_of = a.ticker.upper(), a.as_of or dt.date.today()
    entity = store.resolve(ticker)
    params = load_params(a.params, sic=entity.sic, ticker=ticker)

    from .valuation.engine import run_valuation

    v = run_valuation(store, ticker, as_of, a.price_source, params)
    run_id = journal.new_run_id(ticker, as_of)
    run_dir = journal.save_run(run_id, v, params, render_memo(v, params, run_id, model_id=None), model_id=None)
    report = check_run(run_dir, store)
    journal.save_check(run_id, report)

    e = v.equity
    print(f"Run {run_id}")
    print(f"  Market cap          {usd_m(v.market.market_cap)}")
    print(f"  Liquidation value   {usd_m(e.liquidation.low)} / {usd_m(e.liquidation.base)} / {usd_m(e.liquidation.high)}")
    print(f"  Reproduction value  {usd_m(e.reproduction.low)} / {usd_m(e.reproduction.base)} / {usd_m(e.reproduction.high)}")
    print(f"  System verdict      {v.decision.verdict}")
    print(f"  Checker             {'PASSED' if report.passed else 'FAILED'} "
          f"({report.facts_checked} facts, {report.numbers_checked} memo figures)")
    for err in report.errors[:20]:
        print(f"    - {err}")
    print(f"  Memo                {run_dir / 'memo.md'}")
    return 0 if report.passed else 1


def cmd_check(a) -> int:
    home = config.home()
    journal = Journal(home)
    report = check_run(journal.run_dir(a.run_id), FactStore(home))
    journal.save_check(a.run_id, report)
    print(f"{a.run_id}: {'PASSED' if report.passed else 'FAILED'} "
          f"({report.facts_checked} facts, {report.numbers_checked} memo figures)")
    for err in report.errors:
        print(f"  - {err}")
    return 0 if report.passed else 1


def cmd_decide(a) -> int:
    Journal(config.home()).decide(a.run_id, a.decision, a.note)
    print(f"{a.run_id}: recorded {a.decision.upper()}")
    return 0


def cmd_journal(a) -> int:
    for run_id, as_of, pv, verdict, ok, decision, when, note in Journal(config.home()).list(a.limit):
        check = "unchecked" if ok is None else ("check ok" if ok else "CHECK FAILED")
        mine = f"{decision} on {when:%Y-%m-%d}: {note}" if decision else "no decision yet"
        print(f"{run_id}  params {pv}  system {verdict}  {check}  |  {mine}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="valuer", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("ingest", help="download a company's SEC filings index and XBRL facts")
    s.add_argument("ticker")
    s.set_defaults(fn=cmd_ingest)

    s = sub.add_parser("prices", help="store daily closes from a price source")
    s.add_argument("ticker")
    s.add_argument("--source", choices=["bloomberg", "csv", "yahoo"], default="bloomberg")
    s.add_argument("--csv", type=Path)
    s.add_argument("--start", type=_date)
    s.add_argument("--end", type=_date)
    s.set_defaults(fn=cmd_prices)

    s = sub.add_parser("value", help="run the valuation, write the memo, run the checker")
    s.add_argument("ticker")
    s.add_argument("--as-of", type=_date, help="use only what was public on this date (default: today)")
    s.add_argument("--params", type=Path, default=Path("params/v001"))
    s.add_argument("--price-source", choices=["bloomberg", "csv", "yahoo"], default="bloomberg")
    s.set_defaults(fn=cmd_value)

    s = sub.add_parser("check", help="re-run the checker on a saved run")
    s.add_argument("run_id")
    s.set_defaults(fn=cmd_check)

    s = sub.add_parser("decide", help="record your decision on a run")
    s.add_argument("run_id")
    s.add_argument("decision", choices=["buy", "watch", "pass"])
    s.add_argument("--note", required=True)
    s.set_defaults(fn=cmd_decide)

    s = sub.add_parser("journal", help="list runs and decisions")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(fn=cmd_journal)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
