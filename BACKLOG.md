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
- ~~**ATR/ADX use only Close**~~: **Fixed in M8.** `StrategyComposer` now passes real `data.High`
  and `data.Low` to any indicator whose signature declares those parameters.
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

### M8 — SuperTrend Indicator ✅
> Required to replicate trend-following strategies with dynamic trailing SL (e.g. cTrader Bot2).

- [x] Implement `supertrend` + `supertrend_direction` in `engine/src/backtest/indicators/trend.py`
  - Formula: ATR-based bands (`(H+L)/2 ± mult×ATR`) with bar-by-bar flip logic
  - `supertrend`: returns the active ST line value per bar
  - `supertrend_direction`: returns `+1.0` (uptrend) / `-1.0` (downtrend) per bar
  - Params: `period` (default 10), `multiplier` (default 3.0); fallback to Close when H/L absent
- [x] Both registered in `IndicatorRegistry` (`"supertrend"`, `"supertrend_direction"`)
- [x] Added to `IndicatorDef.type` Literal in `models.py` and `IndicatorTypeSchema` in `shared/src/strategy.ts`
- [x] `StrategyComposer` now passes real `data.High` / `data.Low` to any indicator declaring those params
  (also fixes the known ATR/ADX close-only limitation — resolved here)
- [x] 6 new tests in `tests/unit/test_indicators.py`: length, warmup, direction values, flip, registry (×2)
- [x] Fixture: `tests/fixtures/supertrend_rsi_strategy.json` — SuperTrend direction + RSI entry/exit
- [x] **61/61 tests passing, 92% coverage** — end-to-end smoke test clean

### M10 — Dukascopy Data Downloader ✅
> Real multi-asset OHLCV data via Dukascopy free feed, cached as Parquet.

- [x] `engine/src/data/__init__.py` + `engine/src/data/instruments.py` — 17-instrument catalog
  (Forex majors + crosses, Gold, Silver, Brent, WTI, Natural Gas) with timeframe mapping
- [x] `engine/src/data/downloader.py` — `DukascopyDownloader`: `download()` (incremental cache),
  `download_many()` (bulk with progress callback); Parquet format compatible with existing engine
- [x] `engine/download.py` — CLI: `--instruments`, `--timeframes`, `--from`, `--to`, `--data-dir`,
  `--force`, `--list-instruments`; summary table on completion
- [x] Uses `npx dukascopy-node` subprocess (mirrors cbot-farm) — supports ALL asset classes
- [x] **34 instruments**: forex majors/crosses, Gold, Silver, Brent, WTI, NatGas, Copper + 6 equity indices + 10 NASDAQ stocks (AAPL, MSFT, NVDA, AMZN, TSLA, META, GOOGL, NFLX, AMD, QCOM)
- [x] Equity indices confirmed working: US500 (S&P 500), GER40 (DAX), NAS100, UK100, JPN225, AUS200
- [x] **61/61 tests passing** — end-to-end confirmed: download → backtest on 3 instruments × 2 timeframes

**Supported timeframes:** M1, M5, M10, M15, M30, H1, H4, D1, W1
**Prerequisites:** Node.js / npx in PATH (dukascopy-node pulled automatically via npx)

### M11 — Strategy Lab (Multi-asset × Multi-timeframe UI + Skill) ✅
> Enables running a strategy across multiple assets and timeframes, storing results in the Lab,
> reviewing them in the UI, and promoting the best configurations to production.

- [x] `api/src/db/schema.sql` — two new tables: `lab_sessions` (session metadata + constraints) and
  `backtest_results` (per-combination metrics, FK cascade on session delete)
- [x] `api/src/db/repositories/lab.repo.ts` — `LabRepository`: `createSession`, `listSessions`
  (with aggregated counts), `getSession` (results sorted by Sharpe via `json_extract`),
  `updateSessionStatus`, `addResult`, `updateResultStatus`
- [x] `api/src/routes/lab.ts` — 6 endpoints with Zod validation:
  `POST /lab/sessions`, `GET /lab/sessions`, `GET /lab/sessions/:id`,
  `PATCH /lab/sessions/:id/status`, `POST /lab/sessions/:id/results`, `PATCH /lab/results/:id/status`
- [x] `api/src/server.ts` — registered `labRouter`
- [x] `api/tests/unit/lab.repo.test.ts` — 13 unit tests on in-memory SQLite
- [x] `api/tests/integration/lab.routes.test.ts` — 13 integration tests (supertest)
- [x] **50/50 API tests passing**
- [x] `ui/src/api/client.ts` — added Lab types and `listLabSessions`, `getLabSession`, `updateLabResultStatus`
- [x] `ui/src/components/Lab/LabPage.tsx` — sessions list with inline result expansion;
  result table sorted by Sharpe with params column; per-result status actions (validate/reject/promote);
  `StrategyExplainer` component (indicators, entry/exit rules, position management) parsed from `strategy_json`
- [x] `ui/src/App.tsx` — added `/lab` route and "Lab" nav link
- [x] `.claude/commands/strategy-lab.md` — `/strategy-lab` skill: autonomous improvement loop —
  baseline run → LLM diagnoses weaknesses → proposes structural changes (indicators/filters/rules) →
  tests all instrument × timeframe combos → keeps improvements (+2% threshold) → stores all in Lab →
  human validation only at the end
- [x] Engine: `runner.py` auto-scales `initial_cash` based on instrument price (fixes 0-trade bug on BTCUSD/gold)
- [x] Engine: `downloader.py` saves timezone-naive DatetimeIndex (fixes backtesting.py compatibility)
- [x] Instruments: added 33 crypto pairs (BTCUSD, ETHUSD, LTCUSD, ADAUSD, XLMUSD …)

**Result status lifecycle:** `pending → validated | rejected | production_standard | production_aggressive | production_defensive`

**Known gaps / next steps for Lab:**
- `/strategy-lab` runs single-param simulations only; grid search per (instrument × timeframe) not yet integrated
  → M12: add `--param-grid` to `/strategy-lab`, store `best_params` per result combination
- Long-only strategy; short selling requires bi-directional `entry_rules_long`/`entry_rules_short` schema
  → documented in "Additional Notes" section below
- No multi-timeframe filter (e.g. enter H1 only when D1 SuperTrend is also up); requires engine changes

### M11d — Lab ↔ Strategy Integration ✅
- `lab_sessions.strategy_id` FK → `strategies.id` (ON DELETE SET NULL)
- `strategies.lifecycle_status`: draft|optimizing|validated|production_standard|production_aggressive|production_defensive
- Promoting a Lab result propagates `lifecycle_status` to the linked strategy (atomic transaction)
- StrategiesPage: "Run in Lab" inline form; `lifecycle_status` badge per row
- LabPage: "🔗 Linked to strategy" tag on sessions with FK set

### M9 — Advanced Position Management ⬜ TODO
> Enables replicating exit logic typical of trend-following strategies (trailing SL, scale-out, time exit).
> Extends `PositionManagement` and `StrategyComposer` without breaking existing strategies.

- [ ] **ATR-based SL** — add `sl_atr_mult: float | null` to `PositionManagement`: SL computed as
  `entry_price ± ATR(14) × sl_atr_mult` at trade open (alternative to fixed `sl_pips`)
- [ ] **Trailing SL** — add `trailing_sl: "atr" | "supertrend" | null` to `PositionManagement`:
  - `"atr"`: move SL each bar to `price ± ATR × mult` (only in the favourable direction)
  - `"supertrend"`: SL tracks the active ST line (requires M8)
- [ ] **Scale-out** — add `scale_out: { trigger_r: float, volume_pct: int } | null`:
  - Partial close of `volume_pct`% when profit ≥ `trigger_r × initial SL distance`
  - After scale-out: move remaining SL to breakeven
- [ ] **Time-based exit** — add `time_exit_bars: int | null`: close if P/L ≤ 0 after N bars
- [ ] Update Zod schema in `shared/src/strategy.ts` with all new fields (all optional/nullable)
- [ ] Update `StrategyComposer.next()`: track open-position state (bars elapsed, current SL, scaled flag)
- [ ] Integration test with a fixture that exercises trailing SL, scale-out, and time exit
- [ ] Backward compatibility: existing strategies without the new fields continue to work unchanged

### M7 — Claude Code Team: Strategy Development Team ⬜ PLANNED
> Evolution of Phase 2 skills (single-agent slash commands) into a multi-agent team
> with specialised roles. Activated once Phase 3 introduces async jobs and real data.

**Implementation trigger:** Phase 3 operational (BullMQ + real data available).

**Team structure:**
```
Team "strategy-dev"
├── strategist   — generates/modifies strategies, decides changes based on results
├── backtester   — runs engine/run.py, reads JSONL, reports structured metrics
├── analyst      — interprets result patterns, proposes param grids, identifies regime
└── validator    — (active from Phase 4) robustness suite: walk-forward, Monte Carlo, OOS
```

**Team workflow (replaces single-agent `/iterate`):**
1. `strategist` receives objective (e.g. "optimise for Sharpe > 1.5 on EURUSD H1")
2. `strategist` writes/modifies `draft/<name>.json` and assigns task to `backtester`
3. `backtester` launches subprocess, streams JSONL, saves metrics, notifies `analyst`
4. `analyst` reads metrics, identifies bottleneck, proposes change → notifies `strategist`
5. Loop until target reached or N iterations exhausted
6. `validator` (Phase 4+) runs robustness check before promoting to `validated/`

**Parallelism:** multiple `backtester` agents can be spawned to test different instruments/timeframes
concurrently, reducing the optimisation loop time.

**Existing skills as subagent prompts:**
- `/backtest`      → `backtester` role prompt
- `/optimize`      → coordinates `backtester` + `analyst`
- `/iterate`       → coordinates the full team
- `/new-strategy`  → stays single-agent (short task, no team needed)

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

---

## Additional Notes — Engine features (future, unplanned)

> Gaps identified during analysis of the cTrader strategy `superTrendRsi.cs` (Bot2 v0.9.3).
> Not in the current plan; to be reassessed before Phase 4/5.

- **Short selling**: `StrategyComposer` only calls `self_bt.buy()`. Bi-directional strategies
  require adding `self_bt.sell()` and separate `entry_rules_long` / `entry_rules_short` in the
  JSON schema.
- **Indicator flip detection** (e.g. SuperTrend direction change): the rule engine evaluates only
  the current value of an indicator, not its previous-bar value. Conditions like "was in downtrend,
  now in uptrend" require a cross-bar state mechanism (e.g. `previous_value` in the rule schema
  or a derived `supertrend_direction` indicator).
- **Risk-% position sizing**: currently `size` is a fixed fraction of equity. The cTrader strategy
  uses `risk% × account / (sl_pips × pip_value)`. Requires access to current account balance
  inside `StrategyComposer`.
- **Normalised BB Width**: `bollinger_bands` returns the absolute width `(upper−lower)`. The
  cTrader strategy uses `(upper−lower) / mid × 100`. Can be addressed with a `normalized: bool`
  param or a dedicated `bollinger_bands_pct` indicator.
- **Cooldown logic**: pauses trading after N consecutive losses. Requires global state outside the
  single position context; not expressible in the current rule engine.
- **Trading hours filter**: excludes bars outside a time window. Requires access to the bar
  timestamp inside `next()`.
- **Named param namespacing**: (already in Phase 1 Known Limitations) shared `"period"` key
  applies to all indicators in the param grid — causes collisions in multi-indicator optimisations.
