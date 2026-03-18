Run grid search optimization for a strategy and display results ranked by metric.

**Arguments:** $ARGUMENTS
(format: `<strategy-file> [--metric sharpe_ratio] [--instruments EURUSD] [--timeframes H1] [--is-end 2023-12-31]`)

## IS/OOS convention

Optimization runs on **in-sample data only** (2022-01-01 → `is_end`).
The OOS period (2024-01-01 onward) is never touched here — it is reserved for `/robustness`.

## Instructions

1. Parse arguments:
   - `strategy-file`: required. Resolved same as `/backtest`.
   - `--metric`: optimization target, default `sharpe_ratio`. Supported: `sharpe_ratio`, `calmar_ratio`, `profit_factor`
   - `--instruments`: default `EURUSD`
   - `--timeframes`: default `H1`
   - `--is-end`: last day of IS window, default `2023-12-31`

2. Read the strategy JSON file to understand which indicators and params it uses.

3. **Param grid design:**
   Propose a param grid based on the strategy's indicators. Ask the user to confirm or adjust ranges before running.

   **Known limitation — param key collision:** The engine applies the same swept value to ALL indicators sharing the same param key (e.g., `"period"`). Warn the user if the strategy has multiple indicators with `"period"`. For multi-indicator strategies, suggest running separate single-indicator optimizations or sweeping rule threshold values directly.

   Example grid for an RSI strategy:
   ```json
   { "period": [7, 10, 14, 21, 28] }
   ```

4. Save the grid to `engine/strategies/optimizing/<strategy-name>_grid.json`.

5. Copy the strategy file to `engine/strategies/optimizing/<strategy-name>.json` if it's currently in `draft/`.

6. Run the optimization (IS data only):
   ```bash
   cd /Users/esantori/git/personal/algo-farm/engine && \
   source .venv/bin/activate && \
   python run.py \
     --strategy engine/strategies/optimizing/<strategy-name>.json \
     --param-grid engine/strategies/optimizing/<strategy-name>_grid.json \
     --instruments <instruments> \
     --timeframes <timeframes> \
     --metric <metric> \
     --db /tmp/optimize_$(date +%s).db \
     --data-dir data \
     --date-from 2022-01-01 \
     --date-to <is_end> \
     2>/dev/null
   ```

7. Parse JSONL and collect all `result` messages. Display ranked table:
   ```
   Optimization: <strategy-name> | Metric: sharpe_ratio | IS: 2022-01-01 → 2023-12-31
   ──────────────────────────────────────────────────────────────────
    #  Period  Sharpe   Return    Win%    Trades  MaxDD
   ──────────────────────────────────────────────────────────────────
    1  14      1.84     +12.3%    61.0%   42      -4.2%   ← BEST
    2  21      1.62     +9.1%     58.0%   38      -3.8%
    3  10      1.41     +7.8%     55.0%   51      -5.1%
   ──────────────────────────────────────────────────────────────────
   ```

8. Update the strategy JSON with the best params found (modify the indicator `params` in-place).

9. Suggest next steps: "Run `/robustness` to validate these params on OOS data (2024) before promoting."
