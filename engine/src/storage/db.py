"""SQLite storage: init_db, JobRepo, RunRepo, ErrorLogRepo."""
from __future__ import annotations

import json
import sqlite3
import traceback
import uuid
from datetime import datetime, timezone


def init_db(db_path: str) -> sqlite3.Connection:
    """Create (or open) the SQLite database and ensure all tables exist."""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _create_tables(conn)
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'pending',
            job_type TEXT NOT NULL DEFAULT 'grid_search',
            params_json TEXT,
            resume_from_instrument TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS runs (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES jobs(id),
            instrument TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            params_json TEXT,
            equity_curve_json TEXT,
            trades_json TEXT,
            total_return_pct REAL,
            sharpe_ratio REAL,
            sortino_ratio REAL,
            calmar_ratio REAL,
            max_drawdown_pct REAL,
            win_rate_pct REAL,
            profit_factor REAL,
            total_trades INTEGER,
            avg_trade_duration_bars REAL,
            cagr_pct REAL,
            expectancy REAL,
            completed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS error_log (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            error_type TEXT NOT NULL,
            message TEXT NOT NULL,
            traceback TEXT,
            context_json TEXT,
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


class JobRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(
        self,
        job_type: str = "grid_search",
        params_json: str | None = None,
        job_id: str | None = None,
    ) -> str:
        if job_id is None:
            job_id = str(uuid.uuid4())
        self._conn.execute(
            "INSERT INTO jobs (id, status, job_type, params_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (job_id, "pending", job_type, params_json, _now_iso()),
        )
        self._conn.commit()
        return job_id

    def get(self, job_id: str) -> dict[str, object] | None:
        row = self._conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def update_status(self, job_id: str, status: str) -> None:
        ts_field = ""
        if status == "running":
            ts_field = ", started_at = ?"
        elif status in ("completed", "interrupted", "error"):
            ts_field = ", completed_at = ?"

        if ts_field:
            self._conn.execute(
                f"UPDATE jobs SET status = ?{ts_field} WHERE id = ?",
                (status, _now_iso(), job_id),
            )
        else:
            self._conn.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))
        self._conn.commit()


class RunRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create(
        self,
        job_id: str,
        instrument: str,
        timeframe: str,
        params: dict[str, object],
        equity_curve: list[float],
        trades: list[dict[str, object]],
        metrics_dict: dict[str, object],
    ) -> str:
        run_id = str(uuid.uuid4())
        self._conn.execute(
            """
            INSERT INTO runs (
                id, job_id, instrument, timeframe,
                params_json, equity_curve_json, trades_json,
                total_return_pct, sharpe_ratio, sortino_ratio, calmar_ratio,
                max_drawdown_pct, win_rate_pct, profit_factor, total_trades,
                avg_trade_duration_bars, cagr_pct, expectancy, completed_at
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?
            )
            """,
            (
                run_id, job_id, instrument, timeframe,
                json.dumps(params),
                json.dumps(equity_curve),
                json.dumps(trades),
                metrics_dict.get("total_return_pct"),
                metrics_dict.get("sharpe_ratio"),
                metrics_dict.get("sortino_ratio"),
                metrics_dict.get("calmar_ratio"),
                metrics_dict.get("max_drawdown_pct"),
                metrics_dict.get("win_rate_pct"),
                metrics_dict.get("profit_factor"),
                metrics_dict.get("total_trades"),
                metrics_dict.get("avg_trade_duration_bars"),
                metrics_dict.get("cagr_pct"),
                metrics_dict.get("expectancy"),
                _now_iso(),
            ),
        )
        self._conn.commit()
        return run_id

    def get_completed_signatures(self, job_id: str) -> set[str]:
        """Return set of 'instrument|timeframe|params_json' for completed runs."""
        rows = self._conn.execute(
            "SELECT instrument, timeframe, params_json FROM runs WHERE job_id = ?",
            (job_id,),
        ).fetchall()
        sigs: set[str] = set()
        for row in rows:
            params = row["params_json"] or "{}"
            # Normalise params JSON for stable comparison
            try:
                normalised = json.dumps(json.loads(params), sort_keys=True)
            except json.JSONDecodeError:
                normalised = params
            sigs.add(f"{row['instrument']}|{row['timeframe']}|{normalised}")
        return sigs


class ErrorLogRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def log(
        self,
        job_id: str,
        error_type: str,
        message: str,
        tb: str | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        if tb is None:
            tb = traceback.format_exc()
        self._conn.execute(
            """
            INSERT INTO error_log (id, job_id, error_type, message, traceback, context_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid.uuid4()),
                job_id,
                error_type,
                message,
                tb,
                json.dumps(context) if context else None,
                _now_iso(),
            ),
        )
        self._conn.commit()
