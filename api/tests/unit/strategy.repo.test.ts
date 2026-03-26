import { describe, it, expect, beforeEach, afterEach } from "vitest";
import Database from "better-sqlite3";
import { readFileSync } from "fs";
import { join } from "path";
import { StrategyRepository } from "../../src/db/repositories/strategy.repo.js";
import type { StrategyDefinition } from "@algo-farm/shared/strategy";

function createInMemoryDb(): Database.Database {
  const db = new Database(":memory:");
  db.pragma("foreign_keys = ON");
  const schema = readFileSync(join(__dirname, "../../src/db/schema.sql"), "utf-8");
  db.exec(schema);
  return db;
}

const sampleStrategy: StrategyDefinition = {
  version: "1.0",
  name: "Test RSI Strategy",
  variant: "basic",
  indicators: [{ name: "rsi14", type: "rsi", params: { period: 14 } }],
  entry_rules: [{ indicator: "rsi14", condition: "<", value: 30 }],
  exit_rules: [{ indicator: "rsi14", condition: ">", value: 70 }],
  position_management: {
    size: 0.02,
    sl_pips: 20,
    tp_pips: 40,
    max_open_trades: 1,
    trailing_sl_atr_mult: 2.0,
  },
  entry_rules_short: [],
  exit_rules_short: [],
  signal_gates: [],
  pattern_groups: [],
  suppression_gates: [],
  trigger_holds: [],
  param_overrides: {},
};

describe("StrategyRepository", () => {
  let db: Database.Database;
  let repo: StrategyRepository;

  beforeEach(() => {
    db = createInMemoryDb();
    repo = new StrategyRepository(db);
  });

  afterEach(() => {
    db.close();
  });

  it("creates a strategy and returns id + created_at", () => {
    const result = repo.create(sampleStrategy);
    expect(result.id).toBeTruthy();
    expect(result.created_at).toBeTruthy();
  });

  it("lists strategies in descending order (latest first)", () => {
    repo.create(sampleStrategy);
    repo.create({ ...sampleStrategy, name: "Second Strategy" });
    const list = repo.list();
    expect(list).toHaveLength(2);
    // Second insert appears first (rowid DESC as tiebreaker for same-ms timestamps)
    const names = list.map((s) => s.name);
    expect(names).toContain("Second Strategy");
    expect(names).toContain("Test RSI Strategy");
    expect(names.indexOf("Second Strategy")).toBeLessThan(names.indexOf("Test RSI Strategy"));
  });

  it("gets a strategy by id", () => {
    const { id } = repo.create(sampleStrategy);
    const record = repo.get(id);
    expect(record).not.toBeNull();
    expect(record?.definition.name).toBe("Test RSI Strategy");
    expect(record?.definition.indicators[0].type).toBe("rsi");
  });

  it("returns null for non-existent id", () => {
    const record = repo.get("non-existent-id");
    expect(record).toBeNull();
  });

  it("updates a strategy", () => {
    const { id } = repo.create(sampleStrategy);
    const updated = repo.update(id, { ...sampleStrategy, name: "Updated Strategy" });
    expect(updated).toBe(true);
    const record = repo.get(id);
    expect(record?.definition.name).toBe("Updated Strategy");
  });

  it("returns false when updating non-existent strategy", () => {
    const updated = repo.update("non-existent", sampleStrategy);
    expect(updated).toBe(false);
  });

  it("deletes a strategy", () => {
    const { id } = repo.create(sampleStrategy);
    const deleted = repo.delete(id);
    expect(deleted).toBe(true);
    expect(repo.get(id)).toBeNull();
  });

  it("returns false when deleting non-existent strategy", () => {
    const deleted = repo.delete("non-existent");
    expect(deleted).toBe(false);
  });

  it("list returns only summary fields", () => {
    repo.create(sampleStrategy);
    const list = repo.list();
    expect(list[0]).toHaveProperty("id");
    expect(list[0]).toHaveProperty("name");
    expect(list[0]).toHaveProperty("variant");
    expect(list[0]).toHaveProperty("created_at");
    expect(list[0]).not.toHaveProperty("definition_json");
  });
});
