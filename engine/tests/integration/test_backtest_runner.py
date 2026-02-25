"""Integration tests for BacktestRunner with fixture data."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.backtest.runner import BacktestRunner
from src.models import StrategyDefinition


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
