"""MonteCarloSimulator: shuffle completed trades to estimate outcome distribution.

Takes the list of completed trades from a backtest and randomly permutes their
order ``n_runs`` times, recomputing the equity curve and max drawdown for each
permutation. Reports P5 / P50 / P95 percentiles for max drawdown and final return.

This tests whether the strategy's performance is robust to trade ordering or
whether it relies on a lucky sequence of wins/losses.
"""
from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class MonteCarloSimulator:
    """Shuffle trades N times and report the distribution of outcomes.

    Args:
        n_runs: Number of random permutations to run.
        seed: Random seed for reproducibility.
    """

    def __init__(self, n_runs: int = 1000, seed: int = 42) -> None:
        if n_runs < 1:
            raise ValueError(f"n_runs must be >= 1, got {n_runs}")
        self.n_runs = n_runs
        self.seed = seed

    def simulate(
        self,
        trades: list[dict[str, Any]],
        initial_equity: float = 10_000.0,
    ) -> dict[str, Any]:
        """Run Monte Carlo simulation on the given trade list.

        Args:
            trades: List of trade dicts with a ``return_pct`` key (as returned
                    by ``BacktestRunner._extract_trades``).
            initial_equity: Starting equity value for each simulated path.

        Returns:
            Dict with P5/P50/P95 percentiles for ``max_drawdown`` and
            ``final_return``, plus the number of runs performed.
        """
        if not trades:
            return {
                "runs": 0,
                "max_dd_p5": None,
                "max_dd_p50": None,
                "max_dd_p95": None,
                "return_p5": None,
                "return_p50": None,
                "return_p95": None,
            }

        returns = np.array(
            [float(t.get("return_pct", 0.0)) for t in trades], dtype=np.float64
        )
        rng = np.random.default_rng(self.seed)

        max_drawdowns: list[float] = []
        final_returns: list[float] = []

        for _ in range(self.n_runs):
            shuffled = rng.permutation(returns)
            equity = initial_equity
            peak = equity
            max_dd = 0.0

            for r in shuffled:
                equity *= 1.0 + r
                if equity > peak:
                    peak = equity
                dd = (equity - peak) / peak
                if dd < max_dd:
                    max_dd = dd

            max_drawdowns.append(max_dd)
            final_returns.append((equity - initial_equity) / initial_equity)

        dd_arr = np.array(max_drawdowns)
        ret_arr = np.array(final_returns)

        return {
            "runs": self.n_runs,
            "max_dd_p5":  round(float(np.percentile(dd_arr, 5)), 4),
            "max_dd_p50": round(float(np.percentile(dd_arr, 50)), 4),
            "max_dd_p95": round(float(np.percentile(dd_arr, 95)), 4),
            "return_p5":  round(float(np.percentile(ret_arr, 5)), 4),
            "return_p50": round(float(np.percentile(ret_arr, 50)), 4),
            "return_p95": round(float(np.percentile(ret_arr, 95)), 4),
        }
