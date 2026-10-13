"""Shared helpers for the fetch scripts."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
USER_AGENT = "token-spread/0.1 (research; github.com/martifr4/App_reflexes)"


def load_config() -> dict:
    with open(ROOT / "assumptions.yaml") as f:
        return yaml.safe_load(f)


def today() -> str:
    return dt.date.today().isoformat()


def http_get(url: str, **kw) -> requests.Response:
    """GET with a UA, timeout and 3 retries (backoff 2s/4s)."""
    import time

    last = None
    for attempt in range(3):
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(2 ** (attempt + 1))
    raise last
