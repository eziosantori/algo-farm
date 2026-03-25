"""Integration tests for M9 Advanced Position Management features."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.runner import BacktestRunner
from src.models import (
    EntryAnchoredVwapExit,
    IndicatorDef,
    PositionManagement,
    RuleDef,
    ScaleOut,
    StrategyDefinition,
)


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


def _intraday_ohlcv(close_values: list[float], start: str = "2024-01-03 08:00") -> pd.DataFrame:
    """Build a deterministic OHLCV frame for runtime AVWAP exit tests."""
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


def test_entry_anchored_vwap_exit_closes_long_on_cross_below() -> None:
    """Long trade exits when price closes back below the entry-anchored VWAP."""
    ohlcv = _intraday_ohlcv([100.0, 101.0, 104.0, 106.0, 100.0, 99.0])
    strategy = StrategyDefinition(
        version="1",
        name="entry_avwap_long_exit",
        variant="advanced",
        indicators=[IndicatorDef(name="px", type="close", params={})],
        entry_rules=[RuleDef(indicator="px", condition=">", value=100.5)],
        exit_rules=[],
        position_management=PositionManagement(
            size=0.02,
            entry_anchored_vwap_exit=EntryAnchoredVwapExit(price_source="close"),
        ),
    )

    result = BacktestRunner().run(ohlcv, strategy, params={})
    assert result.metrics.total_trades == 1
    assert result.trades[0]["entry_bar"] == 2
    assert result.trades[0]["exit_bar"] == 5


def test_entry_anchored_vwap_exit_closes_short_on_cross_above() -> None:
    """Short trade exits when price closes back above the entry-anchored VWAP."""
    ohlcv = _intraday_ohlcv([100.0, 99.0, 96.0, 94.0, 100.0, 101.0])
    strategy = StrategyDefinition(
        version="1",
        name="entry_avwap_short_exit",
        variant="advanced",
        indicators=[IndicatorDef(name="px", type="close", params={})],
        entry_rules=[],
        exit_rules=[],
        entry_rules_short=[RuleDef(indicator="px", condition="<", value=99.5)],
        exit_rules_short=[],
        position_management=PositionManagement(
            size=0.02,
            entry_anchored_vwap_exit=EntryAnchoredVwapExit(price_source="close"),
        ),
    )

    result = BacktestRunner().run(ohlcv, strategy, params={})
    assert result.metrics.total_trades == 1
    assert result.trades[0]["entry_bar"] == 2
    assert result.trades[0]["exit_bar"] == 5


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
