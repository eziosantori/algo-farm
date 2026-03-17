#!/usr/bin/env python3
"""Algo Farm Engine — CLI entry point.

stdout: newline-delimited JSON (progress | result | completed)
stderr: logs
exit 0: success
exit 1: error
exit 2: interrupted/resumable
"""
from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import uuid
from pathlib import Path
from typing import Any

# Ensure src/ is on the path when run as a script
sys.path.insert(0, str(Path(__file__).parent))

from src.backtest.runner import BacktestRunner
from src.models import StrategyDefinition
from src.optimization.grid_search import GridSearchOptimizer
from src.storage.db import ErrorLogRepo, JobRepo, RunRepo, init_db
from src.utils import load_ohlcv, setup_logging

logger = logging.getLogger(__name__)

_interrupted = False


def _handle_sigint(signum: int, frame: object) -> None:
    global _interrupted
    _interrupted = True
    logger.warning("SIGINT received — will exit after current run")


def emit(msg: dict[str, Any]) -> None:
    """Write a JSONL message to stdout — the ONLY thing that goes to stdout."""
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="algo-farm-engine",
        description="Run backtest / grid-search optimisation from CLI",
    )
    parser.add_argument("--strategy", required=True, help="Path to strategy JSON file")
    parser.add_argument("--instruments", required=True, help="Comma-separated instruments (e.g. EURUSD,GBPUSD)")
    parser.add_argument("--timeframes", required=True, help="Comma-separated timeframes (e.g. H1,D1)")
    parser.add_argument("--param-grid", dest="param_grid", default=None, help="Path to param_grid JSON file")
    parser.add_argument("--optimize", choices=["grid", "bayesian", "genetic"], default="grid", help="Optimisation method")
    parser.add_argument("--n-trials", dest="n_trials", type=int, default=50, help="Number of trials for Bayesian/Genetic optimisation")
    parser.add_argument("--population-size", dest="population_size", type=int, default=20, help="Population size for NSGA-II genetic optimisation")
    parser.add_argument("--metric", default="sharpe_ratio", help="Metric to optimise for")
    parser.add_argument("--db", required=True, help="Path to SQLite database file")
    parser.add_argument("--data-dir", dest="data_dir", required=True, help="Root directory for OHLCV Parquet files")
    parser.add_argument("--resume-job", dest="resume_job", default=None, help="Job UUID to resume")
    parser.add_argument("--log-level", dest="log_level", default="INFO", help="Logging level")
    # Phase 4 — Robustness validation (all optional, disabled by default)
    parser.add_argument("--oos-pct", dest="oos_pct", type=float, default=0.0,
                        help="Out-of-sample fraction (0 = disabled, e.g. 0.2 for last 20%%)")
    parser.add_argument("--walk-forward", dest="walk_forward", action="store_true",
                        help="Run walk-forward analysis on best params")
    parser.add_argument("--wf-windows", dest="wf_windows", type=int, default=5,
                        help="Number of walk-forward windows (default 5)")
    parser.add_argument("--wf-train-pct", dest="wf_train_pct", type=float, default=0.7,
                        help="Train fraction per walk-forward window (default 0.7)")
    parser.add_argument("--monte-carlo", dest="monte_carlo", action="store_true",
                        help="Run Monte Carlo simulation on best params")
    parser.add_argument("--mc-runs", dest="mc_runs", type=int, default=1000,
                        help="Number of Monte Carlo permutation runs (default 1000)")
    return parser.parse_args(argv)


def load_and_validate_strategy(path: str) -> StrategyDefinition:
    with open(path) as f:
        data = json.load(f)
    return StrategyDefinition.model_validate(data)


def load_param_grid(path: str | None) -> dict[str, Any]:
    if path is None:
        return {}
    with open(path) as f:
        return json.load(f)  # type: ignore[no-any-return]


def main(argv: list[str] | None = None) -> int:
    signal.signal(signal.SIGINT, _handle_sigint)

    args = parse_args(argv)
    setup_logging(args.log_level)

    try:
        definition = load_and_validate_strategy(args.strategy)
    except Exception as exc:
        logger.error("Invalid strategy file: %s", exc)
        return 1

    param_grid = load_param_grid(args.param_grid)
    instruments = [i.strip() for i in args.instruments.split(",")]
    timeframes = [t.strip() for t in args.timeframes.split(",")]

    try:
        conn = init_db(args.db)
    except Exception as exc:
        logger.error("Failed to initialise DB: %s", exc)
        return 1

    job_repo = JobRepo(conn)
    run_repo = RunRepo(conn)
    error_repo = ErrorLogRepo(conn)

    if args.resume_job:
        job_id = args.resume_job
        job = job_repo.get(job_id)
        if job is None:
            logger.error("Job %s not found in DB", job_id)
            return 1
        skip_sigs = run_repo.get_completed_signatures(job_id)
        logger.info("Resuming job %s — skipping %d completed runs", job_id, len(skip_sigs))
    else:
        job_id = str(uuid.uuid4())
        job_repo.create(
            job_type="grid_search",
            params_json=json.dumps({"instruments": instruments, "timeframes": timeframes}),
            job_id=job_id,
        )
        skip_sigs = set()

    job_repo.update_status(job_id, "running")

    if args.optimize == "bayesian":
        from src.optimization.bayesian import BayesianOptimizer
        from src.optimization.genetic import GeneticOptimizer
        optimizer: GridSearchOptimizer | BayesianOptimizer | GeneticOptimizer = BayesianOptimizer(n_trials=args.n_trials)
    elif args.optimize == "genetic":
        from src.optimization.genetic import GeneticOptimizer
        optimizer = GeneticOptimizer(n_trials=args.n_trials, population_size=args.population_size)
    else:
        optimizer = GridSearchOptimizer()

    try:
        result = optimizer.run(
            definition=definition,
            param_grid=param_grid,
            instruments=instruments,
            timeframes=timeframes,
            data_dir=args.data_dir,
            job_id=job_id,
            run_repo=run_repo,
            error_repo=error_repo,
            metric=args.metric,
            skip_sigs=skip_sigs,
            on_progress=emit,
            on_result=emit,
        )
    except Exception as exc:
        logger.error("Optimisation failed: %s", exc)
        error_repo.log(job_id, type(exc).__name__, str(exc))
        job_repo.update_status(job_id, "error")
        return 1

    if _interrupted:
        job_repo.update_status(job_id, "interrupted")
        emit(
            {
                "type": "interrupted",
                "job_id": job_id,
                "message": "Job interrupted — resume with --resume-job",
            }
        )
        return 2

    job_repo.update_status(job_id, "completed")
    completed_msg: dict[str, Any] = {
        "type": "completed",
        "job_id": job_id,
        "best_params": result["best_params"],
        "best_metrics": result["best_metrics"],
        "db_path": args.db,
    }
    if "pareto_front" in result:
        completed_msg["pareto_front"] = result["pareto_front"]
    emit(completed_msg)

    # --- Phase 4: Robustness validation (runs after main optimisation) ---
    run_robustness = args.oos_pct > 0 or args.walk_forward or args.monte_carlo
    if run_robustness:
        best_params = result.get("best_params", {})
        rb_runner = BacktestRunner()
        for instrument in instruments:
            for timeframe in timeframes:
                try:
                    ohlcv = load_ohlcv(args.data_dir, instrument, timeframe)
                except FileNotFoundError as exc:
                    logger.warning("Robustness: data not found (%s/%s): %s", instrument, timeframe, exc)
                    continue

                if args.oos_pct > 0:
                    try:
                        from src.robustness.oos import OOSValidator
                        oos_res = OOSValidator(oos_pct=args.oos_pct).validate(ohlcv, definition, best_params)
                        emit({"type": "oos_result", "job_id": job_id,
                              "instrument": instrument, "timeframe": timeframe,
                              "params": best_params, **oos_res})
                    except Exception as exc:
                        logger.warning("OOS validation failed (%s/%s): %s", instrument, timeframe, exc)

                if args.walk_forward:
                    try:
                        from src.robustness.walk_forward import WalkForwardAnalyzer
                        wf_res = WalkForwardAnalyzer(
                            n_windows=args.wf_windows, train_pct=args.wf_train_pct
                        ).analyze(ohlcv, definition, best_params)
                        emit({"type": "wf_result", "job_id": job_id,
                              "instrument": instrument, "timeframe": timeframe,
                              "params": best_params, **wf_res})
                    except Exception as exc:
                        logger.warning("Walk-forward failed (%s/%s): %s", instrument, timeframe, exc)

                if args.monte_carlo:
                    try:
                        from src.robustness.monte_carlo import MonteCarloSimulator
                        full_result = rb_runner.run(ohlcv, definition, best_params)
                        mc_res = MonteCarloSimulator(n_runs=args.mc_runs).simulate(full_result.trades)
                        emit({"type": "mc_result", "job_id": job_id,
                              "instrument": instrument, "timeframe": timeframe,
                              "params": best_params, **mc_res})
                    except Exception as exc:
                        logger.warning("Monte Carlo failed (%s/%s): %s", instrument, timeframe, exc)

    return 0


if __name__ == "__main__":
    sys.exit(main())
