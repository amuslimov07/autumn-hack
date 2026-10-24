import numpy as np
import pandas as pd

from src.forecasting.evaluation import error_metrics
from src.forecasting.features import feature_row
from src.forecasting.models import forecast_flows
from src.forecasting.prediction import build_forecast
from src.future_events.manager import merge_future_flows, validate_events


def test_forecast_is_daily_and_does_not_read_future_data():
    dates = pd.date_range("2025-01-01", periods=90)
    daily = pd.DataFrame({"date": dates, "inflow": np.where(dates.day_of_week == 1, 100.0, 0.0),
                          "outflow": np.where(dates.day == 1, 50.0, 0.0)})
    forecast = forecast_flows(daily, 30, method="baseline")
    assert len(forecast) == 30
    series = pd.Series(range(100), index=pd.date_range("2025-01-01", periods=100))
    when = pd.Timestamp("2025-03-15")
    before = feature_row(series, when)
    changed = series.copy()
    changed.loc[changed.index >= when] = -9999
    assert feature_row(changed, when) == before


def test_future_event_is_signed_and_not_double_counted_with_confirmed_recurring():
    events = validate_events(pd.DataFrame([{"date": "2025-02-02", "amount": "100,00",
                                             "direction": "списание", "category": "Аренда",
                                             "status": "подтверждено", "account": "A"}]))
    recurring = pd.DataFrame([{"confirmed": True, "accepted": True, "frequency": "ежемесячно", "next_date": pd.Timestamp("2025-02-02"),
                               "amount": -100.0, "account": "A"}])
    flows = merge_future_flows(pd.Timestamp("2025-02-01"), 10, events, recurring, "A")
    assert flows.loc[flows["date"] == pd.Timestamp("2025-02-02"), "event_flow"].iloc[0] == -100
    assert flows.loc[flows["date"] == pd.Timestamp("2025-02-02"), "event_count"].iloc[0] == 1


def test_future_events_support_russian_column_names():
    events = validate_events(pd.DataFrame([{"Дата": "05.02.2025", "Сумма платежа": "2 500",
                                             "Направление": "списание", "Статус": "подтверждено"}]))
    assert events.iloc[0]["amount"] == -2500
    assert events.iloc[0]["status"] == "подтверждено"


def test_recurring_events_from_other_accounts_are_excluded():
    recurring = pd.DataFrame([{"confirmed": True, "accepted": True, "frequency": "ежемесячно",
                               "next_date": pd.Timestamp("2025-02-02"), "amount": -100.0, "account": "B"}])
    flows = merge_future_flows(pd.Timestamp("2025-02-01"), 5, recurring=recurring, account="A")
    assert flows["event_flow"].sum() == 0


def test_build_forecast_accounts_for_balance_and_events():
    ops = pd.DataFrame({"date": pd.to_datetime(["2025-01-01", "2025-01-02"]), "amount": [100, -20],
                        "account": ["A", "A"], "balance": [1100, 1080]})
    ops["direction"] = ["поступление", "списание"]
    ops["counterparty"] = ["x", "y"]
    ops["purpose"] = ["a", "b"]
    ops["inn"] = ["", ""]
    forecast, details = build_forecast(ops, 7)
    assert len(forecast) == 7
    assert details["current_balance"] == 1080
    assert forecast.iloc[0]["date"] == pd.Timestamp("2025-01-03")


def test_forecast_anchor_advances_through_days_without_operations():
    dates = pd.date_range("2025-01-01", periods=35)
    daily = pd.DataFrame({"date": dates, "inflow": np.ones(35), "outflow": np.zeros(35)})
    forecast = forecast_flows(daily, 2, method="baseline", start_date=pd.Timestamp("2025-02-10"))
    assert forecast.iloc[0]["date"] == pd.Timestamp("2025-02-11")


def test_error_metrics_handle_zero_denominator():
    result = error_metrics([0, 0], [1, -1])
    assert result["MAE"] == 1
    assert result["RMSE"] == 1
    assert np.isnan(result["WAPE"])
