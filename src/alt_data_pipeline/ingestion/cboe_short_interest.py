"""Real Cboe/FINRA short interest ingestion.

Cboe publishes FINRA's bi-monthly short interest report as a free CSV. The
file is named for the date it was *published*, but every row inside it
reports counts as of an earlier *settlement* date -- the count actually
happened on the settlement date, and only became public knowledge on the
publication date. Confirmed real gap: a file published 2026-09-11 carried
settlement-date-2026-08-31 data, an 11-day lag. Point-in-time research has
to merge on publication date, never settlement date, or it's using
information before the market could have actually known it.
"""

from __future__ import annotations

from io import StringIO

import pandas as pd
import requests

_SHORT_INTEREST_URL = (
    "https://cdn.cboe.com/resources/us/equities/market-statistics/short-interest/"
    "Bats_Listed_Short_Interest-finra-{date_str}.csv"
)

_RETURN_COLUMNS = [
    "publication_date",
    "settlement_date",
    "symbol",
    "security_name",
    "current_short_interest",
    "previous_short_interest",
    "avg_daily_volume",
    "days_to_cover",
    "short_interest_pct_change",
    "reported_pct_change",
]


def get_short_interest(date_str: str) -> pd.DataFrame:
    """Fetch real Cboe/FINRA short interest data published on ``date_str``.

    ``date_str`` is the *publication* date of the file ("YYYYMMDD",
    matching Cboe's file-naming convention) -- not the settlement date
    reported inside each row, which is typically ~11 days earlier.

    Returns a DataFrame with both dates kept as separate columns (so a
    downstream join can deliberately choose publication date, per the
    point-in-time discipline above), plus per-symbol short interest counts
    and a ``short_interest_pct_change`` column computed here directly from
    the current/previous share counts (Cboe's own ``reported_pct_change``
    is kept alongside it as an independent cross-check, not the source of
    truth).
    """
    url = _SHORT_INTEREST_URL.format(date_str=date_str)
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()

    raw = pd.read_csv(StringIO(resp.text))
    df = pd.DataFrame(
        {
            "publication_date": pd.to_datetime(date_str, format="%Y%m%d"),
            "settlement_date": pd.to_datetime(raw["Cycle Settlement Date"], format="%Y%m%d"),
            "symbol": raw["BATS-Symbol"],
            "security_name": raw["Security Name"],
            "current_short_interest": raw["# Shares Net Short Current Cycle"].astype(float),
            "previous_short_interest": raw["# Shares Net Short Previous Cycle"].astype(float),
            "avg_daily_volume": raw["Cycle Avg Daily Trade Vol"].astype(float),
            "days_to_cover": raw["Min # of Trade Days To Cover Shorts"].astype(float),
            "reported_pct_change": raw["Percent Change in Short Position"].astype(float),
        }
    )

    prev = df["previous_short_interest"]
    df["short_interest_pct_change"] = (
        (df["current_short_interest"] - prev) / prev * 100.0
    ).where(prev != 0)

    return df[_RETURN_COLUMNS]
