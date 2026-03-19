"""ParameterSensitivityAnalyzer: test how robust strategy metrics are to ±param changes.

For each numeric indicator parameter, tries four variations (−20%, −10%, +10%, +20%)
while keeping all other parameters fixed. Reports the Sharpe change per variation and
a per-param stability score (1 = perfectly stable, 0 = fully unstable).

A strategy is considered parameter-stable when ±20% param changes produce < 0.5
Sharpe ratio change. If the strategy requires exact parameter tuning to work, it
is likely overfit.
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from src.backtest.runner import BacktestRunner
from src.models import StrategyDefinition

logger = logging.getLogger(__name__)

# Sharpe change that maps to 0 stability (i.e. "fully unstable" threshold)
_INSTABILITY_THRESHOLD = 0.5

# Default variation deltas as fractions (−20%, −10%, +10%, +20%)
_DEFAULT_DELTAS = (-0.2, -0.1, 0.1, 0.2)


class ParameterSensitivityAnalyzer:
    """Vary each numeric indicator param by fixed fractions and measure Sharpe impact.

    Args:
        deltas: Fractional changes to apply to each param (e.g. -0.2 means × 0.8).
    """

    def __init__(self, deltas: tuple[float, ...] = _DEFAULT_DELTAS) -> None:
        self.deltas = deltas

    def _numeric_base_params(
        self,
        definition: StrategyDefinition,
        params: dict[str, Any],
    ) -> dict[str, float]:
        """Collect all numeric indicator params, preferring overridden values in params."""
        base: dict[str, float] = {}
        for ind_def in definition.indicators:
            for k, v in ind_def.params.items():
                if isinstance(v, (int, float)) and k not in base:
                    base[k] = float(params.get(k, v))
        # Include extra override params not present in indicator defaults
        for k, v in params.items():
            if isinstance(v, (int, float)) and k not in base:
                base[k] = float(v)
        return base

    def analyze(
        self,
        ohlcv: pd.DataFrame,
        definition: StrategyDefinition,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        """Run parameter sensitivity analysis.

        Args:
            ohlcv: Full OHLCV DataFrame (IS window).
            definition: Strategy definition to test.
            params: Best params to use as the base (from optimizer or empty dict).

        Returns:
            Dict with ``base_sharpe``, per-param ``params_tested`` details,
            and ``overall_stability`` (0–1, higher is better).
        """
        runner = BacktestRunner()

        base_result = runner.run(ohlcv, definition, params)
        base_sharpe = base_result.metrics.sharpe_ratio

        numeric_params = self._numeric_base_params(definition, params)
        if not numeric_params:
            return {
                "base_sharpe": round(base_sharpe, 4),
                "params_tested": {},
                "overall_stability": 1.0,
            }

        params_tested: dict[str, Any] = {}
        for param_name, base_value in numeric_params.items():
            variations: list[dict[str, Any]] = []
            for delta in self.deltas:
                varied = base_value * (1.0 + delta)
                # Enforce minimum of 1 for integer-like params (e.g. period)
                if varied < 1.0:
                    varied = 1.0
                varied = round(varied, 4)
                test_params = {**params, param_name: varied}
                try:
                    res = runner.run(ohlcv, definition, test_params)
                    sh_change = res.metrics.sharpe_ratio - base_sharpe
                    variations.append({
                        "delta_pct": int(round(delta * 100)),
                        "value": varied,
                        "sharpe": round(res.metrics.sharpe_ratio, 4),
                        "sharpe_change": round(sh_change, 4),
                    })
                except Exception as exc:
                    logger.debug("Sensitivity run failed for %s=%.4f: %s", param_name, varied, exc)
                    variations.append({
                        "delta_pct": int(round(delta * 100)),
                        "value": varied,
                        "sharpe": None,
                        "sharpe_change": None,
                    })

            valid_changes = [abs(v["sharpe_change"]) for v in variations if v["sharpe_change"] is not None]
            max_change = max(valid_changes) if valid_changes else 0.0
            stability = max(0.0, 1.0 - max_change / _INSTABILITY_THRESHOLD)

            params_tested[param_name] = {
                "base_value": base_value,
                "variations": variations,
                "max_sharpe_change": round(max_change, 4),
                "stability": round(stability, 4),
            }

        stabilities = [v["stability"] for v in params_tested.values()]
        overall_stability = round(sum(stabilities) / len(stabilities), 4) if stabilities else 1.0

        return {
            "base_sharpe": round(base_sharpe, 4),
            "params_tested": params_tested,
            "overall_stability": overall_stability,
        }
