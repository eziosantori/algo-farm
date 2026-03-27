import Database from "better-sqlite3";
import { readFileSync } from "fs";
import { join, dirname } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));

let _db: Database.Database | null = null;

export function getDb(): Database.Database {
  if (!_db) {
    throw new Error("Database not initialized. Call initDb() first.");
  }
  return _db;
}

export function initDb(dbPath: string): Database.Database {
  _db = new Database(dbPath);
  _db.pragma("journal_mode = WAL");
  _db.pragma("foreign_keys = ON");

  const schema = readFileSync(join(__dirname, "schema.sql"), "utf-8");
  _db.exec(schema);

  // Idempotent migrations for existing databases
  const migrations = [
    `ALTER TABLE strategies ADD COLUMN lifecycle_status TEXT NOT NULL DEFAULT 'draft'`,
    `ALTER TABLE lab_sessions ADD COLUMN strategy_id TEXT REFERENCES strategies(id) ON DELETE SET NULL`,
    `ALTER TABLE lab_sessions ADD COLUMN is_start TEXT`,
    `ALTER TABLE lab_sessions ADD COLUMN is_end TEXT`,
    `ALTER TABLE backtest_results ADD COLUMN split TEXT NOT NULL DEFAULT 'full'`,
    `ALTER TABLE lab_sessions ADD COLUMN research_notes TEXT`,
    `ALTER TABLE strategies ADD COLUMN export_dir TEXT`,
  ];
  for (const sql of migrations) {
    try { _db.exec(sql); } catch { /* column already exists */ }
  }

  return _db;
}

/**
 * Delete stale lab sessions to prevent unbounded DB growth.
 *
 * Retention rules (both applied at startup):
 *  - failed sessions older than 14 days → always deleted
 *  - any session older than retainDays that is NOT linked to a
 *    validated / production strategy → deleted
 *
 * Sessions belonging to validated/production strategies are kept forever.
 * backtest_results rows are removed via CASCADE.
 *
 * @param retainDays - controlled by CLEANUP_RETAIN_DAYS env var (default 90)
 */
export function runCleanup(db: Database.Database, retainDays: number = 90): number {
  const result = db.prepare(`
    DELETE FROM lab_sessions
    WHERE
      (status = 'failed' AND created_at < datetime('now', '-14 days'))
      OR (
        created_at < datetime('now', '-' || ? || ' days')
        AND (
          strategy_id IS NULL
          OR strategy_id NOT IN (
            SELECT id FROM strategies
            WHERE lifecycle_status IN (
              'validated',
              'production_standard',
              'production_aggressive',
              'production_defensive'
            )
          )
        )
      )
  `).run(retainDays);
  return result.changes;
}

export function closeDb(): void {
  if (_db) {
    _db.close();
    _db = null;
  }
}
