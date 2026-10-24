import numpy as np
import pandas as pd

from src.risk.assessment import assess_risk


def test_deterministic_breach_and_insufficient_probability():
    forecast = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=3), "balance": [120, 80, 20],
                             "forecast_net": [-40, -40, -60]})
    result = assess_risk(forecast, reserve=50)
    assert result["first_breach"] == pd.Timestamp("2025-01-03")
    assert result["max_deficit"] == 30
    assert result["probability"] is None
    assert "Недостаточно данных" in result["method"]


def test_bootstrap_probability_is_reproducible_with_enough_errors():
    forecast = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=14), "balance": np.linspace(500, 100, 14),
                             "forecast_net": np.full(14, -20.0)})
    errors = np.sin(np.arange(60)) * 10
    first = assess_risk(forecast, reserve=150, residuals=errors, scenarios=200, seed=7)
    second = assess_risk(forecast, reserve=150, residuals=errors, scenarios=200, seed=7)
    assert first["probability"] == second["probability"]
    assert 0 <= first["probability"] <= 1


def test_unknown_balance_has_no_success_shaped_risk_numbers():
    forecast = pd.DataFrame({"date": pd.date_range("2025-01-01", periods=2), "balance": [np.nan, np.nan],
                             "forecast_net": [-10, 0]})
    result = assess_risk(forecast, reserve=100)
    assert result["max_deficit"] is None
    assert result["zero_deficit"] is None
    assert result["probability"] is None
