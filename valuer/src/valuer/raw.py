"""Raw source archive: one folder per company, holding every document exactly as downloaded.

    <home>/raw/<TICKER>/
        SOURCES.md            human-readable index: file, what it is, URL, fetch time, SHA-256
        manifest.json         the same, machine-readable
        sec/                  SEC JSON (filing index, XBRL facts), one file per fetch date
        filings/<accession>/  the filing as filed (.htm) and the plain text the agents read (.txt)
        prices/               the closes stored for this company, per source

Nothing here is edited after download. The .txt files are derived from the .htm by code
(valuer.edgar.text) and their line numbers are the paragraph numbers that citations use.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path


def collect_sources(home: Path, ticker: str, filing_rels: list[str], price_source: str) -> list[dict]:
    """The raw files behind a run: latest SEC JSON, the current filings and the price file."""
    entries = RawArchive(home, ticker).entries()

    def latest(prefix: str) -> list[str]:
        hits = sorted(r for r in entries if r.startswith(prefix))
        return hits[-1:]

    rels = latest("sec/submissions.") + latest("sec/companyfacts.") + [r for r in filing_rels if r in entries]
    rels += [r for r in (f"prices/{price_source}.csv",) if r in entries]
    return [{"path": f"{ticker.upper()}/{r}", "description": entries[r]["description"], "url": entries[r]["url"],
             "sha256": entries[r]["sha256"], "fetched_at": entries[r]["fetched_at"]} for r in rels]


class RawArchive:
    def __init__(self, home: Path, ticker: str):
        self.ticker = ticker.upper()
        self.dir = Path(home) / "raw" / self.ticker
        self._manifest = self.dir / "manifest.json"

    def entries(self) -> dict[str, dict]:
        return json.loads(self._manifest.read_text()) if self._manifest.exists() else {}

    def path(self, rel: str) -> Path:
        return self.dir / rel

    def save(self, rel: str, content: bytes, url: str, description: str) -> Path:
        """Write one file and index it. ``url`` is where it came from ('derived: ...' for local output)."""
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)
        entries = self.entries()
        entries[rel] = {
            "description": description,
            "url": url,
            "fetched_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content),
        }
        self._manifest.write_text(json.dumps(dict(sorted(entries.items())), indent=2))
        self._write_index(entries)
        return p

    def _write_index(self, entries: dict[str, dict]) -> None:
        rows = [
            f"# {self.ticker}: raw sources\n",
            "Every document the system used for this company, as downloaded. Regenerated on each save.\n",
            "| File | What it is | Source | Fetched (UTC) | Bytes | SHA-256 |",
            "|---|---|---|---|---:|---|",
        ]
        for rel, e in sorted(entries.items()):
            src = f"<{e['url']}>" if e["url"].startswith("http") else e["url"]
            rows.append(f"| [{rel}]({rel}) | {e['description']} | {src} | {e['fetched_at']} | {e['bytes']:,} | `{e['sha256'][:16]}` |")
        (self.dir / "SOURCES.md").write_text("\n".join(rows) + "\n")
