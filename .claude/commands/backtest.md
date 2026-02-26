Run the Algo Farm backtest engine for a strategy file and display a formatted results table.

**Arguments:** $ARGUMENTS
(format: `<strategy-file> [--instruments EURUSD,GBPUSD] [--timeframes H1,D1]`)

## Instructions

1. Parse the arguments:
   - `strategy-file`: required. If no path separator, look in `engine/strategies/draft/` first, then `engine/tests/fixtures/`.
   - `--instruments`: comma-separated list, default `EURUSD`
   - `--timeframes`: comma-separated list, default `H1`

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
     --data-dir tests/fixtures/data_cache \
     2>/dev/null
   ```

4. Parse every JSONL line from stdout:
   - `{"type":"progress", ...}` → show a progress indicator
   - `{"type":"result", ...}` → collect metrics per instrument/timeframe
   - `{"type":"completed", ...}` → extract best_params and best_metrics

5. Display a formatted table:
   ```
   Strategy: <name>
   ─────────────────────────────────────────────────────────────────────
   Instrument  Timeframe  Trades  Sharpe   Return    Win%    MaxDD
   ─────────────────────────────────────────────────────────────────────
   EURUSD      H1         42      1.84     +12.3%    61.0%   -4.2%
   ─────────────────────────────────────────────────────────────────────
   ```

6. Diagnose common issues:
   - `total_trades == 0`: warn that entry conditions may never be satisfied. Common causes: `compare_to` with `>/<` on different-period SMAs (the M7 bug is fixed, but logic may still not trigger on synthetic data). Suggest inspecting entry rules or reducing indicator periods.
   - `win_rate == 0%` and `return < 0`: strategy is working but systematically losing — likely inverted signal.
   - `sharpe < 0`: suggest trying `/iterate` to improve.

7. Suggest next steps based on results:
   - Good results (sharpe > 1): → `/optimize` to find best parameters
   - Poor results: → `/iterate` to improve the strategy autonomously
