"""Short interest features -- how much the bearish bet against a stock
changed, how big that bet really is once you account for company size,
and whether it's unusual *for this stock specifically*.

Two of these were already sitting in the ingestion data (percent change,
days-to-cover) -- no new work needed, just named clearly as features here.
Percent of float needs shares outstanding, matched using a BACKWARD as-of
lookup (the most recently published share count as of the short-interest
publication date -- never a later one). Deviation from own baseline needs
the same symbol's real history across multiple cycles, and uses the same
point-in-time discipline as the Form 4 features: each cycle's baseline is
the mean of strictly EARLIER cycles only, never the current or future one.
"""

from __future__ import annotations

import pandas as pd

from ..alignment import latest_known_value_asof
from ..ingestion.edgar_company_info import get_company_sic

_RETURN_COLUMNS = [
    "symbol",
    "publication_date",
    "settlement_date",
    "current_short_interest",
    "percent_change_short_interest",
    "days_to_cover",
    "shares_outstanding",
    "percent_of_float",
    "deviation_from_own_baseline",
]


def engineer_short_interest_features(
    short_interest: pd.DataFrame, shares_outstanding_history: pd.DataFrame
) -> pd.DataFrame:
    """Attach short-interest features to one symbol's short-interest rows.

    ``short_interest`` should already be filtered to a single symbol (from
    ``get_short_interest_finra`` or ``get_short_interest_history``), one or
    more real cycles. ``shares_outstanding_history`` is that same
    company's full real history from ``get_shares_outstanding``.

    Why raw % of float, not raw share counts: a small company's short
    interest jumping from 100k to 200k shares (100% raw increase) can look
    more dramatic than a giant's 40M-to-42M jump (only 5% raw increase),
    even when the giant's move represents a comparably large real bet.
    Normalizing by shares outstanding corrects that size distortion.

    ``deviation_from_own_baseline`` needs at least one strictly-earlier
    cycle to compare against -- NaN on a symbol's first observed cycle.
    """
    df = short_interest.sort_values("publication_date").reset_index(drop=True).copy()

    df["shares_outstanding"] = latest_known_value_asof(
        df["publication_date"], shares_outstanding_history["filed_date"], shares_outstanding_history["shares_outstanding"]
    )
    df["percent_of_float"] = df["current_short_interest"] / df["shares_outstanding"] * 100.0
    df["deviation_from_own_baseline"] = _deviation_from_own_baseline(df["current_short_interest"])
    df = df.rename(columns={"short_interest_pct_change": "percent_change_short_interest"})
    return df[_RETURN_COLUMNS]


def find_sector_peers(target_cik: str, candidate_ciks: list[str]) -> list[str]:
    """Real, verified peers: candidates confirmed to share the target's
    exact real SIC code (Standard Industrial Classification), from EDGAR.

    Never assume a "well-known competitor" is a real sector peer without
    checking -- SIC codes are coarser and narrower than they sound. Real
    example: Apple (SIC 3571, Electronic Computers) and Dell share the
    exact code; Microsoft, Alphabet, Cisco, and several other plausible-
    sounding "tech peers" checked do not.
    """
    target_sic, _ = get_company_sic(target_cik)
    peers = []
    for cik in candidate_ciks:
        sic, _ = get_company_sic(cik)
        if sic == target_sic:
            peers.append(cik)
    return peers


def sector_divergence(target_pct_change: float, peer_pct_changes: list[float]) -> float:
    """``target_pct_change`` minus the mean of ``peer_pct_changes`` for the
    same real cycle.

    Positive: the target's short interest rose more than its verified
    sector peers -- a stock-specific signal. Near zero: moving with the
    sector as a whole, not a targeted bet against this one company. NaN
    if no real peers were found for this SIC code.
    """
    if not peer_pct_changes:
        return float("nan")
    return target_pct_change - (sum(peer_pct_changes) / len(peer_pct_changes))


def _deviation_from_own_baseline(current_short_interest: pd.Series) -> pd.Series:
    """Each cycle's value divided by the mean of all STRICTLY EARLIER
    cycles (assumes ``current_short_interest`` is already sorted
    chronologically ascending for a single symbol). NaN for the first
    observed cycle -- no prior baseline exists yet."""
    result = pd.Series(index=current_short_interest.index, dtype=float)
    prior_values: list[float] = []
    for i, value in current_short_interest.items():
        result.loc[i] = value / (sum(prior_values) / len(prior_values)) if prior_values else float("nan")
        prior_values.append(value)
    return result
