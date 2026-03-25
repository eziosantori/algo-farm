import { describe, it, expect, beforeEach, afterEach } from "vitest";
import Database from "better-sqlite3";
import { readFileSync } from "fs";
import { join } from "path";
import { LabRepository } from "../../src/db/repositories/lab.repo.js";

function createInMemoryDb(): Database.Database {
  const db = new Database(":memory:");
  db.pragma("foreign_keys = ON");
  const schema = readFileSync(join(__dirname, "../../src/db/schema.sql"), "utf-8");
  db.exec(schema);
  return db;
}

const sampleMetrics = {
  total_return_pct: 5.2,
  sharpe_ratio: 1.4,
  sortino_ratio: 1.8,
  calmar_ratio: 1.1,
  max_drawdown_pct: -4.7,
  win_rate_pct: 58.0,
  profit_factor: 1.6,
  total_trades: 42,
  avg_trade_duration_bars: 18,
  cagr_pct: 3.1,
  expectancy: 12.4,
};

const sampleSession = {
  strategy_name: "SuperTrend + RSI",
  strategy_json: '{"version":"1","name":"SuperTrend + RSI"}',
  instruments: ["EURUSD", "XAUUSD"],
  timeframes: ["H1", "M15"],
  constraints: { min_sharpe: 1.2, max_dd: 8 },
};

describe("LabRepository — sessions", () => {
  let db: Database.Database;
  let repo: LabRepository;

  beforeEach(() => {
    db = createInMemoryDb();
    repo = new LabRepository(db);
  });

  afterEach(() => db.close());

  it("creates a session and returns id + created_at", () => {
    const result = repo.createSession(sampleSession);
    expect(result.id).toBeTruthy();
    expect(result.created_at).toBeTruthy();
  });

  it("lists sessions with summary counts", () => {
    const { id } = repo.createSession(sampleSession);
    repo.addResult({
      session_id: id,
      instrument: "EURUSD",
      timeframe: "H1",
      params_json: "{}",
      metrics_json: JSON.stringify(sampleMetrics),
    });
    const list = repo.listSessions();
    expect(list).toHaveLength(1);
    expect(list[0].total_results).toBe(1);
    expect(list[0].validated_results).toBe(0);
    expect(list[0].instruments).toEqual(["EURUSD", "XAUUSD"]);
    expect(list[0].timeframes).toEqual(["H1", "M15"]);
  });

  it("returns null for unknown session", () => {
    expect(repo.getSession("nope")).toBeNull();
  });

  it("getSession includes parsed results sorted by sharpe desc", () => {
    const { id } = repo.createSession(sampleSession);
    repo.addResult({
      session_id: id, instrument: "EURUSD", timeframe: "H1",
      params_json: "{}", metrics_json: JSON.stringify({ ...sampleMetrics, sharpe_ratio: 0.5 }),
    });
    repo.addResult({
      session_id: id, instrument: "XAUUSD", timeframe: "M15",
      params_json: "{}", metrics_json: JSON.stringify({ ...sampleMetrics, sharpe_ratio: 2.1 }),
    });
    const detail = repo.getSession(id)!;
    expect(detail.results).toHaveLength(2);
    expect(detail.results[0].metrics.sharpe_ratio).toBe(2.1);
    expect(detail.results[1].metrics.sharpe_ratio).toBe(0.5);
    expect(detail.constraints).toEqual({ min_sharpe: 1.2, max_dd: 8 });
  });

  it("updates session status", () => {
    const { id } = repo.createSession(sampleSession);
    const ok = repo.updateSessionStatus(id, "completed");
    expect(ok).toBe(true);
    expect(repo.getSession(id)!.status).toBe("completed");
  });

  it("returns false updating status for non-existent session", () => {
    expect(repo.updateSessionStatus("nope", "completed")).toBe(false);
  });
});

describe("LabRepository — results", () => {
  let db: Database.Database;
  let repo: LabRepository;
  let sessionId: string;

  beforeEach(() => {
    db = createInMemoryDb();
    repo = new LabRepository(db);
    ({ id: sessionId } = repo.createSession(sampleSession));
  });

  afterEach(() => db.close());

  it("adds a result and returns id + created_at", () => {
    const result = repo.addResult({
      session_id: sessionId,
      instrument: "EURUSD",
      timeframe: "H1",
      params_json: JSON.stringify({ period: 10 }),
      metrics_json: JSON.stringify(sampleMetrics),
    });
    expect(result.id).toBeTruthy();
  });

  it("result default status is pending", () => {
    const { id } = repo.addResult({
      session_id: sessionId, instrument: "EURUSD", timeframe: "H1",
      params_json: "{}", metrics_json: JSON.stringify(sampleMetrics),
    });
    const detail = repo.getSession(sessionId)!;
    expect(detail.results.find((r) => r.id === id)?.status).toBe("pending");
  });

  it("updates result status to validated", () => {
    const { id } = repo.addResult({
      session_id: sessionId, instrument: "EURUSD", timeframe: "H1",
      params_json: "{}", metrics_json: JSON.stringify(sampleMetrics),
    });
    const updated = repo.updateResultStatus(id, "validated");
    expect(updated?.status).toBe("validated");
  });

  it("updates result status to production_standard", () => {
    const { id } = repo.addResult({
      session_id: sessionId, instrument: "EURUSD", timeframe: "H1",
      params_json: "{}", metrics_json: JSON.stringify(sampleMetrics),
    });
    const updated = repo.updateResultStatus(id, "production_standard");
    expect(updated?.status).toBe("production_standard");
  });

  it("returns null updating status of non-existent result", () => {
    expect(repo.updateResultStatus("nope", "validated")).toBeNull();
  });

  it("validated_results count reflects non-pending/non-rejected statuses", () => {
    const r1 = repo.addResult({
      session_id: sessionId, instrument: "EURUSD", timeframe: "H1",
      params_json: "{}", metrics_json: JSON.stringify(sampleMetrics),
    });
    const r2 = repo.addResult({
      session_id: sessionId, instrument: "XAUUSD", timeframe: "M15",
      params_json: "{}", metrics_json: JSON.stringify(sampleMetrics),
    });
    repo.updateResultStatus(r1.id, "validated");
    repo.updateResultStatus(r2.id, "rejected");
    const list = repo.listSessions();
    expect(list[0].validated_results).toBe(1);
  });

  it("cascade deletes results when session is deleted", () => {
    repo.addResult({
      session_id: sessionId, instrument: "EURUSD", timeframe: "H1",
      params_json: "{}", metrics_json: JSON.stringify(sampleMetrics),
    });
    db.prepare("DELETE FROM lab_sessions WHERE id = ?").run(sessionId);
    const rows = db.prepare("SELECT * FROM backtest_results WHERE session_id = ?").all(sessionId);
    expect(rows).toHaveLength(0);
  });
});

describe("LabRepository — updateSessionNotes", () => {
  let db: Database.Database;
  let repo: LabRepository;

  beforeEach(() => {
    db = createInMemoryDb();
    repo = new LabRepository(db);
  });

  afterEach(() => db.close());

  it("saves notes and returns true", () => {
    const { id } = repo.createSession(sampleSession);
    const ok = repo.updateSessionNotes(id, "## Test notes");
    expect(ok).toBe(true);
    const row = db.prepare("SELECT research_notes FROM lab_sessions WHERE id = ?").get(id) as { research_notes: string };
    expect(row.research_notes).toBe("## Test notes");
  });

  it("returns false for non-existent session id", () => {
    expect(repo.updateSessionNotes("nope", "notes")).toBe(false);
  });
});

describe("LabRepository — getStrategyLabSummary", () => {
  let db: Database.Database;
  let repo: LabRepository;
  let strategyId: string;

  beforeEach(() => {
    db = createInMemoryDb();
    // Add lifecycle_status column as migration would do
    try { db.exec(`ALTER TABLE strategies ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'draft'`); } catch { /* already exists */ }
    repo = new LabRepository(db);
    strategyId = "strategy-" + Math.random().toString(36).slice(2);
    db.prepare(
      `INSERT INTO strategies (id, name, variant, definition_json, created_at, updated_at, lifecycle_status)
       VALUES (?, 'Test', 'basic', '{}', datetime('now'), datetime('now'), 'validated')`
    ).run(strategyId);
  });

  afterEach(() => db.close());

  it("returns null when no sessions are linked", () => {
    expect(repo.getStrategyLabSummary(strategyId)).toBeNull();
  });

  it("top_performers are ordered by sharpe DESC", () => {
    const { id: sessionId } = repo.createSession({ ...sampleSession, strategy_id: strategyId });
    repo.addResult({
      session_id: sessionId, instrument: "EURUSD", timeframe: "H1",
      params_json: "{}", metrics_json: JSON.stringify({ ...sampleMetrics, sharpe_ratio: 0.5 }),
      split: "full",
    });
    repo.addResult({
      session_id: sessionId, instrument: "XAUUSD", timeframe: "H4",
      params_json: "{}", metrics_json: JSON.stringify({ ...sampleMetrics, sharpe_ratio: 1.8 }),
      split: "full",
    });
    const summary = repo.getStrategyLabSummary(strategyId)!;
    expect(summary.top_performers[0].sharpe_ratio).toBe(1.8);
    expect(summary.top_performers[1].sharpe_ratio).toBe(0.5);
  });

  it("excludes split != 'full' from top_performers", () => {
    const { id: sessionId } = repo.createSession({ ...sampleSession, strategy_id: strategyId });
    repo.addResult({
      session_id: sessionId, instrument: "EURUSD", timeframe: "H1",
      params_json: "{}", metrics_json: JSON.stringify({ ...sampleMetrics, sharpe_ratio: 2.0 }),
      split: "is",
    });
    repo.addResult({
      session_id: sessionId, instrument: "XAUUSD", timeframe: "H1",
      params_json: "{}", metrics_json: JSON.stringify({ ...sampleMetrics, sharpe_ratio: 1.2 }),
      split: "full",
    });
    const summary = repo.getStrategyLabSummary(strategyId)!;
    expect(summary.top_performers).toHaveLength(1);
    expect(summary.top_performers[0].instrument).toBe("XAUUSD");
  });

  it("sessions_with_notes only includes sessions with notes set", () => {
    const { id: s1 } = repo.createSession({ ...sampleSession, strategy_id: strategyId });
    const { id: s2 } = repo.createSession({ ...sampleSession, strategy_id: strategyId });
    repo.updateSessionNotes(s1, "## My research");
    const summary = repo.getStrategyLabSummary(strategyId)!;
    expect(summary.sessions_with_notes).toHaveLength(1);
    expect(summary.sessions_with_notes[0].id).toBe(s1);
    expect(summary.sessions_with_notes[0].research_notes).toBe("## My research");
    void s2;
  });

  it("coverage is correct across multiple sessions", () => {
    const { id: s1 } = repo.createSession({ ...sampleSession, strategy_id: strategyId });
    const { id: s2 } = repo.createSession({ ...sampleSession, strategy_id: strategyId });
    repo.addResult({
      session_id: s1, instrument: "EURUSD", timeframe: "H1",
      params_json: "{}", metrics_json: JSON.stringify(sampleMetrics), split: "full",
    });
    repo.addResult({
      session_id: s2, instrument: "GER40", timeframe: "H4",
      params_json: "{}", metrics_json: JSON.stringify(sampleMetrics), split: "full",
    });
    const summary = repo.getStrategyLabSummary(strategyId)!;
    expect(summary.coverage.instruments).toContain("EURUSD");
    expect(summary.coverage.instruments).toContain("GER40");
    expect(summary.coverage.timeframes).toContain("H1");
    expect(summary.coverage.timeframes).toContain("H4");
    expect(summary.coverage.total_runs).toBe(2);
  });

  it("best_params comes from the top performer", () => {
    const { id: sessionId } = repo.createSession({ ...sampleSession, strategy_id: strategyId });
    repo.addResult({
      session_id: sessionId, instrument: "EURUSD", timeframe: "H1",
      params_json: JSON.stringify({ period: 21 }), metrics_json: JSON.stringify({ ...sampleMetrics, sharpe_ratio: 1.5 }),
      split: "full",
    });
    const summary = repo.getStrategyLabSummary(strategyId)!;
    expect(summary.best_params).toEqual({ period: 21 });
  });
});

// ---------------------------------------------------------------------------
// getDeploymentData
// ---------------------------------------------------------------------------

describe("LabRepository — getDeploymentData", () => {
  let db: Database.Database;
  let repo: LabRepository;
  const strategyId = "strat-deploy-01";

  const definition = {
    indicators: [
      { params: { period: 14 } },
      { params: { multiplier: 3.5 } },
    ],
    param_overrides: {
      XAUUSD: { H4: { period: 21, multiplier: 4.0 } },
      GER40: { H1: { period: 10 } },
    },
  };

  beforeEach(() => {
    db = createInMemoryDb();
    repo = new LabRepository(db);
    db.prepare(
      `INSERT INTO strategies (id, name, variant, definition_json, created_at, updated_at, lifecycle_status)
       VALUES (?, 'Test', 'basic', '{}', datetime('now'), datetime('now'), 'validated')`
    ).run(strategyId);
  });
  afterEach(() => db.close());

  it("returns global_params as flat merge of all indicator params", () => {
    const result = repo.getDeploymentData(strategyId, definition);
    expect(result.global_params).toEqual({ period: 14, multiplier: 3.5 });
  });

  it("computes effective_params as global + override for each pair", () => {
    const result = repo.getDeploymentData(strategyId, definition);
    const xau = result.pairs.find((p) => p.instrument === "XAUUSD" && p.timeframe === "H4")!;
    expect(xau.effective_params).toEqual({ period: 21, multiplier: 4.0 });
    expect(xau.overridden_keys).toContain("period");
    expect(xau.overridden_keys).toContain("multiplier");
  });

  it("effective_params for a pair with partial override inherits global for unchanged keys", () => {
    const result = repo.getDeploymentData(strategyId, definition);
    const ger = result.pairs.find((p) => p.instrument === "GER40" && p.timeframe === "H1")!;
    expect(ger.effective_params.period).toBe(10);
    expect(ger.effective_params.multiplier).toBe(3.5); // inherited from global
    expect(ger.overridden_keys).toEqual(["period"]);
  });

  it("includes IS and OOS sharpe from Lab results", () => {
    const { id: sessionId } = repo.createSession({
      ...sampleSession, strategy_id: strategyId,
    });
    repo.addResult({
      session_id: sessionId, instrument: "XAUUSD", timeframe: "H4",
      params_json: JSON.stringify({ period: 21, multiplier: 4.0 }),
      metrics_json: JSON.stringify({ ...sampleMetrics, sharpe_ratio: 0.65 }),
      split: "is",
    });
    repo.addResult({
      session_id: sessionId, instrument: "XAUUSD", timeframe: "H4",
      params_json: JSON.stringify({ period: 21, multiplier: 4.0 }),
      metrics_json: JSON.stringify({ ...sampleMetrics, sharpe_ratio: 0.49 }),
      split: "oos",
    });

    const result = repo.getDeploymentData(strategyId, definition);
    const xau = result.pairs.find((p) => p.instrument === "XAUUSD" && p.timeframe === "H4")!;
    expect(xau.is_sharpe).toBeCloseTo(0.65);
    expect(xau.oos_sharpe).toBeCloseTo(0.49);
    expect(xau.oos_is_ratio).toBeCloseTo(0.49 / 0.65);
  });

  it("passed_robustness is true when a result has validated status", () => {
    const { id: sessionId } = repo.createSession({
      ...sampleSession, strategy_id: strategyId,
    });
    const { id: resultId } = repo.addResult({
      session_id: sessionId, instrument: "XAUUSD", timeframe: "H4",
      params_json: "{}", metrics_json: JSON.stringify(sampleMetrics), split: "is",
    });
    repo.updateResultStatus(resultId, "validated");

    const result = repo.getDeploymentData(strategyId, definition);
    const xau = result.pairs.find((p) => p.instrument === "XAUUSD" && p.timeframe === "H4")!;
    expect(xau.passed_robustness).toBe(true);
  });

  it("passed_robustness is false when result status is pending", () => {
    const { id: sessionId } = repo.createSession({
      ...sampleSession, strategy_id: strategyId,
    });
    repo.addResult({
      session_id: sessionId, instrument: "GER40", timeframe: "H1",
      params_json: "{}", metrics_json: JSON.stringify(sampleMetrics), split: "is",
    });
    const result = repo.getDeploymentData(strategyId, definition);
    const ger = result.pairs.find((p) => p.instrument === "GER40" && p.timeframe === "H1")!;
    expect(ger.passed_robustness).toBe(false);
  });

  it("passed pairs are sorted before failed pairs", () => {
    const { id: sessionId } = repo.createSession({
      ...sampleSession, strategy_id: strategyId,
    });
    repo.addResult({
      session_id: sessionId, instrument: "GER40", timeframe: "H1",
      params_json: "{}", metrics_json: JSON.stringify(sampleMetrics), split: "is",
    });
    const { id: xauResultId } = repo.addResult({
      session_id: sessionId, instrument: "XAUUSD", timeframe: "H4",
      params_json: "{}", metrics_json: JSON.stringify(sampleMetrics), split: "is",
    });
    repo.updateResultStatus(xauResultId, "validated");

    const result = repo.getDeploymentData(strategyId, definition);
    expect(result.pairs[0].instrument).toBe("XAUUSD");
    expect(result.pairs[0].passed_robustness).toBe(true);
  });

  it("returns empty pairs list when no overrides and no Lab results", () => {
    const result = repo.getDeploymentData(strategyId, {
      indicators: [{ params: { period: 14 } }],
      param_overrides: {},
    });
    expect(result.pairs).toHaveLength(0);
    expect(result.global_params).toEqual({ period: 14 });
  });
});
