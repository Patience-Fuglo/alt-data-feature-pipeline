import pandas as pd
import pytest

from alt_data_pipeline.ingestion.cboe_short_interest import get_short_interest

# A real, confirmed-working publication date. Cboe drops old files
# eventually, so if this ever starts failing, it likely needs bumping to a
# more recent real date, not a synthetic/mocked replacement.
REAL_PUBLICATION_DATE = "20260911"


@pytest.fixture(scope="module")
def real_data():
    return get_short_interest(REAL_PUBLICATION_DATE)


def test_returns_expected_columns(real_data):
    assert list(real_data.columns) == [
        "publication_date",
        "settlement_date",
        "symbol",
        "security_name",
        "current_short_interest",
        "previous_short_interest",
        "avg_daily_volume",
        "days_to_cover",
        "short_interest_pct_change",
        "reported_pct_change",
    ]
    assert len(real_data) > 100  # thousands of listed symbols report each cycle


def test_publication_date_matches_input(real_data):
    assert (real_data["publication_date"] == pd.Timestamp("2026-09-11")).all()


def test_settlement_date_is_earlier_than_publication_date(real_data):
    # the core point-in-time fact this module exists to preserve: the count
    # happened before the public could see it, never the other way around
    assert (real_data["settlement_date"] < real_data["publication_date"]).all()


def test_real_settlement_publication_gap_is_eleven_days(real_data):
    gap_days = (real_data["publication_date"] - real_data["settlement_date"]).dt.days
    assert (gap_days == 11).all()


def test_our_computed_pct_change_matches_cboes_own_reported_value(real_data):
    with_data = real_data.dropna(subset=["short_interest_pct_change"])
    assert len(with_data) > 0
    diff = (with_data["short_interest_pct_change"] - with_data["reported_pct_change"]).abs()
    assert diff.max() < 0.01  # sub-cent rounding difference only


def test_zero_previous_short_interest_gives_nan_not_a_crash(real_data):
    zero_prev_rows = real_data[real_data["previous_short_interest"] == 0]
    assert len(zero_prev_rows) > 0  # confirm this real edge case actually occurs in the data
    assert zero_prev_rows["short_interest_pct_change"].isna().all()
