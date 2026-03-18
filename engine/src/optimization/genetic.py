"""GeneticOptimizer: multi-objective optimisation using Optuna NSGA-II sampler.

Simultaneously optimises two objectives:
  - primary  : any metric (default ``sharpe_ratio``), maximised
  - secondary: ``max_drawdown``, maximised (less negative = less drawdown)
               falls back to ``profit_factor`` when primary IS max_drawdown

Returns the Pareto-optimal front together with a single ``best_params`` /
``best_metrics`` entry (the Pareto point with the highest primary-metric value).
"""
from __future__ import annotations

import dataclasses
import json
import logging
import time
from collections.abc import Callable
from typing import Any

import optuna

from src.backtest.runner import BacktestRunner
from src.models import StrategyDefinition
from src.storage.db import ErrorLogRepo, RunRepo
from src.utils import load_ohlcv

logger = logging.getLogger(__name__)
optuna.logging.set_verbosity(optuna.logging.WARNING)

# Default secondary objective; replaced when primary == max_drawdown
_SECONDARY_METRIC = "max_drawdown"
_FALLBACK_SECONDARY = "profit_factor"


class GeneticOptimizer:
    """Multi-objective strategy optimiser using Optuna NSGA-II.

    Args:
        n_trials: Total number of objective evaluations (across all generations).
        population_size: Number of individuals per NSGA-II generation.
    """

    def __init__(self, n_trials: int = 50, population_size: int = 20) -> None:
        self.n_trials = n_trials
        self.population_size = population_size

    def run(
        self,
        definition: StrategyDefinition,
        param_grid: dict[str, Any],
        instruments: list[str],
        timeframes: list[str],
        data_dir: str,
        job_id: str,
        run_repo: RunRepo,
        error_repo: ErrorLogRepo,
        metric: str = "sharpe_ratio",
        skip_sigs: set[str] | None = None,
        on_progress: Callable[[dict[str, Any]], None] | None = None,
        on_result: Callable[[dict[str, Any]], None] | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> dict[str, Any]:
        """Run NSGA-II optimisation.

        Returns:
            dict with keys ``best_params``, ``best_metrics``, and ``pareto_front``.
            ``pareto_front`` is a list of dicts, each with ``params``, the primary
            metric value, and the secondary metric value.
        """
        swept = {k: v for k, v in param_grid.items() if isinstance(v, list)}
        fixed = {k: v for k, v in param_grid.items() if not isinstance(v, list)}
        swept_keys = list(swept.keys())

        secondary = (
            _FALLBACK_SECONDARY if metric == _SECONDARY_METRIC else _SECONDARY_METRIC
        )

        skip = skip_sigs or set()
        runner = BacktestRunner()
        total_calls = self.n_trials * len(instruments) * len(timeframes)
        current = 0
        start_time = time.time()

        def objective(trial: optuna.Trial) -> tuple[float, float]:
            nonlocal current

            params: dict[str, Any] = {**fixed}
            for key in swept_keys:
                params[key] = trial.suggest_categorical(key, swept[key])

            primary_vals: list[float] = []
            secondary_vals: list[float] = []

            for instrument in instruments:
                for timeframe in timeframes:
                    try:
                        ohlcv = load_ohlcv(data_dir, instrument, timeframe, date_from, date_to)
                    except FileNotFoundError as exc:
                        logger.error("Data not found: %s", exc)
                        error_repo.log(job_id, "DataNotFound", str(exc))
                        current += 1
                        continue

                    sig = f"{instrument}|{timeframe}|{json.dumps(params, sort_keys=True)}"
                    if sig in skip:
                        current += 1
                        continue

                    current += 1
                    try:
                        result = runner.run(ohlcv, definition, params)
                    except Exception as exc:
                        logger.error(
                            "Backtest failed (%s/%s %s): %s",
                            instrument,
                            timeframe,
                            params,
                            exc,
                        )
                        error_repo.log(job_id, type(exc).__name__, str(exc))
                        continue

                    metrics_dict = dataclasses.asdict(result.metrics)
                    run_repo.create(
                        job_id=job_id,
                        instrument=instrument,
                        timeframe=timeframe,
                        params=params,
                        equity_curve=result.equity_curve,
                        trades=result.trades,
                        metrics_dict=metrics_dict,
                    )

                    result_msg: dict[str, Any] = {
                        "type": "result",
                        "job_id": job_id,
                        "instrument": instrument,
                        "timeframe": timeframe,
                        "params": params,
                        "metrics": metrics_dict,
                    }
                    if on_result:
                        on_result(result_msg)

                    pv = metrics_dict.get(metric, float("-inf"))
                    sv = metrics_dict.get(secondary, float("-inf"))
                    if isinstance(pv, (int, float)):
                        primary_vals.append(float(pv))
                    if isinstance(sv, (int, float)):
                        secondary_vals.append(float(sv))

                    pct = int(current / total_calls * 100) if total_calls > 0 else 100
                    elapsed = time.time() - start_time
                    if on_progress:
                        on_progress(
                            {
                                "type": "progress",
                                "job_id": job_id,
                                "pct": pct,
                                "current": {
                                    "instrument": instrument,
                                    "timeframe": timeframe,
                                    "iteration": current,
                                    "total": total_calls,
                                },
                                "elapsed_seconds": round(elapsed, 1),
                            }
                        )

            p_val = (
                sum(primary_vals) / len(primary_vals)
                if primary_vals
                else float("-inf")
            )
            s_val = (
                sum(secondary_vals) / len(secondary_vals)
                if secondary_vals
                else float("-inf")
            )

            trial.set_user_attr("params", params)
            trial.set_user_attr("p_val", p_val)
            trial.set_user_attr("s_val", s_val)

            return p_val, s_val

        sampler = optuna.samplers.NSGAIISampler(
            population_size=self.population_size, seed=42
        )
        study = optuna.create_study(directions=["maximize", "maximize"], sampler=sampler)
        study.optimize(objective, n_trials=self.n_trials, show_progress_bar=False)

        # Extract Pareto-optimal front from study.best_trials
        pareto_front: list[dict[str, Any]] = []
        best_params: dict[str, Any] = {}
        best_metrics: dict[str, Any] = {}
        best_primary = float("-inf")

        for t in study.best_trials:
            params = t.user_attrs.get("params", {})
            p_val = t.user_attrs.get("p_val", float("-inf"))
            s_val = t.user_attrs.get("s_val", float("-inf"))
            pareto_front.append({
                "params": params,
                metric: p_val,
                secondary: s_val,
            })
            if p_val > best_primary:
                best_primary = p_val
                best_params = dict(params)
                best_metrics = {metric: p_val, secondary: s_val}

        return {
            "best_params": best_params,
            "best_metrics": best_metrics,
            "pareto_front": pareto_front,
        }
