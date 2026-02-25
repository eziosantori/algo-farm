"""Unit tests for SQLite storage layer."""
from __future__ import annotations

import json
import sqlite3

import pytest

from src.storage.db import ErrorLogRepo, JobRepo, RunRepo, init_db


@pytest.fixture()
def conn() -> sqlite3.Connection:
    c = init_db(":memory:")
    yield c  # type: ignore[misc]
    c.close()


def test_init_db_creates_tables(conn: sqlite3.Connection) -> None:
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {"jobs", "runs", "error_log"}.issubset(tables)


def test_job_create_and_get(conn: sqlite3.Connection) -> None:
    repo = JobRepo(conn)
    job_id = repo.create(job_type="grid_search", params_json='{"x": 1}')
    assert len(job_id) == 36  # UUID
    job = repo.get(job_id)
    assert job is not None
    assert job["status"] == "pending"
    assert job["job_type"] == "grid_search"


def test_job_update_status(conn: sqlite3.Connection) -> None:
    repo = JobRepo(conn)
    job_id = repo.create()
    repo.update_status(job_id, "running")
    job = repo.get(job_id)
    assert job is not None
    assert job["status"] == "running"


def test_job_get_nonexistent(conn: sqlite3.Connection) -> None:
    repo = JobRepo(conn)
    assert repo.get("00000000-0000-0000-0000-000000000000") is None


def test_run_create_and_signatures(conn: sqlite3.Connection) -> None:
    job_repo = JobRepo(conn)
    run_repo = RunRepo(conn)
    job_id = job_repo.create()

    params = {"period": 10}
    metrics = {
        "total_return_pct": 5.0,
        "sharpe_ratio": 1.2,
        "sortino_ratio": 1.5,
        "calmar_ratio": 0.8,
        "max_drawdown_pct": -6.25,
        "win_rate_pct": 55.0,
        "profit_factor": 1.8,
        "total_trades": 20,
        "avg_trade_duration_bars": 5.0,
        "cagr_pct": 4.9,
        "expectancy": 12.5,
    }
    run_id = run_repo.create(
        job_id=job_id,
        instrument="EURUSD",
        timeframe="H1",
        params=params,
        equity_curve=[10000.0, 10500.0],
        trades=[],
        metrics_dict=metrics,
    )
    assert len(run_id) == 36

    sigs = run_repo.get_completed_signatures(job_id)
    expected_sig = f"EURUSD|H1|{json.dumps(params, sort_keys=True)}"
    assert expected_sig in sigs


def test_run_resume_skips_completed(conn: sqlite3.Connection) -> None:
    job_repo = JobRepo(conn)
    run_repo = RunRepo(conn)
    job_id = job_repo.create()

    params = {"period": 20}
    run_repo.create(
        job_id=job_id,
        instrument="GBPUSD",
        timeframe="D1",
        params=params,
        equity_curve=[],
        trades=[],
        metrics_dict={},
    )
    sigs = run_repo.get_completed_signatures(job_id)
    sig = f"GBPUSD|D1|{json.dumps(params, sort_keys=True)}"
    assert sig in sigs


def test_error_log(conn: sqlite3.Connection) -> None:
    repo = ErrorLogRepo(conn)
    job_repo = JobRepo(conn)
    job_id = job_repo.create()

    repo.log(job_id, "ValueError", "something broke", tb="traceback here", context={"k": "v"})
    rows = conn.execute("SELECT * FROM error_log WHERE job_id = ?", (job_id,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["error_type"] == "ValueError"
    assert rows[0]["message"] == "something broke"
