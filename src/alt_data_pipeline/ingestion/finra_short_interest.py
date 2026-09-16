"""Real FINRA short interest, all exchanges (NYSE, Nasdaq, BATS).

Discovered mid-build: the Cboe short-interest module already shipped
(``cboe_short_interest.py``) is real and correct, but it only covers
securities where Cboe/BATS is the *primary listing exchange* -- Apple and
Tesla, both Nasdaq-listed, never appear in it at all. This module pulls
FINRA's own comprehensive short-interest file instead, which includes
every exchange. Confirmed real settlement-to-publication gap here too,
~14 days -- the file dated by settlement 2026-08-31 wasn't actually
published until 2026-09-14, per its own Last-Modified header.
"""

from __future__ import annotations

from io import StringIO

import pandas as pd
import requests

_FINRA_URL = "https://cdn.finra.org/equity/otcmarket/biweekly/shrt{date_str}.csv"

_RETURN_COLUMNS = [
    "publication_date",
    "settlement_date",
    "symbol",
    "security_name",
    "exchange",
    "current_short_interest",
    "previous_short_interest",
    "avg_daily_volume",
    "days_to_cover",
    "short_interest_pct_change",
    "reported_pct_change",
]


def get_short_interest_finra(date_str: str) -> pd.DataFrame:
    """Fetch real FINRA short interest for a settlement-date-named file
    (``date_str``, "YYYYMMDD" -- matches FINRA's file-naming convention,
    which uses settlement date, not publication date, in the URL itself).

    The actual publication date -- when the file became public -- is read
    from the response's own ``Last-Modified`` header, not assumed to equal
    the settlement date embedded in the filename. Any point-in-time merge
    should use ``publication_date``, never ``settlement_date``.
    """
    url = _FINRA_URL.format(date_str=date_str)
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    publication_date = pd.to_datetime(resp.headers["Last-Modified"]).tz_localize(None).normalize()

    raw = pd.read_csv(StringIO(resp.text), sep="|")
    df = pd.DataFrame(
        {
            "publication_date": publication_date,
            "settlement_date": pd.to_datetime(raw["settlementDate"]),
            "symbol": raw["symbolCode"],
            "security_name": raw["issueName"],
            "exchange": raw["issuerServicesGroupExchangeCode"],
            "current_short_interest": raw["currentShortPositionQuantity"].astype(float),
            "previous_short_interest": raw["previousShortPositionQuantity"].astype(float),
            "avg_daily_volume": raw["averageDailyVolumeQuantity"].astype(float),
            "days_to_cover": raw["daysToCoverQuantity"].astype(float),
            "reported_pct_change": raw["changePercent"].astype(float),
        }
    )

    prev = df["previous_short_interest"]
    df["short_interest_pct_change"] = (
        (df["current_short_interest"] - prev) / prev * 100.0
    ).where(prev != 0)

    return df[_RETURN_COLUMNS]
