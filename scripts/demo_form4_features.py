"""Demo: all five Form 4 features on real Apple and Tesla purchase history.

Run: python scripts/demo_form4_features.py
"""

from __future__ import annotations

from alt_data_pipeline.features import engineer_form4_features
from alt_data_pipeline.ingestion.edgar_form4_bulk import get_all_form4_transactions

COLS = [
    "owner_name",
    "transaction_date",
    "purchase_size",
    "insider_role_score",
    "cluster_buying_count",
    "purchase_size_vs_own_history",
    "days_since_own_last_purchase",
]


def main() -> None:
    print("=" * 70)
    print("APPLE -- only one real insider buyer in the entire observable history")
    print("=" * 70)
    apple_txns = get_all_form4_transactions("0000320193", "Apple Inc.")
    apple_features = engineer_form4_features(apple_txns)
    print(apple_features[COLS].to_string(index=False))

    print()
    print("=" * 70)
    print("TESLA -- 6 distinct real insiders, including a real cluster event")
    print("=" * 70)
    tesla_txns = get_all_form4_transactions("0001318605", "Tesla Inc.")
    tesla_features = engineer_form4_features(tesla_txns)
    print(f"{len(tesla_features)} total real Code P purchases, {tesla_features['owner_name'].nunique()} distinct insiders")

    clustered = tesla_features[tesla_features["cluster_buying_count"] > 0]
    print(f"\n{len(clustered)} transactions with a real same-window cluster:")
    print(clustered[COLS].to_string(index=False))


if __name__ == "__main__":
    main()
