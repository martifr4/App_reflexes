"""Filing HTML -> plain text, one paragraph or table row per line.

Deterministic, so the same .htm always gives the same .txt. A table row is always one line,
with its cells separated by spaces. Line numbers (1-based) are the
paragraph numbers used in citations, and quotes are checked against these lines.
"""
from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser

_BLOCK = {"p", "div", "tr", "br", "li", "table", "h1", "h2", "h3", "h4", "h5", "h6", "hr", "title", "ul", "ol"}
_VOID = {"br", "hr", "img", "input", "meta", "link", "col", "area", "base", "source", "wbr"}
_SKIP = {"script", "style", "head", "ix:header"}
_HIDDEN = re.compile(r"display\s*:\s*none", re.I)
_WS = re.compile(r"[\s ​‌‍﻿]+")
_TRANS = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-", "−": "-"})


class _Extractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0
        self.rows = 0  # depth of open <tr>: inside a row, block tags must not break the line

    def handle_starttag(self, tag, attrs):
        if self.skip:
            self.skip += tag not in _VOID
            return
        if tag in _SKIP or _HIDDEN.search(dict(attrs).get("style") or ""):
            self.skip = tag not in _VOID
            return
        if tag == "tr":
            self.rows += 1
            self.parts.append("\n")
        elif tag in _BLOCK:
            self.parts.append(" " if self.rows else "\n")
        elif tag in ("td", "th"):
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if self.skip:
            self.skip -= 1
            return
        if tag == "tr":
            self.rows = max(0, self.rows - 1)
            self.parts.append("\n")
        elif tag in _BLOCK:
            self.parts.append(" " if self.rows else "\n")
        elif tag in ("td", "th"):
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def html_to_lines(html: str) -> list[str]:
    ex = _Extractor()
    ex.feed(html)
    ex.close()
    lines = (_WS.sub(" ", raw).strip() for raw in "".join(ex.parts).split("\n"))
    return [ln for ln in lines if ln]


def normalise(s: str) -> str:
    """Comparison form for quote matching: unicode-folded, straight quotes and dashes, single spaces."""
    return _WS.sub(" ", unicodedata.normalize("NFKC", s).translate(_TRANS)).strip()
