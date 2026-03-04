import { randomUUID } from "crypto";
import type Database from "better-sqlite3";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SessionStatus = "running" | "completed";

export type ResultStatus =
  | "pending"
  | "validated"
  | "rejected"
  | "production_standard"
  | "production_aggressive"
  | "production_defensive";

export interface LabSessionRow {
  id: string;
  strategy_name: string;
  strategy_json: string;
  instruments: string;
  timeframes: string;
  constraints: string | null;
  status: SessionStatus;
  created_at: string;
  updated_at: string;
}

export interface BacktestResultRow {
  id: string;
  session_id: string;
  instrument: string;
  timeframe: string;
  params_json: string;
  metrics_json: string;
  status: ResultStatus;
  created_at: string;
}

export interface BacktestMetrics {
  total_return_pct: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  profit_factor: number;
  total_trades: number;
  avg_trade_duration_bars: number;
  cagr_pct: number;
  expectancy: number;
}

export interface LabSessionSummary {
  id: string;
  strategy_name: string;
  instruments: string[];
  timeframes: string[];
  status: SessionStatus;
  total_results: number;
  validated_results: number;
  created_at: string;
  updated_at: string;
}

export interface LabSessionDetail {
  id: string;
  strategy_name: string;
  strategy: unknown;
  instruments: string[];
  timeframes: string[];
  constraints: Record<string, number> | null;
  status: SessionStatus;
  results: BacktestResultDetail[];
  created_at: string;
  updated_at: string;
}

export interface BacktestResultDetail {
  id: string;
  session_id: string;
  instrument: string;
  timeframe: string;
  params: Record<string, unknown>;
  metrics: BacktestMetrics;
  status: ResultStatus;
  created_at: string;
}

// ---------------------------------------------------------------------------
// Repository
// ---------------------------------------------------------------------------

export class LabRepository {
  constructor(private readonly db: Database.Database) {}

  // --- Sessions -------------------------------------------------------------

  createSession(data: {
    strategy_name: string;
    strategy_json: string;
    instruments: string[];
    timeframes: string[];
    constraints?: Record<string, number> | null;
  }): { id: string; created_at: string } {
    const id = randomUUID();
    const now = new Date().toISOString();

    this.db
      .prepare(
        `INSERT INTO lab_sessions
           (id, strategy_name, strategy_json, instruments, timeframes, constraints, status, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?)`
      )
      .run(
        id,
        data.strategy_name,
        data.strategy_json,
        JSON.stringify(data.instruments),
        JSON.stringify(data.timeframes),
        data.constraints ? JSON.stringify(data.constraints) : null,
        now,
        now
      );

    return { id, created_at: now };
  }

  listSessions(): LabSessionSummary[] {
    const rows = this.db
      .prepare(
        `SELECT
           s.id, s.strategy_name, s.instruments, s.timeframes, s.status,
           s.created_at, s.updated_at,
           COUNT(r.id) AS total_results,
           SUM(CASE WHEN r.status NOT IN ('pending','rejected') THEN 1 ELSE 0 END) AS validated_results
         FROM lab_sessions s
         LEFT JOIN backtest_results r ON r.session_id = s.id
         GROUP BY s.id
         ORDER BY s.created_at DESC, s.rowid DESC`
      )
      .all() as (LabSessionRow & { total_results: number; validated_results: number })[];

    return rows.map((r) => ({
      id: r.id,
      strategy_name: r.strategy_name,
      instruments: JSON.parse(r.instruments) as string[],
      timeframes: JSON.parse(r.timeframes) as string[],
      status: r.status,
      total_results: r.total_results,
      validated_results: r.validated_results,
      created_at: r.created_at,
      updated_at: r.updated_at,
    }));
  }

  getSession(id: string): LabSessionDetail | null {
    const row = this.db
      .prepare(`SELECT * FROM lab_sessions WHERE id = ?`)
      .get(id) as LabSessionRow | undefined;

    if (!row) return null;

    const resultRows = this.db
      .prepare(
        `SELECT * FROM backtest_results WHERE session_id = ?
         ORDER BY json_extract(metrics_json, '$.sharpe_ratio') DESC`
      )
      .all(id) as BacktestResultRow[];

    return {
      id: row.id,
      strategy_name: row.strategy_name,
      strategy: JSON.parse(row.strategy_json) as unknown,
      instruments: JSON.parse(row.instruments) as string[],
      timeframes: JSON.parse(row.timeframes) as string[],
      constraints: row.constraints ? (JSON.parse(row.constraints) as Record<string, number>) : null,
      status: row.status,
      results: resultRows.map(parseResultRow),
      created_at: row.created_at,
      updated_at: row.updated_at,
    };
  }

  updateSessionStatus(id: string, status: SessionStatus): boolean {
    const now = new Date().toISOString();
    const result = this.db
      .prepare(`UPDATE lab_sessions SET status = ?, updated_at = ? WHERE id = ?`)
      .run(status, now, id);
    return result.changes > 0;
  }

  // --- Results --------------------------------------------------------------

  addResult(data: {
    session_id: string;
    instrument: string;
    timeframe: string;
    params_json: string;
    metrics_json: string;
  }): { id: string; created_at: string } {
    const id = randomUUID();
    const now = new Date().toISOString();

    this.db
      .prepare(
        `INSERT INTO backtest_results
           (id, session_id, instrument, timeframe, params_json, metrics_json, status, created_at)
         VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)`
      )
      .run(
        id,
        data.session_id,
        data.instrument,
        data.timeframe,
        data.params_json,
        data.metrics_json,
        now
      );

    // Keep session updated_at in sync
    this.db
      .prepare(`UPDATE lab_sessions SET updated_at = ? WHERE id = ?`)
      .run(now, data.session_id);

    return { id, created_at: now };
  }

  updateResultStatus(id: string, status: ResultStatus): BacktestResultDetail | null {
    const result = this.db
      .prepare(`UPDATE backtest_results SET status = ? WHERE id = ?`)
      .run(status, id);

    if (result.changes === 0) return null;

    const row = this.db
      .prepare(`SELECT * FROM backtest_results WHERE id = ?`)
      .get(id) as BacktestResultRow;

    return parseResultRow(row);
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function parseResultRow(r: BacktestResultRow): BacktestResultDetail {
  return {
    id: r.id,
    session_id: r.session_id,
    instrument: r.instrument,
    timeframe: r.timeframe,
    params: JSON.parse(r.params_json) as Record<string, unknown>,
    metrics: JSON.parse(r.metrics_json) as BacktestMetrics,
    status: r.status,
    created_at: r.created_at,
  };
}
