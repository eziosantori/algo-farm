"""OOSValidator: out-of-sample validation by splitting OHLCV data.

Splits the data into an in-sample (IS) and out-of-sample (OOS) portion,
runs the backtest on both using the same parameters, and reports a
degradation ratio per metric: (oos − is) / |is|.
"""
from __future__ import annotations

import dataclasses
import logging
from typing import Any

import pandas as pd

from src.backtest.runner import BacktestRunner
from src.models import StrategyDefinition

logger = logging.getLogger(__name__)

# Minimum bars for a meaningful backtest on a split portion
_MIN_BARS = 30


class OOSValidator:
    """Split OHLCV into IS/OOS and compare strategy performance on both.

    Args:
        oos_pct: Fraction of bars reserved for OOS (0 < oos_pct < 1).
                 Example: 0.2 reserves the last 20% of bars.
    """

    def __init__(self, oos_pct: float = 0.2) -> None:
        if not 0.0 < oos_pct < 1.0:
            raise ValueError(f"oos_pct must be in (0, 1), got {oos_pct}")
        self.oos_pct = oos_pct

    def split(self, ohlcv: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Return (is_data, oos_data) DataFrames."""
        split_idx = int(len(ohlcv) * (1 - self.oos_pct))
        return ohlcv.iloc[:split_idx].copy(), ohlcv.iloc[split_idx:].copy()

    def validate(
        self,
        ohlcv: pd.DataFrame,
        definition: StrategyDefinition,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Run IS and OOS backtests. Returns metrics for both plus degradation ratios.

        Raises:
            ValueError: if either split has fewer than ``_MIN_BARS`` bars.
        """
        is_data, oos_data = self.split(ohlcv)
        if len(is_data) < _MIN_BARS or len(oos_data) < _MIN_BARS:
            raise ValueError(
                f"Insufficient data after OOS split: IS={len(is_data)}, "
                f"OOS={len(oos_data)} bars (minimum {_MIN_BARS} each)"
            )

        runner = BacktestRunner()
        is_result = runner.run(is_data, definition, params)
        oos_result = runner.run(oos_data, definition, params)

        is_metrics = dataclasses.asdict(is_result.metrics)
        oos_metrics = dataclasses.asdict(oos_result.metrics)

        return {
            "is_metrics": is_metrics,
            "oos_metrics": oos_metrics,
            "degradation": _compute_degradation(is_metrics, oos_metrics),
            "is_bars": len(is_data),
            "oos_bars": len(oos_data),
        }


def _compute_degradation(
    is_metrics: dict[str, Any],
    oos_metrics: dict[str, Any],
) -> dict[str, float | None]:
    """Compute relative change per metric: (oos − is) / |is|.

    Returns None for a metric when is_value is 0 (undefined ratio).
    Positive values mean OOS improved over IS; negative means degradation.
    """
    result: dict[str, float | None] = {}
    for key, is_val in is_metrics.items():
        oos_val = oos_metrics.get(key)
        if not isinstance(is_val, (int, float)) or not isinstance(oos_val, (int, float)):
            result[key] = None
            continue
        if is_val == 0:
            result[key] = None
        else:
            result[key] = round((float(oos_val) - float(is_val)) / abs(float(is_val)), 4)
    return result
