# Algo Farm — Backlog

Progress tracker for all phases and milestones. Updated at the end of each development iteration.

---

## Phase 1 — Standalone Python CLI Engine ✅ DONE

> Standalone backtest and grid-search optimisation engine. No Node.js, Redis, or Docker required.
> Designed for AI agent feedback loops and headless CLI use.

### M1 — Scaffold & Tooling ✅
- [x] `engine/` directory structure created
- [x] `pyproject.toml` with mypy strict + pytest config
- [x] `requirements.txt` (backtesting.py, pandas, pydantic, numpy, scipy, pytest, mypy, black)
- [x] All `__init__.py` stubs in place
- [x] `.gitignore` for venv, pycache, .coverage, .db files
- [x] `pytest --collect-only` runs without errors

### M2 — Pydantic Models, Metrics, Indicators ✅
- [x] `src/models.py` — `StrategyDefinition`, `IndicatorDef`, `RuleDef`, `PositionManagement`, `BacktestMetrics`
- [x] `src/metrics.py` — `calculate_metrics()`: all 11 metrics (Sharpe, Sortino, Calmar, CAGR, max drawdown, win rate, profit factor, total trades, avg duration, expectancy, total return)
- [x] `src/backtest/indicators/trend.py` — `sma`, `ema`, `macd`
- [x] `src/backtest/indicators/momentum.py` — `rsi`, `stoch`, `cci`, `williamsr`, `obv`
- [x] `src/backtest/indicators/volatility.py` — `atr`, `bollinger_bands`, `adx`
- [x] `src/backtest/indicators/__init__.py` — `IndicatorRegistry` with `register()` / `get()` / `list_all()`
- [x] `tests/unit/test_metrics.py` — 10 tests, deterministic inputs → known outputs
- [x] `tests/unit/test_indicators.py` — 18 tests, range checks and registry completeness

### M3 — Fixture Generator & SQLite Storage ✅
- [x] `tests/fixtures/generate_fixtures.py` — 500-bar synthetic OHLCV (sine + trend + noise)
- [x] `tests/fixtures/data_cache/EURUSD/H1.parquet` — committed to git (< 100 KB)
- [x] `tests/fixtures/data_cache/EURUSD/D1.parquet` — committed to git (< 100 KB)
- [x] `tests/fixtures/simple_sma_strategy.json`
- [x] `tests/fixtures/simple_param_grid.json`
- [x] `src/utils.py` — `setup_logging()` (stderr only, force reconfigure), `load_ohlcv()`
- [x] `src/storage/db.py` — `init_db()`, `JobRepo`, `RunRepo`, `ErrorLogRepo`
- [x] Resume signature: `instrument|timeframe|params_json` (sort_keys=True)
- [x] `tests/unit/test_storage.py` — 7 tests on in-memory SQLite
- [x] `tests/unit/test_utils.py` — 5 tests (logging, load_ohlcv success/failure)

### M4 — BacktestRunner & StrategyComposer ✅
- [x] `src/backtest/strategy.py` — `StrategyComposer.build_class()`: generates `backtesting.py` Strategy subclass at runtime
- [x] `src/backtest/runner.py` — `BacktestRunner.run()` → `RunResult(metrics, trades, equity_curve)`
- [x] Trade extraction from `stats._trades` (entry/exit bar, duration, pnl, return_pct)
- [x] `tests/integration/test_backtest_runner.py` — 3 tests on synthetic fixture data

### M5 — GridSearchOptimizer & CLI Entry Point ✅
- [x] `src/optimization/grid_search.py` — `GridSearchOptimizer`: `build_combinations()` + `run()` with `on_progress` / `on_result` callbacks
- [x] `engine/run.py` — full CLI orchestrator: argparse, SIGINT handler, resume logic, `emit()` for JSONL stdout
- [x] JSONL output: `progress`, `result`, `completed`, `interrupted` message types
- [x] Exit codes: 0 = success, 1 = error, 2 = interrupted
- [x] `tests/unit/test_grid_search.py` — 6 tests (combinations, full run with mock)
- [x] `tests/cli/test_cli_contract.py` — 6 tests (exit codes, JSONL validity, resume)

### M6 — Error Handling, Resume, Final Polish ✅
- [x] `ErrorLogRepo.log()` called on all backtest and data-loading failures
- [x] SIGINT → job status set to `interrupted`, exit 2
- [x] `--resume-job` end-to-end: loads completed signatures, skips them in sweep
- [x] `logging.basicConfig(force=True)` prevents stale log handler issues
- [x] `engine/README.md` — onboarding, CLI reference, JSONL spec, metrics table (English)
- [x] **55 tests passing, 92% coverage**

---

## Phase 2 — Strategy Wizard (LLM + React) ⬜ TODO

> User describes a trading idea in natural language → receives a validated `StrategyDefinition` JSON.

### Open questions (must resolve before starting)
- [ ] LLM provider: Claude API or OpenAI? (cost, latency, tool-use capabilities)
- [ ] Auth strategy for the API: API key or none (local-only)?

### Planned milestones
- [ ] M1 — Zod schema generated from `StrategyDefinition` v1 JSON Schema
- [ ] M2 — Node.js Wizard Service: LLM prompt + output validation
- [ ] M3 — React Wizard UI: chat interface, Basic/Advanced toggle, JSON preview
- [ ] M4 — Strategy persisted to SQLite `strategies` table
- [ ] M5 — Error handling: invalid LLM output → user-facing message
- [ ] M6 — E2E test (Playwright): describe idea → submit → confirm in vault

---

## Phase 3 — Node.js API + BullMQ + Dashboard ⬜ TODO

> Wrap the Phase 1 engine behind Node.js API and BullMQ; add React results dashboard.

### Planned milestones
- [ ] M1 — Express API scaffold: TypeScript strict, ESLint, better-sqlite3
- [ ] M2 — BullMQ producer + Python subprocess worker (reads Phase 1 stdout)
- [ ] M3 — WebSocket relay: stdout progress events → React clients
- [ ] M4 — Bayesian optimisation (optuna) added to engine
- [ ] M5 — React Dashboard: equity curve, drawdown, heatmap, live progress
- [ ] M6 — Integration test: job submit via API → completion → results in SQLite

---

## Phase 4 — Robustness Validation Suite ⬜ TODO

- [ ] M1 — Walk-forward analysis
- [ ] M2 — Monte Carlo simulation
- [ ] M3 — Out-of-sample test
- [ ] M4 — Parameter sensitivity
- [ ] M5 — Trade shuffle / permutation test
- [ ] M6 — Composite go/no-go score + report schema
- [ ] M7 — React report display

---

## Phase 5 — Strategy Vault ⬜ TODO

- [ ] M1 — SQLite schema: strategies, parameter_sets, tags, journal_entries, audit_log
- [ ] M2 — Strategy CRUD endpoints
- [ ] M3 — Parameter sets per regime (bull / bear / sideways / default)
- [ ] M4 — Journal CRUD
- [ ] M5 — Status lifecycle: draft → tested → validated → production → archived
- [ ] M6 — React Vault UI: list, detail, filters, journal, parameter editor

---

## Phase 6 — Export Engine ⬜ TODO

- [ ] M1 — `ExportAdapter` interface (format-agnostic)
- [ ] M2 — cTrader C# template + parameter injection
- [ ] M3 — Pine Script v5 template + parameter injection
- [ ] M4 — React Export UI: format selector, parameter mapper, code preview + download
- [ ] M5 — Unit tests: parameter injection into templates
- [ ] M6 — Integration test: export → validate generated code syntax
