"""Unit tests for SuppressionGate, TriggerHold, and risk_pct_group sizing."""
from __future__ import annotations

import math
import types
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from src.backtest.strategy import (
    _check_hold_trigger_fired,
    _compute_trade_size,
    _evaluate_rules,
)
from src.models import (
    PositionManagement,
    RuleDef,
    SuppressionGate,
    TriggerHold,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_indicator(values: list[float]) -> MagicMock:
    """Return a mock indicator that supports [-1] and [-2] indexing."""
    arr = np.array(values, dtype=float)
    mock = MagicMock()
    mock.__getitem__ = lambda self, idx: arr[idx]
    mock.__len__ = lambda self: len(arr)
    return mock


def _make_strategy(**indicators: list[float]) -> MagicMock:
    """Build a mock Strategy with named indicator attributes."""
    strat = MagicMock()
    for name, values in indicators.items():
        setattr(strat, name, _make_indicator(values))
    return strat


# ---------------------------------------------------------------------------
# _check_hold_trigger_fired
# ---------------------------------------------------------------------------

class TestCheckHoldTriggerFired:
    def test_crosses_above_compare_to_fires(self):
        strat = _make_strategy(px=[1.0, 2.0], bbu=[1.5, 1.8])
        rule = RuleDef(indicator="px", condition="crosses_above", compare_to="bbu")
        # prev: px[-2]=1.0 <= bbu[-2]=1.5; now: px[-1]=2.0 > bbu[-1]=1.8 → fires
        assert _check_hold_trigger_fired(strat, "px", [rule]) is True

    def test_crosses_above_compare_to_no_fire(self):
        strat = _make_strategy(px=[1.0, 1.5], bbu=[1.2, 1.8])
        rule = RuleDef(indicator="px", condition="crosses_above", compare_to="bbu")
        # px stays below bbu this bar → does not fire
        assert _check_hold_trigger_fired(strat, "px", [rule]) is False

    def test_crosses_above_value_fires(self):
        strat = _make_strategy(px=[0.9, 1.1])
        rule = RuleDef(indicator="px", condition="crosses_above", value=1.0)
        assert _check_hold_trigger_fired(strat, "px", [rule]) is True

    def test_crosses_below_fires(self):
        strat = _make_strategy(px=[1.5, 0.8], bbl=[1.0, 1.0])
        rule = RuleDef(indicator="px", condition="crosses_below", compare_to="bbl")
        assert _check_hold_trigger_fired(strat, "px", [rule]) is True

    def test_indicator_not_found_returns_false(self):
        strat = MagicMock(spec=[])  # no attributes
        rule = RuleDef(indicator="missing", condition="crosses_above", value=1.0)
        assert _check_hold_trigger_fired(strat, "missing", [rule]) is False

    def test_insufficient_bars_returns_false(self):
        strat = _make_strategy(px=[1.1])  # only one bar
        rule = RuleDef(indicator="px", condition="crosses_above", value=1.0)
        assert _check_hold_trigger_fired(strat, "px", [rule]) is False

    def test_no_matching_rule_returns_false(self):
        strat = _make_strategy(px=[0.9, 1.1])
        rule = RuleDef(indicator="other", condition="crosses_above", value=1.0)
        assert _check_hold_trigger_fired(strat, "px", [rule]) is False

    def test_non_cross_condition_not_matched(self):
        strat = _make_strategy(px=[0.9, 1.1])
        rule = RuleDef(indicator="px", condition=">", value=1.0)
        assert _check_hold_trigger_fired(strat, "px", [rule]) is False


# ---------------------------------------------------------------------------
# _evaluate_rules — trigger_hold_countdown
# ---------------------------------------------------------------------------

class TestEvaluateRulesWithTriggerHold:
    def test_hold_active_skips_cross_check(self):
        """When hold > 0, the crosses_above rule is bypassed (treated as True)."""
        strat = _make_strategy(px=[1.0, 1.0])  # no actual cross happening
        rules = [RuleDef(indicator="px", condition="crosses_above", value=2.0)]
        # without hold: cross doesn't fire → False
        assert _evaluate_rules(strat, rules) is False
        # with hold active: bypassed → True
        assert _evaluate_rules(strat, rules, trigger_hold_countdown={"px": 2}) is True

    def test_hold_zero_does_not_bypass(self):
        strat = _make_strategy(px=[1.0, 1.0])
        rules = [RuleDef(indicator="px", condition="crosses_above", value=2.0)]
        assert _evaluate_rules(strat, rules, trigger_hold_countdown={"px": 0}) is False

    def test_hold_active_with_other_passing_rules(self):
        """Hold bypasses cross; other rules still evaluated normally."""
        strat = _make_strategy(px=[1.0, 1.0], vol=[5.0, 5.0], vol_avg=[3.0, 3.0])
        rules = [
            RuleDef(indicator="px", condition="crosses_above", value=2.0),
            RuleDef(indicator="vol", condition=">", compare_to="vol_avg"),
        ]
        assert _evaluate_rules(strat, rules, trigger_hold_countdown={"px": 1}) is True

    def test_hold_active_with_other_failing_rule(self):
        """Hold bypasses cross but if another rule fails, overall result is False."""
        strat = _make_strategy(px=[1.0, 1.0], vol=[2.0, 2.0], vol_avg=[3.0, 3.0])
        rules = [
            RuleDef(indicator="px", condition="crosses_above", value=2.0),
            RuleDef(indicator="vol", condition=">", compare_to="vol_avg"),
        ]
        # vol < vol_avg → should fail
        assert _evaluate_rules(strat, rules, trigger_hold_countdown={"px": 1}) is False

    def test_hold_only_applies_to_cross_conditions(self):
        """TriggerHold does not bypass non-cross conditions."""
        strat = _make_strategy(vol=[2.0])
        rules = [RuleDef(indicator="vol", condition=">", value=3.0)]
        # Even if hold countdown says 5, it only fires for crosses_above/below
        assert _evaluate_rules(strat, rules, trigger_hold_countdown={"vol": 5}) is False


# ---------------------------------------------------------------------------
# SuppressionGate — countdown logic (tested via simulation of next() behavior)
# ---------------------------------------------------------------------------

class TestSuppressionGateCountdown:
    """Simulate the suppression countdown logic extracted from next()."""

    def _run_suppression_logic(
        self,
        raw_values: list[float],
        suppress_for_bars: int,
        threshold: float = 0.0,
    ) -> list[bool]:
        """Run the suppression gate logic over a sequence of raw pattern values.

        Returns a list of booleans: True means suppression is active on that bar.
        """
        countdown = 0
        results = []
        for raw in raw_values:
            # Decrement first
            if countdown > 0:
                countdown -= 1
            # Check if pattern fires this bar
            if not math.isnan(raw) and raw > threshold:
                countdown = suppress_for_bars
            results.append(countdown > 0)
        return results

    def test_no_suppression_when_pattern_below_threshold(self):
        vals = [0.0, 0.0, 0.0, 0.0]
        results = self._run_suppression_logic(vals, suppress_for_bars=2)
        assert results == [False, False, False, False]

    def test_suppression_activates_when_pattern_fires(self):
        # fires on bar 1, suppress for 2 bars (bars 1 and 2)
        vals = [0.0, 0.8, 0.0, 0.0, 0.0]
        results = self._run_suppression_logic(vals, suppress_for_bars=2)
        # bar 0: no fire, bar 1: fires → countdown=2 → active
        # bar 2: decrement→1 → active; bar 3: decrement→0 → not active; bar 4: no fire
        assert results == [False, True, True, False, False]

    def test_suppression_threshold_respected(self):
        # only fires when score > 0.5
        vals = [0.3, 0.7, 0.0, 0.0]
        results = self._run_suppression_logic(vals, suppress_for_bars=2, threshold=0.5)
        # bar 0: 0.3 <= 0.5 → no fire; bar 1: 0.7 > 0.5 → fires → countdown=2 → active
        assert results == [False, True, True, False]

    def test_re_trigger_resets_countdown(self):
        # fires on bar 0 and bar 3; suppress_for=2
        vals = [0.9, 0.0, 0.0, 0.9, 0.0, 0.0, 0.0]
        results = self._run_suppression_logic(vals, suppress_for_bars=2)
        # bar 0: fires → count=2 (active); bar 1: dec→1 (active); bar 2: dec→0 (inactive)
        # bar 3: fires again → count=2 (active); bar 4: dec→1 (active); bar 5: dec→0 (inactive)
        assert results == [True, True, False, True, True, False, False]

    def test_nan_does_not_trigger_suppression(self):
        vals = [float("nan"), 0.0, 0.0]
        results = self._run_suppression_logic(vals, suppress_for_bars=2)
        assert results == [False, False, False]

    def test_suppress_for_one_bar(self):
        vals = [0.8, 0.0, 0.0]
        results = self._run_suppression_logic(vals, suppress_for_bars=1)
        # bar 0: fires → count=1 (active); bar 1: dec→0 (inactive); bar 2: no fire
        assert results == [True, False, False]


# ---------------------------------------------------------------------------
# risk_pct_group sizing — _compute_trade_size with group score
# ---------------------------------------------------------------------------

class TestRiskPctGroupSizing:
    def _pm(self, risk_pct_min: float, risk_pct_max: float) -> PositionManagement:
        return PositionManagement(
            size=0.02,
            risk_pct_min=risk_pct_min,
            risk_pct_max=risk_pct_max,
        )

    def test_zero_score_gives_min_risk(self):
        pm = self._pm(0.005, 0.02)
        size = _compute_trade_size(pm, price=100.0, sl=99.0, equity=10_000.0, pattern_score=0.0)
        # effective_risk = 0.005; units = (10000 * 0.005) / 1.0 = 50
        assert size == 50

    def test_full_score_gives_max_risk(self):
        pm = self._pm(0.005, 0.02)
        size = _compute_trade_size(pm, price=100.0, sl=99.0, equity=10_000.0, pattern_score=1.0)
        # effective_risk = 0.02; units = (10000 * 0.02) / 1.0 = 200
        assert size == 200

    def test_half_score_interpolates(self):
        pm = self._pm(0.005, 0.02)
        size = _compute_trade_size(pm, price=100.0, sl=99.0, equity=10_000.0, pattern_score=0.5)
        # effective_risk = 0.005 + 0.5 * 0.015 = 0.0125; units = 125
        assert size == 125

    def test_score_above_one_falls_back_to_size(self):
        pm = self._pm(0.005, 0.02)
        # _compute_trade_size only interpolates for 0.0 <= score <= 1.0;
        # score > 1.0 falls through to pm.risk_pct (None here) → pm.size fallback
        size = _compute_trade_size(pm, price=100.0, sl=99.0, equity=10_000.0, pattern_score=1.5)
        assert size == pm.size  # 0.02 fractional fallback

    def test_no_sl_falls_back_to_size_fraction(self):
        pm = self._pm(0.005, 0.02)
        size = _compute_trade_size(pm, price=100.0, sl=None, equity=10_000.0, pattern_score=0.5)
        assert size == pm.size

    def test_risk_pct_overridden_by_min_max(self):
        pm = PositionManagement(
            size=0.02,
            risk_pct=0.01,       # would give 100 units
            risk_pct_min=0.005,
            risk_pct_max=0.02,
        )
        size = _compute_trade_size(pm, price=100.0, sl=99.0, equity=10_000.0, pattern_score=1.0)
        # min/max override risk_pct: effective=0.02 → 200 units
        assert size == 200
