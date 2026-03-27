Generate a new trading strategy JSON file from the user's natural language description and save it to `engine/strategies/draft/`.

**User input:** $ARGUMENTS

## Instructions

1. Parse the user's description and design a `StrategyDefinition` that matches their intent.

2. Use ONLY the supported schema:
   - **Indicators:** `sma`, `ema`, `macd`, `rsi`, `stoch`, `atr`, `bollinger_bands`, `momentum`, `adx`, `cci`, `obv`, `williamsr`, `supertrend`, `supertrend_direction`
   - **Conditions:** `>`, `<`, `>=`, `<=`, `crosses_above`, `crosses_below`
   - **Rule format:** `{"indicator": "<name>", "condition": "<cond>", "value": <number>}` OR `{"indicator": "<name>", "condition": "<cond>", "compare_to": "<other_indicator_name>"}`
   - **version:** always `"1"`, **variant:** `"basic"` (default) or `"advanced"`

3. Important constraints:
   - Every indicator referenced in rules MUST be declared in `indicators[]` with a unique `name`
   - `compare_to` references must match an existing indicator `name` — `"close"` is NOT valid
  - `entry_rules` use AND logic (all conditions must be true)
  - `exit_rules` use OR logic (any condition can trigger exit)
   - `value` and `compare_to` are mutually exclusive per rule

4. Derive a snake_case filename from the strategy name (e.g., `rsi_reversal_adx.json`).

5. Show the complete JSON to the user and ask for confirmation before saving.

6. Save the confirmed file to `engine/strategies/draft/<filename>.json` using the Write tool.

7. **Register the strategy in the API database** so it is visible in the UI:

   ```bash
   curl -s --max-time 3 http://localhost:3001/health
   ```

   If the API is reachable, register the strategy:
   ```bash
   curl -s -X POST http://localhost:3001/strategies \
     -H "Content-Type: application/json" \
     -d '<escaped-strategy-json>'
   ```

   Extract `id` from the response and print:
   ```
   Strategy registered in DB: <id>
   Use --strategy-id <id> in future /iterate, /optimize, /strategy-lab calls
   ```

   If the API is not reachable, skip silently (file is saved, register later when API is up).

8. Suggest the next step:
   ```
   Strategy saved. Run a backtest with:
   /backtest engine/strategies/draft/<filename>.json
   ```

## Example output format

```json
{
  "version": "1",
  "name": "RSI Reversal with ADX Filter",
  "variant": "basic",
  "indicators": [
    { "name": "rsi14",  "type": "rsi", "params": { "period": 14 } },
    { "name": "adx14",  "type": "adx", "params": { "period": 14 } }
  ],
  "entry_rules": [
    { "indicator": "rsi14", "condition": "<",  "value": 30 },
    { "indicator": "adx14", "condition": ">",  "value": 25 }
  ],
  "exit_rules": [
    { "indicator": "rsi14", "condition": ">",  "value": 70 }
  ],
  "position_management": {
    "size": 0.02,
    "sl_pips": null,
    "tp_pips": null,
    "max_open_trades": 1
  }
}
```
