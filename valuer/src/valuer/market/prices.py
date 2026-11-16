"""Price sources. Each returns unadjusted daily closes; the store keeps them append-only."""
from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path
from typing import Iterable

Closes = Iterable[tuple[dt.date, float]]


def from_csv(path: str | Path) -> Closes:
    """CSV with a header and columns `date` (YYYY-MM-DD) and `close`."""
    with open(path, newline="") as fh:
        return [(dt.date.fromisoformat(r["date"].strip()), float(r["close"])) for r in csv.DictReader(fh)]


def from_bloomberg(ticker: str, start: dt.date, end: dt.date, host: str = "localhost", port: int = 8194,
                   suffix: str = "US Equity") -> Closes:
    """PX_LAST from the Bloomberg Desktop API, with no split or dividend adjustment.

    Must run on the machine where the Terminal is logged in (needs `pip install blpapi`).
    """
    import blpapi  # type: ignore[import-not-found]

    opts = blpapi.SessionOptions()
    opts.setServerHost(host)
    opts.setServerPort(port)
    session = blpapi.Session(opts)
    if not session.start() or not session.openService("//blp/refdata"):
        raise RuntimeError(f"Cannot reach the Bloomberg API at {host}:{port}. Is the Terminal running?")
    try:
        req = session.getService("//blp/refdata").createRequest("HistoricalDataRequest")
        req.getElement("securities").appendValue(f"{ticker} {suffix}")
        req.getElement("fields").appendValue("PX_LAST")
        req.set("startDate", start.strftime("%Y%m%d"))
        req.set("endDate", end.strftime("%Y%m%d"))
        req.set("periodicitySelection", "DAILY")
        for flag in ("adjustmentNormal", "adjustmentAbnormal", "adjustmentSplit", "adjustmentFollowDPDF"):
            req.set(flag, False)
        session.sendRequest(req)
        out: list[tuple[dt.date, float]] = []
        while True:
            ev = session.nextEvent(10_000)
            for msg in ev:
                if msg.hasElement("responseError"):
                    raise RuntimeError(f"Bloomberg error: {msg.getElement('responseError')}")
                if msg.hasElement("securityData"):
                    sec = msg.getElement("securityData")
                    if sec.hasElement("securityError"):
                        raise RuntimeError(f"Bloomberg security error: {sec.getElement('securityError')}")
                    rows = sec.getElement("fieldData")
                    for i in range(rows.numValues()):
                        row = rows.getValueAsElement(i)
                        if row.hasElement("PX_LAST"):
                            d = row.getElementAsDatetime("date")
                            out.append((dt.date(d.year, d.month, d.day), row.getElementAsFloat("PX_LAST")))
            if ev.eventType() == blpapi.Event.RESPONSE:
                return out
            if ev.eventType() == blpapi.Event.TIMEOUT:
                raise RuntimeError("Bloomberg request timed out.")
    finally:
        session.stop()


def from_yahoo(ticker: str, start: dt.date, end: dt.date) -> Closes:
    """Unofficial Yahoo chart endpoint. Free fallback only: closes are split-adjusted, so do not
    use it for as-of dates before a split."""
    import requests

    def ts(d: dt.date) -> int:
        return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())

    r = requests.get(
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}",
        params={"period1": ts(start), "period2": ts(end + dt.timedelta(days=1)), "interval": "1d"},
        headers={"User-Agent": "Mozilla/5.0"}, timeout=30,
    )
    r.raise_for_status()
    res = r.json()["chart"]["result"][0]
    offset = res["meta"].get("gmtoffset", 0)
    closes = res["indicators"]["quote"][0]["close"]
    return [
        ((dt.datetime.fromtimestamp(t, dt.timezone.utc) + dt.timedelta(seconds=offset)).date(), round(c, 4))
        for t, c in zip(res.get("timestamp", []), closes) if c is not None
    ]
