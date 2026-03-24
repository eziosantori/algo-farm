"""Unit tests for OOSValidator."""
from __future__ import annotations

import dataclasses
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.robustness.oos import OOSValidator, _compute_degradation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 200) -> pd.DataFrame:
    import numpy as np
    rng = np.random.default_rng(0)
    price = 1.1000 + rng.standard_normal(n).cumsum() * 0.001
    return pd.DataFrame(
        {
            "open": price,
            "high": price + 0.0005,
            "low": price - 0.0005,
            "close": price,
            "volume": rng.integers(100, 1000, n).astype(float),
        }
    )


def _mock_result(sharpe: float = 1.0, total_return: float = 0.05) -> MagicMock:
    """Produce a mock BacktestResult with a metrics dataclass."""
    from src.models import BacktestMetrics  # noqa: PLC0415
    metrics = BacktestMetrics(
        sharpe_ratio=sharpe,
        sortino_ratio=sharpe * 0.9,
        calmar_ratio=0.5,
        total_return_pct=total_return * 100,
        cagr_pct=total_return * 50,
        max_drawdown_pct=10.0,
        max_balance_dd_pct=8.0,
        total_trades=10,
        win_rate_pct=50.0,
        profit_factor=1.2,
        expectancy=0.01,
        avg_trade_duration_bars=5,
    )
    result = MagicMock()
    result.metrics = metrics
    return result


# ---------------------------------------------------------------------------
# OOSValidator.split
# ---------------------------------------------------------------------------

def test_split_proportions() -> None:
    ohlcv = _make_ohlcv(100)
    validator = OOSValidator(oos_pct=0.2)
    is_data, oos_data = validator.split(ohlcv)
    assert len(is_data) == 80
    assert len(oos_data) == 20


def test_split_no_overlap() -> None:
    ohlcv = _make_ohlcv(100)
    validator = OOSValidator(oos_pct=0.3)
    is_data, oos_data = validator.split(ohlcv)
    assert len(is_data) + len(oos_data) == len(ohlcv)
    assert is_data.index[-1] < oos_data.index[0]


# ---------------------------------------------------------------------------
# OOSValidator.validate
# ---------------------------------------------------------------------------

def test_validate_returns_required_keys() -> None:
    from src.models import IndicatorDef, PositionManagement, RuleDef, StrategyDefinition  # noqa: PLC0415
    definition = StrategyDefinition(
        version="1",
        name="Test",
        variant="basic",
        indicators=[IndicatorDef(name="sma", type="sma", params={"period": 10})],
        entry_rules=[RuleDef(indicator="sma", condition=">", value=0.0)],
        exit_rules=[],
        position_management=PositionManagement(),
    )
    ohlcv = _make_ohlcv(200)
    validator = OOSValidator(oos_pct=0.2)

    mock_is = _mock_result(sharpe=1.5, total_return=0.08)
    mock_oos = _mock_result(sharpe=1.0, total_return=0.04)

    with patch("src.robustness.oos.BacktestRunner") as MockRunner:
        MockRunner.return_value.run.side_effect = [mock_is, mock_oos]
        result = validator.validate(ohlcv, definition, {})

    assert "is_metrics" in result
    assert "oos_metrics" in result
    assert "degradation" in result
    assert "is_bars" in result
    assert "oos_bars" in result
    assert result["is_bars"] + result["oos_bars"] == len(ohlcv)


def test_validate_raises_when_too_few_bars() -> None:
    from src.models import IndicatorDef, PositionManagement, RuleDef, StrategyDefinition  # noqa: PLC0415
    definition = StrategyDefinition(
        version="1",
        name="Test",
        variant="basic",
        indicators=[IndicatorDef(name="sma", type="sma", params={"period": 10})],
        entry_rules=[RuleDef(indicator="sma", condition=">", value=0.0)],
        exit_rules=[],
        position_management=PositionManagement(),
    )
    # 50 bars total, 90% IS → OOS = 5 bars < 30 minimum
    ohlcv = _make_ohlcv(50)
    validator = OOSValidator(oos_pct=0.1)
    with pytest.raises(ValueError, match="Insufficient data"):
        validator.validate(ohlcv, definition, {})


def test_oos_validator_rejects_invalid_pct() -> None:
    with pytest.raises(ValueError):
        OOSValidator(oos_pct=0.0)
    with pytest.raises(ValueError):
        OOSValidator(oos_pct=1.0)


# ---------------------------------------------------------------------------
# _compute_degradation
# ---------------------------------------------------------------------------

def test_degradation_negative_when_oos_worse() -> None:
    is_m = {"sharpe_ratio": 2.0}
    oos_m = {"sharpe_ratio": 1.0}
    deg = _compute_degradation(is_m, oos_m)
    assert deg["sharpe_ratio"] == pytest.approx(-0.5, abs=1e-4)


def test_degradation_positive_when_oos_better() -> None:
    is_m = {"sharpe_ratio": 1.0}
    oos_m = {"sharpe_ratio": 1.5}
    deg = _compute_degradation(is_m, oos_m)
    assert deg["sharpe_ratio"] == pytest.approx(0.5, abs=1e-4)


def test_degradation_none_when_is_zero() -> None:
    is_m = {"sharpe_ratio": 0.0}
    oos_m = {"sharpe_ratio": 1.0}
    deg = _compute_degradation(is_m, oos_m)
    assert deg["sharpe_ratio"] is None


def test_degradation_none_for_non_numeric() -> None:
    is_m = {"label": "foo"}
    oos_m = {"label": "bar"}
    deg = _compute_degradation(is_m, oos_m)
    assert deg["label"] is None
