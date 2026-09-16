"""The merged point-in-time panel: one row per real trading day, both
datasets' features aligned onto it and filled to match what each feature
actually represents.

Form 4 events and short-interest reports each happen on their own sparse
schedule -- a handful of days a year, a report every two weeks -- but a
model needs a value every trading day. The fix isn't "fill with zero
everywhere"; it's matching the fill strategy to what the feature means:

- An ongoing-state feature (purchase size, insider role, % of float,
  deviation from baseline...) genuinely still holds until a newer
  observation replaces it -- forward-fill.
- A specific-day event flag ("did a purchase happen today") genuinely
  didn't happen on days with no purchase -- zero-fill, never forward-fill,
  or every day after one real purchase would falsely claim a new one.

Everything is placed using each feature's real *actionable* trading date
(via the same forward as-of alignment built earlier), not its raw event
date -- a Saturday purchase's influence starts Monday, not Saturday.
"""

from __future__ import annotations

import pandas as pd

from ..alignment import align_to_next_trading_day

_FORM4_FORWARD_FILL_COLS = [
    "purchase_size",
    "insider_role_score",
    "cluster_buying_count",
    "purchase_size_vs_own_history",
    "days_since_own_last_purchase",
]

_SHORT_INTEREST_FORWARD_FILL_COLS = [
    "percent_change_short_interest",
    "days_to_cover",
    "percent_of_float",
    "deviation_from_own_baseline",
]


def build_merged_panel(
    trading_days: pd.DatetimeIndex,
    form4_features: pd.DataFrame,
    short_interest_features: pd.DataFrame,
) -> pd.DataFrame:
    """One row per real trading day, both feature sets merged in.

    ``form4_features`` is ``engineer_form4_features``'s output (needs a
    ``transaction_date`` column). ``short_interest_features`` is
    ``engineer_short_interest_features``'s output (needs
    ``publication_date``). Both get aligned to their real actionable
    trading date internally -- callers pass the raw feature output, not
    pre-aligned data.

    Rows before either dataset's first real observation are left NaN,
    deliberately -- forward-fill cannot manufacture information that
    didn't exist yet, and filling it with 0 would falsely claim "verified
    no activity" for a period we simply have no data for at all.
    """
    panel = pd.DataFrame(index=pd.DatetimeIndex(trading_days, name="trading_date"))

    f4 = form4_features.copy()
    f4["trading_date"] = align_to_next_trading_day(f4["transaction_date"], trading_days)
    f4_daily = f4.set_index("trading_date")[_FORM4_FORWARD_FILL_COLS]
    f4_daily = f4_daily[~f4_daily.index.duplicated(keep="last")]

    panel = panel.join(f4_daily.add_prefix("form4_"))
    panel[[f"form4_{c}" for c in _FORM4_FORWARD_FILL_COLS]] = panel[
        [f"form4_{c}" for c in _FORM4_FORWARD_FILL_COLS]
    ].ffill()

    panel["form4_purchase_event"] = panel.index.isin(f4["trading_date"]).astype(int)

    si = short_interest_features.copy()
    si["trading_date"] = align_to_next_trading_day(si["publication_date"], trading_days)
    si_daily = si.set_index("trading_date")[_SHORT_INTEREST_FORWARD_FILL_COLS]
    si_daily = si_daily[~si_daily.index.duplicated(keep="last")]

    panel = panel.join(si_daily.add_prefix("short_interest_"))
    panel[[f"short_interest_{c}" for c in _SHORT_INTEREST_FORWARD_FILL_COLS]] = panel[
        [f"short_interest_{c}" for c in _SHORT_INTEREST_FORWARD_FILL_COLS]
    ].ffill()

    return panel.reset_index()
