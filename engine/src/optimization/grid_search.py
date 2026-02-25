"""GridSearchOptimizer: sweeps param combinations and runs backtests."""
from __future__ import annotations

import dataclasses
import json
import logging
from collections.abc import Callable
from itertools import product
from typing import Any

from src.backtest.runner import BacktestRunner
from src.models import StrategyDefinition
from src.storage.db import ErrorLogRepo, RunRepo
from src.utils import load_ohlcv

logger = logging.getLogger(__name__)


class GridSearchOptimizer:
    def build_combinations(self, param_grid: dict[str, Any]) -> list[dict[str, Any]]:
        """Expand param_grid: arrays are swept, scalars are fixed."""
        swept = {k: v for k, v in param_grid.items() if isinstance(v, list)}
        fixed = {k: v for k, v in param_grid.items() if not isinstance(v, list)}
        if not swept:
            return [{**fixed}]
        combos: list[dict[str, Any]] = []
        for values in product(*swept.values()):
            combos.append({**dict(zip(swept.keys(), values)), **fixed})
        return combos

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
    ) -> dict[str, Any]:
        """Run full grid search. Returns best_params and best_metrics."""
        combinations = self.build_combinations(param_grid)
        total = len(combinations) * len(instruments) * len(timeframes)
        current = 0
        best_value = float("-inf")
        best_params: dict[str, Any] = {}
        best_metrics: dict[str, Any] = {}
        skip = skip_sigs or set()
        runner = BacktestRunner()

        import time

        start_time = time.time()

        for instrument in instruments:
            for timeframe in timeframes:
                try:
                    ohlcv = load_ohlcv(data_dir, instrument, timeframe)
                except FileNotFoundError as exc:
                    logger.error("Data not found: %s", exc)
                    error_repo.log(job_id, "DataNotFound", str(exc))
                    current += len(combinations)
                    continue

                for params in combinations:
                    sig = f"{instrument}|{timeframe}|{json.dumps(params, sort_keys=True)}"
                    if sig in skip:
                        current += 1
                        continue

                    current += 1
                    try:
                        result = runner.run(ohlcv, definition, params)
                    except Exception as exc:
                        logger.error("Backtest failed (%s/%s %s): %s", instrument, timeframe, params, exc)
                        error_repo.log(
                            job_id,
                            type(exc).__name__,
                            str(exc),
                            context={"instrument": instrument, "timeframe": timeframe, "params": params},
                        )
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
                    if isinstance(metric_val, (int, float)) and metric_val > best_value:
                        best_value = float(metric_val)
                        best_params = params
                        best_metrics = metrics_dict

                    pct = int(current / total * 100) if total > 0 else 100
                    elapsed = time.time() - start_time
                    progress_msg: dict[str, Any] = {
                        "type": "progress",
                        "job_id": job_id,
                        "pct": pct,
                        "current": {
                            "instrument": instrument,
                            "timeframe": timeframe,
                            "iteration": current,
                            "total": total,
                        },
                        "elapsed_seconds": round(elapsed, 1),
                    }
                    if on_progress:
                        on_progress(progress_msg)

        return {"best_params": best_params, "best_metrics": best_metrics}
