"""Point-in-time fact store: Parquet files queried through DuckDB.

Rules
-----
* A fact is immutable and identified by where it came from (filing accession) and what it
  measures (concept, unit, period). Restatements are new rows from later filings.
* Every read takes an ``as_of`` date and only sees rows with ``filed <= as_of``. When several
  filings report the same (concept, period), the latest one visible at ``as_of`` wins.
* Prices are append-only: a stored close is never overwritten by a later fetch.
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

PERIODIC_FORMS = ("10-K", "10-K/A", "10-Q", "10-Q/A")
ANNUAL_FORMS = ("10-K", "10-K/A")

FACT_SCHEMA = pa.schema(
    [
        ("fact_id", pa.string()),
        ("cik", pa.int64()),
        ("taxonomy", pa.string()),
        ("concept", pa.string()),
        ("unit", pa.string()),
        ("period_start", pa.date32()),
        ("period_end", pa.date32()),
        ("value", pa.float64()),
        ("accession", pa.string()),
        ("form", pa.string()),
        ("fy", pa.int32()),
        ("fp", pa.string()),
        ("filed", pa.date32()),
    ]
)
FACT_COLS = [f.name for f in FACT_SCHEMA]

ENTITY_SCHEMA = pa.schema(
    [
        ("cik", pa.int64()),
        ("ticker", pa.string()),
        ("name", pa.string()),
        ("sic", pa.int32()),
        ("sic_description", pa.string()),
        ("fiscal_year_end", pa.string()),
    ]
)

FILING_SCHEMA = pa.schema(
    [
        ("cik", pa.int64()),
        ("accession", pa.string()),
        ("form", pa.string()),
        ("filed", pa.date32()),
        ("report_date", pa.date32()),
        ("primary_document", pa.string()),
        ("url", pa.string()),
    ]
)

PRICE_SCHEMA = pa.schema(
    [
        ("price_id", pa.string()),
        ("ticker", pa.string()),
        ("date", pa.date32()),
        ("close", pa.float64()),
        ("source", pa.string()),
        ("fetched_at", pa.timestamp("s")),
    ]
)


class NotIngested(RuntimeError):
    pass


@dataclass(frozen=True)
class Fact:
    fact_id: str
    cik: int
    taxonomy: str
    concept: str
    unit: str
    period_start: dt.date | None
    period_end: dt.date
    value: float
    accession: str
    form: str
    fy: int | None
    fp: str | None
    filed: dt.date


@dataclass(frozen=True)
class Entity:
    cik: int
    ticker: str
    name: str
    sic: int
    sic_description: str
    fiscal_year_end: str


@dataclass(frozen=True)
class Price:
    price_id: str
    ticker: str
    date: dt.date
    close: float
    source: str


def make_fact_id(cik: int, taxonomy: str, concept: str, unit: str, start: str | None, end: str, accn: str) -> str:
    period = f"{start}..{end}" if start else end
    return f"CIK{cik}/{taxonomy}:{concept}/{unit}/{period}/{accn}"


def make_price_id(ticker: str, date: dt.date, source: str) -> str:
    return f"PX/{ticker}/{date.isoformat()}/{source}"


class FactStore:
    def __init__(self, home: Path):
        self.root = Path(home) / "store"
        self._con = duckdb.connect(":memory:")
        self._cache: dict[tuple, Any] = {}

    # ------------------------------------------------------------------ paths
    def _facts_path(self, cik: int) -> Path:
        return self.root / "facts" / f"cik={cik}.parquet"

    def _entity_path(self, cik: int) -> Path:
        return self.root / "entities" / f"cik={cik}.parquet"

    def _filings_path(self, cik: int) -> Path:
        return self.root / "filings" / f"cik={cik}.parquet"

    def _prices_path(self, ticker: str, source: str) -> Path:
        return self.root / "prices" / f"{ticker}.{source}.parquet"

    # ----------------------------------------------------------------- writes
    def _write(self, path: Path, rows: list[dict], schema: pa.Schema) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)
        self._cache.clear()

    def write_facts(self, cik: int, rows: list[dict]) -> int:
        self._write(self._facts_path(cik), rows, FACT_SCHEMA)
        return len(rows)

    def write_entity(self, row: dict) -> None:
        self._write(self._entity_path(row["cik"]), [row], ENTITY_SCHEMA)

    def write_filings(self, cik: int, rows: list[dict]) -> None:
        self._write(self._filings_path(cik), rows, FILING_SCHEMA)

    def add_prices(self, ticker: str, source: str, closes: Iterable[tuple[dt.date, float]]) -> int:
        """Append closes for dates not yet stored. Existing rows are never changed."""
        path = self._prices_path(ticker, source)
        existing = pq.read_table(path).to_pylist() if path.exists() else []
        have = {r["date"] for r in existing}
        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None, microsecond=0)
        new = [
            {
                "price_id": make_price_id(ticker, d, source),
                "ticker": ticker,
                "date": d,
                "close": float(c),
                "source": source,
                "fetched_at": now,
            }
            for d, c in closes
            if d not in have and c is not None
        ]
        if new:
            self._write(path, sorted(existing + new, key=lambda r: r["date"]), PRICE_SCHEMA)
        return len(new)

    # ------------------------------------------------------------------ reads
    def _q(self, sql: str, params: list) -> list[tuple]:
        key = (sql, repr(params))
        if key not in self._cache:
            self._cache[key] = self._con.execute(sql, params).fetchall()
        return self._cache[key]

    def _facts_src(self, cik: int) -> str:
        p = self._facts_path(cik)
        if not p.exists():
            raise NotIngested(f"No facts for CIK {cik}. Run `valuer ingest` first.")
        return f"read_parquet('{p.as_posix()}')"

    def resolve(self, ticker: str) -> Entity:
        d = self.root / "entities"
        if d.exists() and any(d.glob("*.parquet")):
            rows = self._q(
                f"SELECT cik, ticker, name, sic, sic_description, fiscal_year_end "
                f"FROM read_parquet('{d.as_posix()}/*.parquet') WHERE upper(ticker) = ?",
                [ticker.upper()],
            )
            if rows:
                return Entity(*rows[0])
        raise NotIngested(f"{ticker} is not in the store. Run `valuer ingest {ticker}` first.")

    def instant(self, cik: int, concept: str, end: dt.date, as_of: dt.date, unit: str = "USD",
                taxonomy: str = "us-gaap") -> Fact | None:
        """Balance-sheet style fact at ``end``, as known on ``as_of``."""
        rows = self._q(
            f"SELECT {', '.join(FACT_COLS)} FROM {self._facts_src(cik)} "
            "WHERE taxonomy = ? AND concept = ? AND unit = ? AND period_start IS NULL "
            "AND period_end = ? AND filed <= ? AND form IN (SELECT unnest(?)) "
            "ORDER BY filed DESC, accession DESC LIMIT 1",
            [taxonomy, concept, unit, end, as_of, list(PERIODIC_FORMS)],
        )
        return Fact(*rows[0]) if rows else None

    def latest_instant(self, cik: int, concept: str, as_of: dt.date, unit: str = "USD",
                       taxonomy: str = "us-gaap") -> Fact | None:
        """Most recent instant fact for a concept, as known on ``as_of``."""
        rows = self._q(
            f"SELECT {', '.join(FACT_COLS)} FROM {self._facts_src(cik)} "
            "WHERE taxonomy = ? AND concept = ? AND unit = ? AND period_start IS NULL "
            "AND filed <= ? AND form IN (SELECT unnest(?)) "
            "ORDER BY period_end DESC, filed DESC, accession DESC LIMIT 1",
            [taxonomy, concept, unit, as_of, list(PERIODIC_FORMS)],
        )
        return Fact(*rows[0]) if rows else None

    def balance_dates(self, cik: int, as_of: dt.date) -> tuple[dt.date, dt.date]:
        """(latest balance-sheet date, latest fiscal-year-end balance-sheet date) visible on ``as_of``."""
        src = self._facts_src(cik)
        base = (
            f"SELECT max(period_end) FROM {src} WHERE taxonomy = 'us-gaap' AND concept = 'Assets' "
            "AND unit = 'USD' AND filed <= ? AND form IN (SELECT unnest(?))"
        )
        latest = self._q(base, [as_of, list(PERIODIC_FORMS)])[0][0]
        annual = self._q(base, [as_of, list(ANNUAL_FORMS)])[0][0]
        if latest is None or annual is None:
            raise NotIngested(f"CIK {cik}: no balance sheet filed on or before {as_of}.")
        return latest, annual

    def annual_series(self, cik: int, concept: str, as_of: dt.date, on_or_before: dt.date,
                      unit: str = "USD") -> list[Fact]:
        """Full-fiscal-year flow facts from 10-Ks, newest first, one per fiscal year end.

        Each year uses the latest value visible on ``as_of`` (so later recasts replace originals).
        """
        cols = ", ".join(FACT_COLS)
        rows = self._q(
            f"SELECT {cols} FROM (SELECT *, row_number() OVER (PARTITION BY period_end "
            f"ORDER BY filed DESC, accession DESC) AS rn FROM {self._facts_src(cik)} "
            "WHERE taxonomy = 'us-gaap' AND concept = ? AND unit = ? AND period_start IS NOT NULL "
            "AND date_diff('day', period_start, period_end) BETWEEN 340 AND 380 "
            "AND filed <= ? AND period_end <= ? AND form IN (SELECT unnest(?))) "
            "WHERE rn = 1 ORDER BY period_end DESC",
            [concept, unit, as_of, on_or_before, list(ANNUAL_FORMS)],
        )
        return [Fact(*r) for r in rows]

    def latest_duration(self, cik: int, concept: str, as_of: dt.date, unit: str) -> Fact | None:
        """Most recent flow fact (latest period end, then shortest period), as known on ``as_of``."""
        rows = self._q(
            f"SELECT {', '.join(FACT_COLS)} FROM {self._facts_src(cik)} "
            "WHERE taxonomy = 'us-gaap' AND concept = ? AND unit = ? AND period_start IS NOT NULL "
            "AND filed <= ? AND form IN (SELECT unnest(?)) "
            "ORDER BY period_end DESC, period_start DESC, filed DESC, accession DESC LIMIT 1",
            [concept, unit, as_of, list(PERIODIC_FORMS)],
        )
        return Fact(*rows[0]) if rows else None

    def duration(self, cik: int, concept: str, start: dt.date, end: dt.date, as_of: dt.date,
                 unit: str) -> Fact | None:
        rows = self._q(
            f"SELECT {', '.join(FACT_COLS)} FROM {self._facts_src(cik)} "
            "WHERE taxonomy = 'us-gaap' AND concept = ? AND unit = ? AND period_start = ? "
            "AND period_end = ? AND filed <= ? AND form IN (SELECT unnest(?)) "
            "ORDER BY filed DESC, accession DESC LIMIT 1",
            [concept, unit, start, end, as_of, list(PERIODIC_FORMS)],
        )
        return Fact(*rows[0]) if rows else None

    def fact_by_id(self, fact_id: str) -> Fact | None:
        cik = int(fact_id.split("/", 1)[0].removeprefix("CIK"))
        rows = self._q(
            f"SELECT {', '.join(FACT_COLS)} FROM {self._facts_src(cik)} WHERE fact_id = ?", [fact_id]
        )
        return Fact(*rows[0]) if rows else None

    def price_asof(self, ticker: str, as_of: dt.date, source: str, max_stale_days: int = 7) -> Price:
        """Last stored close on or before ``as_of`` from one source."""
        p = self._prices_path(ticker, source)
        if not p.exists():
            raise NotIngested(f"No {source} prices for {ticker}. Run `valuer prices {ticker} --source {source}`.")
        rows = self._q(
            f"SELECT price_id, ticker, date, close, source FROM read_parquet('{p.as_posix()}') "
            "WHERE date <= ? ORDER BY date DESC LIMIT 1",
            [as_of],
        )
        if not rows or (as_of - rows[0][2]).days > max_stale_days:
            raise NotIngested(f"No {source} close for {ticker} within {max_stale_days} days before {as_of}.")
        return Price(*rows[0])

    def price_by_id(self, price_id: str) -> Price | None:
        _, ticker, _, source = price_id.split("/")
        p = self._prices_path(ticker, source)
        if not p.exists():
            return None
        rows = self._q(
            f"SELECT price_id, ticker, date, close, source FROM read_parquet('{p.as_posix()}') WHERE price_id = ?",
            [price_id],
        )
        return Price(*rows[0]) if rows else None
