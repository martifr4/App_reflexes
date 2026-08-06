"""Daily OHLCV ingestion from the Coinbase Exchange REST API.

Why Coinbase Exchange?
    * Free and keyless.
    * Returns real exchange volume (CoinGecko's free OHLC endpoint does not, and it
      silently downsamples to multi-day candles beyond 30 days).
    * Binance is geo-restricted (HTTP 451) from this environment.

Coinbase candle quirks handled here:
    * Endpoint returns rows as ``[time, low, high, open, close, volume]`` — note the
      non-standard column order — newest-first, max 300 candles per request. We
      paginate backwards and normalize to standard OHLCV, oldest-first.
    * ``time`` is a UNIX epoch (UTC) at the candle's *open*. We index by UTC date.

Data-hygiene guarantees:
    * All timestamps are tz-aware UTC and normalized to midnight (daily bars).
    * The date index is reindexed onto a complete daily calendar so missing bars are
      explicit NaNs, not silently skipped rows.
    * Short gaps (<= ``max_forward_fill`` days) are forward-filled on price and marked
      zero-volume; longer gaps are left as NaN and reported.
    * Survivorship: the universe is a fixed, explicit list supplied by config. We do
      NOT reconstruct the historically-tradable set. This is a documented limitation,
      not a silent assumption — see HONEST_ASSESSMENT.md.
"""
from __future__ import annotations

import time as _time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

COINBASE_BASE = "https://api.exchange.coinbase.com"
GRANULARITY_DAILY = 86_400
MAX_CANDLES_PER_REQUEST = 300
OHLCV_COLUMNS = ["open", "high", "low", "close", "volume"]


def _as_utc(ts) -> pd.Timestamp:
    """Coerce anything date-like to a tz-aware UTC Timestamp, whether or not it has tz."""
    ts = pd.Timestamp(ts)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


@dataclass
class CoinbaseClient:
    """Minimal, polite Coinbase Exchange candle client with pagination."""

    base_url: str = COINBASE_BASE
    session: requests.Session = field(default_factory=requests.Session)
    request_pause: float = 0.34  # ~3 req/s, well under public rate limits
    timeout: float = 30.0
    max_retries: int = 4

    def _get(self, url: str, params: dict) -> list:
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
                if resp.status_code == 429:  # rate limited -> back off
                    _time.sleep(1.0 * (attempt + 1))
                    continue
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:  # network/json
                last_exc = exc
                _time.sleep(min(2 ** attempt, 8))
        raise RuntimeError(f"Coinbase request failed after retries: {url}") from last_exc

    def fetch_daily(self, product: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Fetch daily candles for ``product`` in [start, end], paginating backwards.

        Returns a UTC-indexed OHLCV frame (oldest-first). Empty frame if none exist.
        """
        start = _as_utc(start).normalize()
        end = _as_utc(end).normalize()
        url = f"{self.base_url}/products/{product}/candles"

        rows: list[list] = []
        window_end = end
        while window_end >= start:
            # 300 daily candles per window, stepping backwards.
            window_start = max(start, window_end - pd.Timedelta(days=MAX_CANDLES_PER_REQUEST - 1))
            batch = self._get(
                url,
                params={
                    "granularity": GRANULARITY_DAILY,
                    "start": window_start.isoformat(),
                    "end": window_end.isoformat(),
                },
            )
            if batch:
                rows.extend(batch)
            window_end = window_start - pd.Timedelta(days=1)
            _time.sleep(self.request_pause)

        if not rows:
            return pd.DataFrame(columns=OHLCV_COLUMNS, index=pd.DatetimeIndex([], tz="UTC", name="date"))

        # Coinbase order: [time, low, high, open, close, volume]
        df = pd.DataFrame(rows, columns=["time", "low", "high", "open", "close", "volume"])
        df["date"] = pd.to_datetime(df["time"], unit="s", utc=True).dt.normalize()
        df = df.drop(columns="time").set_index("date")
        df = df[~df.index.duplicated(keep="first")].sort_index()
        return df[OHLCV_COLUMNS].astype(float)


def _align_and_clean(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp,
                     max_forward_fill: int) -> tuple[pd.DataFrame, dict]:
    """Reindex onto a complete daily UTC calendar; make gaps explicit then patch short ones.

    Returns the cleaned frame plus a small report describing what was patched.
    """
    if df.empty:
        full = pd.DatetimeIndex(pd.date_range(_as_utc(start), _as_utc(end), freq="D"), name="date")
        empty = pd.DataFrame(index=full, columns=OHLCV_COLUMNS, dtype=float)
        return empty, {"n_bars": 0, "n_missing": len(full), "n_filled": 0, "first": None, "last": None}

    first = max(df.index.min(), _as_utc(start))
    last = min(df.index.max(), _as_utc(end))
    calendar = pd.DatetimeIndex(pd.date_range(first, last, freq="D"), name="date")
    aligned = df.reindex(calendar)

    missing_mask = aligned["close"].isna()
    n_missing_before = int(missing_mask.sum())

    # Forward-fill only short gaps on prices; volume on a synthetic bar is 0 (no trades seen).
    price_cols = ["open", "high", "low", "close"]
    filled = aligned.copy()
    filled[price_cols] = filled[price_cols].ffill(limit=max_forward_fill)
    # A row that was missing but is now price-complete counts as filled; set its volume to 0.
    newly_filled = missing_mask & filled["close"].notna()
    filled.loc[newly_filled, "volume"] = 0.0
    n_filled = int(newly_filled.sum())
    n_missing_after = int(filled["close"].isna().sum())

    report = {
        "n_bars": int(len(filled)),
        "n_missing": n_missing_before,
        "n_filled": n_filled,
        "n_still_missing": n_missing_after,
        "first": str(first.date()),
        "last": str(last.date()),
    }
    return filled, report


def fetch_ohlcv(base_asset: str, cfg, client: CoinbaseClient | None = None,
                use_cache: bool = True) -> pd.DataFrame:
    """Fetch (and cache) a single asset's daily OHLCV frame per the config.

    Parameters
    ----------
    base_asset: e.g. ``"BTC"``.
    cfg: the ``data`` sub-config (dict-like) with keys vs_currency, start, end,
         cache_dir, max_forward_fill.
    """
    vs = cfg["vs_currency"]
    product = f"{base_asset}-{vs}"
    start = pd.Timestamp(cfg["start"], tz="UTC")
    end = pd.Timestamp(cfg["end"], tz="UTC") if cfg.get("end") else pd.Timestamp.utcnow().normalize()

    cache_dir = Path(cfg["cache_dir"])
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_path = cache_dir / f"{product}_1d.parquet"

    if use_cache and cache_path.exists():
        cached = pd.read_parquet(cache_path)
        cached.index = pd.DatetimeIndex(cached.index).tz_convert("UTC")
        # Serve from cache when it already covers the requested window.
        if not cached.empty and cached.index.min() <= start and cached.index.max() >= end:
            return cached.loc[(cached.index >= start) & (cached.index <= end)]

    client = client or CoinbaseClient()
    raw = client.fetch_daily(product, start, end)
    cleaned, report = _align_and_clean(raw, start, end, int(cfg.get("max_forward_fill", 2)))
    cleaned.attrs["ingest_report"] = report
    cleaned.attrs["product"] = product

    if use_cache:
        cleaned.to_parquet(cache_path)
    return cleaned


def load_universe(cfg, client: CoinbaseClient | None = None,
                  use_cache: bool = True) -> dict[str, pd.DataFrame]:
    """Fetch OHLCV for every asset in ``cfg['universe']``.

    Returns a mapping ``base_asset -> OHLCV frame``. Assets that return no data are
    skipped with a printed warning (explicit, not silent survivorship).
    """
    data_cfg = cfg["data"] if "data" in cfg else cfg
    client = client or CoinbaseClient()
    out: dict[str, pd.DataFrame] = {}
    for asset in data_cfg["universe"]:
        df = fetch_ohlcv(asset, data_cfg, client=client, use_cache=use_cache)
        if df["close"].notna().sum() == 0:
            print(f"[data] WARNING: no data for {asset}; excluding from universe.")
            continue
        out[asset] = df
    return out


def to_panel(frames: dict[str, pd.DataFrame], field_name: str = "close") -> pd.DataFrame:
    """Stack a single OHLCV field across assets into one date x asset frame (UTC index)."""
    series = {asset: df[field_name] for asset, df in frames.items()}
    panel = pd.DataFrame(series)
    panel.index.name = "date"
    return panel.sort_index()
