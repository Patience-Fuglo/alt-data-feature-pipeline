"""Real SEC EDGAR Form 4 (insider transaction) filing ingestion.

Pulls a company's filing history from EDGAR's submissions API and keeps
only Form 4s -- the filing an insider (officer, director, or >10% owner)
must submit within 1-2 business days of buying or selling their own
company's stock. This module returns the filing *list* (form, date,
accession number, and the primary document filename needed to fetch each
filing's own transaction detail); reading transaction-level detail (buy
vs. sell, share count, the transaction code distinguishing a genuine
open-market purchase from a routine option exercise or grant) is a
separate step, in ``edgar_form4_detail.py``.
"""

from __future__ import annotations

import re

import pandas as pd
import requests

_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"

# SEC's fair-access policy requires every request to identify a real
# person and contact -- not a gate on public data, just how it tells one
# well-behaved caller apart from a flood of anonymous traffic.
_HEADERS = {"User-Agent": "Patience Fuglo patfug3@gmail.com"}

_RETURN_COLUMNS = ["form", "filing_date", "accession_number", "primary_document", "company"]


def _normalize_cik(cik: str) -> str:
    digits = re.sub(r"\D", "", cik)
    if not digits:
        raise ValueError(f"cik must contain digits, got: {cik!r}")
    if len(digits) > 10:
        raise ValueError(f"cik has more than 10 digits: {cik!r}")
    return digits.zfill(10)


def get_form4_filings(cik: str, company_name: str) -> pd.DataFrame:
    """Fetch real Form 4 filings for a company from SEC EDGAR.

    ``cik`` may be given with or without leading zeros / punctuation (e.g.
    "320193" or "0000320193" or "CIK0000320193" all work) -- it's zero-padded
    to 10 digits before the request.

    Returns a DataFrame with columns ``form, filing_date, accession_number,
    primary_document, company``, sorted by filing_date ascending. Only
    Form 4s are kept; all other filing types (10-K, 10-Q, 8-K, etc.)
    returned by the API are dropped.

    Note: EDGAR's submissions endpoint returns only the ~1,000 most recent
    filings of any type in this response; a company with high filing
    volume across many years would need the paginated older-filings index
    (``filings.files`` in the raw JSON) for full history -- not needed for
    a single company's recent insider activity, which is the scope here.
    """
    padded_cik = _normalize_cik(cik)
    url = _SUBMISSIONS_URL.format(cik=padded_cik)
    resp = requests.get(url, headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()

    recent = data["filings"]["recent"]
    df = pd.DataFrame(
        {
            "form": recent["form"],
            "filing_date": pd.to_datetime(recent["filingDate"]),
            "accession_number": recent["accessionNumber"],
            "primary_document": recent["primaryDocument"],
        }
    )
    df["company"] = company_name

    form4 = df[df["form"] == "4"].sort_values("filing_date").reset_index(drop=True)
    return form4[_RETURN_COLUMNS]
