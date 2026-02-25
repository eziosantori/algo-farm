"""Unit tests for GridSearchOptimizer."""
from __future__ import annotations

import json

import pytest

from src.optimization.grid_search import GridSearchOptimizer


def test_build_combinations_single_param() -> None:
    opt = GridSearchOptimizer()
    combos = opt.build_combinations({"period": [10, 20, 30]})
    assert len(combos) == 3
    assert {"period": 10} in combos
    assert {"period": 30} in combos


def test_build_combinations_multiple_params() -> None:
    opt = GridSearchOptimizer()
    combos = opt.build_combinations({"a": [1, 2], "b": [10, 20]})
    assert len(combos) == 4


def test_build_combinations_fixed_params() -> None:
    opt = GridSearchOptimizer()
    combos = opt.build_combinations({"period": [10, 20], "fixed": 5})
    assert all(c["fixed"] == 5 for c in combos)
    assert len(combos) == 2


def test_build_combinations_all_fixed() -> None:
    opt = GridSearchOptimizer()
    combos = opt.build_combinations({"period": 10, "other": 0.5})
    assert combos == [{"period": 10, "other": 0.5}]


def test_build_combinations_empty() -> None:
    opt = GridSearchOptimizer()
    combos = opt.build_combinations({})
    assert combos == [{}]


def test_grid_search_run_full(
    tmp_path: object,
    synthetic_ohlcv: object,
) -> None:
    """Full grid search run with mocked data loading."""
    import sqlite3
    from pathlib import Path
    from unittest.mock import patch

    from src.models import PositionManagement, RuleDef, StrategyDefinition, IndicatorDef
    from src.storage.db import ErrorLogRepo, JobRepo, RunRepo, init_db

    db_path = str(Path(str(tmp_path)) / "test.db")  # type: ignore[arg-type]
    conn = init_db(db_path)
    job_repo = JobRepo(conn)
    run_repo = RunRepo(conn)
    error_repo = ErrorLogRepo(conn)
    job_id = job_repo.create()

    definition = StrategyDefinition(
        version="1",
        name="Test SMA",
        variant="basic",
        indicators=[IndicatorDef(name="fast_sma", type="sma", params={"period": 10})],
        entry_rules=[RuleDef(indicator="fast_sma", condition=">", value=0.0)],
        exit_rules=[],
        position_management=PositionManagement(),
    )

    results: list[object] = []
    progresses: list[object] = []

    with patch("src.optimization.grid_search.load_ohlcv", return_value=synthetic_ohlcv):
        opt = GridSearchOptimizer()
        result = opt.run(
            definition=definition,
            param_grid={"period": [10, 20]},
            instruments=["EURUSD"],
            timeframes=["H1"],
            data_dir="/fake",
            job_id=job_id,
            run_repo=run_repo,
            error_repo=error_repo,
            on_progress=progresses.append,
            on_result=results.append,
        )

    assert len(results) == 2  # 2 combos
    assert len(progresses) == 2
    assert "best_params" in result
    assert "best_metrics" in result
    conn.close()
