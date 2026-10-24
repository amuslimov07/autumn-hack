"""Deterministic and block-bootstrap cash reserve risk analysis."""

import numpy as np
import pandas as pd


def assess_risk(
    forecast: pd.DataFrame,
    reserve: float = 0.0,
    residuals: np.ndarray | list[float] | None = None,
    scenarios: int = 1000,
    seed: int = 42,
    block_size: int = 7,
    events: pd.DataFrame | None = None,
) -> dict[str, object]:
    """Assess reserve breaches and optionally bootstrap historical forecast errors."""
    if forecast.empty or forecast["balance"].isna().all():
        return {"first_breach": None, "max_deficit": None, "zero_deficit": None, "reserve_deficit": None,
                "probability": None, "risk_level": "не оценён", "method": "Недостаточно данных для оценки вероятности",
                "warning": None, "influencing_events": [], "horizon_days": len(forecast)}
    below = forecast.loc[forecast["balance"] < reserve]
    first = None if below.empty else below.iloc[0]
    deficit = float(max(0, reserve - forecast["balance"].min()))
    zero_deficit = float(max(0, -forecast["balance"].min()))
    influencing_events = []
    if events is not None and first is not None and not events.empty:
        eligible = events.loc[
            events["status"].isin(["ожидается", "подтверждено"]) &
            (pd.to_datetime(events["date"]) >= pd.Timestamp(forecast["date"].min())) &
            (pd.to_datetime(events["date"]) <= pd.Timestamp(first["date"]))
        ]
        influencing_events = [
            {"date": pd.Timestamp(row["date"]), "amount": float(row["amount"]),
             "description": str(row.get("description", "")) or str(row.get("category", "Событие"))}
            for row in eligible.sort_values("date").to_dict("records")
        ]
    errors = np.asarray(residuals if residuals is not None else [], dtype=float)
    probability = None
    method = "Недостаточно данных для оценки вероятности"
    if len(errors) >= 30 and scenarios >= 100:
        rng = np.random.default_rng(seed)
        net = forecast["forecast_net"].to_numpy(dtype=float)
        base = float(forecast["balance"].iloc[0] - forecast["forecast_net"].iloc[0])
        breaches = 0
        n = len(net)
        blocks_needed = int(np.ceil(n / block_size))
        for _ in range(scenarios):
            sample = []
            for _ in range(blocks_needed):
                start = int(rng.integers(0, len(errors) - block_size + 1))
                sample.extend(errors[start:start + block_size])
            scenario_balance = base + np.cumsum(net + np.asarray(sample[:n]))
            breaches += int(np.any(scenario_balance < reserve))
        probability = breaches / scenarios
        method = f"Блочный bootstrap ошибок walk-forward (блок {block_size} дней, {len(errors)} ошибок, {scenarios} сценариев)"
    level = "высокий" if (probability is not None and probability >= 0.5) or (probability is None and first is not None and deficit > 0) else (
        "средний" if (probability is not None and probability >= 0.15) or first is not None else "низкий"
    )
    warning = None
    if first is not None:
        warning = {
            "date": pd.Timestamp(first["date"]),
            "deficit": float(max(0, reserve - first["balance"])),
            "probability": probability,
            "reasons": "Планируемые расходы превышают доступный остаток относительно выбранного резерва.",
            "action": "Проверьте ближайшие крупные платежи и заранее согласуйте сроки поступлений.",
        }
    return {
        "first_breach": None if first is None else pd.Timestamp(first["date"]),
        "max_deficit": deficit,
        "zero_deficit": zero_deficit,
        "reserve_deficit": deficit,
        "influencing_events": influencing_events,
        "probability": probability,
        "risk_level": level,
        "method": method,
        "warning": warning,
        "reserve": reserve,
        "horizon_days": len(forecast),
    }
