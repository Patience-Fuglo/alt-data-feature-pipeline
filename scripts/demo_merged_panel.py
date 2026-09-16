"""Demo: the merged point-in-time panel, real Tesla data -- one row per
real trading day, both datasets' features forward-filled from their real
actionable date, the purchase-event flag zero-filled.

Run: python scripts/demo_merged_panel.py
"""

from __future__ import annotations

from alt_data_pipeline.alignment import get_trading_days
from alt_data_pipeline.features import build_merged_panel, engineer_form4_features, engineer_short_interest_features
from alt_data_pipeline.ingestion import get_shares_outstanding, get_short_interest_history
from alt_data_pipeline.ingestion.edgar_form4_bulk import get_all_form4_transactions

TESLA_CIK = "0001318605"
REAL_SI_DATES = [
    "20260415", "20260430", "20260515", "20260530", "20260615",
    "20260630", "20260715", "20260731", "20260814", "20260831",
]


def main() -> None:
    trading_days = get_trading_days("TSLA", start="2025-08-01", end="2026-09-15")

    form4_all = engineer_form4_features(get_all_form4_transactions(TESLA_CIK, "Tesla Inc."))
    form4 = form4_all[
        (form4_all["transaction_date"] >= trading_days.min()) & (form4_all["transaction_date"] <= trading_days.max())
    ]

    si_all = engineer_short_interest_features(
        get_short_interest_history("TSLA", REAL_SI_DATES), get_shares_outstanding(TESLA_CIK)
    )
    si = si_all[(si_all["publication_date"] >= trading_days.min()) & (si_all["publication_date"] <= trading_days.max())]

    panel = build_merged_panel(trading_days, form4, si)

    print(f"{len(panel)} rows -- one per real trading day, {panel['trading_date'].min().date()} -> {panel['trading_date'].max().date()}")
    print(f"\nNaN counts per column (leading gap before each dataset's first real observation):")
    print(panel.isna().sum().to_string())

    print("\nThe real purchase event day and the week around it:")
    event_idx = panel.index[panel["form4_purchase_event"] == 1][0]
    print(panel.iloc[max(0, event_idx - 1) : event_idx + 3].to_string(index=False))

    print("\nMost recent 3 rows -- forward-filled all the way from both datasets' last real observations:")
    print(panel.tail(3).to_string(index=False))


if __name__ == "__main__":
    main()
