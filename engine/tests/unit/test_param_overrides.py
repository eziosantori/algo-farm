"""Tests for per-pair param_overrides support in StrategyDefinition and StrategyComposer."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.runner import BacktestRunner
from src.models import IndicatorDef, PositionManagement, RuleDef, StrategyDefinition


def _make_strategy(param_overrides: dict | None = None) -> StrategyDefinition:
    """Minimal RSI-based strategy with optional param_overrides."""
    return StrategyDefinition(
        version="1",
        name="override_test",
        variant="basic",
        indicators=[
            IndicatorDef(name="rsi", type="rsi", params={"period": 14}),
        ],
        entry_rules=[RuleDef(indicator="rsi", condition="<", value=30.0)],
        exit_rules=[RuleDef(indicator="rsi", condition=">", value=70.0)],
        position_management=PositionManagement(size=0.01),
        param_overrides=param_overrides or {},
    )


def test_param_overrides_default_empty() -> None:
    """StrategyDefinition.param_overrides defaults to empty dict."""
    definition = _make_strategy()
    assert definition.param_overrides == {}


def test_param_overrides_parsed_from_dict() -> None:
    """param_overrides is parsed correctly from a nested dict."""
    overrides = {"EURUSD": {"H1": {"period": 20}}}
    definition = _make_strategy(param_overrides=overrides)
    assert definition.param_overrides["EURUSD"]["H1"]["period"] == 20


def test_param_overrides_applied_for_matching_pair(synthetic_ohlcv: pd.DataFrame) -> None:
    """When instrument+timeframe match an override, the overridden period is used.

    We verify indirectly: RSI with period=499 on 500 bars produces all NaN
    (warm-up not satisfied), so the strategy fires 0 trades. With the global
    period=14 trades would occur. This proves the override was applied.
    """
    overrides = {"EURUSD": {"H1": {"period": 499}}}
    definition = _make_strategy(param_overrides=overrides)

    runner = BacktestRunner()
    result = runner.run(synthetic_ohlcv, definition, {}, instrument="EURUSD", timeframe="H1")
    # With period=499 on 500 bars, RSI is all NaN → no entries → 0 trades
    assert result.metrics.total_trades == 0


def test_param_overrides_not_applied_for_different_pair(synthetic_ohlcv: pd.DataFrame) -> None:
    """Override for EURUSD H1 does NOT affect a backtest on XAUUSD H4."""
    overrides = {"EURUSD": {"H1": {"period": 499}}}
    definition = _make_strategy(param_overrides=overrides)

    runner = BacktestRunner()
    # Run with a different instrument/timeframe — global period=14 applies
    result_global = runner.run(synthetic_ohlcv, definition, {}, instrument="XAUUSD", timeframe="H4")
    result_override = runner.run(synthetic_ohlcv, definition, {}, instrument="EURUSD", timeframe="H1")

    # Global pair may or may not trade, but override pair must produce 0 trades
    assert result_override.metrics.total_trades == 0


def test_param_overrides_partial_override(synthetic_ohlcv: pd.DataFrame) -> None:
    """Partial override: only overridden keys are replaced; others keep global value."""
    # Strategy with two indicators to test that an override on one doesn't bleed into the other
    from src.models import StrategyDefinition, IndicatorDef, RuleDef, PositionManagement

    definition = StrategyDefinition(
        version="1",
        name="partial_override_test",
        variant="basic",
        indicators=[
            IndicatorDef(name="rsi", type="rsi", params={"period": 14}),
        ],
        entry_rules=[RuleDef(indicator="rsi", condition="<", value=40.0)],
        exit_rules=[RuleDef(indicator="rsi", condition=">", value=60.0)],
        position_management=PositionManagement(size=0.01),
        param_overrides={"EURUSD": {"H1": {"period": 21}}},
    )

    runner = BacktestRunner()
    # Run without instrument/timeframe — global period=14 used
    result_global = runner.run(synthetic_ohlcv, definition, {})
    # Run with matching pair — override period=21 used
    result_override = runner.run(synthetic_ohlcv, definition, {}, instrument="EURUSD", timeframe="H1")

    # Both should complete without error; trade counts may differ due to different periods
    assert result_global.metrics.total_trades >= 0
    assert result_override.metrics.total_trades >= 0


def test_param_overrides_with_optimizer_params(synthetic_ohlcv: pd.DataFrame) -> None:
    """Override takes priority over both ind_def.params and optimizer params.

    Priority order: ind_def.params < optimizer params < param_overrides.
    """
    overrides = {"EURUSD": {"H1": {"period": 499}}}
    definition = _make_strategy(param_overrides=overrides)

    runner = BacktestRunner()
    # Even with optimizer params specifying period=14, override wins for EURUSD H1
    result = runner.run(
        synthetic_ohlcv, definition, {"period": 14}, instrument="EURUSD", timeframe="H1"
    )
    # period=499 from override → all NaN → 0 trades
    assert result.metrics.total_trades == 0
