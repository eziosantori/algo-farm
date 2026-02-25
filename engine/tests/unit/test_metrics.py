"""Unit tests for src/metrics.py."""
from __future__ import annotations

import numpy as np
import pytest

from src.metrics import calculate_metrics
from src.models import BacktestMetrics


def test_zero_trades_returns_zero_metrics() -> None:
    equity = np.array([10000.0, 10000.0, 10000.0])
    m = calculate_metrics(equity, [])
    assert m.total_trades == 0
    assert m.win_rate_pct == 0.0


def test_total_return_positive() -> None:
    equity = np.array([10000.0, 11000.0])
    m = calculate_metrics(equity, [])
    assert abs(m.total_return_pct - 10.0) < 0.001


def test_total_return_negative() -> None:
    equity = np.array([10000.0, 9000.0])
    m = calculate_metrics(equity, [])
    assert abs(m.total_return_pct - (-10.0)) < 0.001


def test_max_drawdown_is_negative() -> None:
    equity = np.array([10000.0, 12000.0, 8000.0, 9000.0])
    m = calculate_metrics(equity, [])
    # Peak is 12000, trough after peak is 8000 → dd = -33.3%
    assert m.max_drawdown_pct < 0
    assert abs(m.max_drawdown_pct - (-33.333)) < 0.1


def test_sharpe_ratio_positive_trend() -> None:
    """Monotonically increasing equity should have positive Sharpe."""
    rng = np.random.default_rng(0)
    equity = 10000.0 + np.cumsum(np.abs(rng.normal(1, 0.1, 300)))
    m = calculate_metrics(equity, [])
    assert m.sharpe_ratio > 0


def test_win_rate_calculation() -> None:
    trades = [
        {"pnl": 100.0, "duration_bars": 5},
        {"pnl": -50.0, "duration_bars": 3},
        {"pnl": 200.0, "duration_bars": 7},
        {"pnl": -30.0, "duration_bars": 2},
    ]
    equity = np.linspace(10000, 10220, 100)
    m = calculate_metrics(equity, trades)
    assert m.total_trades == 4
    assert abs(m.win_rate_pct - 50.0) < 0.001


def test_profit_factor() -> None:
    trades = [
        {"pnl": 300.0, "duration_bars": 5},
        {"pnl": -100.0, "duration_bars": 3},
    ]
    equity = np.linspace(10000, 10200, 50)
    m = calculate_metrics(equity, trades)
    assert abs(m.profit_factor - 3.0) < 0.001


def test_avg_trade_duration() -> None:
    trades = [
        {"pnl": 10.0, "duration_bars": 4},
        {"pnl": 10.0, "duration_bars": 6},
    ]
    equity = np.linspace(10000, 10020, 50)
    m = calculate_metrics(equity, trades)
    assert abs(m.avg_trade_duration_bars - 5.0) < 0.001


def test_calmar_ratio() -> None:
    """Calmar = CAGR / |max_drawdown_pct|."""
    equity = np.array([10000.0, 11000.0, 9000.0, 12000.0])
    m = calculate_metrics(equity, [], bars_per_year=252)
    if m.max_drawdown_pct != 0:
        expected_calmar = m.cagr_pct / abs(m.max_drawdown_pct)
        assert abs(m.calmar_ratio - expected_calmar) < 0.001


def test_short_equity_returns_zero_metrics() -> None:
    m = calculate_metrics(np.array([10000.0]), [])
    assert m.total_return_pct == 0.0
