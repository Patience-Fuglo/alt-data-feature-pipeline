"""Real short-interest history for one symbol across multiple real cycles.

FINRA publishes bi-monthly; a single snapshot can't say whether today's
number is unusual *for this stock specifically* -- that needs its own
real history to compare against.
"""

from __future__ import annotations

import pandas as pd

from .finra_short_interest import get_short_interest_finra


def get_short_interest_history(symbol: str, settlement_dates: list[str]) -> pd.DataFrame:
    """Real short-interest rows for ``symbol`` across each date in
    ``settlement_dates`` ("YYYYMMDD", FINRA's settlement-date file naming).

    Dates with no data for the symbol, or that don't correspond to a real
    settlement cycle, are silently skipped rather than erroring -- not
    every "15th or end of month" guess lands on an actual real cycle.
    """
    rows = []
    for date_str in settlement_dates:
        try:
            day = get_short_interest_finra(date_str)
        except Exception:
            continue
        match = day[day["symbol"] == symbol]
        if len(match):
            rows.append(match)

    if not rows:
        raise ValueError(f"No real short-interest history found for {symbol} in the given dates.")

    return pd.concat(rows, ignore_index=True).sort_values("publication_date").reset_index(drop=True)
