"""Unit tests for RobustnessScorer."""
from __future__ import annotations

import pytest

from src.robustness.scorer import RobustnessScorer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _score(**kwargs) -> dict:
    return RobustnessScorer().score(**kwargs)


# ---------------------------------------------------------------------------
# No signals → graceful None result
# ---------------------------------------------------------------------------

def test_no_signals_returns_none() -> None:
    result = _score()
    assert result["composite_score"] is None
    assert result["grade"] is None
    assert result["go_nogo"] is None


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

def test_returns_required_keys() -> None:
    result = _score(oos_sharpe=0.6, is_sharpe=0.8, wf_efficiency=0.65)
    for key in ("composite_score", "grade", "go_nogo", "components"):
        assert key in result


def test_components_contain_all_five() -> None:
    result = _score(oos_sharpe=0.6, is_sharpe=0.8)
    for key in ("oos_retention", "wf_efficiency", "mc_p5_sharpe", "sensitivity", "permutation"):
        assert key in result["components"]


# ---------------------------------------------------------------------------
# GO / NO-GO threshold
# ---------------------------------------------------------------------------

def test_score_above_60_is_go() -> None:
    # Perfect signals → must be GO
    result = _score(
        oos_sharpe=1.0, is_sharpe=1.0,
        wf_efficiency=0.9,
        mc_p5_sharpe=0.5,
        overall_stability=0.9,
        permutation_p_value=0.01,
    )
    assert result["go_nogo"] == "GO"
    assert result["composite_score"] >= 60.0


def test_score_below_60_is_nogo() -> None:
    # Terrible signals → must be NO-GO
    result = _score(
        oos_sharpe=-0.5, is_sharpe=1.0,
        wf_efficiency=0.1,
        mc_p5_sharpe=-0.5,
        overall_stability=0.0,
        permutation_p_value=0.5,
    )
    assert result["go_nogo"] == "NO-GO"
    assert result["composite_score"] < 60.0


# ---------------------------------------------------------------------------
# Grades
# ---------------------------------------------------------------------------

def test_grade_a_above_80() -> None:
    result = _score(
        oos_sharpe=1.0, is_sharpe=1.0,
        wf_efficiency=0.9,
        mc_p5_sharpe=0.5,
        overall_stability=0.9,
        permutation_p_value=0.005,
    )
    assert result["grade"] == "A"


def test_grade_f_below_50() -> None:
    result = _score(
        oos_sharpe=0.0, is_sharpe=1.0,
        wf_efficiency=0.0,
        mc_p5_sharpe=-0.5,
        overall_stability=0.0,
        permutation_p_value=0.5,
    )
    assert result["grade"] == "F"


# ---------------------------------------------------------------------------
# Partial signals — renormalisation
# ---------------------------------------------------------------------------

def test_single_signal_scores_full_range() -> None:
    """With only one signal, the weight renormalises to 1.0."""
    result = _score(wf_efficiency=0.7)
    assert result["composite_score"] is not None
    assert result["composite_score"] == pytest.approx(100.0, abs=1.0)


def test_missing_signals_excluded_from_components() -> None:
    result = _score(oos_sharpe=0.8, is_sharpe=1.0)
    # oos_retention is present, others missing
    assert result["components"]["oos_retention"]["score"] is not None
    assert result["components"]["wf_efficiency"]["score"] is None


# ---------------------------------------------------------------------------
# OOS retention scoring
# ---------------------------------------------------------------------------

def test_oos_retention_perfect() -> None:
    result = _score(oos_sharpe=1.0, is_sharpe=1.0)
    assert result["components"]["oos_retention"]["score"] == pytest.approx(100.0)


def test_oos_retention_half() -> None:
    result = _score(oos_sharpe=0.5, is_sharpe=1.0)
    assert result["components"]["oos_retention"]["score"] == pytest.approx(50.0)


def test_oos_retention_negative_capped_at_zero() -> None:
    result = _score(oos_sharpe=-0.5, is_sharpe=1.0)
    assert result["components"]["oos_retention"]["score"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Score is bounded 0–100
# ---------------------------------------------------------------------------

def test_composite_score_bounded() -> None:
    for oos in [-1.0, 0.0, 0.5, 1.0, 2.0]:
        for wf in [-0.5, 0.0, 0.5, 1.0, 1.5]:
            result = _score(oos_sharpe=oos, is_sharpe=1.0, wf_efficiency=wf)
            if result["composite_score"] is not None:
                assert 0.0 <= result["composite_score"] <= 100.0
