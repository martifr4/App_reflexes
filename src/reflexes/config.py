"""Configuration loading. All tunables live in YAML; modules receive plain dicts.

We keep this intentionally thin (a dot-accessible dict) so that a config is just
data — easy to snapshot, diff, and record alongside a backtest result.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


class Config(dict):
    """A dict that also supports attribute access and nested `get` via dotted keys."""

    def __getattr__(self, name: str) -> Any:
        try:
            value = self[name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise AttributeError(name) from exc
        if isinstance(value, dict) and not isinstance(value, Config):
            value = Config(value)
        return value

    def get_path(self, dotted: str, default: Any = None) -> Any:
        node: Any = self
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node


def load_config(path: str | Path | None = None) -> Config:
    """Load a YAML config file into a :class:`Config`.

    Parameters
    ----------
    path:
        Path to a YAML file. Defaults to ``config/default.yaml``.
    """
    path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return Config(copy.deepcopy(raw))
