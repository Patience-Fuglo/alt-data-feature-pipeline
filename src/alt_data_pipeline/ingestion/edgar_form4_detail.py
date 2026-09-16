"""Real Form 4 transaction-detail parsing.

The filing list alone (form, date, accession number) can't answer the
question that actually matters -- was this a genuine open-market purchase
with the insider's own money (transaction code P), or routine paperwork
(a grant, an option exercise, a gift)? That requires each filing's own
XML document. Confirmed real structure by pulling an actual Apple Form 4.

One wrinkle discovered by checking, not assuming: the submissions API's
``primaryDocument`` field often points at an XSLT-rendered *viewer* path
(e.g. ``xslF345X06/form4.xml``) that returns HTML, not the raw XML --
fetching it directly silently returns the wrong content type. The real
XML sits at the same accession folder under just the base filename.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

import pandas as pd
import requests

_ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession_nodash}/{filename}"
_HEADERS = {"User-Agent": "Patience Fuglo patfug3@gmail.com"}

_RETURN_COLUMNS = [
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


def _document_url(cik: str, accession_number: str, primary_document: str) -> str:
    cik_no_leading_zeros = str(int(cik))
    accession_nodash = accession_number.replace("-", "")
    # strip the XSLT viewer subfolder if present (e.g. "xslF345X06/form4.xml"
    # -> "form4.xml") -- the raw document sits directly in the accession
    # folder, not inside the viewer path.
    filename = primary_document.rsplit("/", 1)[-1]
    return _ARCHIVES_URL.format(cik=cik_no_leading_zeros, accession_nodash=accession_nodash, filename=filename)


def _text(el: ET.Element | None, path: str, default: str = "") -> str:
    found = el.find(path) if el is not None else None
    return found.text.strip() if found is not None and found.text else default


def _bool(el: ET.Element | None, path: str) -> bool:
    # different filing agents encode these flags differently -- Apple's
    # filer uses "true"/"false", Tesla's uses "1"/"0". Confirmed by
    # checking a real filing from each rather than assuming one format;
    # checking only "true" silently misread a real officer as not one.
    return _text(el, path).strip().lower() in ("true", "1")


def get_form4_transactions(cik: str, accession_number: str, primary_document: str) -> pd.DataFrame:
    """Fetch and parse one Form 4 filing's non-derivative (common stock)
    transactions.

    Most filings report exactly one transaction; some report several in
    the same filing. Filings with only derivative transactions (option
    grants with no common-stock activity) return an empty DataFrame, not
    an error.

    Joint filings with more than one reporting owner attribute all
    transactions to the first-listed owner -- a real but rare case, kept
    simple rather than hidden.
    """
    url = _document_url(cik, accession_number, primary_document)
    resp = requests.get(url, headers=_HEADERS, timeout=10)
    resp.raise_for_status()
    root = ET.fromstring(resp.content)

    owner_el = root.find("reportingOwner")
    owner_name = _text(owner_el, "reportingOwnerId/rptOwnerName")
    owner_cik = _text(owner_el, "reportingOwnerId/rptOwnerCik")
    is_officer = _bool(owner_el, "reportingOwnerRelationship/isOfficer")
    is_director = _bool(owner_el, "reportingOwnerRelationship/isDirector")
    is_ten_pct = _bool(owner_el, "reportingOwnerRelationship/isTenPercentOwner")
    officer_title = _text(owner_el, "reportingOwnerRelationship/officerTitle")

    rows = []
    for txn in root.findall("nonDerivativeTable/nonDerivativeTransaction"):
        rows.append(
            {
                "accession_number": accession_number,
                "owner_name": owner_name,
                "owner_cik": owner_cik,
                "is_officer": is_officer,
                "is_director": is_director,
                "is_ten_percent_owner": is_ten_pct,
                "officer_title": officer_title,
                "transaction_date": _text(txn, "transactionDate/value"),
                "transaction_code": _text(txn, "transactionCoding/transactionCode"),
                "shares": _text(txn, "transactionAmounts/transactionShares/value"),
                "price_per_share": _text(txn, "transactionAmounts/transactionPricePerShare/value"),
                "acquired_disposed_code": _text(txn, "transactionAmounts/transactionAcquiredDisposedCode/value"),
                "shares_owned_following": _text(txn, "postTransactionAmounts/sharesOwnedFollowingTransaction/value"),
            }
        )

    if not rows:
        return pd.DataFrame(columns=_RETURN_COLUMNS)

    df = pd.DataFrame(rows)
    df["transaction_date"] = pd.to_datetime(df["transaction_date"])
    for col in ["shares", "price_per_share", "shares_owned_following"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[_RETURN_COLUMNS]
