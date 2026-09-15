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
| Point-in-time alignment (as-of joins) | not started |
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
