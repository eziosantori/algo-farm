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

## Autonomous Workflow Agent

The `workflow-orchestrator` agent runs the **full strategy development lifecycle autonomously**
— from baseline backtest to robustness validation — with minimal user interaction.
It is defined in `.claude/agents/workflow-orchestrator.md` and uses a dedicated
`strategy-analyst` sub-agent (`.claude/agents/strategy-analyst.md`) for iteration decisions.

### When to use it

Use the workflow agent when you want to go from a draft strategy to `validated` in one shot,
without manually running `/iterate`, `/optimize`, and `/robustness` sequentially.
Use the individual skills (below) when you want fine-grained control over a single phase.

### Prerequisites

```bash
# 1. Start the API (required — agent auto-starts it if unreachable)
pnpm --filter api dev

# 2. Engine venv must exist
cd engine && python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt

# 3. Data is downloaded automatically for missing pairs
```

### Starting a session

Open Claude Code from the project root, then @-mention the agent:

```
@workflow-orchestrator ema_crossover_rsi_filter_iter3.json \
  --goal "sharpe > 0.8" \
  --instruments XAUUSD,GBPUSD,GER40 \
  --timeframes H1,H4 \
  --iterations 3
```

Full option reference:

| Option | Default | Description |
|--------|---------|-------------|
| `<strategy-file>` | required | Path or name in `engine/strategies/draft/` |
| `--goal` | `sharpe > 0.5` | Target: `sharpe > N`, `return > N`, `win_rate > N`, `drawdown < N`, `pf > N` |
| `--instruments` | `EURUSD` | Comma-separated list |
| `--timeframes` | `H1` | Comma-separated list |
| `--iterations` | `3` | Max improvement iterations |
| `--is-end` | `2023-12-31` | Last day of in-sample window (OOS starts next day) |

### What the agent does automatically

| Phase | What happens | User input needed? |
|-------|-------------|-------------------|
| **Prerequisites** | Health check, auto-start API, download missing data, register strategy | No |
| **1 — Baseline** | IS backtest on all pairs, post results to Lab | No |
| **2 — Iterate** | Up to N diagnosis → propose → test → keep/revert cycles | No |
| **3 — Optimize** | Grid search on best variant, apply best params | No |
| **4 — Robustness** | IS baseline + OOS + Walk-Forward + Monte Carlo, robustness table | **YES — promote or keep?** |
| **5 — Done** | Mark sessions completed, print final summary | No |

### Human interaction points

The agent pauses **once**, after the robustness report:

```
Robustness gate: PASS (2/3 pairs)
...table...

What would you like to do?
  promote   — move to validated/ and update lifecycle_status
  keep      — stay in optimizing/ (run /robustness again after tweaks)
  reject    — archive this variant
```

Type `promote`, `keep`, or `reject`.

### IS/OOS convention

- **In-sample (IS):** `2022-01-01` → `is_end` (default `2023-12-31`) — all iteration and optimization runs
- **Out-of-sample (OOS):** `oos_start` (day after `is_end`) → end of available data — touched ONLY in phase 4
- The OOS holdout is never used during iteration or optimization to prevent data leakage

### Viewing results

All Lab sessions and results are recorded in the API database and visible in the UI:

- Lab sessions: `http://localhost:5173/lab`
- Strategies: `http://localhost:5173/strategies`

---

## Quick start for agents — use the skills

Claude Code slash commands are the fastest way to work with strategies **one phase at a time**.
Run them from the project root (`/Users/esantori/git/personal/algo-farm`).

### `/design-strategy "<description>" [--instruments X,Y] [--timeframes H1,H4] [--target "sharpe > 1.0"]`

**Multi-agent Strategy Design Board** — thorough analysis before creation.

Runs 5 specialist subagents (technical analyst, market-structure analyst, risk analyst, advocate, critic) that debate the idea before a Sonnet composer synthesizes the final JSON. Blocking issues are resolved through up to 2 debate rounds.

```
/design-strategy "RSI mean-reversion with SuperTrend filter for XAUUSD H1" \
  --instruments XAUUSD --timeframes H1,H4 --target "sharpe > 0.8"
```

Saves:
- Strategy: `engine/strategies/draft/<name>.json`
- Design report: `docs/ideas/strategies/<name>_design.md` — full discussion + ready-to-run `@workflow-orchestrator` prompt

**Use this when:** the strategy is non-trivial, multi-instrument, or you want indicator/risk design reviewed before spending backtest time.

| Option | Default | Description |
|--------|---------|-------------|
| `--instruments` | `EURUSD` | Comma-separated list |
| `--timeframes` | `H1` | Comma-separated list |
| `--target` | `sharpe > 0.5` | Performance goal passed to advocate/critic |

Agent calls: 6 (standard) or 8 (with debate Round 2). Estimated cost: $0.03–0.10.

---

### `/new-strategy <description>`

Generate a valid `StrategyDefinition` JSON from natural language — **quick, single-shot**.

```
/new-strategy "RSI mean-reversion: buy when RSI < 30 and SuperTrend is up, exit when RSI > 70"
```

Saves to `engine/strategies/draft/<name>.json`. Use this for simple strategies or rapid prototyping. Use `/design-strategy` for thorough multi-perspective analysis.

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

## Candlestick pattern design principles

Empirically validated on 7 US stocks (D1) across 10+ iterations (Phase D integration tests).

### How patterns interact with entry triggers

On D1/H4, a breakout trigger (e.g. Bollinger cross) and a bullish pattern (marubozu, three white soldiers) **rarely coincide on the same bar**. Using patterns as positive AND conditions in `entry_rules` consistently collapses trade frequency — sometimes to 0.

**Three roles patterns can play:**

| Role | How to implement | Effect |
|------|-----------------|--------|
| **Anti-filter (negative AND)** | `{"indicator":"doji14","condition":"<","value":0.2}` | ✅ Blocks indecision bars without killing frequency |
| **Sizing driver** | `risk_pct_min`/`risk_pct_max` + `risk_pct_group` → `PatternGroup` | ✅ Amplifies winners, no frequency cost |
| **Positive AND filter** | `{"indicator":"marub","condition":">","value":0.0}` | ❌ Severe trade reduction on D1/H4 |

**`TriggerHold` does NOT fix the timing mismatch** for positive AND patterns. Even with a 3–5 bar hold window, `marub > 0` remains too restrictive on daily data.

**Recommended pattern wiring for breakout strategies:**

```json
"entry_rules": [
  { "indicator": "px",      "condition": "crosses_above", "compare_to": "bbu" },
  { "indicator": "doji14",  "condition": "<", "value": 0.2 },
  { "indicator": "harami14","condition": "<", "value": 0.2 }
],
"pattern_groups": [{ "name": "bull_confirm", "patterns": ["marub", "soldiers"] }],
"position_management": {
  "risk_pct_min": 0.005, "risk_pct_max": 0.02,
  "risk_pct_group": "bull_confirm"
}
```

Negative patterns filter bad setups. Positive patterns scale position size. Neither reduces trade count.

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
