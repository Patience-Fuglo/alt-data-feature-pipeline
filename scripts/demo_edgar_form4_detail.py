"""Demo: real Form 4 transaction detail -- what a filing list alone can't show.

Run: python scripts/demo_edgar_form4_detail.py
"""

from __future__ import annotations

from alt_data_pipeline.ingestion import get_form4_transactions

# A real, large, publicly known Tesla filing: 25 open-market purchases
# (Code P) by Elon Musk on a single day.
TESLA_CIK = "0001318605"
TESLA_ACCESSION = "0001104659-25-089693"
TESLA_DOCUMENT = "xslF345X05/tm2526050-1_4seq1.xml"


def main() -> None:
    txns = get_form4_transactions(TESLA_CIK, TESLA_ACCESSION, TESLA_DOCUMENT)
    purchases = txns[txns["transaction_code"] == "P"]

    print(f"{len(txns)} transactions parsed from one real filing")
    print(f"Owner: {txns['owner_name'].iloc[0]}  |  Title: {txns['officer_title'].iloc[0]}")
    print(f"Officer: {txns['is_officer'].iloc[0]}  Director: {txns['is_director'].iloc[0]}  "
          f">10% owner: {txns['is_ten_percent_owner'].iloc[0]}")

    total_shares = purchases["shares"].sum()
    total_value = (purchases["shares"] * purchases["price_per_share"]).sum()
    print(f"\n{len(purchases)} genuine open-market purchases (Code P)")
    print(f"Total shares: {total_shares:,.0f}")
    print(f"Total dollar value: ${total_value:,.2f}")


if __name__ == "__main__":
    main()
