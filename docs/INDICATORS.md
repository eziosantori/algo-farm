# Indicators Reference Guide

> Complete documentation of all 60+ supported technical indicators. Last updated: March 2026. `session_return` added (overnight mean-reversion support).

---

## Quick Index by Category

- [**Trend Indicators**](#trend-indicators) — SMA, EMA, MACD, SuperTrend
- [**Momentum Indicators**](#momentum-indicators) — RSI, Stochastic, CCI, Williams %R, ROC, OBV
- [**Volatility Indicators**](#volatility-indicators) — ATR, Bollinger Bands, ADX
- [**Volume Indicators**](#volume-indicators) — OBV, Volume SMA
- [**Session & Intraday**](#session--intraday-indicators) — Session Return, Session High/Low, VWAP, Anchored VWAP
- [**Candlestick Patterns**](#candlestick-patterns) — 17 pattern detection indicators
- [**Ichimoku Cloud**](#ichimoku-cloud) — 5-line trend/momentum system
- [**Higher Timeframe (HTF)**](#higher-timeframe-indicators) — EMA and SMA on alternative timeframes
- [**OHLCV Primitives**](#ohlcv-primitives) — Close, Open, High, Low, Volume (raw data)

---

## Trend Indicators

### SMA — Simple Moving Average

**Type:** `sma`

**Description:** Arithmetic mean of closing price over N bars. No smoothing applied.

**Parameters:**
- `period` (int, default=20): Lookback period in bars

**Example JSON:**
```json
{
  "name": "sma_20",
  "type": "sma",
  "params": { "period": 20 }
}
```

**Rule example:**
```json
{
  "indicator": "sma_20",
  "condition": "<",
  "compare_to": "close"
}
```

**Warmup bars:** `period - 1`

---

### EMA — Exponential Moving Average

**Type:** `ema`

**Description:** Smoothed average that weights recent prices more heavily. Responds faster than SMA to price changes.

**Parameters:**
- `period` (int, default=20): Lookback period in bars

**Example JSON:**
```json
{
  "name": "ema_9",
  "type": "ema",
  "params": { "period": 9 }
}
```

**Warmup bars:** `period - 1`

---

### MACD — Moving Average Convergence/Divergence

**Type:** `macd`

**Description:** Difference between fast (12-period) and slow (26-period) EMAs. Returns **MACD line only** (not signal line or histogram).

**Parameters:**
- `fast_period` (int, default=12): Fast EMA period
- `slow_period` (int, default=26): Slow EMA period
- `signal_period` (int, default=9): Signal line period (not included in output; use for reference)

**Example JSON:**
```json
{
  "name": "macd_12_26",
  "type": "macd",
  "params": { "fast_period": 12, "slow_period": 26, "signal_period": 9 }
}
```

**Rule example:**
```json
{
  "indicator": "macd_12_26",
  "condition": "crosses_above",
  "value": 0
}
```

**Warmup bars:** `slow_period - 1` (26 bars by default)

**Note:** For signal line or histogram, compute independently or use MACD crosses 0 as a proxy.

---

### SuperTrend

**Type:** `supertrend` (line) + `supertrend_direction` (trend state)

**Description:** ATR-based volatility channel that identifies trend direction. Always returns two related indicators:

**Components:**
- `supertrend` — The actual support/resistance line
- `supertrend_direction` — Direction flag: +1 = uptrend, -1 = downtrend

**Parameters:**
- `period` (int, default=10): ATR period
- `multiplier` (float, default=3.0): ATR multiplier for band width

**Example JSON:**
```json
{
  "name": "st",
  "type": "supertrend",
  "params": { "period": 10, "multiplier": 3.0 }
},
{
  "name": "st_dir",
  "type": "supertrend_direction",
  "params": { "period": 10, "multiplier": 3.0 }
}
```

**Rule example:**
```json
{
  "indicator": "st_dir",
  "condition": ">",
  "value": 0
}
```

**Warmup bars:** `period - 1` (10 bars by default)

---

## Momentum Indicators

### RSI — Relative Strength Index

**Type:** `rsi`

**Description:** Oscillator measuring momentum on a scale of 0–100. Values >70 = overbought, <30 = oversold.

**Parameters:**
- `period` (int, default=14): Lookback period in bars

**Example JSON:**
```json
{
  "name": "rsi_14",
  "type": "rsi",
  "params": { "period": 14 }
}
```

**Rule examples:**
```json
{ "indicator": "rsi_14", "condition": "<", "value": 30 }  // Oversold
{ "indicator": "rsi_14", "condition": ">", "value": 70 }  // Overbought
```

**Range:** [0, 100]

**Warmup bars:** `period` (14 bars by default)

---

### Stochastic Oscillator

**Type:** `stoch`

**Description:** Momentum indicator comparing current close to price range over N periods. Range: [0, 100].

**Parameters:**
- `k_period` (int, default=14): Lookback period
- `d_period` (int, default=3): Smoothing period for %D (signal line; not included in output)

**Example JSON:**
```json
{
  "name": "stoch_14_3",
  "type": "stoch",
  "params": { "k_period": 14, "d_period": 3 }
}
```

**Rule examples:**
```json
{ "indicator": "stoch_14_3", "condition": "<", "value": 20 }   // Oversold
{ "indicator": "stoch_14_3", "condition": ">", "value": 80 }   // Overbought
```

**Range:** [0, 100]

**Warmup bars:** `k_period - 1` (14 bars by default)

---

### CCI — Commodity Channel Index

**Type:** `cci`

**Description:** Momentum oscillator measuring deviation from average price. Values >100 = overbought, <-100 = oversold.

**Parameters:**
- `period` (int, default=20): Lookback period in bars

**Example JSON:**
```json
{
  "name": "cci_20",
  "type": "cci",
  "params": { "period": 20 }
}
```

**Warmup bars:** `period - 1` (20 bars by default)

---

### Williams %R (Williams Percent Range)

**Type:** `williamsr`

**Description:** Inverted stochastic oscillator. Range: [-100, 0]. Values near -100 = oversold, near 0 = overbought.

**Parameters:**
- `period` (int, default=14): Lookback period in bars

**Example JSON:**
```json
{
  "name": "williamsr_14",
  "type": "williamsr",
  "params": { "period": 14 }
}
```

**Range:** [-100, 0]

**Warmup bars:** `period - 1` (14 bars by default)

---

### ROC — Rate of Change

**Type:** `roc`

**Description:** Momentum indicator measuring percentage change in price over N bars. Positive = price rising, Negative = price falling.

**Parameters:**
- `period` (int, default=12): Lookback period in bars

**Example JSON:**
```json
{
  "name": "roc_12",
  "type": "roc",
  "params": { "period": 12 }
}
```

**Rule example:**
```json
{ "indicator": "roc_12", "condition": ">", "value": 0 }  // Price rising
```

**Warmup bars:** `period` (12 bars by default)

---

### OBV — On-Balance Volume

**Type:** `obv`

**Description:** Cumulative volume indicator. Rising OBV confirms uptrend, falling OBV suggests downtrend weakness.

**Parameters:**
- (none)

**Example JSON:**
```json
{
  "name": "obv",
  "type": "obv",
  "params": {}
}
```

**Warmup bars:** 1 (valid from bar 1)

---

### Volume SMA

**Type:** `volume_sma`

**Description:** Simple moving average of trading volume.

**Parameters:**
- `period` (int, default=20): Lookback period in bars

**Example JSON:**
```json
{
  "name": "vol_sma_20",
  "type": "volume_sma",
  "params": { "period": 20 }
}
```

**Warmup bars:** `period - 1` (20 bars by default)

---

## Volatility Indicators

### ATR — Average True Range

**Type:** `atr`

**Description:** Measures average price movement range. Volatility indicator: higher ATR = higher volatility.

**Parameters:**
- `period` (int, default=14): Lookback period in bars

**Example JSON:**
```json
{
  "name": "atr_14",
  "type": "atr",
  "params": { "period": 14 }
}
```

**Common uses:**
- Stop-loss distance: `entry_price - atr * 2`
- Take-profit distance: `entry_price + atr * 3`

**Warmup bars:** `period` (14 bars by default)

---

### ATR Robust

**Type:** `atr_robust`

**Description:** Robust variant of ATR that excludes True Range outliers (spikes) beyond N standard deviations before averaging. Reduces sensitivity to gaps/news events.

**Parameters:**
- `period` (int, default=14): Lookback period in bars
- `n_sigma` (float, default=2.0): Standard deviation threshold for outlier detection

**Example JSON:**
```json
{
  "name": "atr_robust_14",
  "type": "atr_robust",
  "params": { "period": 14, "n_sigma": 2.0 }
}
```

**Warmup bars:** `period` (14 bars by default)

---

### ATR Gaussian

**Type:** `atr_gaussian`

**Description:** Gaussian-weighted ATR. Combines outlier exclusion (as in `atr_robust`) with bell-curve weighting that emphasizes recent bars. Responsive to current volatility without overreacting to old spikes.

**Parameters:**
- `period` (int, default=14): Lookback period in bars
- `n_sigma` (float, default=2.0): Outlier detection threshold
- `sigma_factor` (float, default=0.4): Bell curve width (higher = flatter, lower = sharper peak on recent bars)

**Example JSON:**
```json
{
  "name": "atr_gaussian_14",
  "type": "atr_gaussian",
  "params": { "period": 14, "n_sigma": 2.0, "sigma_factor": 0.4 }
}
```

**Warmup bars:** `period` (14 bars by default)

---

### Bollinger Bands

**Type:** `bollinger_upper`, `bollinger_lower`, `bollinger_basis`, `bollinger_bands` (width)

**Description:** SMA ± N standard deviations. Identifies overbought/oversold price extremes.

**Components:**
- `bollinger_upper` — Upper band: SMA + (num_std × σ)
- `bollinger_lower` — Lower band: SMA - (num_std × σ)
- `bollinger_basis` — Middle band (SMA)
- `bollinger_bands` — Band width: upper - lower

**Parameters:**
- `period` (int, default=20): SMA period
- `num_std` (float, default=2.0): Number of standard deviations

**Example JSON:**
```json
{
  "name": "bb_upper",
  "type": "bollinger_upper",
  "params": { "period": 20, "num_std": 2.0 }
},
{
  "name": "bb_lower",
  "type": "bollinger_lower",
  "params": { "period": 20, "num_std": 2.0 }
}
```

**Rule examples:**
```json
{ "indicator": "close", "condition": ">", "compare_to": "bb_upper" }   // Price breaks above
{ "indicator": "bb_upper", "condition": "<", "compare_to": "bb_lower" } // Squeezing
```

**Warmup bars:** `period - 1` (20 bars by default)

---

### ADX — Average Directional Index

**Type:** `adx`

**Description:** Trend strength indicator on scale 0–100. Values >25 = strong trend, <20 = weak/no trend.

**Parameters:**
- `period` (int, default=14): Lookback period in bars

**Example JSON:**
```json
{
  "name": "adx_14",
  "type": "adx",
  "params": { "period": 14 }
}
```

**Rule example:**
```json
{ "indicator": "adx_14", "condition": ">", "value": 25 }  // Strong trend exists
```

**Range:** [0, 100]

**Warmup bars:** `period + 5` (19 bars by default, due to internal smoothing)

---

## Session & Intraday Indicators

### Session Active

**Type:** `session_active`

**Description:** Returns 1 if current bar is within active trading hours, 0 otherwise. Requires timestamps and session definition (e.g., "09:00-17:00 Europe/London").

**Parameters:**
- `session` (str, default="default"): Named session (e.g., "london", "newyork", "tokyo")
- `timezone` (str, optional): IANA timezone (e.g., "Europe/London", "America/New_York")

**Example JSON:**
```json
{
  "name": "session",
  "type": "session_active",
  "params": { "session": "london" }
}
```

**Rule example:**
```json
{ "indicator": "session", "condition": ">", "value": 0.5 }  // Only trade during London hours
```

**Output range:** [0, 1]

---

### Session Return

**Type:** `session_return`

**Description:** Computes the return of a named session window as a decimal fraction: `(session_close - session_open) / session_open`. During the session, the running return from the first bar's open is tracked. After the session ends, the final completed return is carried forward until the next session starts. Returns NaN before the first session has been seen.

Use this to gate entries on the prior session's direction and magnitude — for example, to enter SHORT only when the prior US RTH session rose more than 0.5%.

**Parameters:**
- `from_time` (str, default=`"14:30"`): Session start in 'HH:MM' UTC (inclusive). US RTH open = 14:30 UTC (09:30 EST).
- `to_time` (str, default=`"21:00"`): Session end in 'HH:MM' UTC (exclusive). US RTH close = 21:00 UTC (16:00 EST).

**Output:** Decimal fraction. Positive = session closed above open. Negative = session closed below open.

**Warmup:** NaN until the first session bar is seen.

**Example JSON:**
```json
{
  "name": "rth_return",
  "type": "session_return",
  "params": { "from_time": "14:30", "to_time": "21:00" }
}
```

**Rule examples:**
```json
{ "indicator": "rth_return", "condition": ">", "value":  0.005 }
```
→ Prior RTH was bullish by more than 0.5% (SHORT setup — fade the rally).

```json
{ "indicator": "rth_return", "condition": "<", "value": -0.005 }
```
→ Prior RTH was bearish by more than 0.5% (LONG setup — fade the drop).

**Dispatch note:** Uses the OHLC dispatch branch (`open_`, `high`, `low`, `close`, `timestamps`). The session open anchors to the first bar's **open price**; `high` and `low` are received but not used.

---

### Session High / Session Low

**Type:** `session_high`, `session_low`

**Description:** High and low price within the current active session window.

**Parameters:**
- `session` (str, default="default"): Named session

**Example JSON:**
```json
{
  "name": "sess_high",
  "type": "session_high",
  "params": { "session": "london" }
}
```

---

### VWAP — Volume-Weighted Average Price

**Type:** `vwap`, `vwap_upper`, `vwap_lower`

**Description:** Average price weighted by volume. Anchored at session start or day start. `vwap_upper` and `vwap_lower` are bands around VWAP.

**Components:**
- `vwap` — Base VWAP line
- `vwap_upper` — VWAP + offset (e.g., +5 pips)
- `vwap_lower` — VWAP - offset

**Parameters:**
- `offset_pips` (float, default=5): Width of deviation bands (pips)

**Example JSON:**
```json
{
  "name": "vwap",
  "type": "vwap",
  "params": { "offset_pips": 5 }
}
```

**Rule example:**
```json
{ "indicator": "close", "condition": ">", "compare_to": "vwap" }  // Price above VWAP
```

---

### Anchored VWAP

**Type:** `anchored_vwap`, `anchored_vwap_upper`, `anchored_vwap_lower`

**Description:** VWAP anchored to a user-specified anchor bar (e.g., day open or a significant swing point). Useful for measuring overshoot from a specific price level.

**Parameters:**
- `anchor_bar_offset` (int): Bars back to anchor (0 = current bar, 1 = previous bar, etc.)
- `offset_pips` (float, default=5): Deviation band width

**Example JSON:**
```json
{
  "name": "avwap",
  "type": "anchored_vwap",
  "params": { "anchor_bar_offset": 0, "offset_pips": 5 }
}
```

---

## Candlestick Patterns

Candlestick patterns return a **score in [0, 1]** indicating pattern strength:
- **0** = pattern not detected
- **(0, 1)** = pattern detected with varying strength
- **1** = perfect match for the pattern

All patterns require OHLC data.

### Single-Bar Patterns

| Type | Pattern | What it detects |
|------|---------|-----------------|
| `doji` | Doji | Open ≈ Close; indecision |
| `dragonfly_doji` | Dragonfly Doji | Long tail below, small body; bullish |
| `gravestone_doji` | Gravestone Doji | Long tail above, small body; bearish |
| `hammer` | Hammer | Long tail below short body; bullish reversal |
| `shooting_star` | Shooting Star | Long tail above short body; bearish reversal |
| `spinning_top` | Spinning Top | Long body, small tail; indecision |

### Multi-Bar Patterns

| Type | Pattern | What it detects |
|------|---------|-----------------|
| `bullish_engulfing` | Bullish Engulfing | Down bar followed by up bar that engulfs it |
| `bearish_engulfing` | Bearish Engulfing | Up bar followed by down bar that engulfs it |
| `morning_star` | Morning Star | Down close, then down open with small body, then strong up close |
| `evening_star` | Evening Star | Up close, then up open with small body, then strong down close |
| `piercing_pattern` | Piercing Line | Down close, then up open past midpoint of prev bar |
| `dark_cloud_cover` | Dark Cloud Cover | Up close, then down close past midpoint of prev bar |
| `bullish_marubozu` | Bullish Marubozu | Up bar with no lower wick; strength |
| `bearish_marubozu` | Bearish Marubozu | Down bar with no upper wick; weakness |
| `three_white_soldiers` | Three White Soldiers | 3 consecutive up bars with higher closes |
| `three_black_crows` | Three Black Crows | 3 consecutive down bars with lower closes |
| `harami` | Harami | Smaller body completely inside previous bar's range |

**Example JSON:**
```json
{
  "name": "hammer",
  "type": "hammer",
  "params": {}
}
```

**Rule example (filter weak signals):**
```json
{ "indicator": "hammer", "condition": ">", "value": 0.7 }  // Only strong hammers
```

**Warmup bars:** Pattern-specific (1 for single-bar, 2-3 for multi-bar patterns)

---

## Ichimoku Cloud

Ichimoku is a 5-line trend/momentum system. All 5 components must be registered separately:

**Type:** `ichimoku_tenkan`, `ichimoku_kijun`, `ichimoku_senkou_a`, `ichimoku_senkou_b`, `ichimoku_chikou`

**Description:**
- **Tenkan-sen (Conversion Line):** (9-period high + 9-period low) / 2 — fast trend
- **Kijun-sen (Base Line):** (26-period high + 26-period low) / 2 — slow trend
- **Senkou Span A (Leading Span A):** (Tenkan + Kijun) / 2 — current bar, no forward shift
- **Senkou Span B (Leading Span B):** (52-period high + 52-period low) / 2 — current bar, no forward shift
- **Chikou Span (Lagging Span):** Close shifted **backward** by 26 bars (looks at past)

**⚠️ Important:** Senkou A/B are NOT shifted forward (would leak future data in backtests). They represent the current-bar values. Traditional Ichimoku plots them forward on live charts; our backtest implementation avoids data leakage to preserve statistical validity.

**Parameters (shared across all 5):**
- `tenkan_period` (int, default=9): Tenkan lookback
- `kijun_period` (int, default=26): Kijun lookback
- `senkou_b_period` (int, default=52): Senkou B lookback
- `displacement` (int, default=26): Chikou lag (bars back)

**Example JSON:**
```json
{
  "name": "ichi_tenkan",
  "type": "ichimoku_tenkan",
  "params": { "tenkan_period": 9, "kijun_period": 26, "senkou_b_period": 52, "displacement": 26 }
},
{
  "name": "ichi_kijun",
  "type": "ichimoku_kijun",
  "params": { "tenkan_period": 9, "kijun_period": 26, "senkou_b_period": 52, "displacement": 26 }
},
{
  "name": "ichi_a",
  "type": "ichimoku_senkou_a",
  "params": { "tenkan_period": 9, "kijun_period": 26, "senkou_b_period": 52, "displacement": 26 }
},
{
  "name": "ichi_b",
  "type": "ichimoku_senkou_b",
  "params": { "tenkan_period": 9, "kijun_period": 26, "senkou_b_period": 52, "displacement": 26 }
},
{
  "name": "ichi_chikou",
  "type": "ichimoku_chikou",
  "params": { "tenkan_period": 9, "kijun_period": 26, "senkou_b_period": 52, "displacement": 26 }
}
```

**Rule examples:**
```json
{ "indicator": "ichi_tenkan", "condition": ">", "compare_to": "ichi_kijun" }          // Conversion above Base (bullish)
{ "indicator": "close", "condition": ">", "compare_to": "ichi_a" }                    // Price above cloud
{ "indicator": "ichi_tenkan", "condition": "crosses_above", "compare_to": "ichi_kijun" }  // Golden cross
```

**Warmup bars:** `kijun_period - 1` (26 bars by default, the slowest component)

---

## Higher Timeframe Indicators

HTF (Higher TimeFrame) indicators compute a slower-timeframe MA and forward-fill it onto the current chart. Useful for multi-timeframe confirmation.

The base timeframe is **auto-detected** from bar spacing using the 10th-percentile of non-weekend gaps. This correctly handles 24/7 assets (crypto) and most session-based assets (stocks with ≥2 bars/day). For assets with only 1 bar per day (e.g. daily OHLC bars treated as H4), use the explicit `base_timeframe` override.

### HTF EMA

**Type:** `htf_ema`

**Description:** EMA computed on a higher timeframe (e.g., D1) and forward-filled on each base-timeframe bar.

**Parameters:**
- `timeframe` (str): Target higher timeframe — must be strictly larger than the base TF (e.g., `"D1"`, `"H4"`)
- `period` (int, default=50): EMA period applied on the resampled HTF bars
- `base_timeframe` (str, optional): Explicit base timeframe override (e.g., `"H4"`). Use this for session-based assets (stocks) when auto-detection might misclassify sparse bars as a higher TF.

**Auto-detection notes:**
- 24/7 crypto (e.g., H4 base → 6 bars/day): auto-detection works correctly.
- Session stocks with ≥2 bars/day: auto-detection works (p10 captures the typical intrabar gap).
- Session stocks with 1 bar/day: auto-detection returns D1 → requesting `timeframe="D1"` raises `ValueError`. **Use `base_timeframe="H4"` (or the actual base TF) to override.**

**Example JSON (standard):**
```json
{
  "name": "ema_d1",
  "type": "htf_ema",
  "params": { "timeframe": "D1", "period": 50 }
}
```

**Example JSON (explicit base for stock data):**
```json
{
  "name": "ema_d1",
  "type": "htf_ema",
  "params": { "timeframe": "D1", "period": 50, "base_timeframe": "H4" }
}
```

**Rule example (filter to trend):**
```json
{ "indicator": "close", "condition": ">", "compare_to": "ema_d1" }
```

---

### HTF SMA

**Type:** `htf_sma`

**Description:** SMA computed on a higher timeframe and forward-filled on each base-timeframe bar.

**Parameters:**
- `timeframe` (str): Target higher timeframe (e.g., `"H4"`, `"D1"`)
- `period` (int, default=50): SMA period on target timeframe
- `base_timeframe` (str, optional): Explicit base timeframe override. Same rules as `htf_ema`.

**Example JSON:**
```json
{
  "name": "sma_h4",
  "type": "htf_sma",
  "params": { "timeframe": "H4", "period": 20 }
}
```

---

## OHLCV Primitives

Raw access to OHLCV data. Often used in rules to compare price to indicators or other price points.

### Close

**Type:** `close`

**Description:** Closing price of current bar.

**Example JSON:**
```json
{
  "name": "close",
  "type": "close",
  "params": {}
}
```

**Rule example:**
```json
{ "indicator": "close", "condition": ">", "compare_to": "sma_20" }
```

---

### Open, High, Low

**Type:** `open`, `high`, `low`

**Description:** Opening, highest, and lowest prices of current bar.

**Example JSON:**
```json
{
  "name": "open",
  "type": "open",
  "params": {}
},
{
  "name": "high",
  "type": "high",
  "params": {}
},
{
  "name": "low",
  "type": "low",
  "params": {}
}
```

---

### Volume

**Type:** `volume`

**Description:** Trading volume of current bar.

**Example JSON:**
```json
{
  "name": "vol",
  "type": "volume",
  "params": {}
}
```

---

## Rules Reference

### Supported Conditions

| Condition | Meaning | Example |
|-----------|---------|---------|
| `>` | Greater than | `rsi > 70` (overbought) |
| `<` | Less than | `rsi < 30` (oversold) |
| `>=` | Greater than or equal | `adx >= 25` (strong trend) |
| `<=` | Less than or equal | — |
| `crosses_above` | Value crosses above threshold from below | `tenkan crosses_above kijun` |
| `crosses_below` | Value crosses below threshold from above | `rsi crosses_below 70` (overbought exit) |

### Entry Rules (AND Logic)

All entry rules must be **true** to fire entry:

```json
"entry_rules": [
  { "indicator": "rsi_14", "condition": "<", "value": 30 },
  { "indicator": "ema_9", "condition": ">", "compare_to": "ema_50" },
  { "indicator": "adx_14", "condition": ">", "value": 25 }
]
// Entry fires when RSI < 30 AND EMA9 > EMA50 AND ADX > 25
```

### Exit Rules (OR Logic)

Any exit rule being **true** will close the position:

```json
"exit_rules": [
  { "indicator": "rsi_14", "condition": ">", "value": 70 },
  { "indicator": "supertrend_direction", "condition": "<", "value": 0 },
  { "indicator": "time_bars_in_trade", "condition": ">", "value": 50 }
]
// Exit if RSI > 70 OR ST turns down OR 50 bars elapsed
```

---

## Best Practices

1. **Avoid correlated indicators in entry rules:** RSI + Stochastic together are redundant ❌
   - Better: RSI for entry + separate EMA trend filter ✅

2. **Use candlestick patterns as anti-filters (negative AND), not positive AND:**
   - Do NOT: `"entry_rules": [... , {"indicator": "hammer", "condition": ">", "value": 0}]` ❌ (kills trade frequency)
   - Better: Use as signal gate or sizing input ✅

3. **ATR use cases:**
   - Dynamic SL: `sl = entry - atr * 2.0`
   - Dynamic TP: `tp = entry + atr * 3.0`
   - Filter low-vol periods: `adx > 25 AND atr > min_atr`

4. **Ichimoku interpretation:**
   - Cloud above price = resistance / bearish
   - Cloud below price = support / bullish
   - Tenkan > Kijun = short-term bullish
   - Price > Cloud = strong uptrend

5. **Session filters prevent overnight gap risk:**
   - London session for GBP/USD pairs
   - New York session for USD pairs
   - Avoid exact market-open (high slippage, spreads)

---

## Indicator Availability by Phase

| Phase | New Indicators |
|-------|---|
| 1 | SMA, EMA, MACD, RSI, Stochastic, ATR, Bollinger Bands, ADX, CCI, OBV, Williams %R, SuperTrend, OHLCV |
| 2 | Session, VWAP, Anchored VWAP |
| 3 | ROC, Volume SMA |
| 4 | Candlestick patterns (17 types) |
| 5 | Ichimoku Cloud (5 types), ATR variants (Robust, Gaussian), HTF indicators |

---

## See Also

- [AGENTS.md](../AGENTS.md) — Strategy definition format
- [SCHEMA.md](SCHEMA.md) — Full StrategyDefinition JSON schema
- [CONVENTIONS.md](CONVENTIONS.md) — Naming conventions
