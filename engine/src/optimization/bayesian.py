"""BayesianOptimizer: uses Optuna for Bayesian hyperparameter search."""
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


class BayesianOptimizer:
    """Optimise strategy parameters using Optuna TPE sampler.

    The param_grid format is identical to GridSearchOptimizer:
    - Lists are treated as categorical choices to explore.
    - Scalars are fixed across all trials.
    """

    def __init__(self, n_trials: int = 50) -> None:
        self.n_trials = n_trials

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
        """Run Bayesian optimisation. Returns best_params and best_metrics."""
        swept = {k: v for k, v in param_grid.items() if isinstance(v, list)}
        fixed = {k: v for k, v in param_grid.items() if not isinstance(v, list)}
        swept_keys = list(swept.keys())

        skip = skip_sigs or set()
        runner = BacktestRunner()
        best_value = float("-inf")
        best_params: dict[str, Any] = {}
        best_metrics: dict[str, Any] = {}
        total_calls = self.n_trials * len(instruments) * len(timeframes)
        current = 0
        start_time = time.time()

        def objective(trial: optuna.Trial) -> float:
            nonlocal current, best_value, best_params, best_metrics

            # Build param set for this trial
            params: dict[str, Any] = {**fixed}
            for key in swept_keys:
                params[key] = trial.suggest_categorical(key, swept[key])

            trial_values: list[float] = []

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
                        result = runner.run(ohlcv, definition, params, instrument, timeframe)
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
                    run_id = run_repo.create(
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
                        "run_id": run_id,
                    }
                    if on_result:
                        on_result(result_msg)

                    metric_val = metrics_dict.get(metric, float("-inf"))
                    if isinstance(metric_val, (int, float)):
                        trial_values.append(float(metric_val))
                        if metric_val > best_value:
                            best_value = float(metric_val)
                            best_params = dict(params)
                            best_metrics = dict(metrics_dict)

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

            return sum(trial_values) / len(trial_values) if trial_values else float("-inf")

        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=self.n_trials, show_progress_bar=False)

        return {"best_params": best_params, "best_metrics": best_metrics}
