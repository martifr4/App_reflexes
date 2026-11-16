"""Run archive and decision journal.

Each run is a folder under <home>/runs/<run_id>/ holding memo.md, valuation.json, params.json,
check.json and meta.json. The journal (<home>/journal.duckdb) indexes runs and records the
owner's decisions. Decisions are append-only: changing your mind adds a row.
"""
from __future__ import annotations

import datetime as dt
import json
import subprocess
from pathlib import Path

import duckdb

from .memo.checker import CheckReport
from .params import ParamSet
from .valuation.types import Valuation

_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    run_id VARCHAR PRIMARY KEY, created_at TIMESTAMP, ticker VARCHAR, cik BIGINT, as_of DATE,
    params_version VARCHAR, params_hash VARCHAR, engine_version VARCHAR, git_sha VARCHAR,
    model_id VARCHAR, system_verdict VARCHAR, market_cap DOUBLE, liquidation_low DOUBLE,
    reproduction_base DOUBLE, check_passed BOOLEAN, run_dir VARCHAR);
CREATE TABLE IF NOT EXISTS decisions (
    run_id VARCHAR, decided_at TIMESTAMP, decision VARCHAR, note VARCHAR);
"""


def _git_sha() -> str | None:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
                              cwd=Path(__file__).parent).stdout.strip()
    except Exception:
        return None


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None, microsecond=0)


class Journal:
    def __init__(self, home: Path):
        self.home = Path(home)
        self.runs_dir = self.home / "runs"
        self.runs_dir.mkdir(parents=True, exist_ok=True)
        self._db = self.home / "journal.duckdb"
        with duckdb.connect(str(self._db)) as con:
            con.execute(_DDL)

    def new_run_id(self, ticker: str, as_of: dt.date) -> str:
        return f"{ticker}-{as_of.isoformat()}-{_now().strftime('%Y%m%dT%H%M%SZ')}"

    def run_dir(self, run_id: str) -> Path:
        d = self.runs_dir / run_id
        if not d.is_dir():
            raise FileNotFoundError(f"No run {run_id} under {self.runs_dir}")
        return d

    def save_run(self, run_id: str, valuation: Valuation, params: ParamSet, memo: str, model_id: str | None) -> Path:
        d = self.runs_dir / run_id
        d.mkdir(parents=True)
        (d / "valuation.json").write_text(valuation.model_dump_json(indent=2))
        (d / "params.json").write_text(json.dumps(params.to_json(), indent=2))
        (d / "memo.md").write_text(memo)
        meta = {"run_id": run_id, "created_at": _now().isoformat(), "git_sha": _git_sha(), "model_id": model_id}
        (d / "meta.json").write_text(json.dumps(meta, indent=2))
        m = valuation.meta
        with duckdb.connect(str(self._db)) as con:
            con.execute(
                "INSERT INTO runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)",
                [run_id, _now(), m.ticker, m.cik, m.as_of, m.params_version, m.params_hash, m.engine_version,
                 meta["git_sha"], model_id, valuation.decision.verdict, valuation.market.market_cap,
                 valuation.equity.liquidation.low, valuation.equity.reproduction.base, str(d)],
            )
        return d

    def save_check(self, run_id: str, report: CheckReport) -> None:
        (self.run_dir(run_id) / "check.json").write_text(report.model_dump_json(indent=2))
        with duckdb.connect(str(self._db)) as con:
            con.execute("UPDATE runs SET check_passed = ? WHERE run_id = ?", [report.passed, run_id])

    def decide(self, run_id: str, decision: str, note: str) -> None:
        self.run_dir(run_id)
        with duckdb.connect(str(self._db)) as con:
            row = con.execute("SELECT check_passed FROM runs WHERE run_id = ?", [run_id]).fetchone()
            if row is None:
                raise KeyError(f"Run {run_id} is not in the journal")
            if not row[0]:
                raise RuntimeError(f"Run {run_id} has not passed the checker; decide only on reconciled runs.")
            con.execute("INSERT INTO decisions VALUES (?, ?, ?, ?)", [run_id, _now(), decision.upper(), note])

    def list(self, limit: int = 20) -> list[tuple]:
        with duckdb.connect(str(self._db)) as con:
            return con.execute(
                "SELECT r.run_id, r.as_of, r.params_version, r.system_verdict, r.check_passed, "
                "d.decision, d.decided_at, d.note FROM runs r LEFT JOIN decisions d USING (run_id) "
                "ORDER BY r.created_at DESC, d.decided_at DESC LIMIT ?", [limit]).fetchall()
