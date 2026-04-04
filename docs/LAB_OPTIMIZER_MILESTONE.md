# Lab Optimizer Launcher — Milestone Plan

## Context

The current Lab page is a session viewer designed around the `strategy-lab` Claude Code skill. Since the workflow-orchestrator agent handles strategy genesis effectively, the Lab needs repurposing as a **UI-driven optimization launcher** — select a Vault strategy, pick instruments/timeframes, configure parameter ranges (cTrader-style), choose optimizer, and run in background with real-time progress. **Zero LLM involvement** — pure engine execution.

The backend infrastructure is **already complete**: BullMQ worker, JSONL progress streaming, WebSocket broadcast, all 3 optimizers (grid/bayesian/genetic). The work is almost entirely frontend.

---

## Architecture

### New/Modified Files

```
ui/src/components/Lab/
  LabPage.tsx                    ← MODIFY: tab container "Launch" | "Sessions"
  OptimizationLauncher.tsx       ← NEW: main form (strategy + instruments + timeframes + params + optimizer)
  InstrumentMultiSelect.tsx      ← NEW: grouped autocomplete multiselect
  TimeframeSelect.tsx            ← NEW: toggleable chip buttons (9 options)
  ParamRangeBuilder.tsx          ← NEW: per-param min/max/step or manual list (cTrader-style)
  OptimizerConfig.tsx            ← NEW: grid|bayesian|genetic radio + options
  OptimizationProgress.tsx       ← NEW: real-time progress via useSessionProgress hook
  SessionHistory.tsx             ← NEW: extracted from current LabPage (session list + expand)

ui/src/api/client.ts             ← FIX: add "genetic" to optimizer type, add population_size
ui/src/components/Vault/VaultDetailPage.tsx  ← MODIFY: add "Optimize" button → navigates to /lab
```

### Reuse existing code

- `useSessionProgress` hook (`ui/src/hooks/useSessionProgress.ts`) — WebSocket subscribe/events/progress/completion
- `api.createLabSession()` + `api.runLabSession()` — already wired to BullMQ
- `api.listStrategies()` + `api.getStrategy()` — for strategy picker + param extraction
- Metric color helpers from `LabPage.tsx` (sharpeClass, ddClass, etc.)
- Tailwind styling patterns from VaultPage/LabPage

### State management

Component-local `useReducer` for the launch form (ephemeral, resets between launches). No new Zustand store needed.

### Key data flows

1. **Strategy selection** → `api.getStrategy(id)` → extract tunable params from `definition.indicators[].params` + `definition.position_management` numeric fields
2. **Param grid build** → convert Range(min/max/step) or List(values) or Fixed(value) → flat `Record<string, number[] | number>` for engine
3. **Launch** → `api.createLabSession(...)` → `api.runLabSession(sessionId, {param_grid, optimizer, ...})` → returns immediately (202)
4. **Progress** → `useSessionProgress(sessionId)` → WebSocket events → progress bar + live results table
5. **Vault integration** → "Optimize" button on VaultDetailPage → `navigate("/lab", { state: { strategyId } })`

---

## Implementation Phases

### Phase 1 — Core Form + Launch

**Goal:** Working launcher that selects strategy, instruments, timeframes, optimizer and launches a background job.

1. **Fix `api.runLabSession` types** in `ui/src/api/client.ts`:
   - Add `"genetic"` to optimizer union
   - Add `population_size?: number` to options

2. **Create `InstrumentMultiSelect.tsx`**:
   - Text input for filtering + dropdown with grouped sections (Forex/Metals/Commodities/Indices/Stocks)
   - Static `INSTRUMENT_GROUPS` data (34 instruments)
   - Checkboxes per item, "Select all" per group header
   - Selected shown as removable chips above input
   - Click-outside / Escape to close

3. **Create `TimeframeSelect.tsx`**:
   - 9 toggleable chip/buttons (M1 M5 M10 M15 M30 H1 H4 D1 W1)
   - Multi-select, visual toggle state

4. **Create `OptimizerConfig.tsx`**:
   - Radio tabs: Grid | Bayesian | Genetic
   - Bayesian: n_trials input (default 50)
   - Genetic: n_trials (default 50) + population_size (default 20)
   - Metric selector dropdown (sharpe_ratio, profit_factor, total_return_pct, max_drawdown_pct, win_rate_pct)
   - Optional date range (from/to inputs)

5. **Create `OptimizationLauncher.tsx`**:
   - Strategy picker: dropdown of Vault strategies (filtered by validated/production status)
   - Composes InstrumentMultiSelect + TimeframeSelect + OptimizerConfig
   - Launch button → calls createLabSession + runLabSession
   - No ParamRangeBuilder yet (uses strategy defaults, empty param_grid)

6. **Extract `SessionHistory.tsx`** from current LabPage content

7. **Modify `LabPage.tsx`** to tab layout: "Launch" | "Sessions"

### Phase 2 — ParamRangeBuilder

**Goal:** cTrader-style parameter configuration UI.

1. **Create `ParamRangeBuilder.tsx`**:
   - Extract tunable params from strategy definition (indicators params + position_management numeric fields)
   - Table layout: Parameter name | Current value | Mode toggle (Range/List/Fixed) | Config inputs | Preview
   - Range mode: min, max, step → generates preview array
   - List mode: comma-separated input
   - Fixed mode: single value (default = current)
   - Total combinations counter at bottom (warn if >10,000 for grid)

2. **Wire into OptimizationLauncher** — `buildParamGrid()` converts form state to engine's flat key→array format

### Phase 3 — Real-time Progress

**Goal:** Live optimization tracking in the UI.

1. **Create `OptimizationProgress.tsx`**:
   - Uses `useSessionProgress(sessionId)` hook
   - Progress bar (pct 0-100)
   - Current instrument/timeframe badge
   - Iteration counter (current/total)
   - Elapsed time formatted
   - Live results table: streams `type==="result"` events, sortable by metric columns
   - Connection indicator (green/red dot)
   - Completion summary with best params

2. **Update LabPage** — after launch, show OptimizationProgress; on completion, switch to results view

### Phase 4 — Vault Integration + Polish

**Goal:** Seamless flow from Vault to optimizer.

1. **Add "Optimize" button to VaultDetailPage** → `navigate("/lab", { state: { strategyId } })`
2. **LabPage reads `location.state?.strategyId`** on mount → pre-populates strategy selector, switches to Launch tab
3. Edge cases: strategy without tunable params, WebSocket disconnect, empty states, loading states

---

## Verification

- **Phase 1:** Select strategy + instruments + timeframes + optimizer → click Launch → verify `POST /lab/sessions` + `POST /lab/sessions/:id/run` fire correctly (Network tab). Requires API running (`pnpm --filter api dev`).
- **Phase 2:** Select strategy → verify param table populates → change modes → verify `param_grid` in request body.
- **Phase 3:** Launch a real optimization → verify progress bar updates in real-time → results table fills. Requires Redis + engine data.
- **Phase 4:** Vault → click Optimize → verify redirect to Lab with pre-filled form.

---

## Instruments Reference

| Group | Instruments |
|-------|------------|
| Forex | EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, NZDUSD, USDCAD, EURGBP, EURJPY, GBPJPY, AUDNZD, EURAUD |
| Metals | XAUUSD, XAGUSD |
| Commodities | BCOUSD, WTIUSD, NATGASUSD, XCUUSD |
| Indices | US500, NAS100, GER40, UK100, JPN225, AUS200 |
| Stocks | AAPL, MSFT, AMZN, GOOGL, META, NVDA, TSLA, NFLX, AMD, INTC |

## Timeframes

M1, M5, M10, M15, M30, H1, H4, D1, W1
