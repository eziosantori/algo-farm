# Strategy Ideas Template - Engine-Aligned Research Notes

## Purpose

This document maps a strategy family that fits the current Algo Farm engine and is worth
researching across assets and timeframes.

The goal is not generic theory. The goal is to describe ideas that are close enough to the
current engine and DSL that they can be turned into pilot strategy JSON files without
inventing unsupported runtime behavior.

All artifacts should remain in English.

---

## Why This Family Fits the Current Engine

Important implementation facts:

- list the engine capabilities that materially support this family
- mention the most relevant indicators, execution features, and filters already available
- note whether shorts, session logic, HTF bias, VWAP/AVWAP, or candlestick helpers matter here

Practical consequence:

- summarize what kinds of ideas are a strong fit
- summarize what kinds of ideas should be avoided or simplified

---

## Design Principles

- list the core research principles for this family
- keep the bullets short and practical
- focus on regime, timing, exits, and portability

---

## Current Engine Constraints That Matter

- list only the constraints that directly affect this family
- mention UTC session assumptions when time windows matter
- mention where logic must stay simple because the runtime is not a state machine
- distinguish supported behavior from discretionary concepts that are not modeled

---

## Asset and Timeframe Map

These are practical starting points, not fixed rules.

| Family | Better assets | Better timeframes | Why |
|---|---|---|---|
| Example family | Asset list | TF list | Short reason |

High-level guidance:

- add 3-5 bullets with asset and timeframe heuristics

---

## Strategy Families

## 1. Strategy Name

**Core idea**  
Short plain-English thesis.

**Why this family matters here**  
Explain the specific role of the core indicator or concept.

**Best assets**  
Asset list.

**Best timeframes**  
Timeframe list.

**Market regime fit**  
Describe when the strategy should work and when it should not.

**Suggested indicator stack**  
List the engine indicators or execution features that form the baseline.

**Suggested rule structure**  
Describe the rule flow in language that is close to the current DSL.

**Exit logic**  
Describe the baseline exit thesis and one optional variant if useful.

**Main risks**  
List the primary failure modes.

**Engine fit**  
Rate it briefly: `Very high`, `High`, `Medium`, or `Low`.

**Research notes / first test order**  
State the best first assets, timeframes, and comparison variants.

## 2. Strategy Name

Repeat the same subheading structure.

## 3. Strategy Name

Repeat the same subheading structure.

---

## Research Priority and Next Testing Order

Suggested order:

1. First candidate
2. Second candidate
3. Third candidate

Why this order:

- explain why the selected order is practical for the current engine
- mention which ideas are best as baselines and which need more filtering

Practical recommendation:

- close with 2-4 bullets on how to start testing the family
