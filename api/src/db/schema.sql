CREATE TABLE IF NOT EXISTS strategies (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  variant TEXT NOT NULL,
  definition_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS error_log (
  id TEXT PRIMARY KEY,
  context TEXT,
  error_type TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL
);
