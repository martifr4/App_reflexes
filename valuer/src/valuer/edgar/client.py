"""Minimal SEC EDGAR client: polite rate limit, required User-Agent, raw responses kept on disk."""
from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path

import requests

from ..config import sec_user_agent

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
MIN_INTERVAL_S = 0.2  # SEC allows 10 requests/second; stay well under


class EdgarClient:
    def __init__(self, raw_dir: Path, user_agent: str | None = None):
        self.raw_dir = Path(raw_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": user_agent or sec_user_agent()})
        self._last = 0.0

    def get_json(self, url: str, save_as: str) -> dict:
        """Fetch JSON and keep the raw body under raw/edgar/<save_as>.<UTC date>.json."""
        for attempt in range(4):
            wait = MIN_INTERVAL_S - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            r = self._session.get(url, timeout=60)
            self._last = time.monotonic()
            if r.status_code == 200:
                stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
                (self.raw_dir / f"{save_as}.{stamp}.json").write_bytes(r.content)
                return json.loads(r.content)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            r.raise_for_status()
        raise RuntimeError(f"unreachable: {url}")

    def cik_for_ticker(self, ticker: str) -> int:
        data = self.get_json(TICKERS_URL, "company_tickers")
        for row in data.values():
            if row["ticker"].upper() == ticker.upper():
                return int(row["cik_str"])
        raise KeyError(f"Ticker {ticker} not found in SEC company_tickers.json")

    def submissions(self, cik: int) -> dict:
        return self.get_json(SUBMISSIONS_URL.format(cik=cik), f"submissions-{cik}")

    def companyfacts(self, cik: int) -> dict:
        return self.get_json(COMPANYFACTS_URL.format(cik=cik), f"companyfacts-{cik}")
