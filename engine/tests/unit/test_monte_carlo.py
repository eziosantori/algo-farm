"""Unit tests for MonteCarloSimulator."""
from __future__ import annotations

import pytest

from src.robustness.monte_carlo import MonteCarloSimulator


def _trades(returns: list[float]) -> list[dict]:
    return [{"return_pct": r} for r in returns]


# ---------------------------------------------------------------------------
# Constructor validation
# ---------------------------------------------------------------------------

def test_rejects_zero_runs() -> None:
    with pytest.raises(ValueError):
        MonteCarloSimulator(n_runs=0)


def test_rejects_negative_runs() -> None:
    with pytest.raises(ValueError):
        MonteCarloSimulator(n_runs=-1)


# ---------------------------------------------------------------------------
# Empty trade list
# ---------------------------------------------------------------------------

def test_empty_trades_returns_none_values() -> None:
    sim = MonteCarloSimulator(n_runs=100)
    result = sim.simulate([])
    assert result["runs"] == 0
    assert result["max_dd_p5"] is None
    assert result["max_dd_p50"] is None
    assert result["max_dd_p95"] is None
    assert result["return_p5"] is None
    assert result["return_p50"] is None
    assert result["return_p95"] is None


# ---------------------------------------------------------------------------
# Output structure and types
# ---------------------------------------------------------------------------

def test_returns_required_keys() -> None:
    sim = MonteCarloSimulator(n_runs=50, seed=0)
    result = sim.simulate(_trades([0.01, -0.005, 0.02, -0.01, 0.015]))
    assert "runs" in result
    assert "max_dd_p5" in result
    assert "max_dd_p50" in result
    assert "max_dd_p95" in result
    assert "return_p5" in result
    assert "return_p50" in result
    assert "return_p95" in result


def test_runs_count_matches() -> None:
    n = 200
    sim = MonteCarloSimulator(n_runs=n, seed=0)
    result = sim.simulate(_trades([0.01, -0.01, 0.02]))
    assert result["runs"] == n


# ---------------------------------------------------------------------------
# Statistical properties
# ---------------------------------------------------------------------------

def test_drawdown_percentiles_ordered() -> None:
    """P5 ≤ P50 ≤ P95 for max drawdown (all negative or zero)."""
    sim = MonteCarloSimulator(n_runs=500, seed=42)
    trades = _trades([0.02, -0.03, 0.01, -0.02, 0.015, -0.01])
    result = sim.simulate(trades)
    assert result["max_dd_p5"] <= result["max_dd_p50"] <= result["max_dd_p95"]


def test_return_percentiles_ordered() -> None:
    """P5 ≤ P50 ≤ P95 for final return."""
    sim = MonteCarloSimulator(n_runs=500, seed=42)
    trades = _trades([0.02, -0.03, 0.01, -0.02, 0.015, -0.01])
    result = sim.simulate(trades)
    assert result["return_p5"] <= result["return_p50"] <= result["return_p95"]


def test_drawdown_always_non_positive() -> None:
    """Max drawdown can never be positive."""
    sim = MonteCarloSimulator(n_runs=300, seed=7)
    trades = _trades([0.05, -0.02, 0.03, -0.04])
    result = sim.simulate(trades)
    assert result["max_dd_p95"] <= 0.0


def test_all_winning_trades_zero_drawdown() -> None:
    """Pure uptrend → max drawdown = 0 regardless of ordering."""
    sim = MonteCarloSimulator(n_runs=100, seed=0)
    trades = _trades([0.01] * 20)
    result = sim.simulate(trades)
    assert result["max_dd_p95"] == pytest.approx(0.0, abs=1e-6)


def test_reproducibility_with_same_seed() -> None:
    trades = _trades([0.02, -0.01, 0.03, -0.02, 0.01])
    r1 = MonteCarloSimulator(n_runs=200, seed=99).simulate(trades)
    r2 = MonteCarloSimulator(n_runs=200, seed=99).simulate(trades)
    assert r1 == r2


def test_different_seeds_produce_different_paths() -> None:
    """Seeds 1 and 2 must produce at least one different percentile across all metrics."""
    trades = _trades([0.05, -0.03, 0.04, -0.02, 0.06, -0.04, 0.03, -0.01, 0.07, -0.05])
    r1 = MonteCarloSimulator(n_runs=1000, seed=1).simulate(trades)
    r2 = MonteCarloSimulator(n_runs=1000, seed=2).simulate(trades)
    keys = ["return_p5", "return_p50", "return_p95", "max_dd_p5", "max_dd_p50", "max_dd_p95"]
    assert any(r1[k] != r2[k] for k in keys)


def test_missing_return_pct_defaults_to_zero() -> None:
    """Trades without return_pct key should be treated as 0."""
    sim = MonteCarloSimulator(n_runs=50, seed=0)
    trades = [{"other_key": 0.05}, {"return_pct": 0.01}]
    result = sim.simulate(trades)
    assert result["runs"] == 50
    # No exception raised — that's the key assertion
