import pandas as pd
import pytest

from alt_data_pipeline.ingestion.edgar_form4 import _normalize_cik, get_form4_filings

APPLE_CIK = "0000320193"


# ---- pure logic: CIK normalization ---------------------------------------


def test_normalize_cik_pads_short_number():
    assert _normalize_cik("320193") == "0000320193"


def test_normalize_cik_accepts_already_padded():
    assert _normalize_cik("0000320193") == "0000320193"


def test_normalize_cik_strips_non_digit_characters():
    assert _normalize_cik("CIK0000320193") == "0000320193"


def test_normalize_cik_rejects_no_digits():
    with pytest.raises(ValueError):
        _normalize_cik("abc")


def test_normalize_cik_rejects_too_many_digits():
    with pytest.raises(ValueError):
        _normalize_cik("123456789012")


# ---- real EDGAR integration test -----------------------------------------
# Hits the live data.sec.gov API -- Apple is a stable, always-filing
# company, so this is a reliable real-data smoke test rather than a flaky
# one. No mocked/synthetic response anywhere in this suite.


def test_get_form4_filings_returns_real_form4_only():
    result = get_form4_filings(APPLE_CIK, "Apple Inc.")

    assert list(result.columns) == [
        "form",
        "filing_date",
        "accession_number",
        "primary_document",
        "company",
    ]
    assert (result["primary_document"].str.len() > 0).all()
    assert len(result) > 0
    assert (result["form"] == "4").all()
    assert (result["company"] == "Apple Inc.").all()
    assert pd.api.types.is_datetime64_any_dtype(result["filing_date"])
    assert result["filing_date"].is_monotonic_increasing
    assert result["accession_number"].str.match(r"^\d{10}-\d{2}-\d{6}$").all()


def test_get_form4_filings_accepts_unpadded_cik():
    padded = get_form4_filings(APPLE_CIK, "Apple Inc.")
    unpadded = get_form4_filings("320193", "Apple Inc.")
    assert len(padded) == len(unpadded)
