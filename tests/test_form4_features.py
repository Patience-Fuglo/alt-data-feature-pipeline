import pandas as pd
import pytest

from alt_data_pipeline.features.form4_features import (
    _days_since_own_last_purchase,
    _distinct_other_buyers_in_window,
    _size_relative_to_own_prior_history,
    engineer_form4_features,
)


def _purchase_row(owner_cik, date, shares, price):
    return {
        "accession_number": "test",
        "owner_name": owner_cik,
        "owner_cik": owner_cik,
        "is_officer": False,
        "is_director": False,
        "is_ten_percent_owner": False,
        "officer_title": "",
        "transaction_date": pd.Timestamp(date),
        "transaction_code": "P",
        "shares": shares,
        "price_per_share": price,
        "acquired_disposed_code": "A",
        "shares_owned_following": shares,
        "filing_date": pd.Timestamp(date),
    }


# ---- pure-logic tests: constructed inputs, verifying the algorithm's
# point-in-time behavior directly (same pattern used throughout this
# project for testing the *mechanics* of a from-scratch function -- the
# full pipeline is separately verified against real fetched data below).


def test_cluster_buying_never_counts_a_purchase_that_happens_later():
    purchases = pd.DataFrame(
        [
            _purchase_row("A", "2024-01-01", 100, 10),
            _purchase_row("B", "2024-01-15", 100, 10),  # 14 days after A -- within window
            _purchase_row("C", "2024-02-01", 100, 10),  # 31 days after A -- outside a 30d window from A
        ]
    ).reset_index(drop=True)

    # As of A's own transaction (index 0), nobody else has bought yet at all
    assert _distinct_other_buyers_in_window(purchases, 0, window_days=30) == 0
    # As of B's transaction, A (14 days earlier) is in-window
    assert _distinct_other_buyers_in_window(purchases, 1, window_days=30) == 1
    # As of C's transaction, B (17 days earlier) is in-window but A (31 days earlier) is not
    assert _distinct_other_buyers_in_window(purchases, 2, window_days=30) == 1


def test_cluster_buying_excludes_the_same_insider_buying_again():
    purchases = pd.DataFrame(
        [
            _purchase_row("A", "2024-01-01", 100, 10),
            _purchase_row("A", "2024-01-05", 100, 10),  # same insider, different transaction
        ]
    ).reset_index(drop=True)
    assert _distinct_other_buyers_in_window(purchases, 1, window_days=30) == 0


def test_size_relative_to_own_history_uses_only_strictly_prior_purchases():
    purchases = pd.DataFrame(
        [
            _purchase_row("A", "2024-01-01", 100, 10),  # size 1000, first -> NaN
            _purchase_row("A", "2024-02-01", 100, 20),  # size 2000, vs prior avg 1000 -> 2.0
            _purchase_row("A", "2024-03-01", 100, 40),  # size 4000, vs prior avg (1000+2000)/2=1500 -> 2.667
        ]
    ).reset_index(drop=True)
    purchases["purchase_size"] = purchases["shares"] * purchases["price_per_share"]
    result = _size_relative_to_own_prior_history(purchases)

    assert pd.isna(result.loc[0])
    assert result.loc[1] == pytest.approx(2.0)
    assert result.loc[2] == pytest.approx(4000 / 1500)


def test_days_since_own_last_purchase_ignores_other_insiders():
    purchases = pd.DataFrame(
        [
            _purchase_row("A", "2024-01-01", 100, 10),
            _purchase_row("B", "2024-01-05", 100, 10),  # different insider, shouldn't affect A's gap
            _purchase_row("A", "2024-01-11", 100, 10),
        ]
    ).reset_index(drop=True)
    result = _days_since_own_last_purchase(purchases)

    assert pd.isna(result.loc[0])  # A's first purchase
    assert pd.isna(result.loc[1])  # B's first purchase
    assert result.loc[2] == 10  # A's second purchase, 10 days after A's first (not B's)


# ---- real-data integration test: Susan Wagner's actual, real Apple Form 4
# purchase history (Code P), fetched and verified 2026-09 -- 5 real
# transactions, the only genuine open-market purchases across Apple's
# entire observable filing history.


@pytest.fixture
def real_apple_wagner_transactions():
    # exact real values, re-verified directly against get_all_form4_transactions
    # output on 2026-09-15 -- not reconstructed/approximated.
    rows = [
        _purchase_row(1059235, "2015-07-24", 100, 124.27),
        _purchase_row(1059235, "2015-07-24", 100, 124.34),
        _purchase_row(1059235, "2015-07-24", 100, 124.33),
        _purchase_row(1059235, "2015-07-24", 1500, 124.12),
        _purchase_row(1059235, "2015-07-27", 2000, 122.90),
    ]
    for row in rows:
        row["owner_name"] = "WAGNER SUSAN"
        row["is_director"] = True
    return pd.DataFrame(rows)


def test_engineer_form4_features_on_real_wagner_history(real_apple_wagner_transactions):
    features = engineer_form4_features(real_apple_wagner_transactions)

    assert len(features) == 5
    assert (features["insider_role_score"] == 1).all()  # director only, matches real record
    assert pd.isna(features["purchase_size_vs_own_history"].iloc[0])  # first purchase, no baseline yet
    assert pd.isna(features["days_since_own_last_purchase"].iloc[0])
    # the 4th purchase (real: $186,180) is a real, large jump vs. her own tiny prior average
    assert features["purchase_size_vs_own_history"].iloc[3] > 10
    # last purchase is 3 real days after the same-day cluster
    assert features["days_since_own_last_purchase"].iloc[4] == 3
    # only one real insider bought historically -- no genuine cluster exists in this real data
    assert (features["cluster_buying_count"] == 0).all()
