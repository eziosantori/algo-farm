import { describe, it, expect, beforeEach, afterEach } from "vitest";
import Database from "better-sqlite3";
import { readFileSync } from "fs";
import { join } from "path";
import { runCleanup } from "../../src/db/client.js";

function createInMemoryDb(): Database.Database {
  const db = new Database(":memory:");
  db.pragma("foreign_keys = ON");
  const schema = readFileSync(join(__dirname, "../../src/db/schema.sql"), "utf-8");
  db.exec(schema);
  return db;
}

/** ISO timestamp N days in the past */
function daysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return d.toISOString();
}

function insertSession(
  db: Database.Database,
  id: string,
  opts: { status?: string; daysAgo?: number; strategyId?: string | null } = {},
): void {
  const status = opts.status ?? "completed";
  const createdAt = daysAgo(opts.daysAgo ?? 0);
  const strategyId = opts.strategyId ?? null;
  db.prepare(`
    INSERT INTO lab_sessions
      (id, strategy_name, strategy_json, instruments, timeframes,
       status, created_at, updated_at, strategy_id)
    VALUES (?, 'test', '{}', '[]', '[]', ?, ?, ?, ?)
  `).run(id, status, createdAt, createdAt, strategyId);
}

function insertStrategy(
  db: Database.Database,
  id: string,
  lifecycleStatus: string,
): void {
  const now = new Date().toISOString();
  db.prepare(`
    INSERT INTO strategies
      (id, name, variant, definition_json, created_at, updated_at, lifecycle_status)
    VALUES (?, 'strat', 'basic', '{}', ?, ?, ?)
  `).run(id, now, now, lifecycleStatus);
}

function countSessions(db: Database.Database): number {
  return (db.prepare("SELECT COUNT(*) as n FROM lab_sessions").get() as { n: number }).n;
}

function countResults(db: Database.Database): number {
  return (db.prepare("SELECT COUNT(*) as n FROM backtest_results").get() as { n: number }).n;
}

describe("runCleanup", () => {
  let db: Database.Database;

  beforeEach(() => { db = createInMemoryDb(); });
  afterEach(() => db.close());

  it("returns 0 and removes nothing when DB is empty", () => {
    expect(runCleanup(db, 90)).toBe(0);
    expect(countSessions(db)).toBe(0);
  });

  it("removes failed sessions older than 14 days", () => {
    insertSession(db, "old-fail", { status: "failed", daysAgo: 15 });
    insertSession(db, "recent-fail", { status: "failed", daysAgo: 5 });
    expect(runCleanup(db, 90)).toBe(1);
    expect(countSessions(db)).toBe(1);
  });

  it("removes completed sessions older than retainDays with no strategy_id", () => {
    insertSession(db, "old-orphan", { status: "completed", daysAgo: 100 });
    insertSession(db, "recent-orphan", { status: "completed", daysAgo: 10 });
    expect(runCleanup(db, 90)).toBe(1);
    expect(countSessions(db)).toBe(1);
  });

  it("keeps sessions linked to validated strategies indefinitely", () => {
    insertStrategy(db, "sv1", "validated");
    insertSession(db, "old-validated", { status: "completed", daysAgo: 365, strategyId: "sv1" });
    expect(runCleanup(db, 90)).toBe(0);
    expect(countSessions(db)).toBe(1);
  });

  it("keeps sessions linked to production_standard strategies indefinitely", () => {
    insertStrategy(db, "sp1", "production_standard");
    insertSession(db, "old-prod-std", { status: "completed", daysAgo: 500, strategyId: "sp1" });
    expect(runCleanup(db, 90)).toBe(0);
  });

  it("keeps sessions linked to production_aggressive strategies indefinitely", () => {
    insertStrategy(db, "sp2", "production_aggressive");
    insertSession(db, "old-prod-agg", { status: "completed", daysAgo: 500, strategyId: "sp2" });
    expect(runCleanup(db, 90)).toBe(0);
  });

  it("removes old sessions linked to a non-validated strategy", () => {
    insertStrategy(db, "so1", "optimizing");
    insertSession(db, "old-optim", { status: "completed", daysAgo: 100, strategyId: "so1" });
    expect(runCleanup(db, 90)).toBe(1);
    expect(countSessions(db)).toBe(0);
  });

  it("cascade-deletes backtest_results when session is removed", () => {
    insertSession(db, "sess-cascade", { status: "completed", daysAgo: 100 });
    db.prepare(`
      INSERT INTO backtest_results
        (id, session_id, instrument, timeframe, params_json, metrics_json, created_at)
      VALUES (?, ?, 'EURUSD', 'H1', '{}', '{}', ?)
    `).run("res-1", "sess-cascade", new Date().toISOString());
    expect(countResults(db)).toBe(1);
    runCleanup(db, 90);
    expect(countResults(db)).toBe(0);
    expect(countSessions(db)).toBe(0);
  });

  it("respects custom retainDays — only removes older entries", () => {
    insertSession(db, "sess-30d", { status: "completed", daysAgo: 30 });
    insertSession(db, "sess-10d", { status: "completed", daysAgo: 10 });
    expect(runCleanup(db, 20)).toBe(1); // only sess-30d removed
    expect(countSessions(db)).toBe(1);  // sess-10d survives
  });

  it("removes nothing when all sessions belong to validated strategies", () => {
    insertStrategy(db, "sv2", "validated");
    insertSession(db, "s-a", { daysAgo: 200, strategyId: "sv2" });
    insertSession(db, "s-b", { daysAgo: 400, strategyId: "sv2" });
    expect(runCleanup(db, 90)).toBe(0);
    expect(countSessions(db)).toBe(2);
  });
});
