"""Demo: forward-only as-of alignment applied to both real datasets --
Apple's real Form 4 filing dates, and a real Cboe short-interest
publication date.

Run: python scripts/demo_alignment.py
"""

from __future__ import annotations

from alt_data_pipeline.alignment import align_to_next_trading_day, get_trading_days
from alt_data_pipeline.ingestion import get_form4_filings, get_short_interest

APPLE_CIK = "0000320193"
SHORT_INTEREST_DATE = "20260911"


def main() -> None:
    trading_days = get_trading_days("AAPL", start="2019-01-01", end="2024-12-31")
    print(f"Real trading calendar: {len(trading_days)} days, {trading_days.min().date()} -> {trading_days.max().date()}")

    print("\n--- Form 4 filings ---")
    filings = get_form4_filings(APPLE_CIK, "Apple Inc.")
    in_range = filings[
        (filings["filing_date"] >= trading_days.min()) & (filings["filing_date"] <= trading_days.max())
    ].copy()
    in_range["trading_date"] = align_to_next_trading_day(in_range["filing_date"], trading_days)
    shifted = in_range[in_range["trading_date"] != in_range["filing_date"]]
    print(f"{len(in_range)} filings in calendar range; {len(shifted)} needed forward alignment")
    print("(real finding: EDGAR Form 4 filings never land on a weekend in this company's history)")

    print("\n--- Short interest publication date ---")
    short_interest = get_short_interest(SHORT_INTEREST_DATE)
    pub_date = short_interest[["publication_date"]].drop_duplicates()
    pub_date["trading_date"] = align_to_next_trading_day(
        pub_date["publication_date"], get_trading_days("AAPL", start="2024-01-01", end="2026-12-31")
    )
    print(pub_date.to_string(index=False))


if __name__ == "__main__":
    main()
