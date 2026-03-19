"""PermutationTest: statistical significance test for strategy edge.

Shuffles the sequence of trade returns N times and counts how many shuffled
sequences achieve a trade-level Sharpe ratio >= the actual one.

    p_value = count(shuffled_sharpe >= actual_sharpe) / n_runs

A low p-value (< 0.05) means the observed Sharpe is unlikely to occur by chance
alone — i.e. the strategy has a statistically significant edge.

This differs from MonteCarloSimulator (which focuses on drawdown/return
percentiles) by targeting the specific question: "Is the Sharpe above zero
because of skill or luck?"
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class PermutationTest:
    """Test whether a strategy's Sharpe ratio is statistically significant.

    Args:
        n_runs: Number of random permutations. Use >= 500 for reliable p-values.
        seed: Random seed for reproducibility.
    """

    def __init__(self, n_runs: int = 1000, seed: int = 42) -> None:
        if n_runs < 1:
            raise ValueError(f"n_runs must be >= 1, got {n_runs}")
        self.n_runs = n_runs
        self.seed = seed

    def _trade_sharpe(self, returns: np.ndarray) -> float:
        """Trade-level Sharpe: mean / std of individual trade returns.

        Note: not annualised — consistent across strategies with different trade
        frequencies, and directly comparable to shuffled versions.
        """
        if len(returns) < 2:
            return 0.0
        std = float(np.std(returns, ddof=1))
        if std == 0.0:
            return 0.0
        return float(np.mean(returns)) / std

    def test(self, trades: list[dict[str, Any]]) -> dict[str, Any]:
        """Run the permutation test on a list of completed trades.

        Args:
            trades: Trade dicts with a ``return_pct`` key.

        Returns:
            Dict with ``actual_sharpe``, ``p_value``, ``pct_better``
            (% of shuffles worse than actual — i.e. confidence level),
            ``significant`` (bool, p < 0.05), and ``runs``.
        """
        if len(trades) < 2:
            return {
                "runs": 0,
                "actual_sharpe": None,
                "p_value": None,
                "pct_better": None,
                "significant": None,
            }

        returns = np.array(
            [float(t.get("return_pct", 0.0)) for t in trades], dtype=np.float64
        )
        actual_sharpe = self._trade_sharpe(returns)

        rng = np.random.default_rng(self.seed)
        count_gte = 0
        for _ in range(self.n_runs):
            shuffled_sharpe = self._trade_sharpe(rng.permutation(returns))
            if shuffled_sharpe >= actual_sharpe:
                count_gte += 1

        p_value = round(count_gte / self.n_runs, 4)
        pct_better = round((1.0 - p_value) * 100.0, 1)

        return {
            "runs": self.n_runs,
            "actual_sharpe": round(actual_sharpe, 4),
            "p_value": p_value,
            "pct_better": pct_better,
            "significant": p_value < 0.05,
        }
