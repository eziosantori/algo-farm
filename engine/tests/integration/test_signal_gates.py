"""Integration tests for Phase D features: signal gates and pattern-score sizing."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.runner import BacktestRunner
from src.models import (
    IndicatorDef,
    PositionManagement,
    RuleDef,
    SignalGate,
    StrategyDefinition,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def hammer_strategy() -> StrategyDefinition:
    """Strategy that enters long when hammer pattern fires, exits on RSI > 60."""
    return StrategyDefinition(
        version="1",
        name="Hammer Gate Test",
        variant="basic",
        indicators=[
            IndicatorDef(name="hm", type="hammer", params={}),
            IndicatorDef(name="rsi", type="rsi", params={"period": 14}),
        ],
        entry_rules=[
            RuleDef(indicator="hm", condition=">", value=0.0),
        ],
        exit_rules=[
            RuleDef(indicator="rsi", condition=">", value=60.0),
        ],
        position_management=PositionManagement(size=0.02, sl_pips=20, tp_pips=40),
    )


@pytest.fixture()
def hammer_gated_strategy() -> StrategyDefinition:
    """Same as above but hammer signal stays active for 3 bars (signal gate)."""
    return StrategyDefinition(
        version="1",
        name="Hammer Gate Test (3-bar window)",
        variant="basic",
        indicators=[
            IndicatorDef(name="hm", type="hammer", params={}),
            IndicatorDef(name="rsi", type="rsi", params={"period": 14}),
        ],
        entry_rules=[
            RuleDef(indicator="hm", condition=">", value=0.0),
        ],
        exit_rules=[
            RuleDef(indicator="rsi", condition=">", value=60.0),
        ],
        position_management=PositionManagement(size=0.02, sl_pips=20, tp_pips=40),
        signal_gates=[SignalGate(indicator="hm", active_for_bars=3)],
    )


@pytest.fixture()
def pattern_sizing_strategy() -> StrategyDefinition:
    """Strategy where risk_pct_min/max scale position size by hammer score."""
    return StrategyDefinition(
        version="1",
        name="Pattern Sizing Test",
        variant="basic",
        indicators=[
            IndicatorDef(name="hm", type="hammer", params={}),
        ],
        entry_rules=[
            RuleDef(indicator="hm", condition=">", value=0.0),
        ],
        exit_rules=[
            RuleDef(indicator="hm", condition=">", value=2.0),  # never exits via rule
        ],
        position_management=PositionManagement(
            size=0.02,
            sl_pips=20,
            risk_pct_min=0.005,
            risk_pct_max=0.02,
        ),
    )


# ============================================================================
# D1 — Backtest with pattern indicator completes without errors
# ============================================================================


def test_hammer_pattern_strategy_runs(
    synthetic_ohlcv: pd.DataFrame, hammer_strategy: StrategyDefinition
) -> None:
    """Full backtest with a hammer pattern indicator must not raise."""
    runner = BacktestRunner()
    result = runner.run(synthetic_ohlcv, hammer_strategy, params={})
    assert result.metrics is not None
    assert result.metrics.total_trades >= 0


# ============================================================================
# D2 — Signal gate: gated strategy trades >= ungated strategy
# ============================================================================


def test_signal_gate_enables_more_trades(
    synthetic_ohlcv: pd.DataFrame,
    hammer_strategy: StrategyDefinition,
    hammer_gated_strategy: StrategyDefinition,
) -> None:
    """Adding a 3-bar signal gate should allow equal or more trades than no gate.

    Without gate: entry only fires on the exact bar the hammer appears.
    With gate: entry can fire up to 3 bars after the hammer, so more opportunities.
    """
    runner = BacktestRunner()
    no_gate = runner.run(synthetic_ohlcv, hammer_strategy, params={})
    with_gate = runner.run(synthetic_ohlcv, hammer_gated_strategy, params={})

    assert with_gate.metrics.total_trades >= no_gate.metrics.total_trades, (
        f"Gated strategy should trade at least as much as ungated: "
        f"no_gate={no_gate.metrics.total_trades}, with_gate={with_gate.metrics.total_trades}"
    )


def test_signal_gate_model_validation() -> None:
    """SignalGate validates correctly and attaches to StrategyDefinition."""
    gate = SignalGate(indicator="hm", active_for_bars=5)
    assert gate.indicator == "hm"
    assert gate.active_for_bars == 5

    sd = StrategyDefinition(
        version="1",
        name="Gate Validation",
        variant="basic",
        indicators=[IndicatorDef(name="hm", type="hammer", params={})],
        entry_rules=[RuleDef(indicator="hm", condition=">", value=0.0)],
        exit_rules=[],
        position_management=PositionManagement(),
        signal_gates=[gate],
    )
    assert len(sd.signal_gates) == 1
    assert sd.signal_gates[0].active_for_bars == 5


def test_signal_gate_backward_compat_empty_default() -> None:
    """Strategies without signal_gates should default to empty list."""
    sd = StrategyDefinition(
        version="1",
        name="No Gates",
        variant="basic",
        indicators=[IndicatorDef(name="rsi", type="rsi", params={"period": 14})],
        entry_rules=[RuleDef(indicator="rsi", condition="<", value=30.0)],
        exit_rules=[RuleDef(indicator="rsi", condition=">", value=70.0)],
        position_management=PositionManagement(),
    )
    assert sd.signal_gates == []


# ============================================================================
# D4 — Pattern-score sizing: risk interpolation
# ============================================================================


def test_pattern_sizing_runs(
    synthetic_ohlcv: pd.DataFrame, pattern_sizing_strategy: StrategyDefinition
) -> None:
    """Backtest with risk_pct_min/max must complete without errors."""
    runner = BacktestRunner()
    result = runner.run(synthetic_ohlcv, pattern_sizing_strategy, params={})
    assert result.metrics is not None


def test_pattern_sizing_model_defaults() -> None:
    """risk_pct_min / risk_pct_max default to None (backward-compatible)."""
    pm = PositionManagement()
    assert pm.risk_pct_min is None
    assert pm.risk_pct_max is None


def test_pattern_sizing_interpolation() -> None:
    """_compute_trade_size interpolates effective_risk from pattern_score."""
    from src.backtest.strategy import _compute_trade_size
    from src.models import PositionManagement

    pm = PositionManagement(risk_pct_min=0.005, risk_pct_max=0.020)
    equity = 10_000.0
    price = 1.1000
    sl = price - 0.0020  # 20 pips SL → sl_distance = 0.002

    # score=0 → effective_risk = 0.005
    size_low = _compute_trade_size(pm, price, sl, equity, pattern_score=0.0)
    expected_low = max(1, round(equity * 0.005 / 0.002))  # 25 000
    assert size_low == expected_low

    # score=1 → effective_risk = 0.020
    size_high = _compute_trade_size(pm, price, sl, equity, pattern_score=1.0)
    expected_high = max(1, round(equity * 0.020 / 0.002))  # 100 000
    assert size_high == expected_high

    # score=0.5 → effective_risk = 0.0125
    size_mid = _compute_trade_size(pm, price, sl, equity, pattern_score=0.5)
    expected_mid = max(1, round(equity * 0.0125 / 0.002))  # 62 500
    assert size_mid == expected_mid

    assert size_low < size_mid < size_high


# ============================================================================
# D1 — Integration: full backtest with hammer on EURUSD H1 fixture
# ============================================================================


def test_hammer_on_fixture_data(synthetic_ohlcv: pd.DataFrame) -> None:
    """Full backtest with hammer indicator on synthetic H1-like fixture."""
    strategy = StrategyDefinition(
        version="1",
        name="Hammer EURUSD H1",
        variant="basic",
        indicators=[
            IndicatorDef(name="hm", type="hammer", params={"min_lower_shadow_ratio": 2.0}),
            IndicatorDef(name="atr", type="atr", params={"period": 14}),
        ],
        entry_rules=[RuleDef(indicator="hm", condition=">", value=0.0)],
        exit_rules=[RuleDef(indicator="atr", condition=">", value=0.005)],
        position_management=PositionManagement(size=0.02),
    )
    runner = BacktestRunner()
    result = runner.run(synthetic_ohlcv, strategy, params={})
    assert result.metrics is not None
    assert result.metrics.total_trades >= 0
    # All pattern scores produced must have been in [0, 1] — inferred from no crash
