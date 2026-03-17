"""Unit tests for WalkForwardAnalyzer."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from src.robustness.walk_forward import WalkForwardAnalyzer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ohlcv(n: int = 500) -> pd.DataFrame:
    import numpy as np
    rng = np.random.default_rng(1)
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


def _mock_result(sharpe: float = 1.0, total_return: float = 0.05, trades: int = 10) -> MagicMock:
    from src.models import BacktestMetrics  # noqa: PLC0415
    metrics = BacktestMetrics(
        sharpe_ratio=sharpe,
        sortino_ratio=sharpe * 0.9,
        calmar_ratio=0.5,
        total_return_pct=total_return * 100,
        cagr_pct=total_return * 50,
        max_drawdown_pct=10.0,
        total_trades=trades,
        win_rate_pct=50.0,
        profit_factor=1.2,
        expectancy=0.01,
        avg_trade_duration_bars=5,
    )
    result = MagicMock()
    result.metrics = metrics
    return result


# ---------------------------------------------------------------------------
# WalkForwardAnalyzer.create_windows
# ---------------------------------------------------------------------------

def test_create_windows_count() -> None:
    analyzer = WalkForwardAnalyzer(n_windows=5, train_pct=0.7)
    windows = analyzer.create_windows(100)
    assert len(windows) == 5


def test_create_windows_no_overlap() -> None:
    analyzer = WalkForwardAnalyzer(n_windows=4, train_pct=0.6)
    windows = analyzer.create_windows(200)
    for i in range(len(windows) - 1):
        _, (_, oos_end) = windows[i]
        (is_start, _), _ = windows[i + 1]
        assert oos_end == is_start


def test_create_windows_covers_all_bars() -> None:
    total = 300
    analyzer = WalkForwardAnalyzer(n_windows=3, train_pct=0.7)
    windows = analyzer.create_windows(total)
    first_is_start = windows[0][0][0]
    last_oos_end = windows[-1][1][1]
    assert first_is_start == 0
    assert last_oos_end == total


def test_create_windows_raises_too_few_bars() -> None:
    analyzer = WalkForwardAnalyzer(n_windows=10, train_pct=0.7)
    with pytest.raises(ValueError, match="Too few bars"):
        analyzer.create_windows(5)


def test_analyzer_rejects_invalid_args() -> None:
    with pytest.raises(ValueError):
        WalkForwardAnalyzer(n_windows=1)
    with pytest.raises(ValueError):
        WalkForwardAnalyzer(n_windows=3, train_pct=0.0)
    with pytest.raises(ValueError):
        WalkForwardAnalyzer(n_windows=3, train_pct=1.0)


# ---------------------------------------------------------------------------
# WalkForwardAnalyzer.analyze
# ---------------------------------------------------------------------------

def test_analyze_returns_required_keys() -> None:
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
    ohlcv = _make_ohlcv(500)
    analyzer = WalkForwardAnalyzer(n_windows=3, train_pct=0.7)

    mock_r = _mock_result(sharpe=1.2)
    with patch("src.robustness.walk_forward.BacktestRunner") as MockRunner:
        MockRunner.return_value.run.return_value = mock_r
        result = analyzer.analyze(ohlcv, definition, {})

    assert "windows" in result
    assert "n_windows_run" in result
    assert "mean_is_sharpe" in result
    assert "mean_oos_sharpe" in result
    assert "wf_efficiency" in result


def test_analyze_wf_efficiency_ratio() -> None:
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
    ohlcv = _make_ohlcv(500)
    analyzer = WalkForwardAnalyzer(n_windows=3, train_pct=0.7)

    is_mock = _mock_result(sharpe=2.0)
    oos_mock = _mock_result(sharpe=1.0)

    with patch("src.robustness.walk_forward.BacktestRunner") as MockRunner:
        # Alternating IS, OOS calls per window
        MockRunner.return_value.run.side_effect = [is_mock, oos_mock] * 3
        result = analyzer.analyze(ohlcv, definition, {})

    assert result["wf_efficiency"] == pytest.approx(0.5, abs=1e-3)


def test_analyze_wf_efficiency_none_when_is_zero() -> None:
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
    ohlcv = _make_ohlcv(500)
    analyzer = WalkForwardAnalyzer(n_windows=3, train_pct=0.7)

    zero_mock = _mock_result(sharpe=0.0)
    with patch("src.robustness.walk_forward.BacktestRunner") as MockRunner:
        MockRunner.return_value.run.return_value = zero_mock
        result = analyzer.analyze(ohlcv, definition, {})

    assert result["wf_efficiency"] is None


def test_analyze_window_results_structure() -> None:
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
    ohlcv = _make_ohlcv(500)
    analyzer = WalkForwardAnalyzer(n_windows=3, train_pct=0.7)

    mock_r = _mock_result(sharpe=1.0)
    with patch("src.robustness.walk_forward.BacktestRunner") as MockRunner:
        MockRunner.return_value.run.return_value = mock_r
        result = analyzer.analyze(ohlcv, definition, {})

    for w in result["windows"]:
        assert "window" in w
        assert "is_bars" in w
        assert "oos_bars" in w
        assert "is_sharpe" in w
        assert "oos_sharpe" in w
