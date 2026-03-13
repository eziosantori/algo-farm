"""Unit tests for GeneticOptimizer."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from src.models import IndicatorDef, PositionManagement, RuleDef, StrategyDefinition
from src.optimization.genetic import GeneticOptimizer
from src.storage.db import ErrorLogRepo, JobRepo, RunRepo, init_db


def _make_definition() -> StrategyDefinition:
    return StrategyDefinition(
        version="1",
        name="Test SMA",
        variant="basic",
        indicators=[IndicatorDef(name="fast_sma", type="sma", params={"period": 10})],
        entry_rules=[RuleDef(indicator="fast_sma", condition=">", value=0.0)],
        exit_rules=[],
        position_management=PositionManagement(),
    )


def test_genetic_returns_required_keys(tmp_path: Path, synthetic_ohlcv: object) -> None:
    """run() must return best_params, best_metrics, and pareto_front."""
    conn = init_db(str(tmp_path / "test.db"))
    job_repo = JobRepo(conn)
    run_repo = RunRepo(conn)
    error_repo = ErrorLogRepo(conn)
    job_id = job_repo.create()

    with patch("src.optimization.genetic.load_ohlcv", return_value=synthetic_ohlcv):
        opt = GeneticOptimizer(n_trials=4, population_size=2)
        result = opt.run(
            definition=_make_definition(),
            param_grid={"period": [10, 20]},
            instruments=["EURUSD"],
            timeframes=["H1"],
            data_dir="/fake",
            job_id=job_id,
            run_repo=run_repo,
            error_repo=error_repo,
        )

    assert "best_params" in result
    assert "best_metrics" in result
    assert "pareto_front" in result
    assert isinstance(result["pareto_front"], list)
    conn.close()


def test_genetic_emits_result_and_progress_callbacks(
    tmp_path: Path, synthetic_ohlcv: object
) -> None:
    """on_result and on_progress callbacks must be called."""
    conn = init_db(str(tmp_path / "test.db"))
    job_repo = JobRepo(conn)
    run_repo = RunRepo(conn)
    error_repo = ErrorLogRepo(conn)
    job_id = job_repo.create()

    results: list[object] = []
    progresses: list[object] = []

    with patch("src.optimization.genetic.load_ohlcv", return_value=synthetic_ohlcv):
        opt = GeneticOptimizer(n_trials=4, population_size=2)
        opt.run(
            definition=_make_definition(),
            param_grid={"period": [10, 20]},
            instruments=["EURUSD"],
            timeframes=["H1"],
            data_dir="/fake",
            job_id=job_id,
            run_repo=run_repo,
            error_repo=error_repo,
            on_result=results.append,
            on_progress=progresses.append,
        )

    assert len(results) > 0
    assert all(r["type"] == "result" for r in results)  # type: ignore[index]
    assert len(progresses) > 0
    conn.close()


def test_genetic_secondary_falls_back_when_primary_is_max_drawdown(
    tmp_path: Path, synthetic_ohlcv: object
) -> None:
    """When primary metric is max_drawdown, secondary falls back to profit_factor."""
    conn = init_db(str(tmp_path / "test.db"))
    job_repo = JobRepo(conn)
    run_repo = RunRepo(conn)
    error_repo = ErrorLogRepo(conn)
    job_id = job_repo.create()

    with patch("src.optimization.genetic.load_ohlcv", return_value=synthetic_ohlcv):
        opt = GeneticOptimizer(n_trials=4, population_size=2)
        result = opt.run(
            definition=_make_definition(),
            param_grid={"period": [10, 20]},
            instruments=["EURUSD"],
            timeframes=["H1"],
            data_dir="/fake",
            job_id=job_id,
            run_repo=run_repo,
            error_repo=error_repo,
            metric="max_drawdown",
        )

    assert "best_params" in result
    # pareto entries should contain profit_factor as secondary key
    if result["pareto_front"]:
        assert "profit_factor" in result["pareto_front"][0]


def test_genetic_data_not_found_skips_gracefully(tmp_path: Path) -> None:
    """FileNotFoundError during data loading logs an error and continues."""
    conn = init_db(str(tmp_path / "test.db"))
    job_repo = JobRepo(conn)
    run_repo = RunRepo(conn)
    error_repo = ErrorLogRepo(conn)
    job_id = job_repo.create()

    with patch(
        "src.optimization.genetic.load_ohlcv",
        side_effect=FileNotFoundError("missing"),
    ):
        opt = GeneticOptimizer(n_trials=4, population_size=2)
        result = opt.run(
            definition=_make_definition(),
            param_grid={"period": [10]},
            instruments=["EURUSD"],
            timeframes=["H1"],
            data_dir="/fake",
            job_id=job_id,
            run_repo=run_repo,
            error_repo=error_repo,
        )

    assert result["best_params"] == {}
    conn.close()
