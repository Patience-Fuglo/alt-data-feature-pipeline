import pytest

from alt_data_pipeline.ingestion.finra_short_interest_history import get_short_interest_history

REAL_DATES = ["20260415", "20260430", "20260515", "20260530", "20260615", "20260630"]


def test_returns_real_multi_cycle_history_for_apple():
    history = get_short_interest_history("AAPL", REAL_DATES)
    assert (history["symbol"] == "AAPL").all()
    assert len(history) >= 4  # a few of these real dates aren't real settlement cycles


def test_skips_dates_that_are_not_real_settlement_cycles():
    # 2026-05-30 is a real, confirmed non-cycle (returns HTTP 403) --
    # should be silently skipped, not raise.
    history = get_short_interest_history("AAPL", REAL_DATES)
    assert len(history) < len(REAL_DATES)


def test_sorted_by_publication_date_ascending():
    history = get_short_interest_history("AAPL", REAL_DATES)
    assert history["publication_date"].is_monotonic_increasing


def test_raises_when_symbol_has_no_data_in_any_given_date():
    with pytest.raises(ValueError):
        get_short_interest_history("THIS_SYMBOL_DOES_NOT_EXIST_XYZ", REAL_DATES)
