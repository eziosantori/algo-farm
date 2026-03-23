"""Unit tests for PatternGroup: sum logic, gate interaction, rule evaluation."""

from __future__ import annotations

import numpy as np
import pytest

from src.backtest.strategy import _evaluate_rules
from src.models import PatternGroup, RuleDef, StrategyDefinition, IndicatorDef, PositionManagement


# ============================================================================
# Helpers
# ============================================================================


class _Ind:
    """Minimal indicator stub supporting [-1] indexing."""

    def __init__(self, val: float):
        self._val = val

    def __getitem__(self, _: int) -> float:
        return self._val


class _Strategy:
    """Fake backtesting.Strategy with arbitrary indicator attributes."""

    def __init__(self, **kwargs: float):
        for k, v in kwargs.items():
            setattr(self, k, _Ind(v))


# ============================================================================
# Group sum logic (simulates what next() computes)
# ============================================================================


def _compute_group_sum(
    indicators: dict[str, float],
    patterns: list[str],
    gate_countdown: dict[str, int],
) -> float:
    """Replicate the group-sum logic from StrategyComposer.next()."""
    total = 0.0
    for pname in patterns:
        val = indicators.get(pname, float("nan"))
        if np.isnan(val) or val == 0.0:
            if gate_countdown.get(pname, 0) > 0:
                val = 1.0
            elif np.isnan(val):
                val = 0.0
        total += val
    return total


def test_group_sum_all_zero() -> None:
    """No patterns fired → sum = 0."""
    s = _compute_group_sum({"eng": 0.0, "marub": 0.0, "soldiers": 0.0}, ["eng", "marub", "soldiers"], {})
    assert s == 0.0


def test_group_sum_one_strong() -> None:
    """One textbook-perfect pattern → sum = 1.0."""
    s = _compute_group_sum({"eng": 1.0, "marub": 0.0}, ["eng", "marub"], {})
    assert s == pytest.approx(1.0)


def test_group_sum_two_partial() -> None:
    """Two partial patterns add up: 0.4 + 0.7 = 1.1."""
    s = _compute_group_sum({"eng": 0.4, "marub": 0.7}, ["eng", "marub"], {})
    assert s == pytest.approx(1.1)


def test_group_sum_exceeds_one() -> None:
    """Sum can exceed 1.0 when multiple strong patterns fire simultaneously."""
    s = _compute_group_sum({"eng": 0.9, "marub": 0.8, "soldiers": 0.6}, ["eng", "marub", "soldiers"], {})
    assert s == pytest.approx(2.3)


def test_group_sum_missing_indicator_treated_as_zero() -> None:
    """An indicator absent from the values dict contributes 0 (graceful skip)."""
    s = _compute_group_sum({"eng": 0.8}, ["eng", "ghost"], {})
    assert s == pytest.approx(0.8)


# ============================================================================
# Gate interaction with group sum
# ============================================================================


def test_group_sum_gate_active_contributes_one() -> None:
    """Pattern with countdown > 0 contributes 1.0 even when current score is 0.0."""
    s = _compute_group_sum(
        {"eng": 0.0, "marub": 0.6},
        ["eng", "marub"],
        {"eng": 3},  # eng gate still active
    )
    assert s == pytest.approx(1.6)  # 1.0 (gated) + 0.6


def test_group_sum_gate_active_nan_contributes_one() -> None:
    """Pattern under gate contributes 1.0 even when value is NaN (warmup bar)."""
    s = _compute_group_sum(
        {"eng": float("nan"), "marub": 0.0},
        ["eng", "marub"],
        {"eng": 2},
    )
    assert s == pytest.approx(1.0)


def test_group_sum_gate_expired_uses_raw_zero() -> None:
    """Expired gate (countdown=0) does not override a 0.0 score."""
    s = _compute_group_sum(
        {"eng": 0.0, "marub": 0.5},
        ["eng", "marub"],
        {"eng": 0},
    )
    assert s == pytest.approx(0.5)  # eng=0.0, gate expired


def test_group_sum_all_gated() -> None:
    """Three patterns all under active gates → sum = 3.0."""
    s = _compute_group_sum(
        {"eng": 0.0, "marub": 0.0, "soldiers": 0.0},
        ["eng", "marub", "soldiers"],
        {"eng": 1, "marub": 2, "soldiers": 5},
    )
    assert s == pytest.approx(3.0)


# ============================================================================
# _evaluate_rules with group_values
# ============================================================================


def test_rule_passes_when_group_sum_meets_threshold() -> None:
    strat = _Strategy(rsi=55.0)
    rules = [
        RuleDef(indicator="rsi", condition=">", value=50.0),
        RuleDef(indicator="bull_grp", condition=">=", value=1.0),
    ]
    assert _evaluate_rules(strat, rules, group_values={"bull_grp": 1.1}) is True  # type: ignore[arg-type]


def test_rule_fails_when_group_sum_below_threshold() -> None:
    strat = _Strategy(rsi=55.0)
    rules = [
        RuleDef(indicator="rsi", condition=">", value=50.0),
        RuleDef(indicator="bull_grp", condition=">=", value=1.0),
    ]
    assert _evaluate_rules(strat, rules, group_values={"bull_grp": 0.7}) is False  # type: ignore[arg-type]


def test_rule_exact_threshold_passes() -> None:
    strat = _Strategy(rsi=55.0)
    rules = [RuleDef(indicator="bull_grp", condition=">=", value=1.0)]
    assert _evaluate_rules(strat, rules, group_values={"bull_grp": 1.0}) is True  # type: ignore[arg-type]


def test_rule_strict_greater_at_threshold_fails() -> None:
    strat = _Strategy(rsi=55.0)
    rules = [RuleDef(indicator="bull_grp", condition=">", value=1.0)]
    assert _evaluate_rules(strat, rules, group_values={"bull_grp": 1.0}) is False  # type: ignore[arg-type]


def test_rule_strict_greater_above_threshold_passes() -> None:
    strat = _Strategy()
    rules = [RuleDef(indicator="bull_grp", condition=">", value=1.0)]
    assert _evaluate_rules(strat, rules, group_values={"bull_grp": 1.5}) is True  # type: ignore[arg-type]


def test_group_rule_independent_of_individual_indicator() -> None:
    """Group rule is resolved from group_values even when the same name would
    shadow an indicator — name collision is the user's responsibility."""
    strat = _Strategy(rsi=55.0)
    rules = [
        RuleDef(indicator="rsi", condition=">", value=50.0),
        RuleDef(indicator="bear_grp", condition="<", value=0.5),
    ]
    assert _evaluate_rules(strat, rules, group_values={"bear_grp": 0.2}) is True  # type: ignore[arg-type]
    assert _evaluate_rules(strat, rules, group_values={"bear_grp": 0.9}) is False  # type: ignore[arg-type]


def test_no_group_values_passed_group_rule_fails_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Omitting group_values when rules reference a group name → False + warning."""
    import logging

    strat = _Strategy()
    rules = [RuleDef(indicator="missing_grp", condition=">=", value=1.0)]

    with caplog.at_level(logging.WARNING):
        result = _evaluate_rules(strat, rules)  # type: ignore[arg-type]

    assert result is False
    assert "missing_grp" in caplog.text
