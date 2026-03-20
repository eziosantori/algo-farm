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
  ];
  for (const sql of migrations) {
    try { _db.exec(sql); } catch { /* column already exists */ }
  }

  return _db;
}

export function closeDb(): void {
  if (_db) {
    _db.close();
    _db = null;
  }
}
