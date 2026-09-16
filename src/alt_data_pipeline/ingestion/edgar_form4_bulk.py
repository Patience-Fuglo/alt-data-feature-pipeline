"""Bulk real Form 4 transaction history for one company.

Several of the planned features (cluster buying, a purchase's size
relative to that insider's own history, time since their last purchase)
can't be computed from a single filing -- they need every insider's
transaction history across the company's *entire* filing history. This
walks every real Form 4 filing for a company and parses each one's
transaction detail, respecting EDGAR's request-rate expectations, and
caches the result so the ~10-minute real fetch only happens once.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from .edgar_form4 import get_form4_filings
from .edgar_form4_detail import get_form4_transactions

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[3] / "data"


def get_all_form4_transactions(
    cik: str,
    company_name: str,
    delay_seconds: float = 0.12,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    force_refresh: bool = False,
) -> pd.DataFrame:
    """Real transaction detail for every Form 4 filing on record for a company.

    ``delay_seconds`` between requests keeps well under EDGAR's stated
    10-requests-per-second limit even accounting for network jitter.
    Filings with only derivative transactions contribute no rows (not an
    error -- see ``edgar_form4_detail``).
    """
    cache_path = cache_dir / f"FORM4_ALL_{cik}.csv"
    if not force_refresh and cache_path.exists():
        df = pd.read_csv(cache_path, parse_dates=["transaction_date"])
        for col in ["is_officer", "is_director", "is_ten_percent_owner"]:
            df[col] = df[col].astype(bool)
        return df

    filings = get_form4_filings(cik, company_name)
    all_transactions = []
    for _, row in filings.iterrows():
        try:
            txns = get_form4_transactions(cik, row["accession_number"], row["primary_document"])
        except Exception:
            continue  # a single malformed/unreachable filing shouldn't kill the whole pull
        if len(txns):
            txns["filing_date"] = row["filing_date"]
            all_transactions.append(txns)
        time.sleep(delay_seconds)

    if not all_transactions:
        raise RuntimeError(f"No parseable Form 4 transactions found for CIK {cik}.")

    result = pd.concat(all_transactions, ignore_index=True).sort_values("transaction_date").reset_index(drop=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    result.to_csv(cache_path, index=False)
    return result
