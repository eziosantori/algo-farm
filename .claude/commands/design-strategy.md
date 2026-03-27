Multi-agent strategy design board. Runs 5–7 specialist subagents to analyze, debate, and synthesize a strategy before producing the final StrategyDefinition JSON. Saves a design report to `docs/ideas/strategies/` with the full discussion and a ready-to-use workflow-orchestrator prompt.

**Usage:** `/design-strategy "<description>" [--instruments X,Y] [--timeframes H1,H4] [--target "sharpe > 1.0"]`

**User input:** $ARGUMENTS

---

## Instructions

### Step 0 — Parse arguments

Extract from `$ARGUMENTS`:
- `description`: the quoted natural language trading idea (required)
- `--instruments`: comma-separated list (default: `EURUSD`)
- `--timeframes`: comma-separated list (default: `H1`)
- `--target`: performance goal string (default: `sharpe > 0.5`)

Print:
```
Strategy Design Board — starting analysis
  Idea: <description>
  Instruments: <instruments>
  Timeframes: <timeframes>
  Target: <target>

Phase 1: Analysis (3 agents)...
```

---

### Step 1 — Technical Analyst

Call the `technical-analyst` agent with:

```
User idea: <description>
Instruments: <instruments>
Timeframes: <timeframes>
Target: <target>

Design the core indicator set and trading rules for this strategy.
```

Save the full response as `TECHNICAL_REPORT`. Print: `✓ Technical analyst complete`

---

### Step 2 — Market Structure Analyst

Call the `market-structure-analyst` agent with:

```
User idea: <description>
Instruments: <instruments>
Timeframes: <timeframes>

Technical Analyst Report:
<TECHNICAL_REPORT>

Evaluate the regime fit, timeframe suitability, and recommend any missing filters.
```

Save the full response as `MARKET_REPORT`. Print: `✓ Market structure analyst complete`

---

### Step 3 — Risk & Position Analyst

Call the `risk-position-analyst` agent with:

```
User idea: <description>
Instruments: <instruments>
Timeframes: <timeframes>
Target: <target>

Technical Analyst Report:
<TECHNICAL_REPORT>

Design the position_management block for this strategy.
```

Save the full response as `RISK_REPORT`. Print: `✓ Risk analyst complete — Phase 2: Debate...`

---

### Step 4 — Strategy Advocate

Call the `strategy-advocate` agent with:

```
Technical Analyst Report:
<TECHNICAL_REPORT>

Market Structure Analyst Report:
<MARKET_REPORT>

Risk & Position Analyst Report:
<RISK_REPORT>

Argue for the strengths of this strategy design. Target: <target>
```

Save the full response as `ADVOCATE_REPORT`. Print: `✓ Advocate complete`

---

### Step 5 — Strategy Critic

Call the `strategy-critic` agent with:

```
Technical Analyst Report:
<TECHNICAL_REPORT>

Market Structure Analyst Report:
<MARKET_REPORT>

Risk & Position Analyst Report:
<RISK_REPORT>

Advocate Bull Case:
<ADVOCATE_REPORT>

Instruments: <instruments>
Timeframes: <timeframes>

Identify weaknesses and produce your blocking_concerns list.
```

Save the full response as `CRITIC_REPORT`. Print: `✓ Critic complete`

---

### Step 6 — Check for Round 2

Parse `CRITIC_REPORT` for `blocking_concerns:`. If the list contains one or more items:

Print: `⚡ Blocking concerns detected — starting Round 2 debate...`

**Round 2A — Advocate rebuttal:**

Call the `strategy-advocate` agent with:

```
[ROUND 2 — REBUTTAL]

Technical Analyst Report:
<TECHNICAL_REPORT>

Market Structure Report:
<MARKET_REPORT>

Risk Report:
<RISK_REPORT>

Critic's Blocking Concerns:
<extract blocking_concerns list from CRITIC_REPORT>

Provide targeted rebuttals for each blocking concern. Include proposed JSON fixes where you accept a concern.
```

Save as `ADVOCATE_REBUTTAL`. Append to `ADVOCATE_REPORT`.

**Round 2B — Critic final verdict:**

Call the `strategy-critic` agent with:

```
[ROUND 2 — FINAL VERDICT]

Original reports:
Technical: <TECHNICAL_REPORT>
Market: <MARKET_REPORT>
Risk: <RISK_REPORT>

Advocate's Rebuttals:
<ADVOCATE_REBUTTAL>

Review the rebuttals. Update your blocking_concerns list: remove concerns that were convincingly addressed, keep any that remain unresolved. Output final verdict.
```

Save as `CRITIC_FINAL`. Set `DEBATE_ROUNDS = 2`.

Print: `✓ Round 2 complete`

Otherwise (no blocking concerns): skip Round 2, set `DEBATE_ROUNDS = 1`. Print: `✓ No blocking concerns — proceeding to synthesis`

---

### Step 7 — Strategy Composer

Determine `FINAL_CRITIC` = `CRITIC_FINAL` if Round 2 happened, else `CRITIC_REPORT`.

Call the `strategy-composer` agent with:

```
[SYNTHESIS]

Technical Analyst Report:
<TECHNICAL_REPORT>

Market Structure Analyst Report:
<MARKET_REPORT>

Risk & Position Analyst Report:
<RISK_REPORT>

Advocate Bull Case:
<ADVOCATE_REPORT>

Critic Final Report:
<FINAL_CRITIC>

Target: <target>
Instruments: <instruments>
Timeframes: <timeframes>

Synthesize all reports into a final valid StrategyDefinition JSON. Address every blocking concern.
```

Save the full response as `COMPOSER_REPORT`. Print: `✓ Composition complete — Phase 4: Output...`

---

### Step 8 — Present results to user

Display a formatted summary:

```markdown
## Strategy Design Board — Results

### Analysis Summary
| Analyst | Key Finding |
|---------|------------|
| Technical | [1-line summary] |
| Market Structure | [1-line summary] |
| Risk | [1-line summary] |

### Debate (Round <DEBATE_ROUNDS>)
- **Advocate:** [1–2 sentence highlight]
- **Critic:** [blocking_concerns list, or "None — design approved"]
- **Resolution:** [how concerns were addressed]

### Final Strategy JSON
[Full JSON from COMPOSER_REPORT]
```

Ask the user:
```
Approve this strategy and save?
  yes / approve  → save strategy + report
  no / reject    → discard
  change <...>   → describe what to change (re-runs composer only)
```

---

### Step 9 — On approval: save strategy file

1. Extract `name` from the JSON and derive a `snake_case` filename:
   - "RSI Reversal with ADX Filter" → `rsi_reversal_adx_filter.json`

2. Save strategy to `engine/strategies/draft/<filename>.json`.

3. Register in API if reachable:
   ```bash
   curl -s --max-time 3 http://localhost:3001/health
   ```
   If OK:
   ```bash
   curl -s -X POST http://localhost:3001/strategies \
     -H "Content-Type: application/json" \
     -d '<escaped-strategy-json>'
   ```
   Extract `id` from response. Set `STRATEGY_ID` (empty string if API unreachable).

---

### Step 10 — Save design report

Build the report filename from the strategy name: `<snake_case_name>_design.md`

Save to `docs/ideas/strategies/<snake_case_name>_design.md` with this content:

```markdown
# <Strategy Name> — Design Report

> Generated by AlgoFarm Strategy Design Board — <date YYYY-MM-DD>

## Summary

**Idea:** <description>
**Instruments:** <instruments>
**Timeframes:** <timeframes>
**Target:** <target>
**Debate rounds:** <DEBATE_ROUNDS>
**Strategy file:** `engine/strategies/draft/<filename>.json`
**API id:** `<STRATEGY_ID>` *(empty if API was unreachable at generation time)*

---

## Phase 1 — Technical Analysis

<TECHNICAL_REPORT>

---

## Phase 1 — Market Structure Analysis

<MARKET_REPORT>

---

## Phase 1 — Risk & Position Management

<RISK_REPORT>

---

## Phase 2 — Debate

### Bull Case (Advocate)

<ADVOCATE_REPORT>

### Bear Case (Critic)

<FINAL_CRITIC>

---

## Phase 3 — Composition

<COMPOSER_REPORT>

---

## Workflow Orchestrator — Ready-to-run prompt

Copy and paste this into Claude Code to start the full development lifecycle:

```
@workflow-orchestrator <filename>.json \
  --goal "<target>" \
  --instruments <instruments> \
  --timeframes <timeframes> \
  --iterations 3
```

> The strategy has already been designed through multi-agent debate. Skip directly to backtesting and optimization — no `/new-strategy` or `/iterate` manual steps needed.
```

Print:
```
Report saved: docs/ideas/strategies/<snake_case_name>_design.md
Strategy saved: engine/strategies/draft/<filename>.json
<if STRATEGY_ID non-empty>: API id: <STRATEGY_ID>

To start the full development lifecycle, run:

@workflow-orchestrator <filename>.json \
  --goal "<target>" \
  --instruments <instruments> \
  --timeframes <timeframes> \
  --iterations 3
```

---

### Step 9b — On "change <instruction>"

Re-run only the composer with all original reports plus the change instruction appended. Present new JSON. Ask for approval again (returns to Step 8).

---

### Step 9c — On rejection

Print: `Strategy discarded. Run /design-strategy again with a different idea.`

---

## Notes

- Total agent calls: 6 (no blocking concerns) or 8 (with Round 2 debate)
- Models: Haiku for analysts + advocate + critic; Sonnet for composer
- Output files: `engine/strategies/draft/<name>.json` + `docs/ideas/strategies/<name>_design.md`
- Use `/new-strategy` for quick single-shot generation; use this command for thorough analysis
