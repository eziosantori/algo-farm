# Mission
You are a senior software architect. Analyze the requirements below and produce a set of
planning and architecture documents for an **algo trading strategy development platform**.

## Core principles for the plan
- **Incremental delivery**: every milestone must produce a working, runnable app. No dead-end stubs.
- **Complexity grows gradually**: each phase builds on the previous one without requiring rewrites.
- **Agentic-first**: long-running tasks (backtests, optimizations) must run autonomously without
  user input, potentially for hours/days.
- **Polyglot architecture**: Python for compute-heavy core, Node.js for API layer,
  React/TypeScript for UI. Design clean boundaries between layers.

## Tech stack (fixed, do not suggest alternatives)

| Layer | Stack | Rationale |
|---|---|---|
| **Backtest & Optimization Engine** | Python 3.11+ | Ecosystem: `vectorbt` or `backtesting.py`, `optuna` (Bayesian opt), `scipy`/`numpy`, `pandas` |
| **Data fetching** | Node.js + `dukascopy-node` | Existing familiarity, wrap in a small data service that caches to local files (Parquet or CSV) consumable by Python |
| **API layer** | Node.js + Express (or Fastify) | Orchestrates jobs, serves UI, wraps Python engine via child_process or a lightweight job queue |
| **UI** | React + TypeScript + Vite | Charting: `lightweight-charts` or `recharts`, state: Zustand or React Query |
| **Storage** | SQLite (via `better-sqlite3` on Node side, `sqlite3`/`sqlmodel` on Python side) | Local-first, zero-infra, sufficient for this use case |
| **Python ↔ Node communication** | Define clearly: options are (a) REST microservice (FastAPI), (b) child_process stdio JSON, (c) job queue (BullMQ + Redis). Evaluate trade-offs and pick one, documenting the reasoning. |

### Key architectural constraint
The Python engine must expose a **job-based interface**: a job is submitted
(strategy + parameters + instruments + timeframes), runs to completion writing incremental
results to SQLite/disk, and emits progress events the Node API can poll or subscribe to.
The UI must be able to show live progress of a multi-day optimization run.

---

## Product requirements

### Phase 1 – Strategy Wizard (MVP)
A chat-based UI where the user describes a trading idea in natural language.
The LLM (via API) must:
- Interpret the intent and map it to a structured strategy definition
- Suggest relevant **indicators** (trend, momentum, volatility, volume),
  **filters** (time of day, session, volatility regime, day-of-week), **entry/exit criteria**
- Propose two variants:
  - **Basic**: single entry, fixed SL/TP
  - **Advanced**: scaled entries, partial take-profits (TP1/TP2/TP3), trailing stop, re-entry logic
- Output a structured `StrategyDefinition` (JSON schema) that drives all downstream phases

Define a clear, versioned JSON schema for `StrategyDefinition` (v1) that must remain stable
across phases. This schema must be serializable to both Python (Pydantic model) and TypeScript
(Zod schema) — include both in the plan.

### Phase 2 – Automated Backtest & Optimization Engine (Python core)
Given a `StrategyDefinition`, the Python engine must autonomously:
- Consume OHLCV data from the local cache produced by the Node data service (Parquet preferred)
- Run backtests across all configured **instruments** and **timeframes**
- Run parameter optimization: grid search first, then Bayesian optimization via `optuna`
- Persist results incrementally to SQLite so jobs survive interruption and can be resumed
- Expose a simple CLI entry point (`python engine/run.py --job-id <id>`) callable by Node

**Key metrics** (propose the most appropriate set for retail algo trading):
- Net PnL, CAGR, Max Drawdown, Calmar Ratio, Sharpe, Sortino, Profit Factor
- Win Rate, Avg Win/Loss, Expectancy, # Trades, Avg trade duration
- Stability score: consistency of metrics across instrument × timeframe grid

**Dashboard** (React):
- Equity curve + drawdown chart per run
- Heatmap: instrument × timeframe, colored by chosen metric
- Parameter sensitivity surface
- Live job progress (% complete, current instrument/timeframe being processed)

### Phase 3 – Robustness Validation Suite (Python)
A configurable pipeline of statistical tests, selectable by the user before promoting a strategy:
- **Walk-Forward Analysis** (rolling window and anchored variants)
- **Monte Carlo simulation**: trade order shuffle, random entry jitter, equity curve simulation
  (N iterations, confidence bands)
- **Out-of-sample test**: reserve configurable last N% of data, never touched during optimization
- **Parameter sensitivity test**: performance degradation around optimal parameter set
- **Trade shuffle / permutation test**: null hypothesis that returns are random
- Suggest any other industry-standard robustness tests relevant here

Output: a structured **Robustness Report** (JSON + visual summary in UI) with per-test result
and a final composite go/no-go score with justification.

### Phase 4 – Strategy Vault (Node + SQLite + React)
A local database of validated strategies:
- Full audit trail of all backtest and robustness runs linked to a strategy version
- Free-text notes with timestamped journal entries per strategy
- **Parameter sets** saved per market regime: `bull`, `bear`, `sideways`, `default`
- **Tags**: instrument, timeframe, style (`trend` / `mean-reversion` / `breakout` / `scalping`
  / `carry`), regime
- Search and filter by any combination of tags, instrument, timeframe, regime, status
- Strategy status lifecycle: `draft → tested → validated → production → archived`

### Phase 5 – Export Engine (Node)
Export a saved strategy (with a selected parameter set) to:
- **cTrader / cAlgo**: C# class template with correct `OnStart` / `OnTick` / `OnBar` structure
- **TradingView Pine Script v5**: indicator + strategy template
- Architecture: define a clean `ExportAdapter` interface so new formats can be added
  without touching core logic

---

## Deliverables

Produce the following documents. Every document must be self-contained and immediately usable
by an autonomous coding agent without requiring clarification.

---

### 1. `PLAN.md` — Roadmap & milestones
1. **Architecture overview**: high-level component diagram (Mermaid), data flow from user idea
   → wizard → strategy definition → backtest job → results → vault → export
2. **Tech stack decisions** with rationale (reference fixed stack above, fill all gaps)
3. **Milestone breakdown** — for each milestone:
   - Goal & user-visible outcome
   - Components to build, grouped by layer (Python / Node / React)
   - Definition of Done
   - Estimated complexity: S / M / L / XL
4. **Risks & open questions** that need a decision before or during development
5. **Monorepo folder structure** (`/engine`, `/api`, `/ui`, `/data`, `/shared`, etc.)

---

### 2. `ARCHITECTURE.md` — Technical design
- Detailed Mermaid diagrams: component diagram, sequence diagrams for the critical flows
  (job submission, live progress polling, export pipeline)
- **Python ↔ Node communication**: chosen approach (FastAPI / child_process / BullMQ),
  full trade-off analysis, example request/response payloads
- Layer boundaries: what each layer owns, what it must never do
- Key design patterns to use (e.g. Adapter for exporters, Repository for storage,
  Job pattern for engine tasks) with brief rationale for each
- Error handling strategy across layers (how Python errors surface to the UI)
- Data flow for long-running jobs: submission → progress events → completion → result storage

---

### 3. `SCHEMA.md` — Contracts & data models
- **`StrategyDefinition` v1**: full JSON Schema, Pydantic model (Python), Zod schema (TypeScript)
- **SQLite schema**: all tables with columns, types, indexes, and foreign keys
  (strategies, runs, robustness_reports, parameter_sets, tags, journal_entries, jobs)
- **Job payload schema**: what Node sends to Python when submitting a job, and what Python
  writes back as progress/result events
- **Versioning policy**: how schema changes will be managed across phases (migrations strategy)

---

### 4. `CONVENTIONS.md` — Coding standards & extension patterns
- Naming conventions per layer (Python, Node, TypeScript/React)
- How to add a new **indicator** to the engine (step-by-step, with a minimal example)
- How to add a new **robustness test** to the validation suite (interface to implement,
  where to register it)
- How to add a new **export format** (ExportAdapter interface, registration, testing)
- Commit message format and branch naming
- Environment setup: required tools, versions, how to bootstrap the monorepo locally
- What must have tests and at what level (unit / integration / E2E)

---

### 5. `TESTING_STRATEGY.md` — Test architecture
- Testing philosophy: what to test at each layer and why
- **Python engine**: unit tests for indicators and strategy logic, backtesting correctness
  tests (known input → known output), optimization smoke tests
- **Node API**: unit tests for job orchestration, mock of Python process,
  integration tests for SQLite repositories
- **React UI**: component tests for wizard and dashboard, mock API layer
- **Cross-layer**: E2E test covering wizard → job submission → result display
- How to test long-running jobs without actually running them for hours
- CI pipeline sketch: what runs on every PR, what runs nightly

---

### 6. `API_SPEC.md` — Node API contract *(draft)*
- OpenAPI 3.1 spec (YAML) covering all endpoints needed by the UI through Phase 2
  (wizard, job submission, job status/progress, results, vault CRUD)
- For each endpoint: path, method, request body schema, response schema, error codes
- WebSocket or SSE contract for live job progress events
- This is a living draft — mark endpoints as `[stable]` or `[draft]` explicitly

---

Be opinionated throughout. Where requirements are ambiguous, make a decision and document
your reasoning inline. Prefer explicit over implicit, and boring reliable choices over
clever ones.