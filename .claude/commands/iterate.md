Autonomously improve a trading strategy through repeated backtest → analyze → modify cycles.

**Arguments:** $ARGUMENTS
(format: `<strategy-file-or-id> [--strategy-id <uuid>] [--target "sharpe > 1.5"] [--iterations 5]`)

## Instructions

### Step 1 — Parse arguments

- `strategy-file`: path to strategy JSON. Resolved from `engine/strategies/draft/` if not absolute.
  May be omitted if `--strategy-id` is provided.
- `--strategy-id <uuid>`: UUID of a strategy already saved in the API database.
  When provided, the strategy is fetched from the API instead of a local file.
- `--target`: improvement goal, default `"sharpe > 1.0"`. Supported: `sharpe > N`, `return > N`, `win_rate > N`, `drawdown < N`
- `--iterations`: max iterations, default `5`
- `--api-url`: default `http://localhost:3001`

### Step 2 — Load the strategy

**Case A — `--strategy-id <uuid>` provided:**
```bash
curl -s http://localhost:3001/strategies/<uuid>
```
Extract the `definition` field. Write it to `engine/strategies/draft/<name>.json`.
Set `strategy_id = <uuid>`.

**Case B — file path provided:**
Read the strategy JSON with the Read tool.

Then check if the strategy is already registered in the API database by searching by name:
```bash
curl -s http://localhost:3001/strategies
```
Filter the returned list for a strategy whose `name` matches exactly. If found, set `strategy_id = <id>`.
If not found, register it now:
```bash
curl -s -X POST http://localhost:3001/strategies \
  -H "Content-Type: application/json" \
  -d '<escaped-strategy-json>'
```
Set `strategy_id` from the returned `id`.

Keep the original as `<name>_v0.json` (backup). Working file = the strategy file.

### Step 3 — Download missing data

Check if `engine/data/EURUSD/H1.parquet` exists. If missing, download it:
```bash
cd /Users/esantori/git/personal/algo-farm/engine && \
source .venv/bin/activate && \
python download.py --instruments EURUSD --timeframes H1 \
  --from 2024-01-01 --to $(date +%Y-%m-%d) --data-dir data
```

### Step 4 — Create Lab session linked to the strategy

Check the API is reachable:
```bash
curl -s --max-time 3 http://localhost:3001/health
```
If unreachable: warn the user and skip Lab steps (continue with backtest + file output only).

If reachable, create a Lab session with `strategy_id` so results appear linked in the UI:
```bash
curl -s -X POST http://localhost:3001/lab/sessions \
  -H "Content-Type: application/json" \
  -d '{
    "strategy_name": "<name>",
    "strategy_json": <strategy-json>,
    "instruments": ["EURUSD"],
    "timeframes": ["H1"],
    "strategy_id": "<strategy_id>"
  }'
```
Extract `session_id`. Print: `Lab session: <session_id>`

### Step 5 — Iteration loop (1 to N)

#### 5a — Run backtest
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

#### 5b — Parse metrics from the `completed` JSONL message.

#### 5c — Check target: if met, stop and report success.

#### 5d — Diagnose and propose ONE focused change:

| Problem | Diagnosis | Proposed change |
|---------|-----------|-----------------|
| `total_trades == 0` | Entry never fires | Relax entry rules: remove one condition, or lower period of a fast indicator |
| `total_trades < 5` | Entry too restrictive | Widen value thresholds (e.g., RSI < 35 instead of < 30) |
| `win_rate < 40%` | Signal is reversed | Swap entry/exit conditions, or invert the trend filter |
| `win_rate > 60%` but low return | Trades too short / TP too tight | Increase `tp_pips` or relax exit rule |
| `max_drawdown < -15%` | No loss protection | Add `sl_pips` to position management |
| `sharpe < 0` | Strategy losing consistently | Try opposite direction or completely revise entry |
| `profit_factor < 1` | Losses outweigh gains | Tighten entry (add confirming indicator), add SL |

#### 5e — Apply the change using Edit tool on the strategy file.

#### 5f — Post intermediate result to Lab (if session created):
```bash
curl -s -X POST http://localhost:3001/lab/sessions/<session_id>/results \
  -H "Content-Type: application/json" \
  -d '{
    "instrument": "EURUSD",
    "timeframe": "H1",
    "params_json": "{}",
    "metrics_json": "<escaped-metrics>"
  }'
```

#### 5g — Sync updated strategy to DB (if API reachable):
```bash
curl -s -X PUT http://localhost:3001/strategies/<strategy_id> \
  -H "Content-Type: application/json" \
  -d '<escaped-updated-strategy-json>'
```

#### 5h — Report progress:
```
Iter 2/5 | Sharpe: 0.91 → 1.34 | Trades: 9 → 18 | Target: sharpe > 1.5
Change: Relaxed RSI threshold from 30 to 35
```

### Step 6 — Final report

Show before/after comparison:
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

### Step 7 — Save final version and mark Lab session completed

Save: `engine/strategies/draft/<name>_v<N>.json`

If API reachable:
```bash
# Mark session completed
curl -s -X PATCH http://localhost:3001/lab/sessions/<session_id>/status \
  -H "Content-Type: application/json" \
  -d '{"status": "completed"}'
```

Print:
```
Results visible in UI:
  Strategies: http://localhost:5173/strategies  (lifecycle_status updated)
  Lab:        http://localhost:5173/lab         (session: <session_id>)
```

### Step 8 — Suggest next steps

- Target not met: "Run `/iterate` again or `/optimize` to fine-tune parameters."
- Target met: "Run `/strategy-lab` to test across multiple instruments and timeframes."
