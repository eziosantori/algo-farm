"""Unit tests for compare_to_multiplier and compare_to_offset in RuleDef."""
from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pytest

from src.backtest.strategy import _check_condition
from src.models import RuleDef


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_indicator(values: list[float]) -> MagicMock:
    arr = np.array(values, dtype=float)
    mock = MagicMock()
    mock.__getitem__ = lambda self, idx: arr[idx]
    mock.__len__ = lambda self: len(arr)
    return mock


def _make_strategy(**indicators: list[float]) -> MagicMock:
    strat = MagicMock()
    for name, values in indicators.items():
        setattr(strat, name, _make_indicator(values))
    return strat


# ---------------------------------------------------------------------------
# compare_to_multiplier
# ---------------------------------------------------------------------------

class TestCompareToMultiplier:
    def test_fires_when_current_exceeds_scaled_target(self) -> None:
        # vol_now=160, vol_avg=100 → target = 100 * 1.5 = 150 → 160 > 150 ✓
        strat = _make_strategy(vol_avg=[100.0])
        rule = RuleDef(indicator="vol_now", condition=">", compare_to="vol_avg", compare_to_multiplier=1.5)
        assert _check_condition(strat, rule, 160.0) is True

    def test_no_fire_when_current_below_scaled_target(self) -> None:
        # vol_now=140, vol_avg=100 → target = 100 * 1.5 = 150 → 140 > 150 ✗
        strat = _make_strategy(vol_avg=[100.0])
        rule = RuleDef(indicator="vol_now", condition=">", compare_to="vol_avg", compare_to_multiplier=1.5)
        assert _check_condition(strat, rule, 140.0) is False

    def test_multiplier_below_one(self) -> None:
        # current=45, ref=50 → target = 50 * 0.9 = 45 → 45 > 45 ✗ (strict)
        strat = _make_strategy(ref=[50.0])
        rule = RuleDef(indicator="x", condition=">", compare_to="ref", compare_to_multiplier=0.9)
        assert _check_condition(strat, rule, 45.0) is False

    def test_multiplier_ignored_when_no_compare_to(self) -> None:
        # multiplier has no effect when compare_to is absent; plain value comparison used
        strat = _make_strategy()
        rule = RuleDef(indicator="x", condition=">", value=10.0, compare_to_multiplier=2.0)
        assert _check_condition(strat, rule, 15.0) is True  # 15 > 10


# ---------------------------------------------------------------------------
# compare_to_offset
# ---------------------------------------------------------------------------

class TestCompareToOffset:
    def test_fires_when_current_exceeds_offset_target(self) -> None:
        # px=1205, session_high=1200 → target = 1200 + 5.0 = 1205 → 1205 > 1205 ✗ (strict)
        strat = _make_strategy(session_high=[1200.0])
        rule = RuleDef(indicator="px", condition=">", compare_to="session_high", compare_to_offset=5.0)
        assert _check_condition(strat, rule, 1205.0) is False

    def test_fires_strictly_above_offset_target(self) -> None:
        # px=1206, session_high=1200 → target = 1200 + 5.0 = 1205 → 1206 > 1205 ✓
        strat = _make_strategy(session_high=[1200.0])
        rule = RuleDef(indicator="px", condition=">", compare_to="session_high", compare_to_offset=5.0)
        assert _check_condition(strat, rule, 1206.0) is True

    def test_negative_offset(self) -> None:
        # current < ref - 10; current=88, ref=100 → target = 100 - 10 = 90 → 88 < 90 ✓
        strat = _make_strategy(ref=[100.0])
        rule = RuleDef(indicator="x", condition="<", compare_to="ref", compare_to_offset=-10.0)
        assert _check_condition(strat, rule, 88.0) is True

    def test_offset_ignored_when_no_compare_to(self) -> None:
        strat = _make_strategy()
        rule = RuleDef(indicator="x", condition=">", value=5.0, compare_to_offset=100.0)
        assert _check_condition(strat, rule, 6.0) is True  # 6 > 5


# ---------------------------------------------------------------------------
# multiplier + offset combined
# ---------------------------------------------------------------------------

class TestMultiplierAndOffsetCombined:
    def test_both_applied_in_order(self) -> None:
        # target = ref * 2.0 + 10 = 100 * 2.0 + 10 = 210
        strat = _make_strategy(ref=[100.0])
        rule = RuleDef(indicator="x", condition=">", compare_to="ref",
                       compare_to_multiplier=2.0, compare_to_offset=10.0)
        assert _check_condition(strat, rule, 211.0) is True
        assert _check_condition(strat, rule, 209.0) is False

    def test_gte_condition(self) -> None:
        # target = 100 * 1.5 + 5 = 155; current=155 >= 155 ✓
        strat = _make_strategy(ref=[100.0])
        rule = RuleDef(indicator="x", condition=">=", compare_to="ref",
                       compare_to_multiplier=1.5, compare_to_offset=5.0)
        assert _check_condition(strat, rule, 155.0) is True


# ---------------------------------------------------------------------------
# Regression — existing behaviour unchanged
# ---------------------------------------------------------------------------

class TestRegressionNoScaling:
    def test_plain_compare_to_unchanged(self) -> None:
        strat = _make_strategy(ema=[50.0])
        rule = RuleDef(indicator="px", condition=">", compare_to="ema")
        assert _check_condition(strat, rule, 55.0) is True
        assert _check_condition(strat, rule, 45.0) is False

    def test_plain_value_unchanged(self) -> None:
        strat = _make_strategy()
        rule = RuleDef(indicator="rsi", condition="<", value=30.0)
        assert _check_condition(strat, rule, 25.0) is True
        assert _check_condition(strat, rule, 35.0) is False

    def test_missing_compare_to_returns_false(self) -> None:
        strat = MagicMock(spec=[])  # no attributes → getattr returns None
        rule = RuleDef(indicator="x", condition=">", compare_to="nonexistent")
        assert _check_condition(strat, rule, 100.0) is False
