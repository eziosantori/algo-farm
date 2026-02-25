# AGENTS.md — Codebase Guide for AI Agents

> Read this file first. It is the compact entry point to the codebase.
> For deep dives, follow the links to `docs/`.

---

## What this project is

An **algo trading strategy development platform**. Users describe a trading idea in natural language; the platform converts it to a structured strategy definition, runs backtests and optimizations autonomously, validates robustness statistically, and exports the result to cTrader or TradingView Pine Script.

**Current focus: Phase 1 — Standalone Python Engine.**
Nothing else exists yet. Build the Python CLI engine first. No Node.js, no Redis, no UI. See `docs/PLAN.md §4 Phase 1` for the full spec.

---

## Architecture in one page

```
Phase 1 (now)
  CLI: python engine/run.py --strategy s.json --instruments EURUSD --timeframes H1 --db ./db.sqlite
  Output: newline-delimited JSON on stdout (progress / result / completed)
  Storage: SQLite (algo_farm.db) — written by engine, read by anyone

Phase 2+ (later)
  Node.js API (Express) → wraps CLI via child_process / BullMQ
  React UI → calls Node.js API
  Redis → job queue (BullMQ)
```

### Layer ownership — hard rules

| Layer | Owns | Must NOT |
|-------|------|----------|
| **Python engine** | Backtest, optimization, metrics, robustness, SQLite writes | Serve HTTP, call external APIs, depend on Node/Redis |
| **Node.js API** | Job orchestration, LLM calls, WebSocket, SQLite reads via repos | Run long compute, store state in memory |
| **React UI** | Rendering, client validation, WebSocket subscribe | Call Python directly, write to SQLite |

---

## Folder map (target monorepo layout)

```
algo-farm/
├── AGENTS.md               ← you are here
├── Mission.md              ← original requirements (read-only reference)
├── docs/                   ← all planning & architecture documents
│   ├── PLAN.md             ← roadmap, milestones, folder structure
│   ├── ARCHITECTURE.md     ← diagrams, layer boundaries, data flows
│   ├── SCHEMA.md           ← all data contracts (CLI, SQLite, BullMQ, JSONL)
│   ├── API_SPEC.md         ← OpenAPI 3.1 spec (Phase 2+) + CLI quick-ref
│   ├── CONVENTIONS.md      ← naming, extension patterns, commit format
│   ├── TESTING_STRATEGY.md ← test philosophy, examples, CI pipeline
│   ├── AGENTS_AND_SKILLS.md← in-platform agent roles (Phase 2+)
│   └── copilot-instructions.md ← LLM system prompts & developer AI guidance
├── engine/                 ← Python 3.11+ compute layer (BUILD THIS FIRST)
├── api/                    ← Node.js 20+ API layer (Phase 2+)
├── ui/                     ← React + TypeScript UI (Phase 2+)
├── data/                   ← OHLCV cache (Parquet) + fetch scripts
└── shared/                 ← JSON Schema, Pydantic models, Zod schemas
```

---

## Phase 1 — what to build

### CLI entry point

```
engine/run.py [flags]
```

| Flag | Required | Default | Notes |
|------|----------|---------|-------|
| `--strategy` | Yes | — | Path to `strategy.json` (StrategyDefinition v1) |
| `--instruments` | Yes | — | Comma-separated: `EURUSD,GBPUSD` |
| `--timeframes` | Yes | — | Comma-separated: `H1,D1` |
| `--param-grid` | No | — | Path to `param_grid.json`; omit for single run |
| `--optimize` | No | `grid` | `grid` or `bayesian` (bayesian = Phase 3) |
| `--metric` | No | `sharpe_ratio` | `sharpe_ratio`, `calmar_ratio`, `profit_factor` |
| `--data-start` | No | all | `YYYY-MM-DD` |
| `--data-end` | No | all | `YYYY-MM-DD` |
| `--db` | No | `./algo_farm.db` | SQLite file path |
| `--data-dir` | No | `./data/cache` | Root of Parquet cache |
| `--resume-job` | No | — | Resume interrupted job by UUID |
| `--log-level` | No | `INFO` | `DEBUG`, `INFO`, `WARNING` |

### stdout protocol (JSONL — one JSON object per line)

```jsonl
{"type":"progress","job_id":"<uuid>","pct":25,"current":{"instrument":"EURUSD","timeframe":"H1","iteration":3,"total":12,"phase":"grid_search"},"elapsed_seconds":60,"estimated_remaining_seconds":180}
{"type":"result","job_id":"<uuid>","instrument":"EURUSD","timeframe":"H1","params":{"sma_period":20},"metrics":{"sharpe_ratio":1.42,"max_drawdown":-0.12,"win_rate":0.58,"net_pnl":1250.5,"num_trades":87,"profit_factor":1.65,"calmar_ratio":1.5,"cagr":0.18,"sortino_ratio":1.85,"expectancy":14.37,"avg_trade_duration_bars":6},"run_id":"<uuid>"}
{"type":"completed","job_id":"<uuid>","total_runs":12,"optimization_method":"grid","best_params":{"sma_period":50},"best_metrics":{"sharpe_ratio":1.85,"max_drawdown":-0.14,"win_rate":0.62},"db_path":"./algo_farm.db","completed_at":"2026-02-24T10:00:00Z"}
```

- **Errors → stderr** (plain text, never JSON). Never mix error text into stdout.
- **Exit codes:** `0` = success, `1` = fatal error, `2` = interrupted (resumable).

### `StrategyDefinition` v1 — required fields

Full JSON Schema in `docs/SCHEMA.md §2`. Minimum viable structure:

```json
{
  "version": "1.0",
  "name": "My Strategy",
  "variant": "basic",
  "indicators": [
    { "name": "sma_20", "type": "sma", "params": { "period": 20 } }
  ],
  "entry_rules": [
    { "logic_type": "price_above", "indicator_ref": "sma_20", "side": "long", "all_must_match": true }
  ],
  "exit_rules": [
    { "logic_type": "stop_loss" }
  ],
  "position_management": {
    "variant_type": "basic",
    "stop_loss_pips": 20,
    "take_profit_pips": 40
  }
}
```

Valid `indicator.type` values: `sma ema macd rsi stoch atr bollinger_bands momentum adx cci obv williamsr`

Valid `entry_rule.logic_type` values: `price_above price_below indicator_cross indicator_above indicator_below`

Valid `exit_rule.logic_type` values: `stop_loss take_profit time_based indicator_cross indicator_above indicator_below price_level`

### `param_grid.json` structure

```json
{
  "sma_period": [20, 50, 100],
  "breakout_threshold": [1.0, 1.5, 2.0],
  "slippage_pips": 2
}
```

Arrays = swept. Scalars = fixed. Full schema in `docs/SCHEMA.md §1.1`.

### SQLite tables written by Phase 1 engine

| Table | Written at |
|-------|-----------|
| `jobs` | Job start + completion |
| `runs` | After each instrument/timeframe/param combination |
| `error_log` | On any caught exception |

Full DDL in `docs/SCHEMA.md §3`.

---

## Engine internals — file layout

```
engine/
├── run.py                      ← CLI entry point (argparse → orchestrator)
├── src/
│   ├── backtest/
│   │   ├── runner.py           ← BacktestRunner: load OHLCV, apply strategy, emit results
│   │   ├── strategy.py         ← compose strategy from StrategyDefinition
│   │   └── indicators/
│   │       ├── __init__.py     ← IndicatorRegistry
│   │       ├── trend.py        ← sma, ema, macd
│   │       ├── momentum.py     ← rsi, stoch, cci, williamsr, obv
│   │       └── volatility.py   ← atr, bollinger_bands, adx
│   ├── optimization/
│   │   ├── grid_search.py      ← GridSearchOptimizer
│   │   └── bayesian.py         ← BayesianOptimizer (optuna) — Phase 3
│   ├── robustness/             ← Phase 4: walk_forward, monte_carlo, oos_test, etc.
│   ├── storage/
│   │   ├── db.py               ← SQLite connection, init_db(), repositories
│   │   └── migrations/         ← alembic env + versions
│   ├── metrics.py              ← calculate_sharpe, calmar, sortino, max_dd, etc.
│   └── utils.py                ← logging setup, Parquet loader
└── tests/
    ├── cli/                    ← CLI contract tests (subprocess, no services)
    ├── unit/                   ← indicators, metrics, strategy logic
    ├── integration/            ← backtest correctness (known data → known metrics)
    └── fixtures/
        ├── simple_sma_strategy.json
        ├── simple_param_grid.json
        ├── generate_fixtures.py    ← generates synthetic Parquet data
        └── data_cache/EURUSD/H1.parquet
```

---

## How to extend (pointers)

| Task | Steps | Full guide |
|------|-------|-----------|
| Add indicator | Implement in `indicators/<file>.py`, register in `IndicatorRegistry`, add to JSON Schema enum, write unit test | `docs/CONVENTIONS.md §2` |
| Add robustness test | Implement function in `robustness/<file>.py`, register in `RobustnessRegistry`, write integration test | `docs/CONVENTIONS.md §2` |
| Add export format | Implement `ExportAdapter` in `api/src/services/export/adapters/`, register in `ExportService` | `docs/CONVENTIONS.md §2` |

---

## Code standards (non-negotiable)

- **Python:** type hints on every function (mypy strict), Google-style docstrings, `snake_case`
- **TypeScript:** no `any`, strict mode, `camelCase` functions, `PascalCase` classes
- **Tests:** every new function has a unit test; every CLI flag has a contract test
- **Errors to stderr:** the engine never writes non-JSON to stdout
- **No secrets in code:** all config via env vars or CLI flags

Full standards: `docs/CONVENTIONS.md`

---

## Testing — quick reference

```bash
# Phase 1 CLI contract tests (no services needed)
pytest engine/tests/cli -v

# Unit tests
pytest engine/tests/unit -v

# Integration tests (requires fixture Parquet data)
python engine/tests/fixtures/generate_fixtures.py   # run once
pytest engine/tests/integration -v

# Full engine suite with coverage
pytest engine/tests -v --cov=engine/src --cov-report=term-missing

# Lint + type check
mypy engine/src --strict
black --check engine/src engine/tests
```

Full test architecture: `docs/TESTING_STRATEGY.md`

---

## What NOT to do

- **Do not add HTTP endpoints to the Python engine.** It must remain CLI-only. Node.js is the HTTP layer.
- **Do not import Node.js / BullMQ concepts into Python.** The engine is standalone.
- **Do not write to stdout from the engine except JSONL messages.** All logging goes to stderr via the `logging` module.
- **Do not commit large Parquet files.** The fixture generator creates tiny synthetic data; real data stays in `/data/cache` (gitignored).
- **Do not create a new file for a one-function addition.** Add to the appropriate existing module.
- **Do not skip tests.** CLI contract tests and unit tests are P0.

---

## Key documents

| Document | When to read |
|----------|-------------|
| `docs/PLAN.md` | Roadmap, milestones, folder structure |
| `docs/SCHEMA.md` | All contracts: CLI flags, JSONL protocol, SQLite DDL, StrategyDefinition |
| `docs/ARCHITECTURE.md` | Layer boundaries, sequence diagrams, BullMQ setup |
| `docs/CONVENTIONS.md` | Naming, extension patterns, commit format |
| `docs/TESTING_STRATEGY.md` | Test philosophy, examples, CI pipeline |
| `docs/API_SPEC.md` | REST API (Phase 2+) + CLI quick-reference |
| `docs/AGENTS_AND_SKILLS.md` | In-platform agent roles (Phase 2+) + Phase 1 agent loop |
| `docs/copilot-instructions.md` | LLM system prompts, developer AI guidance |
| `Mission.md` | Original requirements — do not modify |
