import pandas as pd
import pytest

from alt_data_pipeline.ingestion.edgar_shares_outstanding import get_shares_outstanding

APPLE_CIK = "0000320193"


def test_returns_expected_columns():
    df = get_shares_outstanding(APPLE_CIK)
    assert list(df.columns) == ["as_of_date", "filed_date", "shares_outstanding", "form", "accession_number"]
    assert len(df) > 10  # years of real quarterly/annual filings


def test_filed_date_is_after_as_of_date():
    # the real point-in-time gap this module exists to preserve: the
    # measurement always precedes when the public could see it.
    df = get_shares_outstanding(APPLE_CIK)
    assert (df["filed_date"] >= df["as_of_date"]).all()
    assert (df["filed_date"] > df["as_of_date"]).mean() > 0.9  # nearly always a real gap, not same-day


def test_sorted_by_filed_date_ascending():
    df = get_shares_outstanding(APPLE_CIK)
    assert df["filed_date"].is_monotonic_increasing


def test_recent_shares_outstanding_is_real_scale_for_apple():
    # only recent, safely-post-split history is asserted here -- real
    # Apple corporate actions changed the scale twice in this dataset
    # (found by checking, not assumed): shares outstanding was ~900M in
    # the early 2010s, then a real 4-for-1 split in 2020 moved the range
    # from ~4.3B to ~17B overnight (2020-07-31 filing: 4,275,634,000;
    # 2020-10-30 filing: 17,001,802,000). Asserting a fixed range across
    # the whole history would be a false assumption about real data.
    df = get_shares_outstanding(APPLE_CIK)
    recent = df[df["filed_date"] >= "2021-01-01"]
    assert len(recent) > 5
    assert (recent["shares_outstanding"] > 10_000_000_000).all()
    assert (recent["shares_outstanding"] < 20_000_000_000).all()


def test_accepts_unpadded_cik():
    padded = get_shares_outstanding("0000320193")
    unpadded = get_shares_outstanding("320193")
    assert len(padded) == len(unpadded)
