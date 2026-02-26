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
        --data-dir tests/fixtures/data_cache \
        2>/dev/null
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

6. If target is met, suggest: "Consider running `/optimize` to find the best parameters for this improved strategy."
