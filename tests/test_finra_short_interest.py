import pandas as pd
import pytest

from alt_data_pipeline.ingestion.finra_short_interest import DataUnavailableError, get_short_interest_finra

REAL_SETTLEMENT_DATE = "20260831"


@pytest.fixture(scope="module")
def real_data():
    return get_short_interest_finra(REAL_SETTLEMENT_DATE)


def test_returns_expected_columns(real_data):
    assert list(real_data.columns) == [
        "publication_date",
        "settlement_date",
        "symbol",
        "security_name",
        "exchange",
        "current_short_interest",
        "previous_short_interest",
        "avg_daily_volume",
        "days_to_cover",
        "short_interest_pct_change",
        "reported_pct_change",
    ]
    assert len(real_data) > 15000  # comprehensive, cross-exchange, thousands of real symbols


def test_covers_nasdaq_listed_megacaps_the_cboe_only_file_missed(real_data):
    # the whole reason this module exists: cboe_short_interest.py's real
    # BATS-listed-only file doesn't carry these at all.
    for symbol in ["AAPL", "TSLA", "NVDA", "MSFT"]:
        assert (real_data["symbol"] == symbol).sum() == 1


def test_publication_date_is_real_gap_after_settlement_date(real_data):
    gap_days = (real_data["publication_date"] - real_data["settlement_date"]).dt.days
    assert (gap_days == 14).all()
    assert (real_data["publication_date"] > real_data["settlement_date"]).all()


def test_publication_date_comes_from_response_header_not_filename():
    # the URL is settlement-date-named; publication_date must NOT just
    # equal that same date reinterpreted -- it has to be later, from the
    # real Last-Modified header.
    df = get_short_interest_finra(REAL_SETTLEMENT_DATE)
    assert df["publication_date"].iloc[0] != pd.Timestamp(
        f"{REAL_SETTLEMENT_DATE[:4]}-{REAL_SETTLEMENT_DATE[4:6]}-{REAL_SETTLEMENT_DATE[6:]}"
    )


def test_our_computed_pct_change_matches_finras_own_reported_value(real_data):
    with_data = real_data.dropna(subset=["short_interest_pct_change"])
    assert len(with_data) > 1000
    diff = (with_data["short_interest_pct_change"] - with_data["reported_pct_change"]).abs()
    assert diff.max() < 0.01


def test_zero_previous_short_interest_gives_nan_not_a_crash(real_data):
    zero_prev_rows = real_data[real_data["previous_short_interest"] == 0]
    assert len(zero_prev_rows) > 0
    assert zero_prev_rows["short_interest_pct_change"].isna().all()


def test_apple_short_interest_is_sane_real_value(real_data):
    aapl = real_data[real_data["symbol"] == "AAPL"].iloc[0]
    assert aapl["exchange"] == "R"  # real, confirmed exchange code for this file
    assert aapl["current_short_interest"] > 100_000_000  # real scale for AAPL
    assert aapl["reported_pct_change"] == pytest.approx(20.13)


def test_pre_migration_archived_file_raises_rather_than_lying():
    # real, confirmed 2026-09-16: FINRA bulk-migrated its archive to this
    # CDN on 2023-07-27 -- every pre-migration file's Last-Modified header
    # reflects that migration, not its real original publication date.
    # A real 2018 settlement file, checked directly: Last-Modified is
    # literally 2023-07-27, ~1,914 days after its real settlement date --
    # nowhere near the confirmed real ~14-day publication gap. Trusting it
    # would silently encode a false publication date rather than an
    # approximate one, so this must raise, not quietly return bad data.
    with pytest.raises(DataUnavailableError):
        get_short_interest_finra("20180430")


def test_guard_still_allows_a_second_real_recent_file():
    # confirms the guard isn't just permanently broken/over-firing --
    # a different real recent date still works normally.
    df = get_short_interest_finra("20260814")
    gap_days = (df["publication_date"] - df["settlement_date"]).dt.days
    assert (gap_days <= 45).all()
