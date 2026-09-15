"""Demo: real SEC EDGAR Form 4 filing history for a real company.

Run: python scripts/demo_edgar_form4.py
"""

from __future__ import annotations

from alt_data_pipeline.ingestion import get_form4_filings

APPLE_CIK = "0000320193"


def main() -> None:
    filings = get_form4_filings(APPLE_CIK, "Apple Inc.")
    print(f"{len(filings)} Form 4 filings found for Apple Inc.")
    print(f"Range: {filings['filing_date'].min().date()} -> {filings['filing_date'].max().date()}")
    print("\nMost recent 10:")
    print(filings.tail(10).to_string(index=False))


if __name__ == "__main__":
    main()
