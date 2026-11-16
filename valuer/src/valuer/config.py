"""Runtime locations. Everything the system writes lives under VALUER_HOME (default ./data)."""
from __future__ import annotations

import os
from pathlib import Path


def home() -> Path:
    p = Path(os.environ.get("VALUER_HOME", "data")).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def sec_user_agent() -> str:
    ua = os.environ.get("SEC_USER_AGENT", "").strip()
    if not ua:
        raise RuntimeError(
            "SEC_USER_AGENT is not set. SEC requires a contact string, e.g. "
            "export SEC_USER_AGENT='Your Name you@example.com'"
        )
    return ua
