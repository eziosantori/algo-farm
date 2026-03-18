Autonomously improve a strategy across multiple assets and timeframes using LLM-driven iteration.
Runs a baseline, proposes structural improvements (new indicators, filters, rule changes), tests each
variant on all instrument × timeframe combinations, keeps improvements that beat the baseline,
and stores all results in the Strategy Lab. Requires minimal user interaction — only final validation.

**Arguments:** $ARGUMENTS
(format: `<strategy-file-or-id> [--strategy-id <uuid>] [--instruments EURUSD,XAUUSD,BTCUSD] [--timeframes H1,M15] [--target "sharpe > 0.5"] [--iterations 3] [--constraints "min_sharpe=0.4,max_dd=20"] [--is-end 2023-12-31] [--data-dir engine/data] [--api-url http://localhost:3001]`)

---

## IS/OOS convention

All baseline and iteration backtests run on **in-sample data only** (2022-01-01 → `is_end`).
The OOS holdout (2024-01-01 onward) is never touched here — run `/robustness` after this skill.

The Lab session stores `is_start` / `is_end` so the UI can show which period was used.
Results are tagged `split = "is"` in the database.

---

## Instructions

### Step 1 — Parse arguments

- `strategy-file`: path to strategy JSON. Resolve relative names from `engine/strategies/draft/` first, then `engine/tests/fixtures/`. May be omitted if `--strategy-id` is provided.
- `--strategy-id <uuid>`: UUID of a strategy already saved in the API database. When provided, the strategy is fetched from the API instead of a local file.
- `--instruments`: comma-separated list, default `EURUSD`
- `--timeframes`: comma-separated list, default `H1`
- `--target`: improvement goal, default `"sharpe > 0.5"`. Supported: `sharpe > N`, `return > N`, `win_rate > N`, `drawdown < N`, `pf > N` (profit factor)
- `--iterations`: max improvement iterations after baseline, default `3`
- `--constraints`: comma-separated `key=value` pairs for final table display (e.g. `min_sharpe=0.4,max_dd=20`)
- `--is-end`: last day of IS window, default `2023-12-31`
- `--data-dir`: OHLCV data cache, default `engine/data`
- `--api-url`: default `http://localhost:3001`

Parse constraints into a JSON object: `{"min_sharpe": 0.4, "max_dd": 20}`.
Set `is_start = "2022-01-01"`, `is_end = <parsed or default>`.

### Step 2 — Verify and load

1. Check API is reachable (required for strategy-lab):
   ```bash
   curl -s --max-time 3 <api-url>/health
   ```
   If unreachable: tell the user to run `pnpm --filter api dev`, then stop.

2. Load strategy:

   **Case A — `--strategy-id <uuid>` provided:**
   ```bash
   curl -s <api-url>/strategies/<uuid>
   ```
   Extract the `definition` field. Write it to `engine/strategies/draft/<name>.json`.
   Set `strategy_id = <uuid>`.

   **Case B — file path provided:**
   Read the strategy JSON with the Read tool. If not found, stop.

   Then resolve `strategy_id`: call `GET <api-url>/strategies`, filter by `name` matching exactly.
   - If found: `strategy_id = <id>` (and optionally PUT to sync the file version)
   - If not found: register now:
     ```bash
     curl -s -X POST <api-url>/strategies \
       -H "Content-Type: application/json" \
       -d '<escaped-strategy-json>'
     ```
     Set `strategy_id` from the returned `id`.

3. Keep the original strategy JSON as `baseline_strategy`. Working copy = `current_strategy` (same content initially).

### Step 3 — Create Lab session linked to the strategy

```bash
curl -s -X POST <api-url>/lab/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "<name>",
    "strategy_json": <strategy-json>,
    "instruments": [...],
    "timeframes": [...],
    "constraints": <obj-or-null>,
    "strategy_id": "<strategy_id>",
    "is_start": "2022-01-01",
    "is_end": "<is_end>"
  }'
```

Extract `session_id`. Report: `Lab session: <session_id> | Strategy: <strategy_id> | IS: 2022-01-01 → <is_end>`

### Step 3b — Download missing data

Before running any backtest, check which (instrument, timeframe) pairs are missing from `--data-dir`.
For each missing pair, download it:
```bash
cd /Users/esantori/git/personal/algo-farm/engine && \
source .venv/bin/activate && \
python download.py \
  --instruments <missing-instruments> \
  --timeframes <missing-timeframes> \
  --from 2022-01-01 --to 2024-12-31 \
  --data-dir <data-dir>
```
A file is present if `<data-dir>/<INSTRUMENT>/<TIMEFRAME>.parquet` exists.
If download fails for an instrument, skip it and continue with available data.

### Step 4 — Baseline run

Run the engine for **every (instrument × timeframe)** pair using `current_strategy`:

```bash
cd /Users/esantori/git/personal/algo-farm/engine && \
source .venv/bin/activate && \
python run.py \
  --strategy <strategy-file> \
  --instruments <instrument> \
  --timeframes <timeframe> \
  --db /tmp/lab_<instrument>_<timeframe>_$(date +%s).db \
  --data-dir <data-dir> \
  --date-from 2022-01-01 \
  --date-to <is_end> \
  2>/dev/null
```

For each result line (`"type": "result"`): POST to Lab with `split = "is"` and collect metrics.

Compute **score** = average of the target metric across all successful pairs (e.g. if target is `sharpe > 0.5`, score = mean Sharpe across all pairs).

Print baseline summary:
```
Baseline: <strategy_name>
  Mean Sharpe: 0.30 | Mean Return: +165% | Mean DD: -21%
  [1/2] BTCUSD H1  → Sharpe: 0.30 | Return: +197% | DD: -24.7% | Trades: 192
  [2/2] BTCUSD M15 → Sharpe: 0.12 | Return: +129% | DD: -17.2% | Trades: 827
```

### Step 5 — Autonomous improvement loop

Repeat up to `--iterations` times. **Do not ask the user for approval between iterations.**

#### 5a — Diagnose weaknesses

Analyze the metrics from the current best run across ALL pairs. Identify the primary bottleneck using this priority order:

| Condition | Diagnosis | Proposed change |
|-----------|-----------|-----------------|
| Any pair: `total_trades == 0` | Entry never fires | Relax most restrictive entry rule (lower RSI threshold, remove one condition) |
| Mean `win_rate < 35%` | Too many false entries (noise/whipsaw) | Add trend confirmation: EMA cross filter (`ema_fast > ema_slow`), or tighten RSI entry |
| Mean `win_rate > 60%` but `return < target` | Exits too early; winners cut short | Remove RSI exit rule if present; increase ST multiplier by 0.5 |
| Mean `max_drawdown < −20%` | Slow exit during reversals | Shorten ST period by 2–3 bars (faster response), or add RSI exit at < 40 |
| Mean `sharpe < 0.3` and `total_trades > 200/TF` | Overtrading (too much noise) | Raise RSI entry threshold (50→55→60), or add EMA trend filter |
| `profit_factor < 1.2` | Losses outweigh gains | Add/tighten trend filter, increase ST multiplier to reduce whipsawing |
| Mean `sharpe` already near target | Fine-tune | Try tightening multiplier by ±0.5 or RSI threshold by ±5 |

Pick the **single most impactful change**. Apply it to produce `candidate_strategy`.

#### 5b — Apply the change

Use the Edit or Write tool to write `candidate_strategy` to a temp file:
`engine/strategies/draft/<name>_iter<N>.json`

Changes you can make autonomously (examples):
- Add an indicator: `{"name": "ema50", "type": "ema", "params": {"period": 50}}`
- Add an entry rule: `{"indicator": "ema10", "condition": ">", "compare_to": "ema50"}`
- Add an exit rule: `{"indicator": "rsi", "condition": "<", "value": 40}`
- Change indicator params: increase/decrease `period` or `multiplier`
- Remove an entry/exit rule (if it's over-constraining)

**Rules for valid strategy JSON:**
- `entry_rules` are AND conditions — all must be true to enter long
- `exit_rules` are OR conditions — any one triggers close
- `compare_to` must reference another indicator `name` defined in `indicators`
- `"close"` is NOT a valid indicator name — use EMA cross for price-vs-MA filters
- All indicators referenced in rules must exist in the `indicators` array

#### 5c — Run candidate on all pairs

Same engine invocations as Step 4 but using the candidate strategy file. Collect metrics.

#### 5d — Evaluate: keep or revert

Compute candidate score (same formula as baseline).

- If `candidate_score > current_score * 1.02` (at least 2% improvement): **keep** → `current_strategy = candidate_strategy`, `current_score = candidate_score`
- Otherwise: **revert** → discard candidate, keep current

Report one line per iteration:
```
Iter 1/3 | Change: added ema10 > ema50 trend filter
  Mean Sharpe: 0.30 → 0.27 (−10%) ✗ reverted
Iter 2/3 | Change: shortened ST period 10 → 7
  Mean Sharpe: 0.30 → 0.31 (+3%) ✓ kept
```

POST all candidate results to the Lab session regardless of keep/revert (for traceability).

After each **kept** iteration, sync the updated strategy definition back to the DB:
```bash
curl -s -X PUT <api-url>/strategies/<strategy_id> \
  -H "Content-Type: application/json" \
  -d '<escaped-updated-strategy-json>'
```

### Step 6 — Display final comparison table

Fetch session detail from Lab and display all results grouped by version (baseline + each kept iteration):

```
Strategy Lab — Final Results: <strategy_name>
Session: <session_id>
──────────────────────────────────────────────────────────────────────────────────────
Version           Instrument  TF   Sharpe  Return    DD       Win%   PF    Trades
──────────────────────────────────────────────────────────────────────────────────────
baseline (v0)     BTCUSD      H1    0.30   +197.8%  -24.7%   36.5%  1.55    192
baseline (v0)     BTCUSD      M15   0.12   +129.9%  -17.2%   32.3%  1.21    827
──────────────────────────────────────────────────────────────────────────────────────
best (v2, ST p=7) BTCUSD      H1    0.31   +204.2%  -24.3%   34.9%  1.57    195  ✓
best (v2, ST p=7) BTCUSD      M15   0.13   +141.8%  -18.0%   32.1%  1.21    820
──────────────────────────────────────────────────────────────────────────────────────
Target (sharpe > 0.5): NOT YET MET
Best mean Sharpe: 0.22 (baseline: 0.21) — improvement: +5%
```

Mark results meeting constraints with ✓.

### Step 7 — Human-in-the-loop validation (final only)

Present the results and ask the user what to do **once**, at the end:

```
What would you like to do with the best results?
  validate <n>   · reject <n>   · promote <n>   · promote-agg <n>   · promote-def <n>   · done
```

Apply actions via:
```bash
curl -s -X PATCH <api-url>/lab/results/<result_id>/status \
  -H "Content-Type: application/json" \
  -d '{"status": "<status>"}'
```

### Step 8 — Mark session completed and summarise

```bash
curl -s -X PATCH <api-url>/lab/sessions/<session_id>/status \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

Print:
```
Lab session completed.
  Best strategy: <name> (<change summary>)
  Improvement:   Sharpe +5% | DD −0.4pp
  View in UI:    http://localhost:5173/lab
  Session ID:    <session_id>
```

Suggest next steps:
- Target not met: "Run `/strategy-lab` again with `--iterations 5` for more improvement cycles."
- Target met, not promoted: "Run `/optimize` on the best variant to fine-tune individual parameters."
- Results promoted to production: "Export to cTrader with the upcoming `/export` skill (Phase 6)."
