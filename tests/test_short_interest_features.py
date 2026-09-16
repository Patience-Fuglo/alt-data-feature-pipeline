import pandas as pd
import pytest

from alt_data_pipeline.features import (
    engineer_short_interest_features,
    find_sector_peers,
    sector_divergence,
)
from alt_data_pipeline.ingestion.edgar_shares_outstanding import get_shares_outstanding
from alt_data_pipeline.ingestion.finra_short_interest import get_short_interest_finra
from alt_data_pipeline.ingestion.finra_short_interest_history import get_short_interest_history

APPLE_CIK = "0000320193"


@pytest.fixture(scope="module")
def real_apple_features():
    short_interest = get_short_interest_finra("20260831")
    apple_row = short_interest[short_interest["symbol"] == "AAPL"]
    shares = get_shares_outstanding(APPLE_CIK)
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
        "deviation_from_own_baseline",
    ]
    assert len(real_apple_features) == 1


def test_single_cycle_has_no_baseline_yet(real_apple_features):
    assert pd.isna(real_apple_features.iloc[0]["deviation_from_own_baseline"])


# ---- deviation from own baseline, real multi-cycle Apple history --------


REAL_DATES = ["20260415", "20260430", "20260515", "20260615", "20260630", "20260715", "20260731", "20260814", "20260831"]


@pytest.fixture(scope="module")
def real_apple_multi_cycle_features():
    history = get_short_interest_history("AAPL", REAL_DATES)
    shares = get_shares_outstanding(APPLE_CIK)
    return engineer_short_interest_features(history, shares)


def test_first_real_cycle_has_no_baseline(real_apple_multi_cycle_features):
    assert pd.isna(real_apple_multi_cycle_features.iloc[0]["deviation_from_own_baseline"])


def test_later_cycles_have_a_real_baseline_deviation(real_apple_multi_cycle_features):
    later = real_apple_multi_cycle_features.iloc[1:]
    assert not later["deviation_from_own_baseline"].isna().any()


def test_baseline_deviation_matches_manual_calculation(real_apple_multi_cycle_features):
    df = real_apple_multi_cycle_features
    # 3rd real cycle's baseline should be the mean of cycles 0 and 1 only
    manual_baseline = df["current_short_interest"].iloc[:2].mean()
    expected = df["current_short_interest"].iloc[2] / manual_baseline
    assert df["deviation_from_own_baseline"].iloc[2] == pytest.approx(expected)


# ---- sector peers and divergence, real SIC-verified data -----------------


def test_find_sector_peers_confirms_dell_excludes_unrelated_tech():
    # real, verified 2026-09-16: Dell shares Apple's exact SIC (3571);
    # Microsoft, Alphabet, and Cisco, despite being plausible "tech
    # peers," do not share the exact code.
    candidates = ["0000826083", "0001652044", "0000789019", "0000858877"]  # Dell, Alphabet, MSFT, Cisco
    peers = find_sector_peers(APPLE_CIK, candidates)
    assert peers == ["0000826083"]


def test_sector_divergence_matches_manual_calculation():
    si = get_short_interest_finra("20260831")
    aapl_pct = si[si["symbol"] == "AAPL"]["short_interest_pct_change"].iloc[0]
    dell_pct = si[si["symbol"] == "DELL"]["short_interest_pct_change"].iloc[0]

    result = sector_divergence(aapl_pct, [dell_pct])
    assert result == pytest.approx(aapl_pct - dell_pct)
    assert result > 0  # real result: AAPL's short interest rose far more than its verified peer


def test_sector_divergence_with_no_peers_returns_nan():
    assert pd.isna(sector_divergence(10.0, []))


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
