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
