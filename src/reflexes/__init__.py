"""App Reflexes — a modular crypto trading research system.

The package is deliberately split into independently testable modules:

    reflexes.data       -> ingestion + local Parquet cache
    reflexes.features   -> price, volume and (quarantined) news feature frames
    reflexes.decision   -> rules-based and LLM-based signal combiners
    reflexes.portfolio  -> position sizing and risk limits
    reflexes.backtest   -> next-bar backtest engine, metrics, benchmarks, walk-forward

Nothing here optimizes for impressive returns. The goal is an honest read on
whether a multi-signal daily strategy has any out-of-sample edge after costs.
"""

__version__ = "0.1.0"
