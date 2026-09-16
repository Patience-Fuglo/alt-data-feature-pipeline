import pandas as pd
import pytest

from alt_data_pipeline.alignment import align_to_next_trading_day, get_trading_days, latest_known_value_asof


@pytest.fixture(scope="module")
def real_trading_days():
    return get_trading_days("AAPL", start="2019-01-01", end="2024-12-31")


def test_trading_days_excludes_known_us_holidays(real_trading_days):
    for holiday in ["2023-12-25", "2023-07-04", "2023-01-01", "2023-11-23"]:
        assert pd.Timestamp(holiday) not in real_trading_days


def test_trading_days_are_ascending_and_unique(real_trading_days):
    assert real_trading_days.is_monotonic_increasing
    assert not real_trading_days.has_duplicates


def test_weekday_trading_day_maps_to_itself(real_trading_days):
    # 2023-07-03 is a real Monday trading day
    monday = pd.Series([pd.Timestamp("2023-07-03")])
    result = align_to_next_trading_day(monday, real_trading_days)
    assert result.iloc[0] == pd.Timestamp("2023-07-03")


def test_saturday_aligns_forward_to_the_following_monday(real_trading_days):
    saturday = pd.Series([pd.Timestamp("2023-07-01")])  # a real Saturday
    result = align_to_next_trading_day(saturday, real_trading_days)
    assert result.iloc[0] == pd.Timestamp("2023-07-03")  # the real next trading day
    assert result.iloc[0].day_name() == "Monday"


def test_holiday_aligns_forward_past_the_holiday(real_trading_days):
    # 2023-07-04 (Tuesday) was a real market holiday; next trading day is Wednesday 7-5
    holiday = pd.Series([pd.Timestamp("2023-07-04")])
    result = align_to_next_trading_day(holiday, real_trading_days)
    assert result.iloc[0] == pd.Timestamp("2023-07-05")


def test_date_after_calendar_end_returns_nat(real_trading_days):
    far_future = pd.Series([pd.Timestamp("2030-01-01")])
    result = align_to_next_trading_day(far_future, real_trading_days)
    assert pd.isna(result.iloc[0])


def test_date_before_calendar_start_raises(real_trading_days):
    too_early = pd.Series([pd.Timestamp("2000-01-01")])
    with pytest.raises(ValueError):
        align_to_next_trading_day(too_early, real_trading_days)


def test_preserves_original_series_index():
    days = get_trading_days("AAPL", start="2023-01-01", end="2023-12-31")
    events = pd.Series(
        [pd.Timestamp("2023-07-01"), pd.Timestamp("2023-07-03")], index=[42, 99]
    )
    result = align_to_next_trading_day(events, days)
    assert list(result.index) == [42, 99]


def test_real_apple_form4_filings_land_on_trading_days_within_the_calendar(real_trading_days):
    # real finding: EDGAR Form 4 filings for Apple never land on a weekend
    # in the observed history (business-day-only filing pattern) -- every
    # filing that falls inside our known calendar range should align to
    # itself. Filings after the calendar's end correctly come back NaT
    # (not yet known), so those are excluded here rather than counted as
    # mismatches.
    from alt_data_pipeline.ingestion import get_form4_filings

    filings = get_form4_filings("0000320193", "Apple Inc.")
    in_range = filings[
        (filings["filing_date"] >= real_trading_days.min())
        & (filings["filing_date"] <= real_trading_days.max())
    ]
    assert len(in_range) > 100  # sanity-check the filter actually kept real rows

    aligned = align_to_next_trading_day(in_range["filing_date"], real_trading_days)
    assert not aligned.isna().any()
    assert (aligned.values == in_range["filing_date"].values).all()


# ---- latest_known_value_asof: the mirror-image, backward-searching case ---


def _known_series():
    known_dates = pd.DatetimeIndex(["2024-01-01", "2024-04-01", "2024-07-01"])
    values = pd.Series([100, 200, 300])
    return known_dates, values


def test_exact_match_on_known_date_uses_that_dates_value():
    known_dates, values = _known_series()
    result = latest_known_value_asof(pd.Series([pd.Timestamp("2024-04-01")]), known_dates, values)
    assert result.iloc[0] == 200


def test_between_two_known_dates_uses_the_earlier_one_not_the_later():
    # this is the actual look-ahead-bias guard: 2024-05-15 is between the
    # April and July values -- it must use April's (100 -> 200 already
    # known by April), never peek forward to July's 300.
    known_dates, values = _known_series()
    result = latest_known_value_asof(pd.Series([pd.Timestamp("2024-05-15")]), known_dates, values)
    assert result.iloc[0] == 200


def test_before_any_known_date_returns_nan():
    known_dates, values = _known_series()
    result = latest_known_value_asof(pd.Series([pd.Timestamp("2023-01-01")]), known_dates, values)
    assert pd.isna(result.iloc[0])


def test_after_last_known_date_uses_the_latest_value_not_nan():
    # unlike align_to_next_trading_day (which returns NaT past its known
    # range, since a *future* trading day genuinely isn't knowable yet),
    # a slowly-changing value like shares outstanding is presumed to still
    # hold until a newer figure is published -- the latest known value is
    # the correct real-world answer, not "unknown."
    known_dates, values = _known_series()
    result = latest_known_value_asof(pd.Series([pd.Timestamp("2024-12-31")]), known_dates, values)
    assert result.iloc[0] == 300


def test_preserves_event_dates_index():
    known_dates, values = _known_series()
    events = pd.Series([pd.Timestamp("2024-04-01"), pd.Timestamp("2024-08-01")], index=[7, 3])
    result = latest_known_value_asof(events, known_dates, values)
    assert list(result.index) == [7, 3]


def test_real_apple_shares_outstanding_lookup_matches_verified_value():
    from alt_data_pipeline.ingestion.edgar_shares_outstanding import get_shares_outstanding

    shares = get_shares_outstanding("0000320193")
    # verified 2026-09-15: as of the 2026-09-11 short-interest publication
    # date, the most recently filed real figure was 14,594,180,000 (filed
    # 2026-07-31), not the newer or older ones on either side of it.
    result = latest_known_value_asof(
        pd.Series([pd.Timestamp("2026-09-11")]), shares["filed_date"], shares["shares_outstanding"]
    )
    assert result.iloc[0] == 14_594_180_000
