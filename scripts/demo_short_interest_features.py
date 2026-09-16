"""Demo: percent-of-float on real Apple/Tesla/NVIDIA/Microsoft short
interest, correcting for company size the way raw share counts can't.

Run: python scripts/demo_short_interest_features.py
"""

from __future__ import annotations

from alt_data_pipeline.features import engineer_short_interest_features
from alt_data_pipeline.ingestion import get_shares_outstanding, get_short_interest_finra

CIKS = {
    "AAPL": "0000320193",
    "TSLA": "0001318605",
    "NVDA": "0001045810",
    "MSFT": "0000789019",
}
SETTLEMENT_DATE = "20260831"


def main() -> None:
    short_interest = get_short_interest_finra(SETTLEMENT_DATE)

    for symbol, cik in CIKS.items():
        row = short_interest[short_interest["symbol"] == symbol]
        shares = get_shares_outstanding(cik)
        features = engineer_short_interest_features(row, shares)
        r = features.iloc[0]
        print(
            f"{symbol}: short interest {r['current_short_interest']:,.0f} shares "
            f"({r['percent_change_short_interest']:+.2f}% vs. prior cycle), "
            f"{r['days_to_cover']:.2f} days to cover, "
            f"{r['percent_of_float']:.3f}% of float "
            f"(shares outstanding: {r['shares_outstanding']:,.0f})"
        )


if __name__ == "__main__":
    main()
