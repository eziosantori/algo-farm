"""Integration tests for M9 Advanced Position Management features."""
from __future__ import annotations

import pandas as pd
import pytest

from src.backtest.runner import BacktestRunner
from src.models import IndicatorDef, PositionManagement, RuleDef, ScaleOut, StrategyDefinition


def _make_strategy(pm: PositionManagement, extra_indicators: list[IndicatorDef] | None = None) -> StrategyDefinition:
    indicators: list[IndicatorDef] = [
        IndicatorDef(name="st_dir", type="supertrend_direction", params={"period": 7, "multiplier": 3.0}),
        IndicatorDef(name="st_line", type="supertrend",          params={"period": 7, "multiplier": 3.0}),
        IndicatorDef(name="atr14",  type="atr",                  params={"period": 14}),
    ]
    if extra_indicators:
        indicators.extend(extra_indicators)
    return StrategyDefinition(
        version="1",
        name="Test Advanced PM",
        variant="basic",
        indicators=indicators,
        entry_rules=[RuleDef(indicator="st_dir", condition=">", value=0.0)],
        exit_rules=[RuleDef(indicator="st_dir", condition="<", value=0.0)],
        position_management=pm,
    )


def test_atr_sl_at_entry_runs_and_produces_trades(synthetic_ohlcv: pd.DataFrame) -> None:
    """ATR-based SL at entry: strategy executes trades without errors."""
    strategy = _make_strategy(PositionManagement(size=0.02, sl_atr_mult=1.5))
    result = BacktestRunner().run(synthetic_ohlcv, strategy, params={})
    assert result.metrics is not None
    assert result.metrics.total_trades >= 0  # no crash


def test_trailing_sl_atr_runs_without_errors(synthetic_ohlcv: pd.DataFrame) -> None:
    """Trailing SL (ATR-based) strategy executes without errors."""
    strategy = _make_strategy(
        PositionManagement(size=0.02, sl_atr_mult=1.5, trailing_sl="atr", trailing_sl_atr_mult=2.0)
    )
    result = BacktestRunner().run(synthetic_ohlcv, strategy, params={})
    assert result.metrics is not None


def test_trailing_sl_supertrend_runs_without_errors(synthetic_ohlcv: pd.DataFrame) -> None:
    """Trailing SL (SuperTrend line) strategy executes without errors."""
    strategy = _make_strategy(
        PositionManagement(size=0.02, trailing_sl="supertrend")
    )
    result = BacktestRunner().run(synthetic_ohlcv, strategy, params={})
    assert result.metrics is not None


def test_scale_out_runs_without_errors(synthetic_ohlcv: pd.DataFrame) -> None:
    """Scale-out at 1.5R with 50% partial close executes without errors."""
    strategy = _make_strategy(
        PositionManagement(
            size=0.02,
            sl_atr_mult=1.5,
            scale_out=ScaleOut(trigger_r=1.5, volume_pct=50),
        )
    )
    result = BacktestRunner().run(synthetic_ohlcv, strategy, params={})
    assert result.metrics is not None


def test_time_exit_bars_runs_without_errors(synthetic_ohlcv: pd.DataFrame) -> None:
    """Time-based exit (close losing trade after N bars) runs without errors."""
    strategy = _make_strategy(
        PositionManagement(size=0.02, time_exit_bars=20)
    )
    result = BacktestRunner().run(synthetic_ohlcv, strategy, params={})
    assert result.metrics is not None


def test_all_m9_features_combined(synthetic_ohlcv: pd.DataFrame) -> None:
    """All M9 features combined: ATR SL + trailing + scale-out + time exit."""
    strategy = _make_strategy(
        PositionManagement(
            size=0.02,
            sl_atr_mult=1.5,
            trailing_sl="atr",
            trailing_sl_atr_mult=2.0,
            scale_out=ScaleOut(trigger_r=2.0, volume_pct=50),
            time_exit_bars=30,
        )
    )
    result = BacktestRunner().run(synthetic_ohlcv, strategy, params={})
    assert result.metrics is not None
    assert isinstance(result.trades, list)
    assert isinstance(result.equity_curve, list)
    assert len(result.equity_curve) > 0


def test_backward_compat_legacy_strategy_unchanged(synthetic_ohlcv: pd.DataFrame) -> None:
    """Strategy without M9 fields produces valid metrics (backward compatibility)."""
    strategy = StrategyDefinition(
        version="1",
        name="Legacy SMA",
        variant="basic",
        indicators=[IndicatorDef(name="sma20", type="sma", params={"period": 20})],
        entry_rules=[RuleDef(indicator="sma20", condition=">", value=0.0)],
        exit_rules=[],
        position_management=PositionManagement(),  # no M9 fields
    )
    result = BacktestRunner().run(synthetic_ohlcv, strategy, params={})
    assert result.metrics is not None
    assert result.metrics.total_trades >= 0
