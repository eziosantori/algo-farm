import { randomUUID } from "crypto";
import type Database from "better-sqlite3";
import { StrategyDefinition } from "@algo-farm/shared/strategy";

export interface StrategyRow {
  id: string;
  name: string;
  variant: string;
  definition_json: string;
  created_at: string;
  updated_at: string;
}

export interface StrategySummary {
  id: string;
  name: string;
  variant: string;
  created_at: string;
}

export interface StrategyRecord {
  id: string;
  definition: StrategyDefinition;
  created_at: string;
  updated_at: string;
}

export class StrategyRepository {
  constructor(private readonly db: Database.Database) {}

  create(definition: StrategyDefinition): { id: string; created_at: string } {
    const id = randomUUID();
    const now = new Date().toISOString();

    this.db
      .prepare(
        `INSERT INTO strategies (id, name, variant, definition_json, created_at, updated_at)
         VALUES (?, ?, ?, ?, ?, ?)`
      )
      .run(id, definition.name, definition.variant, JSON.stringify(definition), now, now);

    return { id, created_at: now };
  }

  list(): StrategySummary[] {
    const rows = this.db
      .prepare(
        `SELECT id, name, variant, created_at FROM strategies ORDER BY created_at DESC, rowid DESC`
      )
      .all() as StrategySummary[];

    return rows;
  }

  get(id: string): StrategyRecord | null {
    const row = this.db
      .prepare(`SELECT * FROM strategies WHERE id = ?`)
      .get(id) as StrategyRow | undefined;

    if (!row) return null;

    return {
      id: row.id,
      definition: JSON.parse(row.definition_json) as StrategyDefinition,
      created_at: row.created_at,
      updated_at: row.updated_at,
    };
  }

  update(id: string, definition: StrategyDefinition): boolean {
    const now = new Date().toISOString();

    const result = this.db
      .prepare(
        `UPDATE strategies SET name = ?, variant = ?, definition_json = ?, updated_at = ?
         WHERE id = ?`
      )
      .run(definition.name, definition.variant, JSON.stringify(definition), now, id);

    return result.changes > 0;
  }

  delete(id: string): boolean {
    const result = this.db
      .prepare(`DELETE FROM strategies WHERE id = ?`)
      .run(id);

    return result.changes > 0;
  }
}
