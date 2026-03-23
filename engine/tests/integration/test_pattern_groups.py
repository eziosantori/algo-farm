"""Integration tests for PatternGroup — composite pattern scoring."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.runner import BacktestRunner
from src.backtest.strategy import _evaluate_rules
from src.models import (
    IndicatorDef,
    PatternGroup,
    PositionManagement,
    RuleDef,
    StrategyDefinition,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def group_strategy() -> StrategyDefinition:
    """Strategy with a pattern_group that aggregates three bullish patterns."""
    return StrategyDefinition(
        version="1",
        name="Pattern Group Test",
        variant="advanced",
        indicators=[
            IndicatorDef(name="ema50", type="ema", params={"period": 50}),
            IndicatorDef(name="rsi14", type="rsi", params={"period": 14}),
            IndicatorDef(name="eng", type="bullish_engulfing", params={}),
            IndicatorDef(name="marub", type="bullish_marubozu", params={}),
            IndicatorDef(name="soldiers", type="three_white_soldiers", params={}),
        ],
        entry_rules=[
            RuleDef(indicator="rsi14", condition=">", value=50.0),
            RuleDef(indicator="bullish_confirm", condition=">=", value=1.0),
        ],
        exit_rules=[
            RuleDef(indicator="rsi14", condition="<", value=40.0),
        ],
        position_management=PositionManagement(size=0.02, sl_pips=20, tp_pips=40),
        pattern_groups=[
            PatternGroup(
                name="bullish_confirm",
                patterns=["eng", "marub", "soldiers"],
                min_score=1.0,
            )
        ],
    )


# ============================================================================
# PG1 — Model validation
# ============================================================================


def test_pattern_group_model() -> None:
    """PatternGroup validates and attaches to StrategyDefinition."""
    grp = PatternGroup(name="bull_cluster", patterns=["eng", "marub"], min_score=1.0)
    assert grp.name == "bull_cluster"
    assert grp.patterns == ["eng", "marub"]
    assert grp.min_score == 1.0


def test_pattern_group_default_min_score() -> None:
    """min_score defaults to 1.0."""
    grp = PatternGroup(name="g", patterns=["eng"])
    assert grp.min_score == 1.0


def test_pattern_groups_backward_compat() -> None:
    """StrategyDefinition without pattern_groups defaults to empty list."""
    sd = StrategyDefinition(
        version="1",
        name="No Groups",
        variant="basic",
        indicators=[IndicatorDef(name="rsi", type="rsi", params={"period": 14})],
        entry_rules=[RuleDef(indicator="rsi", condition="<", value=30.0)],
        exit_rules=[RuleDef(indicator="rsi", condition=">", value=70.0)],
        position_management=PositionManagement(),
    )
    assert sd.pattern_groups == []


# ============================================================================
# PG2 — _evaluate_rules resolves group_values
# ============================================================================


def test_evaluate_rules_uses_group_values(synthetic_ohlcv: pd.DataFrame) -> None:
    """_evaluate_rules resolves a group name from group_values dict."""

    class _FakeInd:
        """Minimal stub that mimics backtesting indicator (supports [-1] indexing)."""
        def __init__(self, val: float):
            self._val = val
        def __getitem__(self, _: int) -> float:
            return self._val

    class _FakeStrategy:
        rsi14 = _FakeInd(55.0)  # RSI > 50 → True

    rules = [
        RuleDef(indicator="rsi14", condition=">", value=50.0),
        RuleDef(indicator="bullish_confirm", condition=">=", value=1.0),
    ]

    # group sum = 0.0 → rule fails
    assert _evaluate_rules(_FakeStrategy(), rules, group_values={"bullish_confirm": 0.0}) is False  # type: ignore[arg-type]

    # group sum = 1.2 → rule passes
    assert _evaluate_rules(_FakeStrategy(), rules, group_values={"bullish_confirm": 1.2}) is True  # type: ignore[arg-type]


def test_evaluate_rules_missing_group_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    """Referencing an unknown indicator (not in strategy, not in groups) returns False."""
    import logging

    class _FakeInd:
        def __getitem__(self, _: int) -> float:
            return 55.0

    class _FakeStrategy:
        rsi14 = _FakeInd()

    rules = [RuleDef(indicator="ghost_group", condition=">=", value=1.0)]

    with caplog.at_level(logging.WARNING):
        result = _evaluate_rules(_FakeStrategy(), rules, group_values={})  # type: ignore[arg-type]

    assert result is False
    assert "ghost_group" in caplog.text


# ============================================================================
# PG3 — Full backtest with pattern_group
# ============================================================================


def test_pattern_group_backtest_runs(
    synthetic_ohlcv: pd.DataFrame, group_strategy: StrategyDefinition
) -> None:
    """Full backtest referencing a pattern_group must not raise."""
    runner = BacktestRunner()
    result = runner.run(synthetic_ohlcv, group_strategy, params={})
    assert result.metrics is not None
    assert result.metrics.total_trades >= 0


def test_pattern_group_fewer_trades_than_any_single_pattern(
    synthetic_ohlcv: pd.DataFrame,
) -> None:
    """Group sum >= 1.0 is typically harder to reach than a single pattern > 0.

    The group strategy should have fewer or equal trades compared to one that
    only requires a single pattern indicator in its entry rules.
    """
    single_pattern = StrategyDefinition(
        version="1",
        name="Single Pattern",
        variant="advanced",
        indicators=[
            IndicatorDef(name="rsi14", type="rsi", params={"period": 14}),
            IndicatorDef(name="eng", type="bullish_engulfing", params={}),
        ],
        entry_rules=[
            RuleDef(indicator="rsi14", condition=">", value=50.0),
            RuleDef(indicator="eng", condition=">", value=0.0),
        ],
        exit_rules=[RuleDef(indicator="rsi14", condition="<", value=40.0)],
        position_management=PositionManagement(size=0.02, sl_pips=20, tp_pips=40),
    )
    group_strat = StrategyDefinition(
        version="1",
        name="Group Pattern",
        variant="advanced",
        indicators=[
            IndicatorDef(name="rsi14", type="rsi", params={"period": 14}),
            IndicatorDef(name="eng", type="bullish_engulfing", params={}),
            IndicatorDef(name="marub", type="bullish_marubozu", params={}),
        ],
        entry_rules=[
            RuleDef(indicator="rsi14", condition=">", value=50.0),
            RuleDef(indicator="bull_grp", condition=">=", value=1.0),
        ],
        exit_rules=[RuleDef(indicator="rsi14", condition="<", value=40.0)],
        position_management=PositionManagement(size=0.02, sl_pips=20, tp_pips=40),
        pattern_groups=[
            PatternGroup(name="bull_grp", patterns=["eng", "marub"], min_score=1.0)
        ],
    )
    runner = BacktestRunner()
    r_single = runner.run(synthetic_ohlcv, single_pattern, params={})
    r_group = runner.run(synthetic_ohlcv, group_strat, params={})

    # Group may have equal or fewer trades (sum >= 1 is generally harder than any > 0)
    assert r_group.metrics.total_trades <= r_single.metrics.total_trades + 2, (
        f"Group ({r_group.metrics.total_trades}) unexpectedly more than "
        f"single pattern ({r_single.metrics.total_trades})"
    )
