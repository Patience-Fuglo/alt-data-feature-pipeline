"""Real shares-outstanding history from SEC EDGAR's XBRL company-facts API.

Needed for the "% of float" short-interest feature -- raw share counts
distort by company size (a small company's short interest can look
dramatically larger in raw terms than a giant's comparably-sized real
bet). Confirmed real point-in-time gap here too: a value measured
"as of" one date is often not actually filed/public until weeks later.
"""

from __future__ import annotations

import re

import pandas as pd
import requests

_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
_HEADERS = {"User-Agent": "Patience Fuglo patfug3@gmail.com"}

_RETURN_COLUMNS = ["as_of_date", "filed_date", "shares_outstanding", "form", "accession_number"]


def get_shares_outstanding(cik: str) -> pd.DataFrame:
    """Real shares-outstanding history for a company, from its own XBRL filings.

    Returns a DataFrame with ``as_of_date`` (the measurement date) and
    ``filed_date`` (when it actually became public -- use this one for
    any point-in-time merge, never ``as_of_date``), sorted by filed_date
    ascending.
    """
    digits = re.sub(r"\D", "", cik).zfill(10)
    url = _COMPANY_FACTS_URL.format(cik=digits)
    resp = requests.get(url, headers=_HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    facts = data.get("facts", {}).get("dei", {}).get("EntityCommonStockSharesOutstanding", {})
    entries = facts.get("units", {}).get("shares", [])
    if not entries:
        raise ValueError(f"No EntityCommonStockSharesOutstanding facts found for CIK {digits}.")

    df = pd.DataFrame(entries)
    df = df.rename(
        columns={"end": "as_of_date", "filed": "filed_date", "val": "shares_outstanding", "accn": "accession_number"}
    )
    df["as_of_date"] = pd.to_datetime(df["as_of_date"])
    df["filed_date"] = pd.to_datetime(df["filed_date"])
    df = df.sort_values("filed_date").drop_duplicates(subset="filed_date", keep="last").reset_index(drop=True)
    return df[_RETURN_COLUMNS]
