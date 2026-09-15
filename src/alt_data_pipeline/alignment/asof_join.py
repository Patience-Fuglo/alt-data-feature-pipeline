"""Forward-only as-of alignment: map an event date to the next real trading
day on or after it.

A filing dated Saturday doesn't become actionable on Saturday -- markets
are closed. A naive exact-date merge against price data would silently
drop that row (no match) rather than erroring, hiding a systematic gap:
weekend-adjacent events vanish from the dataset, every time, unnoticed.
The fix finds the *next available* trading day instead of demanding an
exact match -- forward only. A backward match would pair the event with a
price from *before* the event was even public -- look-ahead bias, not a
convenience.
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
