"""WalkForwardAnalyzer: rolling IS/OOS windows to test parameter stability over time.

Divides the OHLCV series into N equal non-overlapping windows. Within each
window the first ``train_pct`` fraction is in-sample (IS) and the remainder
is out-of-sample (OOS). The same parameter set is tested in both halves.

WF efficiency = mean(OOS Sharpe) / mean(IS Sharpe).
  > 0.7 → strong generalisation
  0.4–0.7 → acceptable
  < 0.4  → likely overfit
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.backtest.runner import BacktestRunner
from src.models import StrategyDefinition

logger = logging.getLogger(__name__)

_MIN_BARS_PER_SPLIT = 20


class WalkForwardAnalyzer:
    """Test parameter stability across N rolling IS/OOS windows.

    Args:
        n_windows: Number of equal-size windows to create.
        train_pct: Fraction of each window used as IS (0 < train_pct < 1).
    """

    def __init__(self, n_windows: int = 5, train_pct: float = 0.7) -> None:
        if n_windows < 2:
            raise ValueError(f"n_windows must be >= 2, got {n_windows}")
        if not 0.0 < train_pct < 1.0:
            raise ValueError(f"train_pct must be in (0, 1), got {train_pct}")
        self.n_windows = n_windows
        self.train_pct = train_pct

    def create_windows(
        self, total_bars: int
    ) -> list[tuple[tuple[int, int], tuple[int, int]]]:
        """Return list of ((is_start, is_end), (oos_start, oos_end)) index pairs."""
        window_size = total_bars // self.n_windows
        if window_size < 2:
            raise ValueError(
                f"Too few bars ({total_bars}) for {self.n_windows} windows"
            )
        windows = []
        for i in range(self.n_windows):
            start = i * window_size
            end = start + window_size if i < self.n_windows - 1 else total_bars
            split = start + max(1, int((end - start) * self.train_pct))
            windows.append(((start, split), (split, end)))
        return windows

    def analyze(
        self,
        ohlcv: pd.DataFrame,
        definition: StrategyDefinition,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Run IS and OOS backtests on each window. Returns per-window results
        and aggregate WF efficiency."""
        windows = self.create_windows(len(ohlcv))
        runner = BacktestRunner()
        window_results: list[dict[str, Any]] = []
        is_sharpes: list[float] = []
        oos_sharpes: list[float] = []

        for idx, ((is0, is1), (oos0, oos1)) in enumerate(windows):
            is_data = ohlcv.iloc[is0:is1].copy()
            oos_data = ohlcv.iloc[oos0:oos1].copy()

            if len(is_data) < _MIN_BARS_PER_SPLIT or len(oos_data) < _MIN_BARS_PER_SPLIT:
                logger.debug("Window %d skipped: IS=%d OOS=%d bars", idx + 1, len(is_data), len(oos_data))
                continue

            try:
                is_res = runner.run(is_data, definition, params)
                oos_res = runner.run(oos_data, definition, params)
            except Exception as exc:
                logger.warning("Window %d backtest failed: %s", idx + 1, exc)
                continue

            is_sh = is_res.metrics.sharpe_ratio
            oos_sh = oos_res.metrics.sharpe_ratio
            window_results.append(
                {
                    "window": idx + 1,
                    "is_bars": len(is_data),
                    "oos_bars": len(oos_data),
                    "is_sharpe": round(is_sh, 4),
                    "oos_sharpe": round(oos_sh, 4),
                    "is_return_pct": round(is_res.metrics.total_return_pct, 4),
                    "oos_return_pct": round(oos_res.metrics.total_return_pct, 4),
                    "is_trades": is_res.metrics.total_trades,
                    "oos_trades": oos_res.metrics.total_trades,
                }
            )
            is_sharpes.append(is_sh)
            oos_sharpes.append(oos_sh)

        mean_is = sum(is_sharpes) / len(is_sharpes) if is_sharpes else 0.0
        mean_oos = sum(oos_sharpes) / len(oos_sharpes) if oos_sharpes else 0.0
        wf_efficiency: float | None = (
            round(mean_oos / mean_is, 4) if mean_is != 0.0 else None
        )

        return {
            "windows": window_results,
            "n_windows_run": len(window_results),
            "mean_is_sharpe": round(mean_is, 4),
            "mean_oos_sharpe": round(mean_oos, 4),
            "wf_efficiency": wf_efficiency,
        }
