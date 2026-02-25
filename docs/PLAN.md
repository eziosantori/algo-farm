# PLAN.md — Roadmap & Milestones

## Executive Summary

This document outlines the 6-phase roadmap for the **Algo Trading Strategy Development Platform**. Each phase delivers a working, production-ready increment without dead-end stubs. The architecture emphasizes **autonomous long-running jobs**, **clean layer boundaries** (Python compute, Node.js orchestration, React UI), and **incremental validation** (backtest → robust validation → strategy vault → export).

**Phase 1 is a standalone Python CLI engine** — no Node.js, no Redis, no UI. It is the foundation of the system and the first thing to build. It is designed to be used directly by a developer or an AI agent (e.g. an OpenAI/Claude agent running on the same machine) to run strategy experiments in a tight feedback loop without any infrastructure overhead.

---

## 1. Architecture Overview

### High-Level Data Flow

```mermaid
graph LR
    A["👤 User"] -->|"Describes trading idea<br/>in natural language"| B["Strategy Wizard<br/>(React + LLM)"]
    B -->|"JSON<br/>StrategyDefinition v1"| C["Strategy Definition<br/>(Validated)"]
    C -->|"Submit job"| D["Node.js API<br/>(Express)"]
    D -->|"Enqueue job<br/>(BullMQ)"| E["Redis Queue"]
    E -->|"Dequeue & run"| F["Python Engine<br/>(vectorbt/backtesting.py)"]
    F -->|"Backtest results<br/>(incremental)"| G["SQLite<br/>(Results DB)"]
    G -->|"Query results"| H["Dashboard<br/>(React)"]
    H -->|"Validate strategy"| I["Robustness Suite<br/>(Python)"]
    I -->|"Test results"| J["Strategy Vault<br/>(Node + SQLite)"]
    J -->|"Select & format"| K["Export Engine<br/>(Node)"]
    K -->|"cTrader / Pine Script / etc."| L["🎯 Strategy File"]
    
    style A fill:#e1f5ff
    style B fill:#fff3e0
    style F fill:#f3e5f5
    style J fill:#e8f5e9
    style K fill:#fce4ec
```

### Component Layers

| Layer | Responsibility | Tech Stack |
|-------|-----------------|-----------|
| **UI Layer** | Strategy wizard, dashboard, results viewer | React + TypeScript + Vite, Zustand (state), lightweight-charts, WebSocket client |
| **API Layer** | Job orchestration, auth, results serving, export pipeline | Node.js + Express, BullMQ (job queue), better-sqlite3 (DB access) |
| **Compute Layer** | Backtesting, optimization, robustness validation | Python 3.11+, vectorbt or backtesting.py, optuna, scipy/numpy/pandas |
| **Data Layer** | OHLCV caching, persistence, schema versioning | SQLite (local), Parquet/CSV (market data cache), alembic (migrations) |
| **Message Bus** | Async job dispatch, progress events, result delivery | BullMQ + Redis (job queue, retry logic, persistence) |

---

## 2. Tech Stack Decisions

### Python ↔ Node.js Communication: BullMQ + Redis

**Choice:** BullMQ + Redis job queue ✅

**Rationale:**
- **Resilience**: Jobs survive Node.js process restart; Redis persists queue state
- **Scalability**: Multi-worker Python engine can consume jobs in parallel (future feature)
- **Progress events**: BullMQ provides `progress()` callback; UI polls `/jobs/{id}/progress` or subscribes via WebSocket
- **Retry & backoff**: Built-in exponential backoff; failed jobs can be requeued automatically
- **Observability**: BullMQ Admin UI optional; clear job lifecycle (pending → active → completed/failed)

**Trade-offs considered:**
- ❌ FastAPI microservice: Requires open TCP port; more operational overhead; slower for short jobs
- ❌ child_process + stdio: Works for single machine but no persistence; complex error handling; no multi-worker support

**Architecture:**
```
User submits job (React UI)
    ↓
POST /api/jobs (Node.js Express)
    ↓
Insert queue message to Redis via BullMQ
    ↓
Python worker pulls from Redis, runs `python engine/run.py --job-id <id>`
    ↓
Python writes results incrementally to SQLite + emits progress events
    ↓
Node.js polls SQLite, returns results via `/api/results/{job_id}`
    ↓
React UI displays equity curve, metrics, heatmaps
```

### Strategy Definition: Versioned JSON Schema

**V1 philosophy:** Minimal but extensible. Start simple (indicators + entry/exit rules), architect for future complexity (patterns, regime detection, multi-timeframe logic).

**Why:**
- MVP launches faster
- Phase 3+ can introduce complexity via schema versioning (StrategyDefinition v2, v3, etc.)
- Python and TypeScript codegen from single source of truth (JSON Schema)

### Data Storage

**SQLite (local-first):**
- Zero infrastructure (no external database)
- Sufficient for single-machine strategy development
- results) can be exported; version control friendly (text diffs)
- Migration strategy via alembic (Python) + SQL scripts (Node.js)

**OHLCV caching (Parquet + CSV):**
- Node.js data service fetches via dukascopy-node, writes to `/data/cache/{symbol}/{timeframe}.parquet`
- Python engine consumes directly; numpy/pandas optimized for Parquet
- Lifecycle: hourly refresh (configurable), retention policy (e.g., keep 5 years for forex)

### UI State Management

**Zustand** (vs Redux, Jotai, etc.):
- Lightweight, minimal boilerplate
- Perfect for form state (Wizard) and dashboard state (jobs, results, vault filters)
- Side effects via custom hooks (WebSocket subscription for job progress)

### Charting Library

**lightweight-charts** (vs recharts, Chart.js):
- Optimized for financial timeseries (candles, volume, overlays)
- GPU-accelerated rendering for 1M+ candles
- Clean API for equity curves + drawdown dual-axis

---

## 3. Monorepo Folder Structure

```
algo-farm/
├── /shared/
│   ├── schemas/
│   │   ├── strategy-definition.v1.json     # JSON Schema for StrategyDefinition
│   │   ├── job-payload.json                # Job submission / result schema
│   │   └── robustness-report.json          # Robustness test results schema
│   ├── pydantic-models/
│   │   └── strategy_definition.py          # Generated Pydantic models from JSON Schema
│   └── zod-schemas/
│       └── strategy-definition.ts          # Generated Zod schemas from JSON Schema
│
├── /engine/
│   ├── src/
│   │   ├── __init__.py
│   │   ├── main.py                         # Entry point: python engine/run.py --job-id <id>
│   │   ├── backtest/
│   │   │   ├── __init__.py
│   │   │   ├── runner.py                   # Backtest orchestration (grid sweep)
│   │   │   ├── strategy.py                 # Strategy composition from StrategyDefinition
│   │   │   └── indicators/
│   │   │       ├── __init__.py
│   │   │       ├── trend.py                # Examples: SMA, EMA, MACD
│   │   │       ├── momentum.py             # Examples: RSI, STOCH
│   │   │       └── volatility.py           # Examples: ATR, Bollinger Bands
│   │   ├── optimization/
│   │   │   ├── __init__.py
│   │   │   ├── grid_search.py              # Grid-search optimizer
│   │   │   └── bayesian.py                 # Optuna-based Bayesian optimization
│   │   ├── robustness/
│   │   │   ├── __init__.py
│   │   │   ├── walk_forward.py             # Walk-forward analysis
│   │   │   ├── monte_carlo.py              # Monte Carlo simulation
│   │   │   ├── oos_test.py                 # Out-of-sample test
│   │   │   ├── parameter_sensitivity.py    # Parameter robustness
│   │   │   └── trade_shuffle.py            # Trade permutation test
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   ├── db.py                       # SQLite connection / sqlmodel repositories
│   │   │   └── migrations/
│   │   │       ├── env.py                  # Alembic setup
│   │   │       └── versions/               # Migration scripts
│   │   ├── metrics.py                      # Compute PnL, Sharpe, Sortino, Calmar, etc.
│   │   └── utils.py                        # Logging, data loading, etc.
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                     # Pytest fixtures (sample data, mock jobs)
│   │   ├── unit/
│   │   │   ├── test_indicators.py
│   │   │   ├── test_strategy.py
│   │   │   └── test_metrics.py
│   │   ├── integration/
│   │   │   ├── test_backtest_correctness.py  # Known input → known output
│   │   │   └── test_optimization.py
│   │   └── fixtures/
│   │       ├── sample_equity.csv           # Known equity curve
│   │       └── sample_trades.json          # Known trades
│   ├── requirements.txt                    # pip dependencies
│   ├── pyproject.toml                      # Python project metadata (mypy, pytest config)
│   └── README.md
│
├── /api/
│   ├── src/
│   │   ├── server.ts                       # Express app entry point
│   │   ├── config.ts                       # Environment, database paths, Redis config
│   │   ├── db/
│   │   │   ├── client.ts                   # better-sqlite3 connection
│   │   │   ├── repositories/
│   │   │   │   ├── strategy.repo.ts        # CRUD for strategies table
│   │   │   │   ├── run.repo.ts             # CRUD for runs table
│   │   │   │   ├── tag.repo.ts             # CRUD for tags table
│   │   │   │   └── job.repo.ts             # CRUD for jobs table
│   │   │   └── migrations/
│   │   │       └── 001-initial-schema.sql  # SQLite schema
│   │   ├── queue/
│   │   │   ├── client.ts                   # BullMQ connection, job types
│   │   │   ├── producers.ts                # Enqueue jobs (backtest, robustness, etc.)
│   │   │   └── workers.ts                  # TBD: optional polling of Python results
│   │   ├── routes/
│   │   │   ├── wizard.ts                   # POST /wizard/chat, GET /wizard/suggest
│   │   │   ├── jobs.ts                     # POST /jobs, GET /jobs/:id, GET /jobs/:id/progress
│   │   │   ├── results.ts                  # GET /results/:job_id, GET /results/:job_id/heatmap
│   │   │   ├── strategies.ts               # CRUD: POST, GET, PUT, DELETE /strategies
│   │   │   ├── vault.ts                    # Strategy vault search, filter, journal
│   │   │   ├── export.ts                   # POST /export/{strategy_id}/{format}
│   │   │   ├── ws.ts                       # WebSocket: /ws/jobs/:id/progress
│   │   │   └── health.ts                   # GET /health
│   │   └── services/
│   │       ├── wizard.service.ts           # Call LLM API (OpenAI/Claude), validate output
│   │       ├── job.service.ts              # Job lifecycle: submit → poll → store results
│   │       ├── export.service.ts           # Adapter pattern: dispatch to format-specific handlers
│   │       └── python-engine.service.ts    # Spawn Python subprocess, handle exit codes
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── wizard.service.test.ts
│   │   │   ├── job.service.test.ts         # Mock Redis queue, test job orchestration
│   │   │   └── repositories.test.ts        # Mock SQLite, test CRUD
│   │   ├── integration/
│   │   │   └── e2e-wizard-to-results.test.ts  # Real API, mock Python, test full flow
│   │   └── fixtures/
│   │       └── sample-jobs.json
│   ├── package.json                        # Node dependencies
│   ├── tsconfig.json                       # TypeScript config (strict: true)
│   ├── eslintrc.json                       # Linting rules
│   ├── .env.example                        # Configuration template
│   └── README.md
│
├── /ui/
│   ├── src/
│   │   ├── main.tsx                        # React entry point (Vite)
│   │   ├── App.tsx                         # Router: Wizard, Dashboard, Vault, Export
│   │   ├── hooks/
│   │   │   ├── useWizard.ts                # Wizard form state + LLM chat
│   │   │   ├── useJobProgress.ts           # WebSocket subscription for job progress
│   │   │   ├── useBacktestResults.ts       # Fetch and cache results
│   │   │   └── useVault.ts                 # Strategy vault search, filter
│   │   ├── components/
│   │   │   ├── Wizard/
│   │   │   │   ├── ChatMessage.tsx
│   │   │   │   ├── IndicatorSelector.tsx
│   │   │   │   ├── VariantToggle.tsx       # Basic / Advanced
│   │   │   │   └── review.tsx              # JSON preview + submit
│   │   │   ├── Dashboard/
│   │   │   │   ├── EquityCurve.tsx         # lightweight-charts
│   │   │   │   ├── Drawdown.tsx
│   │   │   │   ├── HeatmapGrid.tsx         # instrument × timeframe
│   │   │   │   ├── ParameterSensitivity.tsx
│   │   │   │   ├── JobProgress.tsx         # % complete, current instrument/timeframe
│   │   │   │   ├── MetricsTable.tsx
│   │   │   │   └── index.tsx
│   │   │   ├── Vault/
│   │   │   │   ├── StrategyList.tsx
│   │   │   │   ├── StrategyDetail.tsx
│   │   │   │   ├── TagFilter.tsx
│   │   │   │   ├── JournalEntry.tsx
│   │   │   │   ├── ParameterSetForm.tsx    # bull/bear/sideways/default
│   │   │   │   └── index.tsx
│   │   │   ├── Export/
│   │   │   │   ├── FormatSelector.tsx      # cTrader, Pine Script, etc.
│   │   │   │   ├── ParameterMapper.tsx     # Map strategy params to export format
│   │   │   │   └── PreviewCode.tsx
│   │   │   └── Common/
│   │   │       ├── Header.tsx
│   │   │       ├── ErrorBoundary.tsx
│   │   │       └── Loading.tsx
│   │   ├── store/
│   │   │   ├── index.ts                    # Zustand store(s)
│   │   │   ├── wizard.ts                   # Wizard state (strategy draft)
│   │   │   ├── jobs.ts                     # Active jobs, results cache
│   │   │   └── vault.ts                    # Selected strategies, filter
│   │   ├── api/
│   │   │   ├── client.ts                   # Fetch wrapper (auth headers, error handling)
│   │   │   ├── wizard.api.ts               # /wizard/chat, /wizard/suggest
│   │   │   ├── jobs.api.ts                 # /jobs, /results
│   │   │   ├── strategies.api.ts           # /strategies CRUD
│   │   │   ├── export.api.ts               # /export
│   │   │   └── ws.ts                       # WebSocket connection manager
│   │   ├── types/
│   │   │   ├── strategy.ts                 # StrategyDefinition TypeScript type
│   │   │   ├── job.ts                      # Job, JobResult, JobProgress types
│   │   │   └── api.ts                      # API response envelopes
│   │   ├── styles/
│   │   │   ├── global.css                  # Reset, themes
│   │   │   └── components.css              # Component-scoped styles
│   │   └── vite-env.d.ts
│   ├── tests/
│   │   ├── unit/
│   │   │   └── hooks.test.tsx              # Test custom hooks (rendering, state updates)
│   │   ├── integration/
│   │   │   └── wizard-flow.test.tsx        # Render Wizard, simulate user input, mock API
│   │   └── e2e/
│   │       └── full-flow.spec.ts           # Playwright: wizard → submit → results display
│   ├── package.json                        # React, Vite, testing deps
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── vitest.config.ts                    # Vitest + Playwright
│   └── README.md
│
├── /data/
│   ├── cache/                              # OHLCV data cache (Parquet/CSV)
│   │   ├── EURUSD/
│   │   │   ├── H1.parquet
│   │   │   ├── D1.parquet
│   │   │   └── ...
│   │   └── GBPUSD/
│   │       └── ...
│   ├── scripts/
│   │   ├── fetch.js                        # Node.js script: dukascopy-node → Parquet
│   │   └── README.md                       # How to run data fetcher
│   └── .gitignore                          # Ignore parquet files (store in /dev/null or external storage)
│
├── /docs/
│   ├── PLAN.md                             # This file
│   ├── ARCHITECTURE.md                     # Technical design
│   ├── SCHEMA.md                           # Data models & contracts
│   ├── CONVENTIONS.md                      # Coding standards
│   ├── TESTING_STRATEGY.md                 # Test architecture
│   ├── API_SPEC.md                         # OpenAPI spec (draft)
│   ├── copilot-instructions.md             # AI guidance
│   └── AGENTS_AND_SKILLS.md                # Autonomous agent roles
│
├── .gitignore
├── Makefile                                # make init, make run-api, make run-engine, etc.
├── docker-compose.yml                      # Redis + optional SQL browser (DBeaver)
├── README.md                               # Project overview, quickstart
└── Mission.md                              # Original requirements (reference)
```

---

## 4. Phase Breakdown & Milestones

### Phase 1: Standalone Python Engine (CLI / Agent-First MVP)
**Goal:** A fully working backtest + optimization engine callable from the command line, with no dependency on Node.js, Redis, or any UI. Usable by a developer or an AI agent on the same machine to run strategy experiments in a tight feedback loop.

**Components:**

| Layer | Component | Work Items |
|-------|-----------|-----------|
| **Python** | CLI entry point | `python engine/run.py --strategy strategy.json [options]` |
| **Python** | Backtest Runner | Load OHLCV from Parquet/CSV, compose strategy from `StrategyDefinition`, run backtest, compute metrics |
| **Python** | Grid Search Optimizer | Sweep parameter grid, persist each run result incrementally to SQLite |
| **Python** | Metrics Engine | PnL, CAGR, Max DD, Calmar, Sharpe, Sortino, Profit Factor, Win Rate, Expectancy, # Trades |
| **Python** | SQLite persistence | Write results to local `algo_farm.db`; job survives interruption and can be resumed |
| **Python** | stdout JSON output | Emit progress events and final summary as newline-delimited JSON (easy to parse by an agent) |
| **Shared** | `StrategyDefinition` v1 | JSON Schema + Pydantic model (Python-side only at this phase) |
| **Data** | OHLCV cache | Node.js data fetcher (dukascopy-node) writes Parquet to `/data/cache`; Python reads it |

**CLI Interface:**

```bash
# Run backtest with a single parameter set
python engine/run.py \
  --strategy strategy.json \
  --instruments EURUSD,GBPUSD \
  --timeframes H1,D1 \
  --db ./algo_farm.db

# Run grid search optimization
python engine/run.py \
  --strategy strategy.json \
  --instruments EURUSD \
  --timeframes H1 \
  --param-grid param_grid.json \
  --optimize grid \
  --metric sharpe_ratio \
  --db ./algo_farm.db

# Resume an interrupted job
python engine/run.py --resume-job <job_id> --db ./algo_farm.db
```

**stdout protocol (newline-delimited JSON, easy to consume by an agent):**

```jsonl
{"type": "progress", "pct": 25, "current": {"instrument": "EURUSD", "timeframe": "H1", "iteration": 3, "total": 12}}
{"type": "progress", "pct": 50, "current": {"instrument": "EURUSD", "timeframe": "D1", "iteration": 6, "total": 12}}
{"type": "result", "instrument": "EURUSD", "timeframe": "H1", "params": {"sma_period": 20}, "metrics": {"sharpe": 1.42, "max_dd": -0.14, "win_rate": 0.58}}
{"type": "completed", "job_id": "uuid", "best_params": {"sma_period": 50}, "best_sharpe": 1.85, "db_path": "./algo_farm.db"}
```

**Agent feedback loop example (pseudocode):**

```python
# An AI agent can run this loop autonomously, no UI or infrastructure needed
for variant in strategy_variants:
    write_json("strategy.json", variant)
    output = subprocess.run(["python", "engine/run.py", "--strategy", "strategy.json", ...])
    results = parse_jsonl(output.stdout)
    best = results["best_sharpe"]
    # Agent decides next variant based on results
```

**User-Visible Outcome:**
- Developer writes a `strategy.json` and a `param_grid.json`
- Runs the CLI, sees live progress in terminal
- Results land in `algo_farm.db` (SQLite), queryable directly
- An AI agent can drive the full experiment loop without any running service

**Definition of Done:**
- ✅ CLI entry point accepts `--strategy`, `--instruments`, `--timeframes`, `--param-grid`, `--metric`, `--db`, `--resume-job`
- ✅ `StrategyDefinition` v1 JSON Schema defined and validated on load
- ✅ Backtest runs correctly against Parquet OHLCV data
- ✅ Grid search optimizer sweeps all param combinations, persists each run to SQLite
- ✅ All key metrics computed (Sharpe, Calmar, Max DD, Win Rate, Expectancy, etc.)
- ✅ Progress emitted to stdout as newline-delimited JSON
- ✅ Job can be interrupted and resumed (`--resume-job`)
- ✅ Unit tests: indicators, metrics (known input → known output)
- ✅ Integration test: known strategy + known data → known metrics
- ✅ Works with zero Node.js / Redis / Docker dependency

**Estimated Complexity:** M (medium)

---

### Phase 2: Strategy Wizard (LLM Chat)
**Goal:** User can describe a trading idea in natural language and receive a JSON `StrategyDefinition` v1.

**Components:**

| Layer | Component | Work Items |
|-------|-----------|-----------|
| **React** | Wizard UI | Chat interface (input), LLM responses (async), Basic/Advanced toggle, JSON preview |
| **Node.js** | Wizard Service | Call LLM API, validate output against StrategyDefinition v1 JSON Schema, error recovery |
| **Shared** | Zod models | Generate Zod schemas (TypeScript-side) from the JSON Schema defined in Phase 1 |

**User-Visible Outcome:**
- User opens app
- Describes strategy idea ("Breakout when price breaks above 20-day high, exit on 2x RR")
- LLM suggests indicators (breakout detector), entry rule, exit rule
- User toggles Basic/Advanced (fixed TP vs. TP1/TP2)
- Clicks "Create Strategy" → JSON saved to vault database

**Definition of Done:**
- ✅ Wizard chat UI renders and sends messages to backend
- ✅ LLM prompt returns valid StrategyDefinition JSON (validated against schema)
- ✅ Strategy definition persisted to SQLite `strategies` table
- ✅ Unit tests: LLM output validation, schema validation
- ✅ E2E test (Playwright): describe idea → submit → confirm saved in vault
- ✅ Error handling: invalid LLM output (schema mismatch, missing fields) → user-friendly error message

**Estimated Complexity:** M (medium)

---

### Phase 3: Backtest & Optimization Engine (API + Dashboard)
**Goal:** Wrap the Phase 1 Python engine behind the Node.js API and BullMQ job queue; add the React dashboard for results visualization and live progress.

**Components:**

| Layer | Component | Work Items |
|-------|-----------|-----------|
| **Python** | Bayesian Optimizer | Add optuna Bayesian opt on top of Phase 1 grid search; progress events via stdout |
| **Node.js** | Job Orchestration | BullMQ producer, spawn Phase 1 CLI as child process, job state / result storage |
| **Node.js** | WebSocket server | Relay stdout progress events to connected React clients |
| **React** | Dashboard | Equity curve, drawdown, heatmap (instrument × timeframe), parameter sensitivity, live job progress |
| **Shared** | Job Payload Schema | Define input (strategy ID, instruments, timeframes, param ranges), output (results summary) |

**User-Visible Outcome:**
- User selects a strategy from vault
- Specifies: instruments (EURUSD, GBPUSD), timeframes (H1, D1), parameter ranges (SL: 10-50 pips, TP ratio: 1-3)
- Clicks "Start Backtest + Optimize"
- Dashboard shows live progress: "Processing EURUSD H1... (2/8)"
- After hours, all results appear: equity curve, drawdown chart, heatmap colored by Sharpe, parameter sensitivity surface
- User can download CSV of all runs

**Definition of Done:**
- ✅ Node.js wraps Phase 1 CLI via BullMQ job, reads stdout JSON stream for progress
- ✅ Bayesian optimization (optuna) added to engine
- ✅ Incremental result storage (results written per instrument/timeframe, survives interruption)
- ✅ Node.js emits progress events via WebSocket to React
- ✅ Dashboard renders equity curve (lightweight-charts), heatmap (color scale), live % progress
- ✅ Integration test: job submit via API → completion → results in SQLite

**Estimated Complexity:** XL (very large)

---

### Phase 4: Robustness Validation Suite
**Goal:** Add statistical robustness tests to the Phase 1 Python engine; expose them via API and UI.

**Components:**

| Layer | Component | Work Items |
|-------|-----------|-----------|
| **Python** | Robustness Tests | Walk-forward, Monte Carlo, OOS, parameter sensitivity, trade shuffle |
| **Python** | Report Generation | Composite go/no-go score with justification |
| **Node.js** | Job Orchestration | New job type: "robustness-validation" |
| **React** | Report Display | Per-test results, composite score, charts (equity confidence bands, trade distribution) |

**User-Visible Outcome:**
- User selects optimized strategy from dashboard
- Clicks "Validate Strategy"
- Specifies: walk-forward window size, Monte Carlo iterations (1000), OOS split (last 20%), parameter sensitivity range (±10%)
- Runs multi-day robustness job
- Report summary: "Go (8.8/10)" with rationale: "Walk-forward Sharpe degradation only 5%, OOS performance similar, trade distribution stable"
- User can now mark strategy "Validated" and save it by regime (bull/bear/sideways parameter sets)

**Definition of Done:**
- ✅ All 5 robustness tests implemented (walk-forward, Monte Carlo, OOS, param sensitivity, trade shuffle)
- ✅ Composite scoring algorithm (weighted average of test scores)
- ✅ Robustness results stored in `robustness_reports` table with full audit trail
- ✅ Report JSON schema defined (version, test_results[], composite_score, justification)
- ✅ React component displays report with summary + per-test breakdown
- ✅ Unit tests: each robustness test with mock data → known output
- ✅ Integration test: from validated backtest → robustness job → report in DB

**Estimated Complexity:** XL

---

### Phase 5: Strategy Vault
**Goal:** User can organize, search, and manage validated strategies with regime-specific parameters and journal notes.

**Components:**

| Layer | Component | Work Items |
|-------|-----------|-----------|
| **Node.js** | Strategy CRUD + Filters | PUT /strategies/:id/status, GET /strategies?tag=trend&regime=bull&timeframe=D1 |
| **React** | Vault UI | Strategy list, detail view, tag cloud, status lifecycle, journal, parameter set editor |
| **SQLite** | Schema | strategies, parameter_sets (regime: bull/bear/sideways/default), tags, journal_entries, audit_log tables |

**User-Visible Outcome:**
- Vault page shows all strategies (filters: style, regime, status, timeframe)
- Select strategy → view all backtest/robustness runs (audit trail), add journal notes, save parameter sets for each regime
- "Produce strategy: 'Breakout Trend' (bull regime, D1 timeframe, SL=25pips, TP_ratio=2.5)"
- Status transition: draft → tested → validated → production → archived (immutable audit log)

**Definition of Done:**
- ✅ Strategy table design with versioning (immutable history)
- ✅ Full CRUD endpoints (create, read, update, delete strategies)
- ✅ Parameter set CRUD (per regime)
- ✅ Journal CRUD (timestamped notes)
- ✅ Tag/filter system (full-text search optional)
- ✅ Status lifecycle with immutable audit log
- ✅ React Vault UI: list, detail, filter, journal, parameter editor
- ✅ Integration tests: CRUD flows, status transitions

**Estimated Complexity:** L (large)

---

### Phase 6: Export Engine
**Goal:** User can export a validated strategy (with selected parameter set) to cTrader/cAlgo C# or TradingView Pine Script.

**Components:**

| Layer | Component | Work Items |
|-------|-----------|-----------|
| **Node.js** | Export Service | Adapter pattern: dispatch to format handlers (cTrader, Pine Script, etc.) |
| **Node.js** | Format Handlers | cTrader C# template, Pine Script v5 template, parameter injection |
| **React** | Export UI | Format selector, parameter mapping (SL → TradeDirection or ordertypeinterpretations), preview code |

**User-Visible Outcome:**
- Vault detail: "Breakout Trend (validated)"
- Click "Export"
- Select: format (cTrader), parameter set (bull regime)
- App generates C# cAlgo code with `OnStart`, `OnTick`, `OnBar`, `OnStop`
- User downloads file, imports into cTrader

**Definition of Done:**
- ✅ ExportAdapter interface (format-agnostic)
- ✅ cTrader C# template (OnStart, OnTick, OnBar, strategy logic, SL/TP placement)
- ✅ Pine Script v5 template (indicator definitions, strategy logic)
- ✅ Parameter injection (e.g., SMA period, breakout threshold)
- ✅ Code preview + download
- ✅ Unit tests: parameter injection into templates
- ✅ Integration test: export strategy → validate generated code syntax

**Estimated Complexity:** M

---

## 5. Risks & Open Questions

| Risk | Mitigation | Owner | Timeline |
|------|------------|-------|----------|
| **Redis/BullMQ complexity** - first time using BullMQ + Redis | Start with simple job producer/consumer pattern, mock Redis in tests, use BullMQ docs + examples | Backend lead | Phase 2 planning |
| **Python ↔ SQLite (sqlmodel) learning curve** | Create simple repository examples, use SQLModel guides, pair-program setup | Backend/Engine lead | Phase 2 week 1 |
| **LLM prompt brittleness** - strategy wizard output doesn't always parse as valid JSON | Build robust validation layer + user reporting endpoint ("This definition is incorrect"), iterate prompts based on feedback | LLM specialist | Phase 1 week 2–3 |
| **Backtest performance** - 10+ instruments × 5 timeframes × 1000s of parameter combos = hours/days | Parallelize Python workers (multi-processing), implement early stopping (Bayesian opt stops if Sharpe plateaus), document expected runtime | Engine lead | Phase 2 planning |
| **React state explosion** - Wizard + Dashboard + Vault state intertwined, hard to manage | Use Zustand stores (separate per feature: wizard, jobs, vault), no global mega-store | Frontend lead | Phase 1 design review |
| **Data freshness** - dukascopy cache stale, user gets incorrect backtest results | Implement cache metadata (fetch timestamp, expiry), user-facing "data stale" warning, auto-refresh nightly job | Data lead | Pre-launch |

### Open Questions (Due Before Phase 2 Start)

1. **LLM Provider:** OpenAI (GPT-4o) or Claude? (Cost, latency, reliability trade-off)
2. **Redis deployment:** Docker Compose (localhost) or managed Redis (AWS ElastiCache)?
3. **Authentication:** Simple API key or OAuth2/JWT for multi-user setup?
4. **Export priority:** Which formats first—cTrader, Pine Script, or both?
5. **Vault search scope:** Full-text search on strategy descriptions + parameter history, or simple tag/filter only?

---

## 6. Milestones Timeline

| Phase | Duration | Start | End | Deliverable |
|-------|----------|-------|-----|-------------|
| **Phase 1: Standalone Python Engine** | 2–3 weeks | Week 1 | Week 3 | CLI backtest + grid optimization, agent/headless ready, zero infra dependencies |
| **Phase 2: Strategy Wizard** | 2–3 weeks | Week 4 | Week 6 | Strategy definition from natural language (LLM + React) |
| **Phase 3: API + Dashboard** | 4–5 weeks | Week 7 | Week 12 | Node.js API wrapping Phase 1, BullMQ jobs, Bayesian opt, results dashboard |
| **Phase 4: Robustness Suite** | 3–4 weeks | Week 13 | Week 17 | Walk-forward, Monte Carlo, OOS, param sensitivity, trade shuffle tests |
| **Phase 5: Vault** | 2–3 weeks | Week 18 | Week 21 | Strategy storage, search, status lifecycle, journal, regimes |
| **Phase 6: Export** | 1–2 weeks | Week 22 | Week 24 | cTrader + Pine Script exporters |
| **Post-launch** | Ongoing | Week 25+ | — | Performance optimization, additional export formats, UI polish |

---

## 7. Getting Started

**Monorepo initialization:**
```bash
# Prerequisites: Python 3.11+, Node 20+, Redis
git clone <repo>

# Bootstrap
make init                     # Installs venv, node deps, creates SQLite schema, starts Redis

# Run locally (development)
make run-api                  # Node.js API on 3001
make run-engine-worker        # Python worker (poll BullMQ)
make run-ui                   # React dev server on 5173
make run-redis                # Redis in Docker (optional)

# Test
make test                     # All tests (unit + integration)
make test-unit                # Unit tests only
make e2e-wizard-flow          # Playwright: full wizard → submit flow
```

---

## Next Steps

1. **Finalize LLM provider & authentication** (resolve open questions above)
2. **Create detailed ARCHITECTURE.md** with sequence diagrams & error flows
3. **Define StrategyDefinition v1 JSON Schema** (SCHEMA.md)
4. **Set up monorepo scaffolding** (folders, basic Express + React + Python shells)
5. **Begin Phase 1 implementation** (wizard LLM integration)
