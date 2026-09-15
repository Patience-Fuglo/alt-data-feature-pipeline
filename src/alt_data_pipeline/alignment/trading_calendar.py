"""A real trading calendar, derived from a real ticker's actual trade dates.

There's no separate "which days was the market open" data source needed
here -- if a liquid ticker has a daily bar for a date, the market was open
that day. That's a real calendar, not an approximation of one.
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[3] / "data"


def get_trading_days(
    ticker: str = "AAPL",
    start: str = "2010-01-01",
    end: str = "2026-12-31",
    cache_dir: Path = DEFAULT_CACHE_DIR,
    max_retries: int = 3,
) -> pd.DatetimeIndex:
    """Real trading days between ``start`` and ``end``, from ``ticker``'s
    actual daily bars (tz-naive, ascending, no duplicates)."""
    cache_path = cache_dir / f"TRADING_DAYS_{ticker.upper()}_{start}_{end}.csv"
    if cache_path.exists():
        return pd.DatetimeIndex(pd.read_csv(cache_path)["date"], dtype="datetime64[ns]")

    import yfinance as yf

    raw = None
    for attempt in range(max_retries):
        try:
            raw = yf.download(ticker, start=start, end=end, progress=False, threads=False)
        except Exception:
            raw = None
        if raw is not None and not raw.empty:
            break
        if attempt < max_retries - 1:
            time.sleep(2**attempt)

    if raw is None or raw.empty:
        raise RuntimeError(f"Could not derive a trading calendar from {ticker}: no data returned.")

    days = pd.DatetimeIndex(pd.to_datetime(raw.index).tz_localize(None)).sort_values().unique()
    cache_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": days}).to_csv(cache_path, index=False)
    return days
