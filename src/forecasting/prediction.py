"""Build a complete balance forecast from history and explicit future events."""

import pandas as pd

from src.forecasting.evaluation import evaluate_balance_horizons, walk_forward_evaluation
from src.forecasting.models import forecast_flows


def build_forecast(
    operations: pd.DataFrame,
    horizon_days: int = 90,
    starting_balance: float | None = None,
    events: pd.DataFrame | None = None,
    recurring: pd.DataFrame | None = None,
    account: str | None = None,
    method: str = "auto",
    start_date: pd.Timestamp | None = None,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Produce dated projections and preserve known events as a separate layer."""
    from src.data.preprocessing import aggregate_daily
    from src.future_events.manager import merge_future_flows

    history_ops = operations if account is None else operations.loc[operations["account"] == account]
    daily = aggregate_daily(history_ops)
    if daily.empty:
        raise ValueError("Нет операций для выбранного счёта.")
    forecast_start = pd.Timestamp(start_date or daily["date"].max()).normalize()
    backtest, metrics = walk_forward_evaluation(daily, horizon=7)
    selected_method = "baseline"
    if not metrics.empty and {"ML", "baseline"}.issubset(set(metrics["method"])):
        score = metrics.set_index("method")["MAE"]
        selected_method = "ML" if score["ML"] < score["baseline"] else "baseline"
    forecast_method = selected_method if method == "auto" else method
    forecast = forecast_flows(daily, horizon_days, method=forecast_method, start_date=forecast_start)
    used_method = forecast.attrs.get("method", forecast_method)
    last_date = forecast_start
    event_flows = merge_future_flows(last_date, horizon_days, events, recurring, account)
    forecast = forecast.merge(event_flows, on="date", how="left")
    forecast["event_flow"] = forecast["event_flow"].fillna(0.0)
    forecast["event_count"] = forecast["event_count"].fillna(0).astype(int)
    forecast["forecast_net"] = forecast["net_flow"] + forecast["event_flow"]

    balance_series = history_ops.loc[history_ops["balance"].notna()].sort_values("date")
    closing = balance_series.groupby("date")["balance"].last()
    if not closing.empty:
        current_balance = float(closing.iloc[-1])
        balance_source = "остаток из выписки"
    elif starting_balance is not None:
        current_balance = float(starting_balance)
        balance_source = "введён пользователем"
    else:
        current_balance = None
        balance_source = "неизвестен"
    if current_balance is not None:
        forecast["balance"] = current_balance + forecast["forecast_net"].cumsum()
        validation_errors = pd.Series(dtype=float)
        if not backtest.empty:
            validation_errors = (
                backtest.loc[backtest["method"] == selected_method, "actual_net"] -
                backtest.loc[backtest["method"] == selected_method, "predicted_net"]
            )
        if len(validation_errors) >= 14:
            # Approximate cumulative interval from the selected model's held-out flow errors.
            spread = float(validation_errors.std(ddof=1))
            expansion = 1.96 * spread * (forecast.index.to_series().add(1).pow(0.5).to_numpy())
            forecast["lower"] = forecast["balance"] - expansion
            forecast["upper"] = forecast["balance"] + expansion
        else:
            forecast["lower"] = float("nan")
            forecast["upper"] = float("nan")
    else:
        forecast["balance"] = float("nan")
        forecast["lower"] = float("nan")
        forecast["upper"] = float("nan")

    return forecast, {
        "daily": daily,
        "current_balance": current_balance,
        "balance_source": balance_source,
        "metrics": metrics,
        "balance_horizons": evaluate_balance_horizons(daily),
        "backtest": backtest,
        "selected_method": selected_method,
        "forecast_method": used_method,
    }
