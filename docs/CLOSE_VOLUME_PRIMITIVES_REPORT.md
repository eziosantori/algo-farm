# CLOSE_VOLUME_PRIMITIVES_REPORT.md

## Executive Summary

This short report clarifies a recurring point about the engine DSL:

- the engine can already express "current close" and "current volume"
- the limitation is not data availability
- the limitation is that the strategy DSL works with named indicators, not raw OHLCV fields or arithmetic expressions

In practice, this means:

- `close now` is currently represented via `ema(period=1)` or `sma(period=1)`
- `volume now` is currently represented via `volume_sma(period=1)`
- simple comparisons such as `current_volume > average_volume` are already supported
- richer expressions such as `current_volume > 1.5 * average_volume` are not supported natively

This is a DSL ergonomics problem, not a market-data problem.

---

## What the Engine Supports Today

The strategy DSL evaluates rules by comparing one named indicator to:

- a fixed scalar value
- another named indicator

Current examples that already work:

- `px > ema_20`
- `px crosses_above bollinger_upper`
- `vol_now > vol_avg`

Recommended current proxies:

- `px = ema(period=1)` or `sma(period=1)` -> current close
- `vol_now = volume_sma(period=1)` -> current bar volume
- `vol_avg = volume_sma(period=20)` -> recent average volume

This means the engine already supports practical rules such as:

```json
{
  "indicators": [
    { "name": "px", "type": "ema", "params": { "period": 1 } },
    { "name": "ema_20", "type": "ema", "params": { "period": 20 } },
    { "name": "vol_now", "type": "volume_sma", "params": { "period": 1 } },
    { "name": "vol_avg", "type": "volume_sma", "params": { "period": 20 } }
  ],
  "entry_rules": [
    { "indicator": "px", "condition": ">", "compare_to": "ema_20" },
    { "indicator": "vol_now", "condition": ">", "compare_to": "vol_avg" }
  ]
}
```

---

## What Is Not Supported Natively

The current DSL does not support raw-field references such as:

- `close`
- `open`
- `high`
- `low`
- `volume`

It also does not support arithmetic expressions inside rules, for example:

- `close > session_high + 0.25 * atr`
- `volume_now > volume_avg * 1.5`
- `close > htf_ema and close < bollinger_upper + atr`

So the real constraint is:

- no raw OHLCV primitives in the rule language
- no expression layer on top of indicators

---

## Data Reality Check

For US stocks in the local parquet cache, volume is present and non-zero.

Verified examples in `engine/data/`:

- `AAPL/H1.parquet`
- `AAPL/D1.parquet`
- `MSFT/H1.parquet`
- `NVDA/H1.parquet`
- `AMZN/H1.parquet`
- `TSLA/H1.parquet`

This confirms that volume-based stock strategies are valid in this project.

---

## Current Best Practice

Until the DSL is extended, the most pragmatic convention is:

1. Represent price-now with `ema(period=1)` or `sma(period=1)`
2. Represent volume-now with `volume_sma(period=1)`
3. Compare those series against standard indicators or rolling averages
4. Keep strategy JSON readable through clear indicator names such as `px`, `vol_now`, and `vol_avg`

This is already sufficient for:

- stock breakout with volume confirmation
- stock swing continuation with volume support
- price-vs-band breakout logic
- price-vs-session-level logic

---

## Recommended Improvements

### Option 1: Add passthrough primitives

Add native indicator types such as:

- `close`
- `open`
- `high`
- `low`
- `volume`

This is the smallest and cleanest usability improvement.

Benefits:

- strategy JSON becomes easier to read
- no need for the `ema(1)` or `volume_sma(1)` convention
- no behavioral change to the engine core

Recommended priority: High.

### Option 2: Add scaled comparisons to `RuleDef`

Extend rules with optional fields such as:

- `compare_to_multiplier`
- `compare_to_offset`

Example target behavior:

- `vol_now > vol_avg * 1.5`
- `px > session_high + 0.2 * atr`

Benefits:

- unlocks more realistic breakout and volume filters
- keeps the DSL structured and safer than full free-form expressions

Recommended priority: High.

### Option 3: Add helper indicators for common derived quantities

Examples:

- volume ratio
- price distance from Bollinger upper/lower
- distance from session high/low in ATR units

Benefits:

- better research flexibility
- avoids making the rule language too complex

Recommended priority: Medium.

### Option 4: Add a full expression layer

This would allow generic arithmetic on indicators directly inside rules.

Benefits:

- maximum flexibility

Costs:

- more complexity in validation
- higher implementation and testing burden
- greater risk of making the DSL harder to reason about

Recommended priority: Low for now.

---

## Recommendation

The best near-term path is:

1. Keep using the current convention:
   `px = ema(1)` and `vol_now = volume_sma(1)`
2. Add native passthrough primitives for OHLCV
3. Add `compare_to_multiplier` and `compare_to_offset` to `RuleDef`

That combination would solve most practical strategy-design pain points without turning the DSL into a mini programming language.

---

## Final Conclusion

The engine does not lack access to current price or current volume.

What it lacks is a more explicit and expressive way to reference them in strategy JSON.

Today:

- workable
- correct
- slightly awkward

With two focused DSL improvements:

- native OHLCV primitives
- scaled indicator comparisons

the engine would become materially better for breakout, swing, and stock-volume strategies.
