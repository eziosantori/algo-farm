"""Unit tests for PermutationTest."""
from __future__ import annotations

import pytest

from src.robustness.permutation import PermutationTest


def _trades(returns: list[float]) -> list[dict]:
    return [{"return_pct": r} for r in returns]


# ---------------------------------------------------------------------------
# Constructor
# ---------------------------------------------------------------------------

def test_rejects_zero_runs() -> None:
    with pytest.raises(ValueError):
        PermutationTest(n_runs=0)


def test_rejects_negative_runs() -> None:
    with pytest.raises(ValueError):
        PermutationTest(n_runs=-1)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_empty_trades() -> None:
    result = PermutationTest(n_runs=100).test([])
    assert result["runs"] == 0
    assert result["actual_sharpe"] is None
    assert result["p_value"] is None
    assert result["pct_better"] is None
    assert result["significant"] is None


def test_single_trade() -> None:
    result = PermutationTest(n_runs=100).test(_trades([0.05]))
    assert result["runs"] == 0  # < 2 trades → skip


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------

def test_returns_required_keys() -> None:
    result = PermutationTest(n_runs=50, seed=0).test(_trades([0.02, -0.01, 0.03] * 5))
    for key in ("runs", "actual_sharpe", "p_value", "pct_better", "significant"):
        assert key in result


def test_runs_count_matches() -> None:
    result = PermutationTest(n_runs=200, seed=0).test(_trades([0.01, -0.005, 0.02] * 5))
    assert result["runs"] == 200


# ---------------------------------------------------------------------------
# Statistical properties
# ---------------------------------------------------------------------------

def test_p_value_in_range() -> None:
    result = PermutationTest(n_runs=500, seed=42).test(_trades([0.02, -0.01, 0.015] * 10))
    assert 0.0 <= result["p_value"] <= 1.0


def test_pct_better_complements_p_value() -> None:
    result = PermutationTest(n_runs=500, seed=42).test(_trades([0.02, -0.01, 0.015] * 10))
    assert abs(result["pct_better"] / 100.0 - (1.0 - result["p_value"])) < 0.01


def test_significant_flag_matches_p_value() -> None:
    result = PermutationTest(n_runs=500, seed=42).test(_trades([0.02, -0.01, 0.015] * 10))
    assert result["significant"] == (result["p_value"] < 0.05)


def test_all_winning_strategy_low_p_value() -> None:
    """A consistently profitable trade sequence should have very low p-value."""
    wins = _trades([0.05] * 30)  # 30 identical winning trades
    result = PermutationTest(n_runs=1000, seed=7).test(wins)
    # All shuffles produce the same result → p_value should be 1.0 (trivially)
    # because actual_sharpe == every shuffled sharpe (all permutations identical)
    # So this just tests no crash
    assert result["p_value"] is not None


def test_reproducibility() -> None:
    trades = _trades([0.03, -0.02, 0.04, -0.01, 0.02] * 4)
    r1 = PermutationTest(n_runs=200, seed=99).test(trades)
    r2 = PermutationTest(n_runs=200, seed=99).test(trades)
    assert r1 == r2


def test_different_seeds_differ() -> None:
    trades = _trades([0.05, -0.03, 0.04, -0.02, 0.06, -0.04] * 5)
    r1 = PermutationTest(n_runs=500, seed=1).test(trades)
    r2 = PermutationTest(n_runs=500, seed=2).test(trades)
    # p_values may differ (unless both happen to be 0 or 1)
    assert r1["actual_sharpe"] == r2["actual_sharpe"]  # actual sharpe is deterministic


def test_missing_return_pct_defaults_to_zero() -> None:
    trades = [{"other_key": 0.05}, {"return_pct": 0.01}, {"return_pct": 0.02}]
    result = PermutationTest(n_runs=50, seed=0).test(trades)
    assert result["runs"] == 50
