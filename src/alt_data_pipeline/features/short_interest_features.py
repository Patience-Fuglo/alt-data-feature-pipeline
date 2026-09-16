"""Short interest features -- how much the bearish bet against a stock
changed, and how big that bet really is once you account for company size.

Two of these were already sitting in the ingestion data (percent change,
days-to-cover) -- no new work needed, just named clearly as features here.
The third, percent of float, needs a genuinely new real ingredient: shares
outstanding, matched to each short-interest reading using a BACKWARD
as-of lookup (the most recently published share count as of the
short-interest publication date -- never a later one).
"""

from __future__ import annotations

import pandas as pd

from ..alignment import latest_known_value_asof

_RETURN_COLUMNS = [
    "symbol",
    "publication_date",
    "settlement_date",
    "current_short_interest",
    "percent_change_short_interest",
    "days_to_cover",
    "shares_outstanding",
    "percent_of_float",
]


def engineer_short_interest_features(
    short_interest: pd.DataFrame, shares_outstanding_history: pd.DataFrame
) -> pd.DataFrame:
    """Attach short-interest features to one symbol's short-interest rows.

    ``short_interest`` should already be filtered to a single symbol (from
    ``get_short_interest``, possibly across several publication dates).
    ``shares_outstanding_history`` is that same company's full real
    history from ``get_shares_outstanding``.

    Why raw % of float, not raw share counts: a small company's short
    interest jumping from 100k to 200k shares (100% raw increase) can look
    more dramatic than a giant's 40M-to-42M jump (only 5% raw increase),
    even when the giant's move represents a comparably large real bet.
    Normalizing by shares outstanding corrects that size distortion.
    """
    df = short_interest.copy()
    df["shares_outstanding"] = latest_known_value_asof(
        df["publication_date"], shares_outstanding_history["filed_date"], shares_outstanding_history["shares_outstanding"]
    )
    df["percent_of_float"] = df["current_short_interest"] / df["shares_outstanding"] * 100.0
    df = df.rename(columns={"short_interest_pct_change": "percent_change_short_interest"})
    return df[_RETURN_COLUMNS]
