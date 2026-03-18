Run the Algo Farm backtest engine for a strategy file and display a formatted results table.

**Arguments:** $ARGUMENTS
(format: `<strategy-file> [--instruments EURUSD,GBPUSD] [--timeframes H1,D1] [--is-end 2023-12-31] [--full]`)

## IS/OOS convention

By default all backtests run on **in-sample data only** (2022-01-01 → `is_end`).
This prevents contaminating the OOS holdout period used by `/robustness`.

- `--is-end <date>`: last day of the IS window (default: `2023-12-31`)
- `--full`: skip date filtering, use all available data (use only for exploration)

## Instructions

1. Parse the arguments:
   - `strategy-file`: required. If no path separator, look in `engine/strategies/draft/` first, then `engine/tests/fixtures/`.
   - `--instruments`: comma-separated list, default `EURUSD`
   - `--timeframes`: comma-separated list, default `H1`
   - `--is-end`: default `2023-12-31`
   - `--full`: if present, omit `--date-from` / `--date-to` from the engine call

2. Verify the strategy file exists. If not found, tell the user and stop.

3. Run the backtest using the Bash tool:
   ```bash
   cd /Users/esantori/git/personal/algo-farm/engine && \
   source .venv/bin/activate && \
   python run.py \
     --strategy <strategy-file> \
     --instruments <instruments> \
     --timeframes <timeframes> \
     --db /tmp/backtest_$(date +%s).db \
     --data-dir data \
     --date-from 2022-01-01 \
     --date-to <is_end> \
     2>/dev/null
   ```
   If `--full` was passed, omit `--date-from` and `--date-to`.

4. Parse every JSONL line from stdout:
   - `{"type":"progress", ...}` → show a progress indicator
   - `{"type":"result", ...}` → collect metrics per instrument/timeframe
   - `{"type":"completed", ...}` → extract best_params and best_metrics

5. Display a formatted table (show IS window in header):
   ```
   Strategy: <name>  [IS: 2022-01-01 → 2023-12-31]
   ─────────────────────────────────────────────────────────────────────
   Instrument  Timeframe  Trades  Sharpe   Return    Win%    MaxDD
   ─────────────────────────────────────────────────────────────────────
   EURUSD      H1         42      1.84     +12.3%    61.0%   -4.2%
   ─────────────────────────────────────────────────────────────────────
   ```

6. Diagnose common issues:
   - `total_trades == 0`: warn that entry conditions may never be satisfied. Common causes: `compare_to` with `>/<` on different-period SMAs, or `crosses_above` with a `value` threshold that is never reached on IS data.
   - `win_rate == 0%` and `return < 0`: strategy is working but systematically losing — likely inverted signal.
   - `sharpe < 0`: suggest trying `/iterate` to improve.

7. Suggest next steps based on results:
   - Good results (sharpe > 0.5): → `/optimize` to find best parameters, then `/robustness` to validate OOS
   - Poor results: → `/iterate` to improve the strategy autonomously
