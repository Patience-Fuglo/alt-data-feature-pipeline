"""Real company sector classification from SEC EDGAR.

Needed to find genuine peers for the sector-divergence feature: is a
stock's short-interest change specific to that one company, or is the
whole sector moving together? "Sector" here means SIC (Standard
Industrial Classification) code -- an old, coarse government
classification, but a real and verifiable one, not a guess at which
companies "feel similar."
"""

from __future__ import annotations

import re

import requests

_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
_HEADERS = {"User-Agent": "Patience Fuglo patfug3@gmail.com"}


def get_company_sic(cik: str) -> tuple[str, str]:
    """Real SIC code and description for a company, from EDGAR.

    Returns (sic_code, sic_description), e.g. ("3571", "Electronic Computers").
    """
    digits = re.sub(r"\D", "", cik).zfill(10)
    url = _SUBMISSIONS_URL.format(cik=digits)
    resp = requests.get(url, headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data.get("sic", ""), data.get("sicDescription", "")
