import pandas as pd

from alt_data_pipeline.features import build_merged_panel


def _trading_days(n=20):
    return pd.date_range("2024-01-02", periods=n, freq="B")  # business days, real weekday pattern


def _form4_row(date, purchase_size=1000.0):
    return {
        "transaction_date": pd.Timestamp(date),
        "purchase_size": purchase_size,
        "insider_role_score": 2,
        "cluster_buying_count": 0,
        "purchase_size_vs_own_history": 1.0,
        "days_since_own_last_purchase": 0.0,
    }


def _si_row(date, pct_change=5.0):
    return {
        "publication_date": pd.Timestamp(date),
        "percent_change_short_interest": pct_change,
        "days_to_cover": 2.0,
        "percent_of_float": 1.0,
        "deviation_from_own_baseline": 1.0,
    }


def test_purchase_event_is_one_only_on_the_actual_event_day():
    days = _trading_days()
    form4 = pd.DataFrame([_form4_row(days[5])])
    si = pd.DataFrame([_si_row(days[3])])

    panel = build_merged_panel(days, form4, si)
    events = panel[panel["form4_purchase_event"] == 1]["trading_date"]
    assert list(events) == [days[5]]
    assert (panel["form4_purchase_event"].isin([0, 1])).all()


def test_continuous_form4_features_forward_fill_after_the_event():
    days = _trading_days()
    form4 = pd.DataFrame([_form4_row(days[5], purchase_size=1234.0)])
    si = pd.DataFrame([_si_row(days[3])])

    panel = build_merged_panel(days, form4, si)
    after = panel[panel["trading_date"] >= days[5]]
    assert (after["form4_purchase_size"] == 1234.0).all()


def test_rows_before_first_observation_stay_nan_not_zero():
    # deliberate: forward-fill can't manufacture data that doesn't exist,
    # and zero would falsely claim "verified no activity" for a period we
    # simply have no data for.
    days = _trading_days()
    form4 = pd.DataFrame([_form4_row(days[5])])
    si = pd.DataFrame([_si_row(days[3])])

    panel = build_merged_panel(days, form4, si)
    before = panel[panel["trading_date"] < days[5]]
    assert before["form4_purchase_size"].isna().all()
    # but the event flag IS zero-filled even before the first observation --
    # "no purchase happened yet" is a real, known fact for those days
    assert (before["form4_purchase_event"] == 0).all()


def test_short_interest_features_forward_fill_independently_of_form4():
    days = _trading_days()
    form4 = pd.DataFrame([_form4_row(days[10])])
    si = pd.DataFrame([_si_row(days[2], pct_change=7.5)])

    panel = build_merged_panel(days, form4, si)
    after_si_before_form4 = panel[(panel["trading_date"] >= days[2]) & (panel["trading_date"] < days[10])]
    assert (after_si_before_form4["short_interest_percent_change_short_interest"] == 7.5).all()
    assert after_si_before_form4["form4_purchase_size"].isna().all()


def test_new_observation_supersedes_the_prior_forward_filled_value():
    days = _trading_days()
    form4 = pd.DataFrame([_form4_row(days[2], purchase_size=100.0), _form4_row(days[8], purchase_size=999.0)])
    si = pd.DataFrame([_si_row(days[0])])

    panel = build_merged_panel(days, form4, si)
    mid = panel[(panel["trading_date"] >= days[2]) & (panel["trading_date"] < days[8])]
    late = panel[panel["trading_date"] >= days[8]]
    assert (mid["form4_purchase_size"] == 100.0).all()
    assert (late["form4_purchase_size"] == 999.0).all()


def test_multiple_same_day_events_collapse_to_one_row_keeping_the_last():
    days = _trading_days()
    form4 = pd.DataFrame([_form4_row(days[4], purchase_size=1.0), _form4_row(days[4], purchase_size=2.0)])
    si = pd.DataFrame([_si_row(days[0])])

    panel = build_merged_panel(days, form4, si)
    assert len(panel) == len(days)  # one row per trading day, no duplication
    assert panel.loc[panel["trading_date"] == days[4], "form4_purchase_size"].iloc[0] == 2.0


def test_output_has_one_row_per_trading_day():
    days = _trading_days(30)
    form4 = pd.DataFrame([_form4_row(days[1])])
    si = pd.DataFrame([_si_row(days[1])])
    panel = build_merged_panel(days, form4, si)
    assert len(panel) == 30
    assert list(panel["trading_date"]) == list(days)


# ---- real end-to-end integration: Tesla, real Musk cluster + real short interest ----


def test_real_tesla_merged_panel():
    from alt_data_pipeline.alignment import get_trading_days
    from alt_data_pipeline.features import engineer_form4_features, engineer_short_interest_features
    from alt_data_pipeline.ingestion import get_shares_outstanding, get_short_interest_history
    from alt_data_pipeline.ingestion.edgar_form4_bulk import get_all_form4_transactions

    TESLA_CIK = "0001318605"
    trading_days = get_trading_days("TSLA", start="2025-08-01", end="2026-09-15")

    form4_all = engineer_form4_features(get_all_form4_transactions(TESLA_CIK, "Tesla Inc."))
    form4 = form4_all[
        (form4_all["transaction_date"] >= trading_days.min()) & (form4_all["transaction_date"] <= trading_days.max())
    ]

    real_dates = ["20260415", "20260430", "20260515", "20260615", "20260630", "20260715", "20260731", "20260814", "20260831"]
    si_all = engineer_short_interest_features(
        get_short_interest_history("TSLA", real_dates), get_shares_outstanding(TESLA_CIK)
    )
    si = si_all[(si_all["publication_date"] >= trading_days.min()) & (si_all["publication_date"] <= trading_days.max())]

    panel = build_merged_panel(trading_days, form4, si)

    assert len(panel) == len(trading_days)
    # the real 2025-09-12 Musk purchase day should show exactly one event row
    assert panel["form4_purchase_event"].sum() == 1
    event_row = panel[panel["form4_purchase_event"] == 1].iloc[0]
    assert event_row["trading_date"] == pd.Timestamp("2025-09-12")
    assert event_row["form4_insider_role_score"] == 4  # real: officer + director + >10% owner
    # forward-fill should carry that day's values all the way to the last trading day
    assert panel.iloc[-1]["form4_insider_role_score"] == 4
