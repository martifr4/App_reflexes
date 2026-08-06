"""Walk-forward / out-of-sample split.

The combiners here have no *fitted* parameters — the rules weights and thresholds are
chosen a priori in the YAML config, and the LLM combiner has no trained weights at all.
So this is a simple in-sample / out-of-sample date split rather than a rolling refit:
everything before ``oos_start`` is in-sample (the period whose behavior informed the
config choices), and everything on/after ``oos_start`` is a holdout that was never used
to pick any parameter.

This is deliberately honest about its limits — see HONEST_ASSESSMENT.md. A true
walk-forward with periodic refitting would be required before trusting a *fitted*
strategy; the scaffolding here (clean IS/OOS boundary, separate reporting) is the
minimum, not the maximum.
"""
from __future__ import annotations

import pandas as pd


def split_is_oos(series_or_frame, oos_start) -> tuple:
    """Split a date-indexed series/frame into (in_sample, out_of_sample) at ``oos_start``.

    ``oos_start`` is inclusive of the out-of-sample side.
    """
    idx = series_or_frame.index
    oos_ts = pd.Timestamp(oos_start)
    if idx.tz is not None and oos_ts.tz is None:
        oos_ts = oos_ts.tz_localize(idx.tz)
    is_mask = idx < oos_ts
    return series_or_frame[is_mask], series_or_frame[~is_mask]
