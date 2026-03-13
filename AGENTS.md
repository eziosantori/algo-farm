# AGENTS.md — Codebase Guide for AI Agents

> Read this file first. It is the compact entry point to the codebase.
> For deep dives, follow the links to `docs/`.

---

## What this project is

An **algo trading strategy development platform**. Users describe a trading idea in natural language;
the platform converts it to a structured strategy definition, runs backtests and optimizations
autonomously, validates robustness statistically, and exports the result to cTrader or Pine Script.

**Current status:** Phase 1 (Python Engine), Phase 2 (Strategy Wizard + Lab), and Phase 3
(BullMQ + Dashboard + Bayesian optimisation) are complete.

---

## Quick start for agents — use the skills

Claude Code slash commands are the fastest way to work with strategies.
Run them from the project root (`/Users/esantori/git/personal/algo-farm`).

### `/new-strategy <description>`

Generate a valid `StrategyDefinition` JSON from natural language.

```
/new-strategy "RSI mean-reversion: buy when RSI < 30 and SuperTrend is up, exit when RSI > 70"
```

Saves to `engine/strategies/draft/<name>.json`.

---

### `/backtest <strategy-file> [--instruments EURUSD,XAUUSD] [--timeframes H1,M15]`

Run the engine on one or more (instrument × timeframe) pairs and display a formatted metrics table.

```
/backtest supertrend_rsi.json
/backtest supertrend_rsi.json --instruments EURUSD,BTCUSD --timeframes H1,M15
```

Resolves names from `engine/strategies/draft/` if not an absolute path.
Downloads missing data automatically (Dukascopy, cached as Parquet).

---

### `/iterate <strategy-file> [--target "sharpe > 1.0"] [--iterations 5]`

Autonomously improves a strategy through repeated backtest → diagnose → modify cycles.

```
/iterate supertrend_rsi.json --target "sharpe > 1.5" --iterations 5
```

- Diagnoses the worst metric and applies one focused structural change per iteration
- Keeps the change only if it improves the score by ≥ 2%
- Saves the best version as `engine/strategies/draft/<name>_v<N>.json`
- Posts final results to the Lab API → visible at `http://localhost:5173/lab`

---

### `/optimize <strategy-file> [--metric sharpe_ratio] [--param-grid grid.json]`

Grid-search parameter sweep. Displays results ranked by metric.

```
/optimize supertrend_rsi.json --metric sharpe_ratio
```

---

### `/strategy-lab <strategy-file> [options]`

Multi-asset × multi-timeframe improvement loop. Most powerful skill.

```
/strategy-lab supertrend_rsi.json \
  --instruments EURUSD,XAUUSD,BTCUSD \
  --timeframes H1,M15 \
  --target "sharpe > 0.5" \
  --iterations 3
```

Full option set:

| Option | Default | Description |
|--------|---------|-------------|
| `--instruments` | `EURUSD` | Comma-separated list |
| `--timeframes` | `H1` | Comma-separated list |
| `--target` | `sharpe > 0.5` | `sharpe > N`, `return > N`, `win_rate > N`, `drawdown < N`, `pf > N` |
| `--iterations` | `3` | Max improvement iterations after baseline |
| `--constraints` | — | `min_sharpe=0.4,max_dd=20` — filter display table |
| `--data-dir` | `engine/data` | Parquet cache root |
| `--api-url` | `http://localhost:3001` | Lab API base URL |

Flow:
1. Runs baseline on all pairs
2. Diagnoses weaknesses, applies one structural change per iteration
3. Keeps improvements (≥ 2% threshold), reverts regressions
4. Posts all results to Lab → asks for human validation once at the end
5. Downloads missing data automatically before running

Results visible at `http://localhost:5173/lab` after the run.

---

## Architecture

```
Python engine (CLI)          Node.js API (Express)         React UI
─────────────────────        ─────────────────────         ─────────────────────
engine/run.py                api/src/server.ts             ui/src/App.tsx
engine/download.py           api/src/routes/              ui/src/components/
engine/src/backtest/         api/src/queue/ (BullMQ)      ui/src/hooks/
engine/src/optimization/     api/src/websocket/           ui/src/api/client.ts
engine/src/data/             api/src/db/                  ui/src/store/
```

```
CLI agents (LLM-driven):  run Python directly — no queue overhead
UI-submitted jobs:        POST /lab/sessions/:id/run → BullMQ → Worker → Python subprocess
                          → JSONL stdout → WebSocket → React ProgressPanel (live)
```

### Layer ownership — hard rules

| Layer | Owns | Must NOT |
|-------|------|----------|
| **Python engine** | Backtest, optimisation, metrics, SQLite writes | Serve HTTP, call external APIs, depend on Node/Redis |
| **Node.js API** | Job orchestration, LLM calls, WebSocket, SQLite reads | Run long compute, store state in memory |
| **React UI** | Rendering, client validation, WebSocket subscribe | Call Python directly, write to SQLite |

---

## Strategy lifecycle

```
[/new-strategy or Wizard] → strategies (DB, lifecycle_status=draft)
              │
              ▼ "Run in Lab" (StrategiesPage → POST /lab/sessions)
         lab_sessions (strategy_id FK)
              │
              ▼ promote result (PATCH /lab/results/:id/status)
         strategies.lifecycle_status updated automatically (atomic transaction)
              │
         draft → optimizing → validated → production_standard / production_aggressive / production_defensive
```

Strategy files on disk: `engine/strategies/{draft,optimizing,validated,production}/`

---

## `StrategyDefinition` v1 — canonical format

```json
{
  "version": "1",
  "name": "SuperTrend + RSI",
  "variant": "basic",
  "indicators": [
    { "name": "st_dir", "type": "supertrend_direction", "params": { "period": 10, "multiplier": 3.0 } },
    { "name": "rsi",    "type": "rsi",                  "params": { "period": 14 } }
  ],
  "entry_rules": [
    { "indicator": "st_dir", "condition": ">", "value": 0 },
    { "indicator": "rsi",    "condition": ">", "value": 50 }
  ],
  "exit_rules": [
    { "indicator": "st_dir", "condition": "<", "value": 0 }
  ],
  "position_management": {
    "size": 0.02,
    "sl_pips": null,
    "tp_pips": null,
    "max_open_trades": 1
  }
}
```

**Rule format:**

```json
{ "indicator": "<name>", "condition": ">|<|>=|<=|==|!=", "value": <number> }
{ "indicator": "<name>", "condition": ">|<|>=|<=",        "compare_to": "<other-indicator-name>" }
```

- `entry_rules` = AND conditions (all must be true to enter long)
- `exit_rules` = OR conditions (any one triggers close)
- `compare_to` must reference another `name` in `indicators` — NOT `"close"`

**Valid `indicator.type` values:**

```
sma  ema  macd  rsi  stoch  atr  bollinger_bands  adx  cci  obv  williamsr
supertrend  supertrend_direction
```

**`param_grid.json` structure** (for `/optimize`):

```json
{ "period": [10, 14, 20], "multiplier": [2.0, 3.0] }
```

Arrays = swept. Scalars = fixed. Keys must match indicator param names.

---

## Engine CLI reference

```bash
cd /Users/esantori/git/personal/algo-farm/engine && source .venv/bin/activate

# Single backtest
python run.py --strategy strategies/draft/my_strategy.json \
  --instruments EURUSD --timeframes H1 \
  --db /tmp/run.db --data-dir data

# Grid optimisation
python run.py --strategy strategies/draft/my_strategy.json \
  --instruments EURUSD --timeframes H1 \
  --param-grid strategies/draft/my_grid.json \
  --optimize grid --metric sharpe_ratio \
  --db /tmp/run.db --data-dir data

# Bayesian optimisation
python run.py ... --optimize bayesian --n-trials 50

# Download data (auto-called by skills when data is missing)
python download.py --instruments EURUSD,XAUUSD,BTCUSD \
  --timeframes H1,M15 \
  --from 2024-01-01 --to $(date +%Y-%m-%d) \
  --data-dir data
```

**Data file location:** `engine/data/<INSTRUMENT>/<TIMEFRAME>.parquet`
**Synthetic fixtures (committed):** `engine/tests/fixtures/data_cache/EURUSD/{H1,D1}.parquet` (500 bars)
**Supported instruments:** 34 total — forex majors/crosses, Gold, Silver, Brent, WTI, NatGas, Copper, US500, NAS100, GER40, UK100, JPN225, AUS200, 10 NASDAQ stocks, 33 crypto pairs (BTCUSD, ETHUSD …)
**Supported timeframes:** M1, M5, M10, M15, M30, H1, H4, D1, W1

### JSONL stdout protocol

```jsonl
{"type":"progress","pct":25,"current":{"instrument":"EURUSD","timeframe":"H1","iteration":3,"total":12},"elapsed_seconds":60}
{"type":"result","instrument":"EURUSD","timeframe":"H1","params":{"period":14},"metrics":{"sharpe_ratio":1.42,"max_drawdown":-0.12,"win_rate_pct":58.0,"total_trades":87,"profit_factor":1.65,"total_return_pct":18.5}}
{"type":"completed","total_runs":12,"best_params":{"period":14},"best_metrics":{...}}
```

Errors → stderr only. Exit codes: `0` = success, `1` = error, `2` = interrupted (resumable).

---

## Lab API quick reference

Base URL: `http://localhost:3001`

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/lab/sessions` | Create session |
| `GET` | `/lab/sessions` | List sessions |
| `GET` | `/lab/sessions/:id` | Session detail + results |
| `PATCH` | `/lab/sessions/:id/status` | Update status (`running`/`completed`/`failed`) |
| `POST` | `/lab/sessions/:id/results` | Add result |
| `POST` | `/lab/sessions/:id/run` | Enqueue backtest job (BullMQ) |
| `PATCH` | `/lab/results/:id/status` | Validate/promote/reject result |

Result status lifecycle: `pending → validated | rejected | production_standard | production_aggressive | production_defensive`

---

## Monorepo setup

```bash
# After fresh clone
pnpm install
pnpm rebuild better-sqlite3 esbuild

# Run API (port 3001)
pnpm --filter api dev

# Run UI (port 5173, proxies /api → 3001)
pnpm --filter ui dev

# Run tests
pnpm --filter api test          # 64 tests
cd engine && pytest tests -v    # 61 tests

# Redis required for BullMQ (UI-submitted jobs)
docker compose up -d
```

**env vars** (`api/.env`): `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `PORT=3001`, `DB_PATH=./algo_farm.db`, `REDIS_URL=redis://localhost:6379`, `PYTHON_BIN=/path/to/engine/.venv/bin/python`, `DATA_DIR=./engine/data`, `WORKER_CONCURRENCY=2`

---

## Testing quick reference

```bash
# Python engine — full suite
cd engine && source .venv/bin/activate
pytest tests -v --cov=src --cov-report=term-missing

# API — all tests (unit + integration)
pnpm --filter api test

# Type check
mypy engine/src --strict
```

---

## Code standards

- **Python:** type hints everywhere (mypy strict), Google-style docstrings, `snake_case`
- **TypeScript:** no `any`, strict mode, `camelCase` functions, `PascalCase` classes
- **Tests:** every new function has a unit test; every CLI flag has a contract test
- **Errors to stderr:** the engine never writes non-JSON to stdout
- **No secrets in code:** all config via env vars or CLI flags
- **Written artifacts always in English:** code, comments, docs, JSON, commit messages

---

## What NOT to do

- **Do not add HTTP endpoints to the Python engine.** It must remain CLI-only.
- **Do not use `"close"` as a `compare_to` value** in rules — it is not a valid indicator name. Use an EMA for price-vs-MA comparisons.
- **Do not write to stdout from the engine except JSONL.** All logging goes to stderr.
- **Do not commit large Parquet files.** Real data goes in `engine/data/` (gitignored).
- **Do not create a new file for a one-function addition.**
- **Do not skip tests.** CLI contract tests and unit tests are P0.
- **Do not use `execFileSync` or blocking subprocess calls** in the Node.js API — always use async `spawn` + Promise to avoid blocking the event loop and causing BullMQ lock expiry.

---

## Key documents

| Document | When to read |
|----------|-------------|
| `BACKLOG.md` | Milestones, status, known limitations |
| `docs/SCHEMA.md` | All contracts: CLI flags, JSONL protocol, SQLite DDL |
| `docs/ARCHITECTURE.md` | Layer boundaries, sequence diagrams |
| `docs/CONVENTIONS.md` | Naming, extension patterns, commit format |
| `docs/TESTING_STRATEGY.md` | Test philosophy, CI pipeline |
| `docs/API_SPEC.md` | REST API + CLI quick-reference |
| `Mission.md` | Original requirements — do not modify |
