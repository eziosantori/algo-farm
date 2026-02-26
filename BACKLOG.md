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

### M7 — Bug fix: indicator-to-indicator comparisons ✅
Discovered during first-agent onboarding test (trend-following strategy simulation):
- [x] **Bug fixed**: `_check_condition()` in `strategy.py` evaluated `>`, `<`, `>=`, `<=` only against
  numeric `value`; when `compare_to` was set (indicator-vs-indicator), it always returned `False` silently.
  Fix: resolve `compare_to` to the other indicator's current value before comparison.
- [x] `tests/fixtures/sma_trend_bounce_strategy.json` — 3-SMA trend bounce fixture (verified working)
- [x] `tests/fixtures/sma_trend_bounce_grid.json` — reference param grid
- [x] **55/55 tests still passing** after fix

### Known limitations (to address in future milestones)
- **Param grid key collision**: when multiple indicators share the same param key (e.g. `"period"`),
  the grid applies the same swept value to ALL of them. Multi-indicator strategies with different
  periods must be iterated manually (agent feedback loop) rather than via `--param-grid`.
  → To fix in Phase 3: named param namespacing (e.g. `"fast_sma.period"`, `"slow_sma.period"`).
- **ATR/ADX use only Close**: `StrategyComposer` passes only `data.Close` to all indicators via
  `self_bt.I(fn, data.Close, ...)`. ATR and ADX accept optional `high`/`low` but receive `close`
  for all three, reducing accuracy. Real H/L data is available in the Parquet files.
  → To fix in Phase 3: pass `data.High`, `data.Low` to indicators that declare those parameters.
- **No automated feedback loop**: the agent iteration loop described in `AGENTS.md` is manual
  at Phase 1 (read JSONL → edit JSON → re-run). The automated loop (BullMQ + WebSocket + LLM
  refinement) is Phase 3 scope.
- **Fixture data is synthetic**: 500 bars of random-walk OHLCV (2020-01-01 to 2020-01-21 H1).
  Trend/crossover alignment differs from real market data; strategies validated here need
  re-testing on real data before use.

---

## Phase 2 — Strategy Wizard (LLM + React) ✅ DONE

> User describes a trading idea in natural language → receives a validated `StrategyDefinition` JSON.
> Stack: Node.js/Express API + Claude `tool_use` + React/Vite UI. pnpm monorepo.

### M1 — Node.js API scaffold ✅
- [x] `api/package.json` + `tsconfig.json` (ESNext + bundler moduleResolution)
- [x] `api/src/server.ts` — Express app + CORS + JSON middleware
- [x] `api/src/db/client.ts` — better-sqlite3 connection + WAL mode + `init_db()`
- [x] `api/src/db/schema.sql` — DDL: `strategies`, `error_log` tables
- [x] `GET /health` → `{"status":"ok"}`
- [x] `pnpm-workspace.yaml` + root `package.json` for monorepo
- [x] `pnpm.onlyBuiltDependencies` for native binaries (better-sqlite3, esbuild)

### M2 — Shared Zod schema + Strategy CRUD ✅
- [x] `shared/src/strategy.ts` — Zod schema mirroring Phase 1 Pydantic models exactly
- [x] `@algo-farm/shared` workspace package with exports
- [x] `api/src/db/repositories/strategy.repo.ts` — `StrategyRepository` CRUD (create/list/get/update/delete)
- [x] `api/src/middleware/validate.ts` — `validateBody()` Zod middleware factory
- [x] `api/src/routes/strategies.ts` — POST/GET/GET:id/PUT/DELETE routes
- [x] `api/vitest.config.ts` — alias for `@algo-farm/shared`
- [x] `api/tests/unit/strategy.repo.test.ts` — 9 tests on in-memory SQLite
- [x] `api/tests/integration/strategies.routes.test.ts` — 9 integration tests (supertest)

### M3 — Claude Wizard Service ✅
- [x] `api/src/services/wizard.service.ts` — `WizardService.chat()` with `tool_use` forcing structured output
- [x] Retry once on Zod validation failure with error feedback to Claude
- [x] `api/src/routes/wizard.ts` — `POST /wizard/chat`
- [x] `api/.env.example` — `ANTHROPIC_API_KEY`, `PORT`, `DB_PATH`
- [x] `api/tests/unit/wizard.service.test.ts` — 3 tests (success, retry, no-tool-use error)
- [x] **21/21 tests passing**

### M3b — Multi-provider LLM support ✅
- [x] Provider abstraction: `api/src/services/providers/base.ts` — `LLMProvider` interface, `SYSTEM_PROMPT`, `STRATEGY_TOOL_SCHEMA`, `validateWithRetry()`
- [x] `api/src/services/providers/claude.provider.ts` — extracted from wizard.service, zero logic changes
- [x] `api/src/services/providers/gemini.provider.ts` — `@google/generative-ai`, `FunctionCallingMode.ANY`; schema sanitized for Gemini (`$ref` inline, `additionalProperties`/array types stripped); model configurable via `GEMINI_MODEL` (default: `gemini-2.0-flash-lite`)
- [x] `api/src/services/providers/openrouter.provider.ts` — `openai` SDK + baseURL override; model configurable via `OPENROUTER_MODEL` (default: `upstage/solar-pro-3:free`, verified tool-calling support)
- [x] `wizard.service.ts` rewritten as factory delegating to provider by ID
- [x] `POST /wizard/chat` accepts `provider: "claude"|"gemini"|"openrouter"` (default: `"gemini"`)
- [x] `api/.env.example` — added `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`
- [x] `api/package.json` — added `@google/generative-ai`, `openai`
- [x] `ui/src/store/wizard.ts` — `provider` state + `setProvider()`
- [x] `ui/src/api/client.ts` — `wizardChat(message, provider)` passes provider in body
- [x] `ui/src/components/Wizard/WizardPage.tsx` — dropdown "Provider: Gemini | Claude | Qwen/OpenRouter"
- [x] **24/24 tests passing**, zero TypeScript errors (API + UI)

### M4 — React UI (Wizard + Strategy List) ✅
- [x] `ui/` scaffold: `package.json`, `tsconfig.json`, `vite.config.ts`, `index.html`
- [x] `ui/src/main.tsx` + `App.tsx` — React Router: `/wizard` | `/strategies`
- [x] `ui/src/api/client.ts` — typed fetch wrapper (proxied via `/api`)
- [x] `ui/src/store/wizard.ts` — Zustand store: messages, currentStrategy, isLoading
- [x] `ui/src/components/Wizard/WizardPage.tsx` — chat UI + loading state + save button
- [x] `ui/src/components/Wizard/StrategyPreview.tsx` — field summary + JSON preview
- [x] `ui/src/components/Strategies/StrategiesPage.tsx` — table with inline JSON expand
- [x] Vite dev proxy: `/api` → `http://localhost:3001`

### M5 — Docs ✅
- [x] `api/README.md` — setup, env vars, endpoints reference
- [x] `ui/README.md` — setup, proxy note, pages reference
- [x] `BACKLOG.md` updated

### M6b — Claude Code Skills ✅
Strategy lifecycle folder structure and Claude Code slash commands for the core workflow:
- [x] `engine/strategies/{draft,optimizing,validated,production}/` — lifecycle folders (allineate a Phase 5 Strategy Vault)
- [x] `.claude/commands/new-strategy.md` — `/new-strategy <description>`: genera strategy.json valido e salva in `draft/`
- [x] `.claude/commands/backtest.md` — `/backtest <file> [--instruments] [--timeframes]`: lancia motore e mostra tabella metriche
- [x] `.claude/commands/optimize.md` — `/optimize <file> [--metric]`: grid search con tabella risultati ordinata
- [x] `.claude/commands/iterate.md` — `/iterate <file> [--target] [--iterations]`: loop autonomo backtest → analisi → modifica
- [x] `.claude/settings.local.json` — permessi Bash per `python engine/run.py`

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
