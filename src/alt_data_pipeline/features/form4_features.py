"""The five Form 4 features -- each one a proxy for how much genuine
conviction, not routine paperwork, sits behind an insider's purchase.

Every feature here is computed only from information available strictly
*before* the transaction it describes -- the same point-in-time discipline
this whole project applies everywhere else (purged walk-forward's embargo,
the as-of join's forward-only search), now applied to feature engineering
itself. A naive version of "how many other insiders recently bought" or
"how does this compare to their own history" could easily peek at data
from *after* the transaction date without realizing it -- that would be
look-ahead bias baked directly into a feature, not just a validation
split.
"""

from __future__ import annotations

import pandas as pd

# Officer weighted highest: an officer (CEO, CFO, etc.) sees day-to-day
# operations; a director typically only reviews periodic summaries. A
# >10%-owner stake reflects aligned incentive, not necessarily operational
# insight, so it's weighted like a director. This is one reasonable,
# explainable scheme, not the only valid one -- documented as a choice.
_ROLE_WEIGHTS = {"is_officer": 2, "is_director": 1, "is_ten_percent_owner": 1}


def engineer_form4_features(transactions: pd.DataFrame, cluster_window_days: int = 30) -> pd.DataFrame:
    """Given a company's full real transaction history (all codes, from
    ``get_all_form4_transactions``), return one row per genuine open-market
    purchase (Code P) with all five features attached.

    Columns added: ``purchase_size``, ``insider_role_score``,
    ``cluster_buying_count``, ``purchase_size_vs_own_history``,
    ``days_since_own_last_purchase``.
    """
    purchases = transactions[transactions["transaction_code"] == "P"].copy()
    purchases = purchases.sort_values("transaction_date").reset_index(drop=True)

    purchases["purchase_size"] = purchases["shares"] * purchases["price_per_share"]

    purchases["insider_role_score"] = sum(
        purchases[col].astype(int) * weight for col, weight in _ROLE_WEIGHTS.items()
    )

    purchases["cluster_buying_count"] = [
        _distinct_other_buyers_in_window(purchases, i, cluster_window_days)
        for i in range(len(purchases))
    ]

    purchases["purchase_size_vs_own_history"] = _size_relative_to_own_prior_history(purchases)
    purchases["days_since_own_last_purchase"] = _days_since_own_last_purchase(purchases)

    return purchases


def _distinct_other_buyers_in_window(purchases: pd.DataFrame, i: int, window_days: int) -> int:
    """Count of DIFFERENT insiders (by owner_cik) whose own Code P purchase
    falls in [this transaction's date - window_days, this transaction's
    date] -- strictly on or before, never after, so this never uses
    information from the future relative to row ``i``."""
    row = purchases.iloc[i]
    window_start = row["transaction_date"] - pd.Timedelta(days=window_days)
    in_window = purchases[
        (purchases["transaction_date"] >= window_start)
        & (purchases["transaction_date"] <= row["transaction_date"])
        & (purchases["owner_cik"] != row["owner_cik"])
    ]
    return in_window["owner_cik"].nunique()


def _size_relative_to_own_prior_history(purchases: pd.DataFrame) -> pd.Series:
    """Each purchase's dollar size divided by that same insider's own
    average purchase size from STRICTLY EARLIER purchases only (an
    expanding, point-in-time mean -- never including the current row or
    anything after it). NaN for an insider's first observed purchase,
    since there's no prior baseline to compare against yet."""
    result = pd.Series(index=purchases.index, dtype=float)
    seen_sizes: dict[str, list[float]] = {}
    for i, row in purchases.iterrows():
        owner = row["owner_cik"]
        prior = seen_sizes.get(owner, [])
        result.loc[i] = row["purchase_size"] / (sum(prior) / len(prior)) if prior else float("nan")
        seen_sizes.setdefault(owner, []).append(row["purchase_size"])
    return result


def _days_since_own_last_purchase(purchases: pd.DataFrame) -> pd.Series:
    """Days since that same insider's own previous Code P purchase. NaN
    for their first observed purchase."""
    result = pd.Series(index=purchases.index, dtype=float)
    last_seen: dict[str, pd.Timestamp] = {}
    for i, row in purchases.iterrows():
        owner = row["owner_cik"]
        prev_date = last_seen.get(owner)
        result.loc[i] = (row["transaction_date"] - prev_date).days if prev_date is not None else float("nan")
        last_seen[owner] = row["transaction_date"]
    return result
