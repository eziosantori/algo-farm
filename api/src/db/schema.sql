CREATE TABLE IF NOT EXISTS strategies (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  variant TEXT NOT NULL,
  definition_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  lifecycle_status TEXT NOT NULL DEFAULT 'draft'
);

CREATE TABLE IF NOT EXISTS error_log (
  id TEXT PRIMARY KEY,
  context TEXT,
  error_type TEXT NOT NULL,
  message TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lab_sessions (
  id TEXT PRIMARY KEY,
  strategy_name TEXT NOT NULL,
  strategy_json TEXT NOT NULL,
  instruments TEXT NOT NULL,
  timeframes TEXT NOT NULL,
  constraints TEXT,
  status TEXT NOT NULL DEFAULT 'running',
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  strategy_id TEXT REFERENCES strategies(id) ON DELETE SET NULL,
  -- IS/OOS date window for this session (NULL = full data range used)
  is_start TEXT,
  is_end TEXT
);

CREATE TABLE IF NOT EXISTS backtest_results (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL REFERENCES lab_sessions(id) ON DELETE CASCADE,
  instrument TEXT NOT NULL,
  timeframe TEXT NOT NULL,
  params_json TEXT NOT NULL,
  metrics_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  created_at TEXT NOT NULL,
  -- 'is' = in-sample, 'oos' = out-of-sample, 'full' = no split applied
  split TEXT NOT NULL DEFAULT 'full'
);
