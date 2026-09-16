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
| FINRA comprehensive short interest ingestion | done |
| Shares outstanding ingestion | done |
| Short interest feature engineering (5 of 5 features) | done |
| Merged point-in-time panel | done |
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

## Short interest ingestion

`src/alt_data_pipeline/ingestion/cboe_short_interest.py` and
`finra_short_interest.py`

Short interest — how many shares are currently sold short, i.e. how much
the market is betting a stock will fall — is published bi-monthly. Every
report carries two dates: a *settlement* date (when the count actually
happened) and a *publication* date (when the public could first see it).
Merging on settlement date is pretending the market knew a number before
it was actually published.

Two real sources here, deliberately — not redundant, genuinely different
coverage, found by checking rather than assuming one file was enough:

- **Cboe** (`get_short_interest`) covers securities where Cboe/BATS is the
  *primary listing exchange* — confirmed real gap: 11 days. It does not
  include Apple, Tesla, or most Nasdaq/NYSE megacaps at all.
- **FINRA** (`get_short_interest_finra`) is comprehensive — every exchange
  in one file, confirmed real gap: 14 days, read from the response's own
  `Last-Modified` header rather than assumed equal to the settlement date
  in the filename.

```python
from alt_data_pipeline.ingestion import get_short_interest, get_short_interest_finra

cboe_report = get_short_interest("20260911")          # Cboe/BATS-listed only
finra_report = get_short_interest_finra("20260831")    # all exchanges, incl. AAPL/TSLA
```

In both, `short_interest_pct_change` is computed directly from the raw
current/previous share counts, not taken from the source's own
pre-computed column — `reported_pct_change` is kept alongside purely as
an independent cross-check (they agree to within the source's own
rounding).

Run the real-data demos:

```bash
python scripts/demo_cboe_short_interest.py
python scripts/demo_short_interest_features.py
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

**The mirror-image case.** `latest_known_value_asof` searches *backward*:
for a slowly-changing quantity like shares outstanding, the correct value
as of a given date is the most recently *published* one — never a later
one that didn't exist yet. Forward would be the look-ahead bias here,
not the fix. Same discipline as the forward case (never let the future
leak into a point-in-time value), opposite direction, because the two
questions are genuinely different: "when can I first act on this event"
vs. "what was the most recently known value of this slowly-changing
number."

```python
from alt_data_pipeline.alignment import latest_known_value_asof
from alt_data_pipeline.ingestion import get_shares_outstanding

shares = get_shares_outstanding("0000320193")
as_of_publication = latest_known_value_asof(
    short_interest["publication_date"], shares["filed_date"], shares["shares_outstanding"]
)
```

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

## Short interest feature engineering

`src/alt_data_pipeline/features/short_interest_features.py`

Three of the five short-interest features, so far:

1. **Percent change in short interest** and **2. days-to-cover** were
   already sitting in the ingestion data — passed through here under
   clear feature names, no new work needed.
2. **Percent of float** — raw share counts distort by company size. A
   small company's short interest jumping from 100k to 200k shares looks
   like a 100% increase; a giant's 40M-to-42M jump is "only" 5%, even
   when it represents a comparably large real bet. Normalizing by shares
   outstanding corrects that. Built using the backward as-of lookup
   above, matched to shares outstanding known *as of* the short-interest
   publication date.

Real result, four real megacaps, same real settlement cycle:

| Symbol | % of float |
|---|---|
| AAPL | 0.958% |
| TSLA | 1.879% |
| NVDA | 1.238% |
| MSFT | 1.003% |

```python
from alt_data_pipeline.features import engineer_short_interest_features
from alt_data_pipeline.ingestion import get_shares_outstanding, get_short_interest_finra

short_interest = get_short_interest_finra("20260831")
aapl = short_interest[short_interest["symbol"] == "AAPL"]
shares = get_shares_outstanding("0000320193")
features = engineer_short_interest_features(aapl, shares)
```

**4. Deviation from own baseline** and **5. sector divergence** — the
final two, built next.

Deviation from own baseline needed real history: FINRA only links its 2
most recent files on the catalog page, but older ones are still real and
reachable at the same predictable URL pattern — 9 real cycles pulled,
April through August 2026 (one date, 2026-05-30, correctly skipped: not
a real settlement day). Same point-in-time rule as the Form 4 features:
each cycle's baseline is the mean of strictly *earlier* cycles only.

Sector divergence needed a genuine peer check, not an assumption. Real
company sector data (SIC code) comes from the same EDGAR endpoint already
used elsewhere. Checked 5 plausible "tech peer" candidates for Apple
(Dell, HP, Alphabet, Microsoft, Cisco) against its real SIC code
(3571, Electronic Computers) — only **Dell** shares the exact code.
Real result: Apple's short interest rose +20.13% one cycle while its one
verified peer rose only +3.07% — a +17.06 point divergence, i.e. this
looks like a stock-specific move, not the whole sector shifting together.

```python
from alt_data_pipeline.features import engineer_short_interest_features, find_sector_peers, sector_divergence
from alt_data_pipeline.ingestion import get_short_interest_history, get_shares_outstanding

history = get_short_interest_history("AAPL", ["20260415", "20260430", ...])
features = engineer_short_interest_features(history, get_shares_outstanding("0000320193"))

peers = find_sector_peers("0000320193", candidate_ciks)
```

Run the real-data demos:

```bash
python scripts/demo_short_interest_features.py
python scripts/demo_short_interest_history_features.py
```

## Merged point-in-time panel

`src/alt_data_pipeline/features/merged_panel.py`

Form 4 events and short-interest reports each happen on their own sparse
schedule, but a model needs a value every trading day. The fix isn't
"fill with zero everywhere" — it's matching the fill strategy to what
each feature actually represents:

- An **ongoing-state** feature (purchase size, insider role, % of float,
  deviation from baseline...) genuinely still holds until a newer
  observation replaces it — forward-filled.
- A **specific-day event flag** ("did a purchase happen today") genuinely
  didn't happen on days with no purchase — zero-filled, never
  forward-filled, or every day after one real purchase would falsely
  claim a new one happened.

Everything is placed on its real *actionable* trading date — via the same
forward as-of alignment from earlier — not its raw event date.

Rows before either dataset's first real observation are left `NaN`,
deliberately. Forward-fill can't manufacture data that doesn't exist, and
filling those leading rows with 0 would falsely claim "verified no
activity" for a period with no data at all — a distinction real data
forces that a synthetic panel starting from day one never has to make.

```python
from alt_data_pipeline.alignment import get_trading_days
from alt_data_pipeline.features import build_merged_panel, engineer_form4_features, engineer_short_interest_features

trading_days = get_trading_days("TSLA", start="2025-08-01", end="2026-09-15")
panel = build_merged_panel(trading_days, form4_features, short_interest_features)
```

Real result: 281 real trading days, Tesla — the real 2025-09-12 Musk
purchase (officer + director + >10% owner, role score 4) forward-fills
correctly all the way to the most recent trading day, while short
interest carries its own independent forward-fill on its own bi-monthly
schedule, right up until each new real cycle supersedes it.

Run the real-data demo:

```bash
python scripts/demo_merged_panel.py
```

---

This closes out `alt-data-feature-pipeline`: real ingestion, point-in-time
alignment (both directions), transaction-detail parsing, all ten features
across both datasets, and the merged panel. Next: `alt-data-alpha-signal`,
the flagship signal built on top of this panel.
