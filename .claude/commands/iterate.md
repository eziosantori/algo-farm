Autonomously improve a trading strategy through repeated backtest → analyze → modify cycles.

**Arguments:** $ARGUMENTS
(format: `<strategy-file> [--target "sharpe > 1.5"] [--iterations 5]`)

## Instructions

1. Parse arguments:
   - `strategy-file`: required. Resolved from `engine/strategies/draft/` if not absolute.
   - `--target`: improvement goal as a string expression, default `"sharpe > 1.0"`. Supported targets: `sharpe > N`, `return > N`, `win_rate > N`, `drawdown < N`
   - `--iterations`: max iterations, default `5`

2. Read the current strategy JSON. Keep the original as `<name>_v0.json` (backup).

3. For each iteration (1 to N):

   a. **Run backtest** using the engine:
      ```bash
      cd /Users/esantori/git/personal/algo-farm/engine && \
      source .venv/bin/activate && \
      python run.py \
        --strategy <strategy-file> \
        --instruments EURUSD \
        --timeframes H1 \
        --db /tmp/iterate_<iter>_$(date +%s).db \
        --data-dir data \
        2>/dev/null
      ```
      If the data file is missing (`data/EURUSD/H1.parquet` not found), download it first:
      ```bash
      cd /Users/esantori/git/personal/algo-farm/engine && \
      source .venv/bin/activate && \
      python download.py --instruments EURUSD --timeframes H1 \
        --from 2024-01-01 --to $(date +%Y-%m-%d) --data-dir data
      ```

   b. **Parse metrics** from the `completed` JSONL message.

   c. **Check target:** if met, stop and report success.

   d. **Diagnose and propose ONE focused change** based on the worst metric:

      | Problem | Diagnosis | Proposed change |
      |---------|-----------|-----------------|
      | `total_trades == 0` | Entry never fires | Relax entry rules: remove one condition, or lower period of a fast indicator |
      | `total_trades < 5` | Entry too restrictive | Widen value thresholds (e.g., RSI < 35 instead of < 30) |
      | `win_rate < 40%` | Signal is reversed | Swap entry/exit conditions, or invert the trend filter |
      | `win_rate > 60%` but low return | Trades too short / TP too tight | Increase `tp_pips` or relax exit rule |
      | `max_drawdown < -15%` | No loss protection | Add `sl_pips` to position management |
      | `sharpe < 0` | Strategy losing consistently | Try opposite direction (sell instead of buy) or completely revise entry |
      | `profit_factor < 1` | Losses outweigh gains | Tighten entry (add confirming indicator), add SL |

   e. **Apply the change** to the strategy JSON (use Edit tool on the file).

   f. **Report progress:**
      ```
      Iter 2/5 | Sharpe: 0.91 → 1.34 | Trades: 9 → 18 | Target: sharpe > 1.5
      Change: Relaxed RSI threshold from 30 to 35
      ```

4. **Final report** — show before/after comparison:
   ```
   Iteration complete (3/5 iterations used)
   ──────────────────────────────────────────
   Metric          Before    After     Change
   Sharpe          -6.40     1.34      +7.74
   Return          -2.66%    +8.12%    +10.78pp
   Win rate        0.0%      57.0%     +57pp
   Max drawdown    -2.67%    -3.10%    -0.43pp
   Trades          9         21        +12
   ──────────────────────────────────────────
   Target (sharpe > 1.5): NOT YET MET — run /iterate again or /optimize to fine-tune params
   ```

5. Save the final version as `engine/strategies/draft/<name>_v<N>.json`.

6. **Save results to Lab** so they are visible in the UI (`http://localhost:5173/lab`):

   Check if the API is reachable:
   ```bash
   curl -s --max-time 3 http://localhost:3001/health
   ```
   If reachable, create a Lab session and post the final result:
   ```bash
   # Create session
   curl -s -X POST http://localhost:3001/lab/sessions \
     -H "Content-Type: application/json" \
     -d '{"strategy_name": "<name>", "strategy_json": "<escaped-final-json>", "instruments": ["EURUSD"], "timeframes": ["H1"]}'
   # Post final result (extract session_id from above response)
   curl -s -X POST http://localhost:3001/lab/sessions/<session_id>/results \
     -H "Content-Type: application/json" \
     -d '{"instrument": "EURUSD", "timeframe": "H1", "params_json": "{}", "metrics_json": "<escaped-final-metrics>"}'
   # Mark session completed
   curl -s -X PATCH http://localhost:3001/lab/sessions/<session_id>/status \
     -H "Content-Type: application/json" \
     -d '{"status": "completed"}'
   ```
   If API is not reachable, skip silently (results are already saved to file).

7. If target is met, suggest: "Consider running `/optimize` to find the best parameters for this improved strategy."
