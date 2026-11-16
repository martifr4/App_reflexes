"""Minimal SEC EDGAR client: polite rate limit and the User-Agent SEC requires. It only fetches;
callers archive what they get (see valuer.raw)."""
from __future__ import annotations

import time

import requests

from ..config import sec_user_agent

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
COMPANYFACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
MIN_INTERVAL_S = 0.2  # SEC allows 10 requests/second; stay well under


class EdgarClient:
    def __init__(self, user_agent: str | None = None):
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": user_agent or sec_user_agent()})
        self._last = 0.0

    def get(self, url: str) -> bytes:
        for attempt in range(4):
            wait = MIN_INTERVAL_S - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            r = self._session.get(url, timeout=120)
            self._last = time.monotonic()
            if r.status_code == 200:
                return r.content
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(2 ** (attempt + 1))
                continue
            r.raise_for_status()
        raise RuntimeError(f"unreachable: {url}")
