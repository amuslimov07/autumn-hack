"""Baseline and ML daily flow models."""

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from config.settings import MINIMUM_HISTORY_DAYS_FOR_ML, RANDOM_SEED
from src.forecasting.features import feature_row, supervised_features


def baseline_value(history: pd.Series, date: pd.Timestamp) -> float:
    """Use same-weekday median when available, otherwise trailing 28-day median."""
    weekday = history.loc[history.index.day_of_week == date.day_of_week].tail(12)
    recent = history.tail(28)
    if len(weekday) >= 4:
        return float(weekday.median())
    return float(recent.median()) if len(recent) else 0.0


def _fit_ml(history: pd.Series) -> HistGradientBoostingRegressor | None:
    if len(history) < MINIMUM_HISTORY_DAYS_FOR_ML:
        return None
    x, y = supervised_features(history)
    if len(x) < 60:
        return None
    model = HistGradientBoostingRegressor(max_iter=100, max_leaf_nodes=12, l2_regularization=1.0, random_state=RANDOM_SEED)
    model.fit(x, y)
    return model


def forecast_component(history: pd.Series, future_dates: pd.DatetimeIndex, method: str) -> pd.Series:
    """Forecast one nonnegative flow component recursively."""
    series = history.astype(float).copy().sort_index()
    predictions = []
    model = _fit_ml(series) if method == "ML" else None
    chosen = "ML" if model is not None else "baseline"
    for date in future_dates:
        if chosen == "ML":
            features = pd.DataFrame([feature_row(series, date)])
            value = float(model.predict(features)[0])
        else:
            value = baseline_value(series, date)
        value = max(0.0, value)
        predictions.append(value)
        series.loc[date] = value
    return pd.Series(predictions, index=future_dates, dtype=float)


def forecast_flows(daily: pd.DataFrame, horizon_days: int, method: str = "auto", start_date: pd.Timestamp | None = None) -> pd.DataFrame:
    """Forecast inflows and outflows independently and report selected method."""
    if daily.empty:
        raise ValueError("Для прогноза нужна хотя бы одна историческая операция.")
    indexed = daily.set_index("date").sort_index().asfreq("D", fill_value=0)
    date0 = pd.Timestamp(start_date or indexed.index.max())
    if date0 < indexed.index.max():
        raise ValueError("Дата начала прогноза не может предшествовать последним историческим данным.")
    if date0 > indexed.index.max():
        full_index = pd.date_range(indexed.index.min(), date0, freq="D")
        indexed = indexed.reindex(full_index, fill_value=0.0)
        indexed.index.name = "date"
    future_dates = pd.date_range(date0 + pd.Timedelta(days=1), periods=horizon_days)
    requested = method
    use_ml = method in {"auto", "ML"} and len(indexed) >= MINIMUM_HISTORY_DAYS_FOR_ML
    selected = "ML" if use_ml else "baseline"
    inflow = forecast_component(indexed["inflow"], future_dates, selected)
    outflow = forecast_component(indexed["outflow"], future_dates, selected)
    if requested == "ML" and selected == "baseline":
        selected = "baseline (недостаточно истории)"
    result = pd.DataFrame({"date": future_dates, "inflow": inflow.values, "outflow": outflow.values})
    result["net_flow"] = result["inflow"] - result["outflow"]
    result.attrs["method"] = selected
    return result
