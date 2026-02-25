# Algo Farm — Engine

Standalone Python backtest and optimisation engine. No Node.js, Redis, or Docker required.
Designed to be driven from the CLI, a terminal, or an AI agent in an automated loop.

**stdout → pure JSONL. stderr → logs. exit 0/1/2.**

---

## Prerequisites

- Python 3.11+ (tested on 3.13)
- `pip` or any other Python package manager

Check your version:

```bash
python3 --version
```

---

## Onboarding (first time)

```bash
# 1. Enter the engine directory
cd engine

# 2. Create the virtual environment
python3 -m venv .venv

# 3. Activate it
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate           # Windows

# 4. Install dependencies
pip install -r requirements.txt

# 5. Generate synthetic test data (required by the test suite)
python tests/fixtures/generate_fixtures.py
```

Done. The environment is ready.

---

## Running the tests

```bash
# Full suite (unit + integration + CLI contract)
pytest

# Unit tests only (fast, no external dependencies)
pytest tests/unit -v

# Integration tests only (BacktestRunner against fixture data)
pytest tests/integration -v

# CLI contract tests only (spawns the real process via subprocess)
pytest tests/cli -v

# With coverage report
pytest --cov=src --cov-report=term-missing
```

Expected result: **55 passed**, coverage ≥ 90%.

---

## Running a backtest / optimisation

### Minimal command

```bash
python run.py \
  --strategy   <path/to/strategy.json> \
  --instruments EURUSD \
  --timeframes  H1 \
  --db          ./algo_farm.db \
  --data-dir    ./data/cache
```

### With grid search

```bash
python run.py \
  --strategy    tests/fixtures/simple_sma_strategy.json \
  --instruments EURUSD,GBPUSD \
  --timeframes  H1,D1 \
  --param-grid  tests/fixtures/simple_param_grid.json \
  --metric      sharpe_ratio \
  --db          ./algo_farm.db \
  --data-dir    tests/fixtures
```

### Resuming an interrupted job

```bash
# The job_id appears in every JSONL message (field "job_id")
python run.py \
  --strategy    tests/fixtures/simple_sma_strategy.json \
  --instruments EURUSD \
  --timeframes  H1 \
  --param-grid  tests/fixtures/simple_param_grid.json \
  --db          ./algo_farm.db \
  --data-dir    tests/fixtures \
  --resume-job  <job-uuid>
```

### All available flags

| Flag | Required | Default | Description |
|------|:---:|---------|-------------|
| `--strategy` | yes | — | Path to the strategy JSON file |
| `--instruments` | yes | — | Comma-separated instruments (`EURUSD,GBPUSD`) |
| `--timeframes` | yes | — | Comma-separated timeframes (`H1,D1`) |
| `--db` | yes | — | Path to the SQLite database file (created if missing) |
| `--data-dir` | yes | — | Root directory for OHLCV Parquet files |
| `--param-grid` | no | `{}` | Path to the param grid JSON file |
| `--optimize` | no | `grid` | Optimisation method (`grid`) |
| `--metric` | no | `sharpe_ratio` | Metric to optimise for |
| `--resume-job` | no | — | UUID of the job to resume |
| `--log-level` | no | `INFO` | Log level on stderr (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

---

## JSONL output

Everything written to **stdout** is newline-delimited JSON. Three message types:

```jsonc
// Progress (emitted after each parameter combination)
{"type": "progress", "job_id": "...", "pct": 45, "current": {"instrument": "EURUSD", "timeframe": "H1", "iteration": 5, "total": 12}, "elapsed_seconds": 12.3}

// Result of a single combination
{"type": "result", "job_id": "...", "instrument": "EURUSD", "timeframe": "H1", "params": {"period": 20}, "metrics": {...}, "run_id": "..."}

// Job completed
{"type": "completed", "job_id": "...", "best_params": {...}, "best_metrics": {...}, "db_path": "./algo_farm.db"}
```

**Exit codes:** `0` = success, `1` = error, `2` = interrupted (resumable via `--resume-job`).

---

## Strategy format (`strategy.json`)

```json
{
  "version": "1",
  "name": "SMA Crossover",
  "variant": "basic",
  "indicators": [
    { "name": "fast_sma", "type": "sma", "params": { "period": 10 } },
    { "name": "slow_sma", "type": "sma", "params": { "period": 30 } }
  ],
  "entry_rules": [
    { "indicator": "fast_sma", "condition": "crosses_above", "compare_to": "slow_sma" }
  ],
  "exit_rules": [
    { "indicator": "fast_sma", "condition": "crosses_below", "compare_to": "slow_sma" }
  ],
  "position_management": {
    "size": 0.02,
    "sl_pips": null,
    "tp_pips": null,
    "max_open_trades": 1
  }
}
```

**Supported indicators:** `sma`, `ema`, `macd`, `rsi`, `stoch`, `atr`, `bollinger_bands`, `adx`, `cci`, `obv`, `williamsr`

**Supported conditions:** `>`, `<`, `>=`, `<=`, `crosses_above`, `crosses_below`

---

## Param grid format (`param_grid.json`)

```json
{
  "period": [10, 20, 30],
  "commission": 0.0002
}
```

- **Array** → swept parameter: generates N combinations
- **Scalar** → fixed parameter: same value across all combinations

---

## OHLCV data layout

Parquet files must follow this directory structure:

```
<data-dir>/
└── <INSTRUMENT>/
    └── <TIMEFRAME>.parquet
```

Example: `./data/cache/EURUSD/H1.parquet`

Required columns: `open`, `high`, `low`, `close` (case-insensitive). `volume` is optional.
The index must be datetime or datetime-castable.

---

## Project structure

```
engine/
├── run.py                          # CLI entry point
├── pyproject.toml                  # mypy, pytest, black configuration
├── requirements.txt
├── src/
│   ├── models.py                   # Pydantic: StrategyDefinition, BacktestMetrics
│   ├── metrics.py                  # calculate_metrics() — 11 metrics
│   ├── utils.py                    # setup_logging(), load_ohlcv()
│   ├── backtest/
│   │   ├── runner.py               # BacktestRunner.run()
│   │   ├── strategy.py             # StrategyComposer — builds classes at runtime
│   │   └── indicators/             # Pure NumPy functions + IndicatorRegistry
│   ├── optimization/
│   │   └── grid_search.py          # GridSearchOptimizer (itertools.product)
│   └── storage/
│       └── db.py                   # SQLite: JobRepo, RunRepo, ErrorLogRepo
└── tests/
    ├── conftest.py                 # Shared fixtures (synthetic_ohlcv, in_memory_db)
    ├── cli/                        # Subprocess tests — JSONL contract and exit codes
    ├── unit/                       # Metrics, indicators, storage, utils
    ├── integration/                # BacktestRunner against real Parquet data
    └── fixtures/
        ├── generate_fixtures.py    # One-time script to generate synthetic data
        ├── simple_sma_strategy.json
        ├── simple_param_grid.json
        └── data_cache/EURUSD/      # H1.parquet and D1.parquet (committed to git)
```

---

## Computed metrics

| Field | Description |
|-------|-------------|
| `total_return_pct` | Total return over the period (%) |
| `sharpe_ratio` | Annualised Sharpe ratio |
| `sortino_ratio` | Annualised Sortino ratio (downside deviation only) |
| `calmar_ratio` | CAGR / \|max drawdown\| |
| `max_drawdown_pct` | Maximum drawdown (%, negative value) |
| `win_rate_pct` | Percentage of trades closed in profit |
| `profit_factor` | Gross profit / Gross loss |
| `total_trades` | Total number of closed trades |
| `avg_trade_duration_bars` | Average trade duration in bars |
| `cagr_pct` | Annualised CAGR (%) |
| `expectancy` | Average PnL per trade |
