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
| Form 4 transaction detail | done |
| Form 4 feature engineering (5 features) | done |
| Short interest feature engineering (5 features) | not started |
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

## Form 4 transaction detail

`src/alt_data_pipeline/ingestion/edgar_form4_detail.py`

The filing list alone can't answer the question that actually matters —
was this a genuine open-market purchase with the insider's own money
(transaction code P), or routine paperwork (a grant, an option exercise,
a gift)? That requires each filing's own document. Two real issues,
found by checking actual filings rather than assuming a single format:

- The submissions API's `primaryDocument` field often points at an
  XSLT-*rendered viewer* path that returns HTML, not the underlying XML —
  the real document sits at the same accession folder under just the
  base filename.
- Different filing agents encode the same boolean fields differently —
  one real filing used `"true"`/`"false"`, another used `"1"`/`"0"` for
  the identical `isOfficer` field. Checking only one format silently
  misread a real company's CEO as not an officer.

```python
from alt_data_pipeline.ingestion import get_form4_filings, get_form4_transactions

filings = get_form4_filings("0000320193", "Apple Inc.")
row = filings.iloc[-1]
transactions = get_form4_transactions(
    "0000320193", row["accession_number"], row["primary_document"]
)
```

Run the real-data demo (a real, large filing — 25 open-market purchases
by one CEO in a single day):

```bash
python scripts/demo_edgar_form4_detail.py
```

## Form 4 feature engineering

`src/alt_data_pipeline/features/form4_features.py`

Five features, each a proxy for how much genuine conviction — not routine
paperwork — sits behind an insider's purchase:

1. **Purchase size** — dollars committed, a proxy for conviction strength.
2. **Insider role/seniority** — an officer sees day-to-day operations; a
   director typically only reviews periodic summaries.
3. **Cluster buying** — how many *other* insiders independently bought in
   the same window. Harder to explain away as one person's opinion.
4. **Purchase size vs. own history** — this purchase's size relative to
   that same insider's own past average. A spike above someone's personal
   normal is the signal, even if the raw dollar amount looks unremarkable
   in isolation.
5. **Days since that insider's own last purchase** — a routine buyer's
   purchase carries little new information; a long silence broken by a
   sudden purchase says more.

Every feature is computed using only information strictly *before* the
transaction it describes — an insider's own history feature only ever
averages *prior* purchases, and cluster buying only ever looks *backward*
from a given transaction. The same point-in-time discipline used
everywhere else in this project (the purged walk-forward's embargo, the
forward-only as-of join), applied here to feature engineering itself: a
naive symmetric window or a mean over *all* of an insider's history
(including the future relative to a given row) would quietly leak
look-ahead bias into the feature itself.

Real result: across Apple's entire observable filing history, only one
insider has ever made a genuine open-market purchase. Tesla's history has
6 distinct real buyers, including a real, verifiable cluster — Elon Musk
and then-board-member Larry Ellison both bought on 2020-02-14.

```python
from alt_data_pipeline.features import engineer_form4_features
from alt_data_pipeline.ingestion.edgar_form4_bulk import get_all_form4_transactions

transactions = get_all_form4_transactions("0001318605", "Tesla Inc.")
features = engineer_form4_features(transactions)
```

Run the real-data demo:

```bash
python scripts/demo_form4_features.py
```
