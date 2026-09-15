"""Demo: real Cboe/FINRA short interest data, and the settlement-vs-
publication gap that matters for point-in-time research.

Run: python scripts/demo_cboe_short_interest.py
"""

from __future__ import annotations

from alt_data_pipeline.ingestion import get_short_interest

PUBLICATION_DATE = "20260911"


def main() -> None:
    df = get_short_interest(PUBLICATION_DATE)
    gap_days = (df["publication_date"] - df["settlement_date"]).dt.days.iloc[0]

    print(f"{len(df)} symbols reported in the {PUBLICATION_DATE} file")
    print(f"Settlement date: {df['settlement_date'].iloc[0].date()}")
    print(f"Publication date: {df['publication_date'].iloc[0].date()}")
    print(f"Gap: {gap_days} days -- data this old before the public could see it")

    print("\nLargest short-interest increases this cycle:")
    top = df.dropna(subset=["short_interest_pct_change"]).nlargest(5, "short_interest_pct_change")
    print(top[["symbol", "security_name", "current_short_interest", "short_interest_pct_change"]].to_string(index=False))


if __name__ == "__main__":
    main()
