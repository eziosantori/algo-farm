"""Integration tests for BacktestRunner with fixture data."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.backtest.runner import BacktestRunner
from src.models import IndicatorDef, PositionManagement, RuleDef, StrategyDefinition


@pytest.fixture()
def sma_strategy() -> StrategyDefinition:
    fixtures = Path(__file__).parent.parent / "fixtures"
    with open(fixtures / "simple_sma_strategy.json") as f:
        data = json.load(f)
    return StrategyDefinition.model_validate(data)


def test_backtest_runner_returns_run_result(
    synthetic_ohlcv: pd.DataFrame, sma_strategy: StrategyDefinition
) -> None:
    runner = BacktestRunner()
    result = runner.run(synthetic_ohlcv, sma_strategy, params={"period": 10})
    assert result.metrics is not None
    assert isinstance(result.equity_curve, list)
    assert len(result.equity_curve) > 0
    assert isinstance(result.trades, list)


def test_backtest_runner_metrics_are_finite(
    synthetic_ohlcv: pd.DataFrame, sma_strategy: StrategyDefinition
) -> None:
    import math

    runner = BacktestRunner()
    result = runner.run(synthetic_ohlcv, sma_strategy, params={})
    m = result.metrics
    assert math.isfinite(m.sharpe_ratio) or m.sharpe_ratio == 0.0
    assert math.isfinite(m.total_return_pct)
    assert m.total_trades >= 0
    assert m.win_rate_pct >= 0 and m.win_rate_pct <= 100


def test_backtest_runner_equity_curve_starts_at_10k(
    synthetic_ohlcv: pd.DataFrame, sma_strategy: StrategyDefinition
) -> None:
    runner = BacktestRunner()
    result = runner.run(synthetic_ohlcv, sma_strategy, params={})
    assert abs(result.equity_curve[0] - 10_000.0) < 1.0


def _intraday_ohlcv(close_values: list[float], start: str = "2024-01-03 08:00") -> pd.DataFrame:
    """Build a compact intraday OHLCV frame for rule-level integration tests."""
    close = np.array(close_values, dtype=float)
    open_p = np.roll(close, 1)
    open_p[0] = close[0]
    high = np.maximum(open_p, close) + 0.2
    low = np.minimum(open_p, close) - 0.2
    volume = np.ones(len(close), dtype=float) * 1000.0
    index = pd.date_range(start, periods=len(close), freq="1h")
    return pd.DataFrame(
        {"Open": open_p, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=index,
    )


def test_backtest_runner_supports_anchored_vwap_cross_rule() -> None:
    ohlcv = _intraday_ohlcv([90.0, 80.0, 120.0, 80.0, 70.0])
    strategy = StrategyDefinition(
        version="1",
        name="anchored_vwap_cross",
        variant="basic",
        indicators=[
            IndicatorDef(name="px", type="close", params={}),
            IndicatorDef(
                name="avwap",
                type="anchored_vwap",
                params={"anchor_mode": "start_hour", "anchor_time": "09:00", "price_source": "close"},
            ),
        ],
        entry_rules=[RuleDef(indicator="px", condition="crosses_above", compare_to="avwap")],
        exit_rules=[RuleDef(indicator="px", condition="crosses_below", compare_to="avwap")],
        position_management=PositionManagement(size=0.02),
    )

    result = BacktestRunner().run(ohlcv, strategy, params={})
    assert result.metrics.total_trades >= 1


def test_backtest_runner_supports_vwap_upper_breakout_rule() -> None:
    ohlcv = _intraday_ohlcv([100.0, 100.0, 130.0, 100.0, 100.0])
    strategy = StrategyDefinition(
        version="1",
        name="vwap_upper_breakout",
        variant="basic",
        indicators=[
            IndicatorDef(name="px", type="close", params={}),
            IndicatorDef(
                name="mid",
                type="vwap",
                params={"from_time": "08:00", "to_time": "13:00", "price_source": "close", "num_std": 1.0},
            ),
            IndicatorDef(
                name="upper",
                type="vwap_upper",
                params={"from_time": "08:00", "to_time": "13:00", "price_source": "close", "num_std": 1.0},
            ),
        ],
        entry_rules=[RuleDef(indicator="px", condition=">", compare_to="upper")],
        exit_rules=[RuleDef(indicator="px", condition="crosses_below", compare_to="mid")],
        position_management=PositionManagement(size=0.02),
    )

    result = BacktestRunner().run(ohlcv, strategy, params={})
    assert result.metrics.total_trades >= 1
