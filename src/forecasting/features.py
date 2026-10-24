"""Leakage-safe time-series features."""

import pandas as pd


def feature_row(history: pd.Series, date: pd.Timestamp) -> dict[str, float]:
    """Create calendar and lag features using observations strictly before date."""
    past = history.loc[history.index < date].tail(28)
    values = past.to_list()
    row: dict[str, float] = {
        "weekday": float(date.weekday()),
        "day": float(date.day),
        "month": float(date.month),
        "weekofyear": float(date.isocalendar().week),
    }
    for lag in (1, 7, 14, 28):
        row[f"lag_{lag}"] = float(values[-lag]) if len(values) >= lag else 0.0
    row["mean_7"] = float(past.tail(7).mean()) if len(past) else 0.0
    row["mean_28"] = float(past.mean()) if len(past) else 0.0
    return row


def supervised_features(series: pd.Series) -> tuple[pd.DataFrame, pd.Series]:
    """Build rows from historical data where each row only sees earlier values."""
    rows, targets = [], []
    for date in series.index[28:]:
        rows.append(feature_row(series, date))
        targets.append(float(series.loc[date]))
    return pd.DataFrame(rows, index=series.index[28:]), pd.Series(targets, index=series.index[28:])
