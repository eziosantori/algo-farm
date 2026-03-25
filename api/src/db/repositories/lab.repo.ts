import { randomUUID } from "crypto";
import type Database from "better-sqlite3";
import type { LifecycleStatus } from "./strategy.repo.js";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SessionStatus = "running" | "completed" | "failed";

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
  strategy_id?: string | null;
  is_start?: string | null;
  is_end?: string | null;
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
  split: "is" | "oos" | "full" | "robustness_score" | "wf" | "mc" | "sensitivity" | "permutation";
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
  strategy_id?: string | null;
  is_start?: string | null;
  is_end?: string | null;
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
  strategy_id?: string | null;
  is_start?: string | null;
  is_end?: string | null;
  research_notes: string | null;
}

export interface TopPerformerRow {
  instrument: string;
  timeframe: string;
  sharpe_ratio: number;
  total_return_pct: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  profit_factor: number;
  total_trades: number;
  params: Record<string, unknown>;
  status: string;
}

export interface StrategyLabSummary {
  top_performers: TopPerformerRow[];
  best_params: Record<string, unknown>;
  coverage: {
    instruments: string[];
    timeframes: string[];
    total_runs: number;
  };
  sessions_with_notes: Array<{
    id: string;
    created_at: string;
    research_notes: string;
  }>;
}

export interface DeploymentPairRow {
  instrument: string;
  timeframe: string;
  /** Global indicator params merged with per-pair overrides — the params to apply on platform */
  effective_params: Record<string, unknown>;
  /** Keys whose value differs from the global default */
  overridden_keys: string[];
  is_sharpe: number | null;
  oos_sharpe: number | null;
  /** oos_sharpe / is_sharpe ratio (null when either is unavailable or is_sharpe ≤ 0) */
  oos_is_ratio: number | null;
  passed_robustness: boolean;
}

export interface DeploymentSummary {
  strategy_id: string;
  /** Flat merge of all indicator default params — the baseline applied to pairs without overrides */
  global_params: Record<string, unknown>;
  pairs: DeploymentPairRow[];
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
  split: "is" | "oos" | "full" | "robustness_score" | "wf" | "mc" | "sensitivity" | "permutation";
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
    strategy_id?: string;
    is_start?: string | null;
    is_end?: string | null;
  }): { id: string; created_at: string } {
    const id = randomUUID();
    const now = new Date().toISOString();

    this.db
      .prepare(
        `INSERT INTO lab_sessions
           (id, strategy_name, strategy_json, instruments, timeframes, constraints, status, created_at, updated_at, strategy_id, is_start, is_end)
         VALUES (?, ?, ?, ?, ?, ?, 'running', ?, ?, ?, ?, ?)`
      )
      .run(
        id,
        data.strategy_name,
        data.strategy_json,
        JSON.stringify(data.instruments),
        JSON.stringify(data.timeframes),
        data.constraints ? JSON.stringify(data.constraints) : null,
        now,
        now,
        data.strategy_id ?? null,
        data.is_start ?? null,
        data.is_end ?? null
      );

    return { id, created_at: now };
  }

  listSessions(): LabSessionSummary[] {
    const rows = this.db
      .prepare(
        `SELECT
           s.id, s.strategy_name, s.instruments, s.timeframes, s.status,
           s.created_at, s.updated_at, s.strategy_id,
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
      strategy_id: r.strategy_id ?? null,
      is_start: r.is_start ?? null,
      is_end: r.is_end ?? null,
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
      strategy_id: row.strategy_id ?? null,
      is_start: row.is_start ?? null,
      is_end: row.is_end ?? null,
      research_notes: (row as LabSessionRow & { research_notes?: string | null }).research_notes ?? null,
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
    split?: "is" | "oos" | "full" | "robustness_score" | "wf" | "mc" | "sensitivity" | "permutation";
  }): { id: string; created_at: string } {
    const id = randomUUID();
    const now = new Date().toISOString();
    const split = data.split ?? "full";

    this.db
      .prepare(
        `INSERT INTO backtest_results
           (id, session_id, instrument, timeframe, params_json, metrics_json, status, created_at, split)
         VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?)`
      )
      .run(
        id,
        data.session_id,
        data.instrument,
        data.timeframe,
        data.params_json,
        data.metrics_json,
        now,
        split
      );

    // Keep session updated_at in sync
    this.db
      .prepare(`UPDATE lab_sessions SET updated_at = ? WHERE id = ?`)
      .run(now, data.session_id);

    return { id, created_at: now };
  }

  updateResultStatus(id: string, status: ResultStatus): BacktestResultDetail | null {
    const lifecycleStatuses: Set<string> = new Set([
      "validated",
      "production_standard",
      "production_aggressive",
      "production_defensive",
    ]);

    const txn = this.db.transaction(() => {
      const result = this.db
        .prepare(`UPDATE backtest_results SET status = ? WHERE id = ?`)
        .run(status, id);

      if (result.changes === 0) return null;

      if (lifecycleStatuses.has(status)) {
        const link = this.db
          .prepare(
            `SELECT s.strategy_id FROM lab_sessions s
             JOIN backtest_results r ON r.session_id = s.id
             WHERE r.id = ?`
          )
          .get(id) as { strategy_id: string | null } | undefined;

        if (link?.strategy_id) {
          const now = new Date().toISOString();
          this.db
            .prepare(`UPDATE strategies SET lifecycle_status = ?, updated_at = ? WHERE id = ?`)
            .run(status as LifecycleStatus, now, link.strategy_id);
        }
      }

      const row = this.db
        .prepare(`SELECT * FROM backtest_results WHERE id = ?`)
        .get(id) as BacktestResultRow;

      return parseResultRow(row);
    });

    return txn();
  }

  updateSessionNotes(id: string, notes: string): boolean {
    const now = new Date().toISOString();
    const result = this.db
      .prepare(`UPDATE lab_sessions SET research_notes = ?, updated_at = ? WHERE id = ?`)
      .run(notes, now, id);
    return result.changes > 0;
  }

  getDeploymentData(
    strategyId: string,
    definition: {
      indicators: Array<{ params: Record<string, unknown> }>;
      param_overrides?: Record<string, Record<string, Record<string, unknown>>>;
    },
  ): DeploymentSummary {
    // 1. Global params: flat merge of all indicator default params
    const global_params: Record<string, unknown> = {};
    for (const ind of definition.indicators) {
      Object.assign(global_params, ind.params);
    }
    const param_overrides = definition.param_overrides ?? {};

    // 2. Query most-recent IS + OOS results per (instrument, timeframe) for this strategy
    const PASSED = new Set(["validated", "production_standard", "production_aggressive", "production_defensive"]);
    const rows = this.db
      .prepare(
        `SELECT r.instrument, r.timeframe, r.split, r.metrics_json, r.status
         FROM backtest_results r
         JOIN lab_sessions ls ON r.session_id = ls.id
         WHERE ls.strategy_id = ? AND r.split IN ('is', 'oos')
         ORDER BY r.instrument, r.timeframe, r.split, r.created_at DESC`,
      )
      .all(strategyId) as Array<{
        instrument: string; timeframe: string;
        split: string; metrics_json: string; status: string;
      }>;

    // 3. Build per-pair metrics index (first row per split = most recent)
    type PairData = { is_sharpe: number | null; oos_sharpe: number | null; passed: boolean };
    const pairIndex = new Map<string, PairData>();
    for (const row of rows) {
      const key = `${row.instrument}|${row.timeframe}`;
      if (!pairIndex.has(key)) {
        pairIndex.set(key, { is_sharpe: null, oos_sharpe: null, passed: false });
      }
      const entry = pairIndex.get(key)!;
      const m = JSON.parse(row.metrics_json) as { sharpe_ratio?: number };
      if (row.split === "is" && entry.is_sharpe === null) {
        entry.is_sharpe = m.sharpe_ratio ?? null;
      }
      if (row.split === "oos" && entry.oos_sharpe === null) {
        entry.oos_sharpe = m.sharpe_ratio ?? null;
      }
      if (PASSED.has(row.status)) entry.passed = true;
    }

    // 4. Collect all pairs: union of param_overrides keys + Lab results
    const allKeys = new Set<string>(pairIndex.keys());
    for (const instrument of Object.keys(param_overrides)) {
      for (const timeframe of Object.keys(param_overrides[instrument])) {
        allKeys.add(`${instrument}|${timeframe}`);
      }
    }

    // 5. Build DeploymentPairRow for each pair
    const pairs: DeploymentPairRow[] = [];
    for (const key of allKeys) {
      const [instrument, timeframe] = key.split("|");
      const override = param_overrides[instrument]?.[timeframe] ?? {};
      const effective_params = { ...global_params, ...override };
      const overridden_keys = Object.keys(override).filter(
        (k) => JSON.stringify(override[k]) !== JSON.stringify(global_params[k]),
      );
      const entry = pairIndex.get(key);
      const is_sharpe = entry?.is_sharpe ?? null;
      const oos_sharpe = entry?.oos_sharpe ?? null;
      const oos_is_ratio =
        is_sharpe !== null && oos_sharpe !== null && is_sharpe > 0
          ? oos_sharpe / is_sharpe
          : null;
      pairs.push({
        instrument,
        timeframe,
        effective_params,
        overridden_keys,
        is_sharpe,
        oos_sharpe,
        oos_is_ratio,
        passed_robustness: entry?.passed ?? false,
      });
    }

    // Sort: passed first → OOS/IS ratio desc → alphabetical
    pairs.sort((a, b) => {
      if (a.passed_robustness !== b.passed_robustness) return a.passed_robustness ? -1 : 1;
      const ra = a.oos_is_ratio ?? -Infinity;
      const rb = b.oos_is_ratio ?? -Infinity;
      if (rb !== ra) return rb - ra;
      return `${a.instrument}${a.timeframe}`.localeCompare(`${b.instrument}${b.timeframe}`);
    });

    return { strategy_id: strategyId, global_params, pairs };
  }

  getStrategyLabSummary(strategyId: string): StrategyLabSummary | null {
    const sessionCount = this.db
      .prepare(`SELECT COUNT(*) as n FROM lab_sessions WHERE strategy_id = ?`)
      .get(strategyId) as { n: number };
    if (sessionCount.n === 0) return null;

    const rows = this.db.prepare(`
      SELECT br.instrument, br.timeframe, br.params_json, br.metrics_json, br.status
      FROM backtest_results br
      JOIN lab_sessions ls ON br.session_id = ls.id
      WHERE ls.strategy_id = ? AND br.split = 'full'
      ORDER BY json_extract(br.metrics_json, '$.sharpe_ratio') DESC
      LIMIT 10
    `).all(strategyId) as Array<{
      instrument: string;
      timeframe: string;
      params_json: string;
      metrics_json: string;
      status: string;
    }>;

    const coverageRows = this.db.prepare(`
      SELECT DISTINCT br.instrument, br.timeframe
      FROM backtest_results br
      JOIN lab_sessions ls ON br.session_id = ls.id
      WHERE ls.strategy_id = ? AND br.split = 'full'
    `).all(strategyId) as Array<{ instrument: string; timeframe: string }>;

    const notesRows = this.db.prepare(`
      SELECT id, created_at, research_notes
      FROM lab_sessions
      WHERE strategy_id = ? AND research_notes IS NOT NULL
      ORDER BY created_at DESC
    `).all(strategyId) as Array<{ id: string; created_at: string; research_notes: string }>;

    const top_performers: TopPerformerRow[] = rows.map((r) => ({
      ...(JSON.parse(r.metrics_json) as BacktestMetrics),
      instrument: r.instrument,
      timeframe: r.timeframe,
      params: JSON.parse(r.params_json) as Record<string, unknown>,
      status: r.status,
    }));

    return {
      top_performers,
      best_params: top_performers[0]?.params ?? {},
      coverage: {
        instruments: [...new Set(coverageRows.map((r) => r.instrument))],
        timeframes: [...new Set(coverageRows.map((r) => r.timeframe))],
        total_runs: coverageRows.length,
      },
      sessions_with_notes: notesRows.map((r) => ({
        id: r.id,
        created_at: r.created_at,
        research_notes: r.research_notes,
      })),
    };
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
    split: r.split ?? "full",
  };
}
