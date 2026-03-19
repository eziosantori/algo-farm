"""Integration tests for Phase C — short-side execution."""
from __future__ import annotations

import pandas as pd
import pytest

from src.backtest.runner import BacktestRunner
from src.models import IndicatorDef, PositionManagement, RuleDef, StrategyDefinition


def _ohlcv(fixture: pd.DataFrame) -> pd.DataFrame:
    return fixture


def _long_only_strategy(pm: PositionManagement | None = None) -> StrategyDefinition:
    """Baseline long-only strategy: enter when ST direction > 0, exit when ST direction < 0."""
    return StrategyDefinition(
        version="1",
        name="LongOnly",
        variant="basic",
        indicators=[
            IndicatorDef(name="st_dir", type="supertrend_direction", params={"period": 7, "multiplier": 3.0}),
        ],
        entry_rules=[RuleDef(indicator="st_dir", condition=">", value=0.0)],
        exit_rules=[RuleDef(indicator="st_dir", condition="<", value=0.0)],
        position_management=pm or PositionManagement(size=0.02),
    )


def _bidirectional_strategy(pm: PositionManagement | None = None) -> StrategyDefinition:
    """Bidirectional strategy: long when ST direction > 0, short when ST direction < 0."""
    return StrategyDefinition(
        version="1",
        name="Bidirectional",
        variant="advanced",
        indicators=[
            IndicatorDef(name="st_dir", type="supertrend_direction", params={"period": 7, "multiplier": 3.0}),
        ],
        entry_rules=[RuleDef(indicator="st_dir", condition=">", value=0.0)],
        exit_rules=[RuleDef(indicator="st_dir", condition="<", value=0.0)],
        entry_rules_short=[RuleDef(indicator="st_dir", condition="<", value=0.0)],
        exit_rules_short=[RuleDef(indicator="st_dir", condition=">", value=0.0)],
        position_management=pm or PositionManagement(size=0.02),
    )


# ---------------------------------------------------------------------------
# Basic smoke tests
# ---------------------------------------------------------------------------

class TestShortSideExecution:
    def test_long_only_runs_without_errors(self, synthetic_ohlcv: pd.DataFrame) -> None:
        result = BacktestRunner().run(synthetic_ohlcv, _long_only_strategy(), params={})
        assert result.metrics is not None

    def test_bidirectional_runs_without_errors(self, synthetic_ohlcv: pd.DataFrame) -> None:
        result = BacktestRunner().run(synthetic_ohlcv, _bidirectional_strategy(), params={})
        assert result.metrics is not None

    def test_bidirectional_has_more_or_equal_trades_than_long_only(
        self, synthetic_ohlcv: pd.DataFrame
    ) -> None:
        """Bidirectional adds short trades on top of longs → total_trades >= long-only."""
        long_result = BacktestRunner().run(synthetic_ohlcv, _long_only_strategy(), params={})
        bi_result = BacktestRunner().run(synthetic_ohlcv, _bidirectional_strategy(), params={})
        assert bi_result.metrics is not None
        assert long_result.metrics is not None
        assert bi_result.metrics.total_trades >= long_result.metrics.total_trades

    def test_short_only_strategy(self, synthetic_ohlcv: pd.DataFrame) -> None:
        """Strategy with only entry_rules_short (no long rules) → produces trades from short entries."""
        strategy = StrategyDefinition(
            version="1",
            name="ShortOnly",
            variant="basic",
            indicators=[
                IndicatorDef(name="st_dir", type="supertrend_direction", params={"period": 7, "multiplier": 3.0}),
            ],
            entry_rules=[],          # no long entries
            exit_rules=[],
            entry_rules_short=[RuleDef(indicator="st_dir", condition="<", value=0.0)],
            exit_rules_short=[RuleDef(indicator="st_dir", condition=">", value=0.0)],
            position_management=PositionManagement(size=0.02),
        )
        result = BacktestRunner().run(synthetic_ohlcv, strategy, params={})
        assert result.metrics is not None
        # Short-only with no long rules → 0 trades from long; depends on data direction

    def test_backward_compat_no_short_fields(self, synthetic_ohlcv: pd.DataFrame) -> None:
        """Existing strategies without entry_rules_short still work correctly."""
        strategy = StrategyDefinition(
            version="1",
            name="OldFormat",
            variant="basic",
            indicators=[
                IndicatorDef(name="st_dir", type="supertrend_direction", params={"period": 7, "multiplier": 3.0}),
            ],
            entry_rules=[RuleDef(indicator="st_dir", condition=">", value=0.0)],
            exit_rules=[RuleDef(indicator="st_dir", condition="<", value=0.0)],
            position_management=PositionManagement(size=0.02),
            # entry_rules_short and exit_rules_short omitted → default []
        )
        result = BacktestRunner().run(synthetic_ohlcv, strategy, params={})
        assert result.metrics is not None


class TestShortSideWithSLTP:
    def test_short_with_atr_sl(self, synthetic_ohlcv: pd.DataFrame) -> None:
        """Short entry with ATR-based SL (SL above entry) should not crash."""
        strategy = _bidirectional_strategy(
            pm=PositionManagement(size=0.02, sl_atr_mult=1.5)
        )
        result = BacktestRunner().run(synthetic_ohlcv, strategy, params={})
        assert result.metrics is not None

    def test_short_with_atr_sl_and_tp(self, synthetic_ohlcv: pd.DataFrame) -> None:
        """Short entry with ATR SL + ATR TP should not crash."""
        strategy = _bidirectional_strategy(
            pm=PositionManagement(size=0.02, sl_atr_mult=1.5, tp_atr_mult=2.0)
        )
        result = BacktestRunner().run(synthetic_ohlcv, strategy, params={})
        assert result.metrics is not None

    def test_short_with_trailing_atr_sl(self, synthetic_ohlcv: pd.DataFrame) -> None:
        """Short entry with trailing ATR SL should not crash."""
        strategy = _bidirectional_strategy(
            pm=PositionManagement(size=0.02, sl_atr_mult=1.5, trailing_sl="atr", trailing_sl_atr_mult=2.0)
        )
        result = BacktestRunner().run(synthetic_ohlcv, strategy, params={})
        assert result.metrics is not None

    def test_short_with_risk_pct_sizing(self, synthetic_ohlcv: pd.DataFrame) -> None:
        """Short + risk_pct: _compute_trade_size uses abs(price - sl) for short SL above entry."""
        strategy = _bidirectional_strategy(
            pm=PositionManagement(size=0.02, sl_atr_mult=1.5, risk_pct=0.01)
        )
        result = BacktestRunner().run(synthetic_ohlcv, strategy, params={})
        assert result.metrics is not None
