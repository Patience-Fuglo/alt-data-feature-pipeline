import pytest

from alt_data_pipeline.ingestion.edgar_company_info import get_company_sic

APPLE_CIK = "0000320193"


def test_returns_real_apple_sic():
    sic, description = get_company_sic(APPLE_CIK)
    assert sic == "3571"
    assert description == "Electronic Computers"


def test_accepts_unpadded_cik():
    sic1, _ = get_company_sic("320193")
    sic2, _ = get_company_sic("0000320193")
    assert sic1 == sic2


def test_different_real_companies_have_different_real_sic_codes():
    # confirmed 2026-09-16: Apple (hardware) and Microsoft (software
    # services) are NOT the same SIC despite both being "big tech" --
    # checked directly rather than assumed.
    apple_sic, _ = get_company_sic(APPLE_CIK)
    msft_sic, _ = get_company_sic("0000789019")
    assert apple_sic != msft_sic
