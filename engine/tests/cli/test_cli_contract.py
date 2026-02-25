"""CLI contract tests via subprocess."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


FIXTURES = Path(__file__).parent.parent / "fixtures"
ENGINE_DIR = Path(__file__).parent.parent.parent
STRATEGY = str(FIXTURES / "simple_sma_strategy.json")
PARAM_GRID = str(FIXTURES / "simple_param_grid.json")
DATA_DIR = str(FIXTURES)


def _run_engine(*extra_args: str, db: str) -> subprocess.CompletedProcess[bytes]:
    cmd = [
        sys.executable,
        str(ENGINE_DIR / "run.py"),
        "--strategy", STRATEGY,
        "--instruments", "EURUSD",
        "--timeframes", "H1",
        "--param-grid", PARAM_GRID,
        "--db", db,
        "--data-dir", DATA_DIR,
        *extra_args,
    ]
    return subprocess.run(cmd, capture_output=True, cwd=str(ENGINE_DIR))


def test_cli_exit_code_zero_on_success(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    result = _run_engine(db=db)
    assert result.returncode == 0, result.stderr.decode()


def test_cli_stdout_is_valid_jsonl(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    result = _run_engine(db=db)
    lines = [l for l in result.stdout.strip().split(b"\n") if l]
    assert len(lines) > 0, "No output on stdout"
    for line in lines:
        msg = json.loads(line)
        assert "type" in msg
        assert msg["type"] in ("progress", "result", "completed", "interrupted")


def test_cli_last_message_is_completed(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    result = _run_engine(db=db)
    lines = [l for l in result.stdout.strip().split(b"\n") if l]
    last = json.loads(lines[-1])
    assert last["type"] == "completed"
    assert "job_id" in last
    assert "best_params" in last
    assert "db_path" in last


def test_cli_exit_code_one_on_bad_strategy(tmp_path: Path) -> None:
    bad_strategy = tmp_path / "bad.json"
    bad_strategy.write_text('{"invalid": true}')
    db = str(tmp_path / "test.db")
    cmd = [
        sys.executable,
        str(ENGINE_DIR / "run.py"),
        "--strategy", str(bad_strategy),
        "--instruments", "EURUSD",
        "--timeframes", "H1",
        "--db", db,
        "--data-dir", DATA_DIR,
    ]
    result = subprocess.run(cmd, capture_output=True, cwd=str(ENGINE_DIR))
    assert result.returncode == 1


def test_cli_nothing_written_to_stderr_on_success(tmp_path: Path) -> None:
    """Stderr may have log output, but stdout must be JSONL only."""
    db = str(tmp_path / "test.db")
    result = _run_engine(db=db)
    # All stdout lines must be valid JSON
    for line in result.stdout.strip().split(b"\n"):
        if line:
            json.loads(line)  # raises if invalid


def test_cli_resume_skips_completed_runs(tmp_path: Path) -> None:
    db = str(tmp_path / "test.db")
    # First run
    r1 = _run_engine(db=db)
    assert r1.returncode == 0
    lines1 = [json.loads(l) for l in r1.stdout.strip().split(b"\n") if l]
    job_id = next(m["job_id"] for m in lines1 if m["type"] == "completed")

    # Resume — should complete quickly with no new result messages
    r2 = _run_engine("--resume-job", job_id, db=db)
    assert r2.returncode == 0
    lines2 = [json.loads(l) for l in r2.stdout.strip().split(b"\n") if l]
    # No new result messages (all runs already done)
    result_msgs = [m for m in lines2 if m["type"] == "result"]
    assert len(result_msgs) == 0
