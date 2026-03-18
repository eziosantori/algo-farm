Validate a strategy's robustness on out-of-sample data, walk-forward analysis, and Monte Carlo simulation.
This is the **mandatory gate** between in-sample optimization and production promotion.
A strategy may only be promoted after passing all three checks.

**Arguments:** $ARGUMENTS
(format: `<strategy-file-or-id> [--instruments EURUSD,XAUUSD] [--timeframes H1,H4] [--is-end 2023-12-31] [--mc-runs 1000] [--api-url http://localhost:3001]`)

---

## Pass/Fail criteria

| Check | Gate | What it means if it fails |
|---|---|---|
| OOS Sharpe ≥ 50% IS Sharpe | per instrument/TF | Overfitted on IS period |
| WF efficiency > 0.5 | per instrument/TF | Parameters not stable across time |
| MC P5 Sharpe > 0 | per instrument/TF | Edge is not statistically significant |

A strategy **passes** if ALL three checks pass on ≥ 60% of tested pairs.

---

## Instructions

### Step 1 — Parse arguments

- `strategy-file`: path to strategy JSON (with best IS params already applied). Resolved from `engine/strategies/optimizing/` first, then `draft/`.
- `--strategy-id`: UUID to fetch from API instead of local file.
- `--instruments`: default `EURUSD`
- `--timeframes`: default `H1`
- `--is-end`: last day of IS window (default: `2023-12-31`). OOS starts the next day.
- `--mc-runs`: Monte Carlo permutations (default: `1000`)
- `--api-url`: default `http://localhost:3001`

Derive:
- `is_start = "2022-01-01"`, `is_end = <parsed or default>`
- `oos_start = day after is_end` (e.g. `2024-01-01`)

### Step 2 — Check API, auto-start if needed

```bash
curl -s --max-time 3 <api-url>/health
```
If unreachable, start it:
```bash
pnpm --filter api dev > /tmp/api_dev.log 2>&1 &
sleep 4
curl -s --max-time 3 <api-url>/health
```

### Step 3 — Load strategy and resolve strategy_id (same as other skills)

Read the strategy JSON. Look up or register in the API. Set `strategy_id`.

### Step 4 — Create robustness Lab session

```bash
curl -s -X POST <api-url>/lab/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "<name> [robustness]",
    "strategy_json": <strategy-json-string>,
    "instruments": [...],
    "timeframes": [...],
    "strategy_id": "<strategy_id>",
    "is_start": "<is_start>",
    "is_end": "<is_end>"
  }'
```

Extract `session_id`. Report: `Robustness session: <session_id> | IS: <is_start> → <is_end> | OOS: <oos_start> → end`

### Step 5 — Run IS baseline (reference metrics)

For each (instrument × timeframe):
```bash
cd /Users/esantori/git/personal/algo-farm/engine && \
source .venv/bin/activate && \
python run.py \
  --strategy <strategy-file> \
  --instruments <instrument> \
  --timeframes <timeframe> \
  --db /tmp/rob_is_<instrument>_<timeframe>_$(date +%s).db \
  --data-dir data \
  --date-from <is_start> \
  --date-to <is_end> \
  2>/dev/null
```

Collect IS Sharpe per pair. POST to Lab with `split = "is"`.

### Step 6 — Run OOS backtest

For each (instrument × timeframe):
```bash
cd /Users/esantori/git/personal/algo-farm/engine && \
source .venv/bin/activate && \
python run.py \
  --strategy <strategy-file> \
  --instruments <instrument> \
  --timeframes <timeframe> \
  --db /tmp/rob_oos_<instrument>_<timeframe>_$(date +%s).db \
  --data-dir data \
  --date-from <oos_start> \
  2>/dev/null
```

Collect OOS Sharpe. POST to Lab with `split = "oos"`.

Check: `oos_sharpe >= 0.5 * is_sharpe` → PASS / FAIL

### Step 7 — Run Walk-Forward analysis (on IS data)

For each (instrument × timeframe):
```bash
cd /Users/esantori/git/personal/algo-farm/engine && \
source .venv/bin/activate && \
python run.py \
  --strategy <strategy-file> \
  --instruments <instrument> \
  --timeframes <timeframe> \
  --db /tmp/rob_wf_<instrument>_<timeframe>_$(date +%s).db \
  --data-dir data \
  --date-from <is_start> \
  --date-to <is_end> \
  --walk-forward \
  --wf-windows 5 \
  --wf-train-pct 0.7 \
  2>/dev/null
```

Parse `"type": "wf_result"` lines. Check: `wf_efficiency > 0.5` → PASS / FAIL

### Step 8 — Run Monte Carlo simulation (on IS data)

For each (instrument × timeframe):
```bash
cd /Users/esantori/git/personal/algo-farm/engine && \
source .venv/bin/activate && \
python run.py \
  --strategy <strategy-file> \
  --instruments <instrument> \
  --timeframes <timeframe> \
  --db /tmp/rob_mc_<instrument>_<timeframe>_$(date +%s).db \
  --data-dir data \
  --date-from <is_start> \
  --date-to <is_end> \
  --monte-carlo \
  --mc-runs <mc_runs> \
  2>/dev/null
```

Parse `"type": "mc_result"` lines. Check: `p5_sharpe > 0` → PASS / FAIL

### Step 9 — Display results table

```
Robustness Report: <strategy_name>
IS: 2022-01-01 → 2023-12-31  |  OOS: 2024-01-01 → end
────────────────────────────────────────────────────────────────────────────────────────
Pair          IS Sharpe  OOS Sharpe  OOS/IS   WF Eff   MC P5   OOS    WF     MC
────────────────────────────────────────────────────────────────────────────────────────
XAUUSD  H4      0.651      0.489     75%      0.63     0.08    PASS   PASS   PASS  ✓
XAUUSD  H1      0.248      0.091     37%      0.48    -0.05    FAIL   FAIL   FAIL  ✗
BTCUSD  H1      0.188      0.142     76%      0.55     0.04    PASS   PASS   PASS  ✓
────────────────────────────────────────────────────────────────────────────────────────
Overall: 2/3 pairs passed (67%) → STRATEGY PASSES ROBUSTNESS GATE ✓
```

### Step 10 — Promote or keep in optimizing

**If strategy passes (≥ 60% pairs pass all 3 checks):**
- Move strategy file from `engine/strategies/optimizing/` to `engine/strategies/validated/`
- Update lifecycle_status via API: `PUT /strategies/<id>` with `lifecycle_status: "validated"`
- Report: "Strategy promoted to `validated/`. Run `/strategy-lab` for multi-asset production readiness check."

**If strategy fails:**
- Keep in `engine/strategies/optimizing/`
- Report which checks failed and why
- Suggest: "Run `/iterate` with tighter entry rules, or `/optimize` with different param ranges."

### Step 11 — Mark session completed

```bash
curl -s -X PATCH <api-url>/lab/sessions/<session_id>/status \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

Print:
```
Robustness session completed.
  Session ID: <session_id>
  View in UI: http://localhost:5173/lab
```
