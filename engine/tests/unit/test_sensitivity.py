"""Unit tests for ParameterSensitivityAnalyzer."""
from __future__ import annotations

import pandas as pd
import pytest

from src.robustness.sensitivity import ParameterSensitivityAnalyzer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 200) -> pd.DataFrame:
    """Minimal synthetic OHLCV — all-ones so backtest can run without crashing."""
    import numpy as np
    rng = np.random.default_rng(42)
    close = 100.0 + rng.standard_normal(n).cumsum()
    close = np.maximum(close, 1.0)
    return pd.DataFrame(
        {
            "Open":   close * 0.999,
            "High":   close * 1.002,
            "Low":    close * 0.998,
            "Close":  close,
            "Volume": np.ones(n) * 1000,
        },
        index=pd.date_range("2022-01-01", periods=n, freq="h"),
    )


def _simple_strategy() -> dict:
    return {
        "version": "1",
        "name": "test_sensitivity",
        "variant": "basic",
        "indicators": [
            {"name": "rsi14", "type": "rsi", "params": {"period": 14}},
        ],
        "entry_rules": [{"indicator": "rsi14", "condition": ">", "value": 50}],
        "exit_rules":  [{"indicator": "rsi14", "condition": "<", "value": 50}],
        "position_management": {"size": 0.02, "max_open_trades": 1},
    }


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

def test_default_deltas() -> None:
    s = ParameterSensitivityAnalyzer()
    assert len(s.deltas) == 4
    assert -0.2 in s.deltas and 0.2 in s.deltas


def test_custom_deltas() -> None:
    s = ParameterSensitivityAnalyzer(deltas=(-0.1, 0.1))
    assert s.deltas == (-0.1, 0.1)


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

def test_returns_required_keys() -> None:
    from src.models import StrategyDefinition
    defn = StrategyDefinition.model_validate(_simple_strategy())
    result = ParameterSensitivityAnalyzer().analyze(_make_ohlcv(), defn, {})
    assert "base_sharpe" in result
    assert "params_tested" in result
    assert "overall_stability" in result


def test_params_tested_has_period_key() -> None:
    from src.models import StrategyDefinition
    defn = StrategyDefinition.model_validate(_simple_strategy())
    result = ParameterSensitivityAnalyzer().analyze(_make_ohlcv(), defn, {})
    assert "period" in result["params_tested"]


def test_variation_count_matches_deltas() -> None:
    from src.models import StrategyDefinition
    defn = StrategyDefinition.model_validate(_simple_strategy())
    analyzer = ParameterSensitivityAnalyzer(deltas=(-0.1, 0.1))
    result = analyzer.analyze(_make_ohlcv(), defn, {})
    period_data = result["params_tested"]["period"]
    assert len(period_data["variations"]) == 2


def test_variation_keys() -> None:
    from src.models import StrategyDefinition
    defn = StrategyDefinition.model_validate(_simple_strategy())
    result = ParameterSensitivityAnalyzer().analyze(_make_ohlcv(), defn, {})
    period_data = result["params_tested"]["period"]
    for v in period_data["variations"]:
        assert "delta_pct" in v
        assert "value" in v
        assert "sharpe" in v
        assert "sharpe_change" in v


# ---------------------------------------------------------------------------
# Statistical properties
# ---------------------------------------------------------------------------

def test_overall_stability_in_range() -> None:
    from src.models import StrategyDefinition
    defn = StrategyDefinition.model_validate(_simple_strategy())
    result = ParameterSensitivityAnalyzer().analyze(_make_ohlcv(), defn, {})
    assert 0.0 <= result["overall_stability"] <= 1.0


def test_per_param_stability_in_range() -> None:
    from src.models import StrategyDefinition
    defn = StrategyDefinition.model_validate(_simple_strategy())
    result = ParameterSensitivityAnalyzer().analyze(_make_ohlcv(), defn, {})
    for param_data in result["params_tested"].values():
        assert 0.0 <= param_data["stability"] <= 1.0


def test_no_params_returns_stability_one() -> None:
    """Strategy with no numeric params → overall_stability = 1.0."""
    from src.models import StrategyDefinition
    # Use a strategy whose indicator params are all empty (not feasible with real
    # indicators, but we can override with an empty params dict and no numeric defaults)
    defn = StrategyDefinition.model_validate(_simple_strategy())
    # Patch: manually override by providing no numeric params from the definition
    # by using a strategy with params already swept to empty
    analyzer = ParameterSensitivityAnalyzer()
    # Monkey-patch _numeric_base_params to return {}
    analyzer._numeric_base_params = lambda d, p: {}  # type: ignore[assignment]
    result = analyzer.analyze(_make_ohlcv(), defn, {})
    assert result["overall_stability"] == 1.0
    assert result["params_tested"] == {}


def test_override_params_are_used_as_base() -> None:
    """Params overrides should become the base value for sensitivity."""
    from src.models import StrategyDefinition
    defn = StrategyDefinition.model_validate(_simple_strategy())
    result = ParameterSensitivityAnalyzer().analyze(_make_ohlcv(), defn, {"period": 21})
    period_data = result["params_tested"]["period"]
    assert period_data["base_value"] == 21.0
