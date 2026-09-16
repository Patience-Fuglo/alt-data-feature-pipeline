import pandas as pd
import pytest

from alt_data_pipeline.features import engineer_short_interest_features
from alt_data_pipeline.ingestion.edgar_shares_outstanding import get_shares_outstanding
from alt_data_pipeline.ingestion.finra_short_interest import get_short_interest_finra


@pytest.fixture(scope="module")
def real_apple_features():
    short_interest = get_short_interest_finra("20260831")
    apple_row = short_interest[short_interest["symbol"] == "AAPL"]
    shares = get_shares_outstanding("0000320193")
    return engineer_short_interest_features(apple_row, shares)


def test_returns_expected_columns(real_apple_features):
    assert list(real_apple_features.columns) == [
        "symbol",
        "publication_date",
        "settlement_date",
        "current_short_interest",
        "percent_change_short_interest",
        "days_to_cover",
        "shares_outstanding",
        "percent_of_float",
    ]
    assert len(real_apple_features) == 1


def test_percent_of_float_is_a_sane_real_value(real_apple_features):
    row = real_apple_features.iloc[0]
    # real AAPL short interest (~140M shares) against real shares
    # outstanding (~14.6B) should land in a small single-digit percent
    assert 0.5 < row["percent_of_float"] < 3.0


def test_percent_of_float_matches_manual_calculation(real_apple_features):
    row = real_apple_features.iloc[0]
    expected = row["current_short_interest"] / row["shares_outstanding"] * 100.0
    assert row["percent_of_float"] == pytest.approx(expected)


def test_shares_outstanding_used_is_the_correct_point_in_time_value(real_apple_features):
    # verified 2026-09-15: as of this short interest file's real
    # 2026-09-14 publication date, the most recently filed real shares
    # count was 14,594,180,000 (filed 2026-07-31) -- not a later one.
    assert real_apple_features.iloc[0]["shares_outstanding"] == 14_594_180_000


def test_percent_change_and_days_to_cover_pass_through_correctly(real_apple_features):
    row = real_apple_features.iloc[0]
    assert row["percent_change_short_interest"] == pytest.approx(20.133926, abs=1e-4)
    assert row["days_to_cover"] == pytest.approx(3.53)
