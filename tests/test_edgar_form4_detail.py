import pandas as pd
import pytest

from alt_data_pipeline.ingestion.edgar_form4_detail import _document_url, get_form4_transactions

# Three real, confirmed filings, each exercising a different real-world case:
APPLE_SALE = dict(
    cik="0000320193",
    accession_number="0001140361-26-036226",
    primary_document="xslF345X06/form4.xml",
)  # single Code S transaction, isOfficer encoded as "true"/"false"

TESLA_PURCHASES = dict(
    cik="0001318605",
    accession_number="0001104659-25-089693",
    primary_document="xslF345X05/tm2526050-1_4seq1.xml",
)  # 25 real Code P transactions same day, booleans encoded as "1"/"0"

APPLE_DERIVATIVE_ONLY = dict(
    cik="0000320193",
    accession_number="0000320193-25-000033",
    primary_document="xslF345X05/wk-form4_1740699194.xml",
)  # a real filing with no non-derivative (common stock) transactions


# ---- URL construction ------------------------------------------------------


def test_document_url_strips_xslt_viewer_subfolder():
    url = _document_url("320193", "0001140361-26-036226", "xslF345X06/form4.xml")
    assert url == "https://www.sec.gov/Archives/edgar/data/320193/000114036126036226/form4.xml"


def test_document_url_handles_already_bare_filename():
    url = _document_url("320193", "0001140361-26-036226", "form4.xml")
    assert url.endswith("/000114036126036226/form4.xml")


# ---- real filing parsing ---------------------------------------------------


def test_apple_sale_parses_correctly_with_true_false_booleans():
    df = get_form4_transactions(**APPLE_SALE)
    assert len(df) == 1
    row = df.iloc[0]
    assert row["owner_name"] == "Newstead Jennifer"
    assert row["is_officer"] is True or row["is_officer"] == True  # noqa: E712
    assert row["officer_title"] == "SVP, GC and Government Affairs"
    assert row["transaction_code"] == "S"
    assert row["shares"] == 1438
    assert row["price_per_share"] == pytest.approx(317.23)
    assert row["acquired_disposed_code"] == "D"


def test_tesla_purchases_parse_correctly_with_one_zero_booleans():
    # this is the real bug this test suite exists to catch: a filer using
    # "1"/"0" instead of "true"/"false" for the same boolean fields.
    df = get_form4_transactions(**TESLA_PURCHASES)
    assert len(df) == 25
    assert (df["owner_name"] == "Musk Elon").all()
    assert (df["is_officer"] == True).all()  # noqa: E712
    assert (df["is_director"] == True).all()  # noqa: E712
    assert (df["is_ten_percent_owner"] == True).all()  # noqa: E712
    assert (df["officer_title"] == "CEO").all()
    assert (df["transaction_code"] == "P").all()
    assert (df["acquired_disposed_code"] == "A").all()
    assert df["shares"].sum() > 2_000_000
    total_value = (df["shares"] * df["price_per_share"]).sum()
    assert total_value == pytest.approx(999_959_042.37, abs=1.0)


def test_transaction_date_is_real_datetime():
    df = get_form4_transactions(**TESLA_PURCHASES)
    assert pd.api.types.is_datetime64_any_dtype(df["transaction_date"])
    assert (df["transaction_date"] == pd.Timestamp("2025-09-12")).all()


def test_derivative_only_filing_returns_empty_dataframe_not_an_error():
    df = get_form4_transactions(**APPLE_DERIVATIVE_ONLY)
    assert len(df) == 0
    assert list(df.columns) == [
        "accession_number",
        "owner_name",
        "owner_cik",
        "is_officer",
        "is_director",
        "is_ten_percent_owner",
        "officer_title",
        "transaction_date",
        "transaction_code",
        "shares",
        "price_per_share",
        "acquired_disposed_code",
        "shares_owned_following",
    ]
