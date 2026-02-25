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

from src.models import StrategyDefinition
from src.optimization.grid_search import GridSearchOptimizer
from src.storage.db import ErrorLogRepo, JobRepo, RunRepo, init_db
from src.utils import setup_logging

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
    parser.add_argument("--optimize", choices=["grid"], default="grid", help="Optimisation method")
    parser.add_argument("--metric", default="sharpe_ratio", help="Metric to optimise for")
    parser.add_argument("--db", required=True, help="Path to SQLite database file")
    parser.add_argument("--data-dir", dest="data_dir", required=True, help="Root directory for OHLCV Parquet files")
    parser.add_argument("--resume-job", dest="resume_job", default=None, help="Job UUID to resume")
    parser.add_argument("--log-level", dest="log_level", default="INFO", help="Logging level")
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
    emit(
        {
            "type": "completed",
            "job_id": job_id,
            "best_params": result["best_params"],
            "best_metrics": result["best_metrics"],
            "db_path": args.db,
        }
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
