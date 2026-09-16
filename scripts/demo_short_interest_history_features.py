"""Demo: deviation from own baseline (real multi-cycle history) and
sector divergence (real SIC-verified peer) -- the final two short
interest features.

Run: python scripts/demo_short_interest_history_features.py
"""

from __future__ import annotations

from alt_data_pipeline.features import engineer_short_interest_features, find_sector_peers, sector_divergence
from alt_data_pipeline.ingestion import get_short_interest_finra, get_short_interest_history, get_shares_outstanding

APPLE_CIK = "0000320193"
REAL_DATES = ["20260415", "20260430", "20260515", "20260530", "20260615", "20260630", "20260715", "20260731", "20260814", "20260831"]
CANDIDATE_PEER_CIKS = ["0000826083", "0000047217", "0001652044", "0000789019", "0000858877"]  # Dell, HP, Alphabet, MSFT, Cisco


def main() -> None:
    print("=" * 70)
    print("DEVIATION FROM OWN BASELINE -- real 9-cycle Apple history")
    print("=" * 70)
    history = get_short_interest_history("AAPL", REAL_DATES)
    shares = get_shares_outstanding(APPLE_CIK)
    features = engineer_short_interest_features(history, shares)
    print(features[["publication_date", "current_short_interest", "deviation_from_own_baseline"]].to_string(index=False))

    print()
    print("=" * 70)
    print("SECTOR DIVERGENCE -- real SIC-verified peer check")
    print("=" * 70)
    peers = find_sector_peers(APPLE_CIK, CANDIDATE_PEER_CIKS)
    print(f"Checked 5 plausible 'tech peer' candidates (Dell, HP, Alphabet, Microsoft, Cisco)")
    print(f"Real SIC-code-confirmed peers: {len(peers)} of 5")

    si = get_short_interest_finra("20260831")
    aapl_pct = si[si["symbol"] == "AAPL"]["short_interest_pct_change"].iloc[0]
    dell_pct = si[si["symbol"] == "DELL"]["short_interest_pct_change"].iloc[0]
    divergence = sector_divergence(aapl_pct, [dell_pct])

    print(f"\nAAPL short-interest change: {aapl_pct:+.2f}%")
    print(f"DELL (verified peer) change: {dell_pct:+.2f}%")
    print(f"Sector divergence: {divergence:+.2f} percentage points")
    print("(large positive = stock-specific move, not the whole sector shifting together)")


if __name__ == "__main__":
    main()
