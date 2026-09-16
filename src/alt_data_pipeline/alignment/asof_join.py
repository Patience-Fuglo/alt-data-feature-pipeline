"""As-of alignment, both directions -- the correct direction depends on
the question being asked, not a fixed rule.

``align_to_next_trading_day`` searches FORWARD: a filing dated Saturday
doesn't become actionable on Saturday, so it maps to the next real
trading day. Searching backward here would pair the event with a price
from *before* it was even public -- look-ahead bias.

``latest_known_value_asof`` searches BACKWARD: for a slowly-changing
quantity like shares outstanding, you want the most recently *published*
value as of a given date, never a future one that didn't exist yet.
Searching forward here would be the actual look-ahead bias -- using a
share count from after the date in question.

Same underlying discipline (never let the future leak into a point-in-time
value), opposite search direction, because the two questions are
genuinely different: "when can I first act on this event" vs. "what was
the most recently known value of this slowly-changing number."
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def align_to_next_trading_day(event_dates: pd.Series, trading_days: pd.DatetimeIndex) -> pd.Series:
    """For each date in ``event_dates``, return the next trading day in
    ``trading_days`` that is on or after it.

    The result keeps ``event_dates``' original index, so it can be assigned
    straight back as a new column: ``df["trading_date"] =
    align_to_next_trading_day(df["filing_date"], trading_days)``.

    Raises ValueError if any event date falls before the earliest known
    trading day (the "next trading day" can't be determined reliably
    outside the calendar's known range). Returns ``NaT`` for an event date
    after the latest known trading day -- not yet known, not an error.
    """
    trading_days = pd.DatetimeIndex(trading_days).sort_values()
    event_values = pd.DatetimeIndex(event_dates)

    if len(event_values) > 0 and event_values.min() < trading_days.min():
        raise ValueError(
            f"event date {event_values.min().date()} is before the earliest known "
            f"trading day {trading_days.min().date()} -- extend the calendar's start."
        )

    positions = np.searchsorted(trading_days.values, event_values.values, side="left")
    aligned = [
        trading_days[pos] if pos < len(trading_days) else pd.NaT for pos in positions
    ]
    return pd.Series(aligned, index=event_dates.index, name="trading_date")


def latest_known_value_asof(
    event_dates: pd.Series, known_dates: pd.DatetimeIndex, values: pd.Series
) -> pd.Series:
    """For each date in ``event_dates``, return the value from ``values``
    whose ``known_dates`` entry is the LATEST one on or before it --
    backward search, the mirror image of ``align_to_next_trading_day``.

    ``known_dates`` and ``values`` must be the same length and order (e.g.
    a shares-outstanding history's ``filed_date`` and
    ``shares_outstanding`` columns). Returns NaN for an event date before
    any known date -- nothing was knowable yet at that point.
    """
    order = np.argsort(known_dates.values if hasattr(known_dates, "values") else np.asarray(known_dates))
    sorted_dates = pd.DatetimeIndex(known_dates).values[order]
    sorted_values = pd.Series(values).to_numpy()[order]

    event_values = pd.DatetimeIndex(event_dates)
    positions = np.searchsorted(sorted_dates, event_values.values, side="right") - 1
    aligned = [sorted_values[pos] if pos >= 0 else float("nan") for pos in positions]
    return pd.Series(aligned, index=event_dates.index, name="latest_known_value")
