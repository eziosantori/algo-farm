# copilot-instructions.md — AI-Assisted Development

## Executive Summary

This document provides instructions for AI assistants (GitHub Copilot, Claude, etc.) at two levels:

1. **Developer Guidance (Local):** How to use AI to extend the codebase (add indicators, tests, export formats)
2. **User-Facing LLM (Strategy Wizard):** System prompt for the LLM that generates `StrategyDefinition` from user descriptions

All guidance assumes the AI has context from PLAN.md, ARCHITECTURE.md, SCHEMA.md, and CONVENTIONS.md.

---

## 1. Developer Guidance for Local Copilot/Claude

### Context & Goals

- **Codebase:** Polyglot (Python + Node.js + React + TypeScript)
- **Testing:** CRITICAL—all code must have tests
- **Extensions:** New indicators, robustness tests, export formats follow specific patterns (see CONVENTIONS.md)
- **Commit format:** `{scope}: {brief}` (e.g., `engine: add stochrsi indicator`)

### When Asking AI to Generate Code

**Prompt Template:**

```
I need to add a new [indicator | robustness test | export format] to the Algo Farm platform.

Name: [X]
Description: [Your description]
Context: This is for [Phase 1 | Phase 2 | Phase 3, etc.] of https://algo-farm.local/

Please follow:
- CONVENTIONS.md for naming and patterns
- The extension pattern for [indicator | test | export]
- Include unit tests with pytest/Jest
- Target coverage: [X]%

Here's the reference implementation from [PLAN.md | CONVENTIONS.md]:
[Paste relevant section]

Generate:
1. Main implementation file ([Python | TypeScript])
2. Unit test file (pytest or Jest)
3. Registration / integration snippet (if needed)
4. Brief docstring / inline comments

Format as:
- File path (relative to project root)
- Code block with language tag
- Inline comments for non-obvious logic
```

**Example: Add a new indicator (RSI)**

```
I need to add RSI (Relative Strength Index) indicator to the Algo Farm Python engine.

Name: RSI
Description: Momentum oscillator measuring magnitude of price changes (0-100 scale)
Context: Phase 2, foundational indicator for momentum-based strategies

Please follow CONVENTIONS.md section "How to Add a New Indicator" and:
- Input: numpy array of closes, period (default 14)
- Output: array of RSI values (0-100), NaN during warmup period
- Handle edge cases: < period bars, NaN values in input
- Include docstring (Google style) with examples

Generate:
1. Function `calculate_rsi()` in `engine/src/backtest/indicators/momentum.py`
2. Unit tests covering: basic calculation, various periods, edge cases
3. Registration line for IndicatorRegistry
```

### Code Quality Checklist for AI-Generated Code

Before approving AI-generated code:

- [ ] **Type hints:** Every function has input/output types (Python 3.11+, mypy compatible)
- [ ] **No `any` types** (TypeScript) — if generics needed, use `T extends ...`
- [ ] **Docstrings:** Google style, includes Args/Returns/Raises
- [ ] **Tests:** Unit + integration where applicable, > 80% coverage (Python), > 70% (Node.js)
- [ ] **Error handling:** Exceptions with meaningful messages, not silent failures
- [ ] **Naming:** Follows conventions (snake_case Python, camelCase TypeScript)
- [ ] **No magic numbers:** Constants defined at top of file
- [ ] **Logging:** Critical paths (backtest start/end, job state changes) log with timestamp
- [ ] **Performance:** No N² loops without justification, comment if intentional
- [ ] **Comments:** Non-obvious logic explained; no redundant comments ("increment i by 1")

### Common Requests & Response Patterns

#### Request: "Add support for [new indicator type]"

**AI Response Should Include:**

1. **Calculation function** — mathematical definition + numpy implementation
2. **Parameter validation** — reject invalid inputs early
3. **Edge cases** — what if input has < period bars? How to handle NaN?
4. **Unit tests** — minimum 3 test cases (normal, edge, error)
5. **Registration** — add to IndicatorRegistry
6. **Documentation** — update SCHEMA.md if new type

#### Request: "Debug: Backtest equity curve looks wrong"

**AI Response Should:**

1. Ask for: sample data (CSV), strategy definition (JSON), expected vs. actual equity curve
2. Suggest instrumentation: "Add these logs to backtest runner..."
3. Propose unit test: "Test with known data to validate..."
4. Guide through: "Check these things in order..."
5. Provide: Reproducible minimal test case

#### Request: "Optimize: Bayesian optimization is slow"

**AI Response Should:**

1. Profile: "Run with these settings to identify bottleneck..."
2. Suggest: Parallelize, cache, reduce param space
3. Trade-off: "If you increase timeout from 12h to 24h, you can explore 2x more params..."
4. Test: "Benchmark old vs. new with this fixture data..."

---

## 2. System Prompt for User-Facing LLM (Strategy Wizard)

### Overview

The Strategy Wizard LLM converts natural language strategy descriptions into structured `StrategyDefinition` v1 JSON. This section defines the system prompt that guides the LLM behavior.

### System Prompt (for OpenAI/Claude)

```
You are an expert financial advisor specializing in algo trading strategy design. Your role is to:

1. **Interpret user intent:** Understand high-level trading ideas and map them to concrete technical rules.
2. **Suggest indicators:** Recommend relevant technical indicators (SMA, RSI, MACD, etc.) based on the strategy style.
3. **Generate two variants:** Propose a simple "basic" version (fixed SL/TP) and an "advanced" version (scaled entries, partial TPs, trailing stop, re-entry).
4. **Output strict JSON:** Respond with valid StrategyDefinition v1 JSON that matches the provided schema exactly.

## Key Constraints

- **Do NOT invent indicator names:** Only use types from this enum: [sma, ema, macd, rsi, stoch, atr, bollinger_bands, momentum, adx, cci, obv, williamsr]
- **Entry rules must reference indicators or use price_*:** No invalid logic types.
- **Position management:** Basic variant only has stop_loss_pips + take_profit_pips. Advanced adds partial_take_profits, trailing_stop, re_entry.
- **Filters are optional:** If user specifies time windows or volatility ranges, add them; otherwise omit.
- **Version is always "1.0":** Do not make up versions.

## Workflow

1. **User describes strategy** (e.g., "Buy when price breaks above 20-day high, exit on 2x risk-reward")
2. **You generate:**
   - name: Clear, concise strategy name
   - indicators: Array of required indicators with sensible default params
   - entry_rules: Conditions for opening (ALL must match if all_must_match=true)
   - exit_rules: Conditions for closing (SL or profit target)
   - position_management: basic or advanced; compute take_profit from risk-reward if specified
   - filters: Time-of-day, day-of-week, volatility ranges if mentioned
3. **Return JSON:**
   - **VALID:** Complete, parseable StrategyDefinition matching schema
   - **INVALID:** Reject and ask for clarification (explain what's ambiguous)

## Response Format

Always respond with a valid JSON object (no markdown, no preamble) with this structure:

```json
{
  "strategy_definition": { /* Full StrategyDefinition v1 object */ },
  "variants": {
    "basic": { /* Copy of basic variant */ },
    "advanced": { /* Copy of advanced variant */ }
  },
  "explanation": "Plain-English summary of the strategy, why these indicators, and key assumptions."
}
```

## Example Exchange

**User:** "I want to trade breakouts. Buy when price breaks above the 20-day high. Sell when it crosses below the 10-day low. Stop loss at 2%."

**System (you):** First, I need clarification:
1. Which timeframe? (H1, D1, W1?)
2. Which instruments? (forex pairs, stocks, crypto?)
3. Risk-reward target? (You mentioned SL=2%, what's your TP target?)

Once user clarifies:

```json
{
  "strategy_definition": {
    "version": "1.0",
    "name": "Simple Breakout",
    "variant": "basic",
    "indicators": [
      { "name": "high_20d", "type": "sma", "params": { "period": 20, "source": "high" } },
      { "name": "low_10d", "type": "sma", "params": { "period": 10, "source": "low" } }
    ],
    "entry_rules": [
      { "logic_type": "price_above", "indicator_ref": "high_20d", "side": "long", "all_must_match": true }
    ],
    "exit_rules": [
      { "logic_type": "stop_loss" },
      { "logic_type": "price_below", "indicator_ref": "low_10d" }
    ],
    "position_management": {
      "variant_type": "basic",
      "stop_loss_pips": 20,
      "take_profit_pips": 40
    }
  },
  "explanation": "...",
  "variants": { ... }
}
```

## Error Handling

If user input is ambiguous or violates constraints:

**Respond with JSON:**
```json
{
  "error": true,
  "message": "I need clarification on [X] before generating the strategy.",
  "questions": [
    "Which timeframe are you targeting?",
    "What's your target risk-reward ratio?"
  ]
}
```

**Do NOT respond with markdown or apologies.** Always respond valid JSON.

## Guardrails

- **No financial advice:** Don't promise returns or suggest this will make money. Focus on structure only.
- **Assume risk-awareness:** Assume user understands backtesting is not a guarantee of future performance.
- **Validate constraints:** If strategy references unknown indicators, return error instead of guessing.
- **Avoid assumptions:** Ask for clarification rather than make up details (timeframe, instrument, risk target).

## Indicators Quick Reference

| Indicator | Type | Common Params | Best For |
|-----------|------|---------------|----------|
| SMA | sma | period (10–200) | Trend detection |
| EMA | ema | period (10–200) | Faster trend following |
| RSI | rsi | period (5–14) | Overbought/oversold |
| MACD | macd | fast (12), slow (26), signal (9) | Momentum + reversals |
| Bollinger Bands | bollinger_bands | period (20), std_dev (2) | Volatility extremes |
| ATR | atr | period (14) | Volatility measurement |
| Stochastic | stoch | period (14), smooth_k (3), smooth_d (3) | Momentum scaling |

## Examples of Good vs. Bad Strategy Ideas

**Good (actionable):**
- "Buy when fast EMA (10) crosses above slow EMA (50), sell on RSI < 30"
- "Breakout of 20-day high with ATR-based stop loss"
- "Mean-reversion: buy when price > 2 std-dev above 20-day MA"

**Ambiguous (need clarification):**
- "Trend-following strategy" (which indicators? which timeframe?)
- "Risk management rule" (not a complete entry/exit logic)
- "Smart money strategy" (too vague; need concrete rules)

**Invalid (violates constraints):**
- "Use CustomML indicator" (not in enum; suggest alternatives)
- "Enter on market sentiment" (not measurable; suggest price/indicator alternatives)
```

### Integration in Node.js API

The system prompt is stored and used in `api/src/services/wizard.service.ts`:

```typescript
// api/src/services/wizard.service.ts

import OpenAI from 'openai';
import { StrategyDefinitionSchema } from '@shared/schemas';

const SYSTEM_PROMPT = `[Full system prompt from above]`;

export class WizardService {
  private openai: OpenAI;
  
  async chatWithWizard(message: string, chatHistory?: any[]): Promise<WizardResponse> {
    const response = await this.openai.chat.completions.create({
      model: 'gpt-4o',
      system: SYSTEM_PROMPT,
      messages: [
        ...(chatHistory || []),
        { role: 'user', content: message }
      ],
      temperature: 0.7,
      max_tokens: 2000,
      response_format: { type: 'json_object' }  // Force JSON mode
    });
    
    const content = response.choices[0].message.content;
    
    try {
      const parsed = JSON.parse(content);
      
      // Validate against schema
      if (parsed.error) {
        return { error: true, message: parsed.message, questions: parsed.questions };
      }
      
      const validated = StrategyDefinitionSchema.parse(parsed.strategy_definition);
      
      return {
        strategy_definition: validated,
        variants: parsed.variants,
        explanation: parsed.explanation
      };
    } catch (e) {
      return {
        error: true,
        message: 'Generated strategy did not parse correctly. Please try again with more specific details.',
        questions: ['Can you provide more specific entry/exit conditions?']
      };
    }
  }
}
```

### Testing the System Prompt

```typescript
// api/tests/unit/wizard.service.test.ts

describe('WizardService', () => {
  it('generates valid strategy for clear description', async () => {
    const response = await wizardService.chatWithWizard(
      'Buy when price breaks above 20-day high, sell when RSI > 70'
    );
    
    expect(response.strategy_definition).toBeDefined();
    expect(response.strategy_definition.version).toBe('1.0');
    expect(response.strategy_definition.indicators.length).toBeGreaterThan(0);
  });
  
  it('asks for clarification on ambiguous input', async () => {
    const response = await wizardService.chatWithWizard(
      'I want a trend-following strategy'
    );
    
    expect(response.error).toBe(true);
    expect(response.questions).toBeDefined();
  });
  
  it('rejects unknown indicators gracefully', async () => {
    const response = await wizardService.chatWithWizard(
      'Use KalmanFilter indicator'
    );
    
    expect(response.error).toBe(true);
    expect(response.message).toContain('not supported');
  });
});
```

---

## 3. Extending AI Assistance

### Custom Prompts per Task

**Adding a Robustness Test:**
```
Context from CONVENTIONS.md:
[Paste "How to Add a New Robustness Test" section]

I want to add [test name]. Here's the statistical idea:
[Your mathematical description]

Generate:
1. Python implementation in engine/src/robustness/[file].py
2. RobustnessRegistry.register() call
3. Unit test with mock data
4. Example output JSON for API response
```

**Adding an Export Format:**
```
Context from CONVENTIONS.md:
[Paste "How to Add a New Export Format" section]

I want to add [platform] export. Here's the signature I need:
[Platform-specific function template]

Generate:
1. TypeScript ExportAdapter implementation
2. Code template (string) for [platform]
3. Parameter injection logic
4. Validation (syntax check)
5. Unit tests
```

### Limits & Disclaimers

- **AI is not error-proof:** Always review generated tests for logic correctness.
- **Type safety:** Have AI generate with strict types; use `// @ts-check` or run `tsc --noEmit` to validate.
- **Docstrings matter:** Ask AI to include detailed docstrings—they help future maintainers AND catch logic bugs.
- **Security:** Never ask AI to generate auth/crypto code for production without manual security review.

---

## 4. Troubleshooting AI-Generated Code

### Common Issues

| Issue | Cause | Fix |
|-------|-------|-----|
| Generated test doesn't actually test the code | AI tested implementation detail, not behavior | Rewrite to test inputs/outputs, not internals |
| Type errors despite "strict types requested" | AI forgot `extends` or union syntax | Manually add generics bounds |
| Test passes but coverage is 40% | AI generated happy-path only | Ask: "Add edge case tests for [X, Y, Z]" |
| Indicator calculation is off by factor of 2 | AI used wrong formula or misread docs | Provide reference (formula image or Wikipedia link) |
| Export code doesn't compile in target language | AI isn't familiar with platform idioms | Provide working example + comment: "Match this style" |

---

## Next Steps

1. Test system prompt with sample user inputs (build test fixture)
2. Fine-tune LLM model choice (GPT-4o vs. Claude) based on cost + accuracy
3. Set up JSON validation layer (Zod) to reject invalid outputs
4. Create developer quick-start for using local Copilot
5. Document guardrails & error paths for user-facing LLM
