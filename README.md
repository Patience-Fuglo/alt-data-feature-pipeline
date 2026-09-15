# alt-data-feature-pipeline

Point-in-time ingestion, alignment, and feature engineering for two
alternative equity datasets — SEC EDGAR Form 4 insider transactions and
Cboe/FINRA short interest — merged into a single model-ready panel.

The hypothesis this pipeline is built to test: genuine insider conviction
(an open-market purchase with the insider's own money) diverging from
rising short interest (the broader market betting against the same stock)
is a real signal worth investigating, distinct from either data point
alone.

## Status

| Module | Status |
|---|---|
| SEC EDGAR Form 4 ingestion | done |
| Cboe/FINRA short interest ingestion | done |
| Point-in-time alignment (as-of joins) | done |
| Feature engineering | not started |
| Merged panel | not started |

## SEC EDGAR Form 4 ingestion

`src/alt_data_pipeline/ingestion/edgar_form4.py`

Pulls a company's real filing history from EDGAR's public submissions API
and keeps only Form 4s — the filing an insider must submit within 1-2
business days of buying or selling their own company's stock. Returns the
filing list (form, date, accession number); reading which transactions
were genuine open-market purchases versus routine option exercises or
grants requires each filing's own document, a separate step.

```python
from alt_data_pipeline.ingestion import get_form4_filings

filings = get_form4_filings("0000320193", "Apple Inc.")
```

Every request identifies a real contact, per EDGAR's fair-access policy —
not a gate on public data, just how a shared, high-traffic service tells
one well-behaved caller apart from a flood of anonymous requests.

Run the real-data demo:

```bash
pip install -e .
python scripts/demo_edgar_form4.py
```

Run the tests (includes a live call against the real EDGAR API, not a
mocked response):

```bash
pytest tests/
```

## Cboe/FINRA short interest ingestion

`src/alt_data_pipeline/ingestion/cboe_short_interest.py`

Short interest — how many shares are currently sold short, i.e. how much
the market is betting a stock will fall — is published bi-monthly. Every
report carries two dates: a *settlement* date (when the count actually
happened) and a *publication* date (when the public could first see it).
Confirmed real gap: an 11-day lag, every cycle. A pipeline that merges on
settlement date is pretending the market knew a number before it was
actually published.

```python
from alt_data_pipeline.ingestion import get_short_interest

report = get_short_interest("20260911")  # publication date, not settlement date
```

`short_interest_pct_change` is computed here directly from the raw
current/previous share counts, not taken from Cboe's own pre-computed
column — `reported_pct_change` is kept alongside it purely as an
independent cross-check (they agree to within Cboe's own rounding).

Run the real-data demo:

```bash
python scripts/demo_cboe_short_interest.py
```

## Point-in-time alignment (as-of joins)

`src/alt_data_pipeline/alignment/`

A filing dated Saturday doesn't become actionable on Saturday — markets
are closed. An exact-date merge against price data would silently drop
that row entirely rather than erroring, hiding a systematic pattern:
weekend-adjacent events vanish from the dataset every time, unnoticed.
The fix maps each event date to the *next available* trading day —
forward only, never backward. A backward match would pair an event with a
price from before the event was even public.

`trading_calendar.get_trading_days` derives a real trading calendar
directly from a real ticker's actual trade dates — confirmed real US
holidays (July 4th, Christmas, Thanksgiving) come back correctly absent.
`asof_join.align_to_next_trading_day` does the actual mapping.

```python
from alt_data_pipeline.alignment import align_to_next_trading_day, get_trading_days

trading_days = get_trading_days("AAPL", start="2019-01-01", end="2024-12-31")
df["trading_date"] = align_to_next_trading_day(df["filing_date"], trading_days)
```

Real finding: across 590 real Apple Form 4 filings, none landed on a
weekend — EDGAR's Form 4 filing pattern is business-day-only in practice.
Every filing inside the known calendar range aligns to itself.

Run the real-data demo:

```bash
python scripts/demo_alignment.py
```
