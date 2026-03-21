# Candlestick Patterns for Algo Trading

**Purpose:** Catalog of candlestick patterns that can improve algo performance when used as entry/exit filters or confirmation signals.

**Classification:** Price Action Indicators / Pattern Recognition

**Implementation Status:** 📝 Ideas (not yet implemented)

---

## 🎯 Why Candlestick Patterns in Algo Trading?

Candlestick patterns capture market psychology and price action structure:

- **Reversal signals** → filter entries in mean-reversion strategies
- **Continuation patterns** → confirm trend-following entries
- **Indecision patterns** → avoid entries in choppy markets
- **High/low conviction** → adjust position sizing based on pattern strength

**Key advantage:** Patterns work on any timeframe and can be combined with technical indicators (RSI, EMA, ADX, etc.)

---

## 📊 Pattern Categories

### 1. **Reversal Patterns** (Trend change signals)

#### 🔴 Bearish Reversal (Sell signals)

**Shooting Star**
- **Structure:** Small body at bottom, long upper shadow (≥2x body), little/no lower shadow
- **Conditions:**
  ```python
  upper_shadow = high - max(open, close)
  body = abs(close - open)
  lower_shadow = min(open, close) - low
  
  shooting_star = (
      upper_shadow >= 2 * body and
      lower_shadow <= 0.3 * body and
      close < open  # bearish close preferred
  )
  ```
- **Interpretation:** Rejection at highs, sellers took control
- **Use case:** Exit long positions, filter short entries in trend-following

**Evening Star** (3-candle pattern)
- **Structure:**
  1. Large bullish candle
  2. Small-body candle (gap up) - indecision
  3. Large bearish candle closing below first candle's midpoint
- **Conditions:**
  ```python
  c1_bullish = close[0] > open[0] and (close[0] - open[0]) > 2 * ATR
  c2_small = abs(close[1] - open[1]) < 0.5 * ATR
  c3_bearish = close[2] < open[2] and close[2] < (open[0] + close[0]) / 2
  
  evening_star = c1_bullish and c2_small and c3_bearish
  ```
- **Use case:** Strong reversal signal, combine with RSI > 70 for overbought confirmation

**Bearish Engulfing**
- **Structure:** Bullish candle followed by larger bearish candle that completely engulfs it
- **Conditions:**
  ```python
  prev_bullish = close[0] > open[0]
  curr_bearish = close[1] < open[1]
  engulfing = open[1] > close[0] and close[1] < open[0]
  
  bearish_engulfing = prev_bullish and curr_bearish and engulfing
  ```
- **Use case:** Exit longs, filter shorts in mean-reversion after overbought

**Dark Cloud Cover**
- **Structure:** Bullish candle → bearish candle opening above prev high, closing below midpoint
- **Conditions:**
  ```python
  prev_bullish = close[0] > open[0]
  gap_up = open[1] > high[0]
  deep_penetration = close[1] < (open[0] + close[0]) / 2
  
  dark_cloud = prev_bullish and gap_up and deep_penetration
  ```
- **Use case:** Reversal confirmation at resistance levels

#### 🟢 Bullish Reversal (Buy signals)

**Hammer**
- **Structure:** Small body at top, long lower shadow (≥2x body), little/no upper shadow
- **Conditions:**
  ```python
  lower_shadow = min(open, close) - low
  body = abs(close - open)
  upper_shadow = high - max(open, close)
  
  hammer = (
      lower_shadow >= 2 * body and
      upper_shadow <= 0.3 * body and
      close > open  # bullish close preferred
  )
  ```
- **Interpretation:** Rejection at lows, buyers stepped in
- **Use case:** Entry filter for mean-reversion strategies when RSI < 30

**Morning Star** (3-candle pattern)
- **Structure:**
  1. Large bearish candle
  2. Small-body candle (gap down) - indecision
  3. Large bullish candle closing above first candle's midpoint
- **Conditions:**
  ```python
  c1_bearish = close[0] < open[0] and (open[0] - close[0]) > 2 * ATR
  c2_small = abs(close[1] - open[1]) < 0.5 * ATR
  c3_bullish = close[2] > open[2] and close[2] > (open[0] + close[0]) / 2
  
  morning_star = c1_bearish and c2_small and c3_bullish
  ```
- **Use case:** Strong buy signal after downtrend, combine with oversold RSI

**Bullish Engulfing**
- **Structure:** Bearish candle followed by larger bullish candle that completely engulfs it
- **Conditions:**
  ```python
  prev_bearish = close[0] < open[0]
  curr_bullish = close[1] > open[1]
  engulfing = open[1] < close[0] and close[1] > open[0]
  
  bullish_engulfing = prev_bearish and curr_bullish and engulfing
  ```
- **Use case:** Entry confirmation in oversold zones

**Piercing Pattern**
- **Structure:** Bearish candle → bullish candle opening below prev low, closing above midpoint
- **Conditions:**
  ```python
  prev_bearish = close[0] < open[0]
  gap_down = open[1] < low[0]
  deep_penetration = close[1] > (open[0] + close[0]) / 2
  
  piercing = prev_bearish and gap_down and deep_penetration
  ```
- **Use case:** Reversal confirmation at support levels

---

### 2. **Continuation Patterns** (Trend persistence)

**Bullish Marubozu**
- **Structure:** Long bullish candle, no shadows (or very small)
- **Conditions:**
  ```python
  body = close - open
  total_range = high - low
  
  bullish_marubozu = (
      close > open and
      body >= 0.95 * total_range and
      body > 1.5 * ATR
  )
  ```
- **Use case:** Strong bullish momentum, add to trend-following positions

**Bearish Marubozu**
- **Structure:** Long bearish candle, no shadows
- **Use case:** Strong bearish momentum, stay short in downtrends

**Three White Soldiers** (3-candle bullish)
- **Structure:** 3 consecutive bullish candles, each opening within prev body, closing near high
- **Use case:** Confirmed uptrend, filter long entries

**Three Black Crows** (3-candle bearish)
- **Structure:** 3 consecutive bearish candles, each opening within prev body, closing near low
- **Use case:** Confirmed downtrend, filter short entries

---

### 3. **Indecision Patterns** (Avoid trading)

**Doji**
- **Structure:** Open ≈ Close (very small body), any shadow length
- **Conditions:**
  ```python
  body = abs(close - open)
  doji = body <= 0.1 * ATR
  ```
- **Types:**
  - **Dragonfly Doji:** Long lower shadow, no upper shadow (bullish at support)
  - **Gravestone Doji:** Long upper shadow, no lower shadow (bearish at resistance)
  - **Long-Legged Doji:** Long shadows both sides (high volatility, indecision)
- **Use case:** **Avoid entries** when Doji appears, market is indecisive

**Spinning Top**
- **Structure:** Small body, long shadows on both sides
- **Conditions:**
  ```python
  body = abs(close - open)
  upper_shadow = high - max(open, close)
  lower_shadow = min(open, close) - low
  
  spinning_top = (
      body < 0.5 * ATR and
      upper_shadow > body and
      lower_shadow > body
  )
  ```
- **Use case:** **Avoid entries** in choppy markets, wait for direction

**Harami** (Inside bar)
- **Structure:** Large candle followed by small candle completely inside prev range
- **Conditions:**
  ```python
  prev_large = (high[0] - low[0]) > 2 * ATR
  inside = high[1] < high[0] and low[1] > low[0]
  
  harami = prev_large and inside
  ```
- **Use case:** Consolidation, wait for breakout direction

---

## 🔧 Implementation Strategy

### How to Use Patterns in Algo Farm

**Option 1: As Entry/Exit Filters**
```python
# Example: Add Hammer as long entry filter
class MeanReversionWithHammer(Strategy):
    def __init__(self):
        self.rsi = RSI(14)
        
    def entry_conditions(self):
        hammer = self.is_hammer(self.data.iloc[-1])
        oversold = self.rsi.iloc[-1] < 30
        
        return hammer and oversold
        
    def is_hammer(self, candle):
        lower_shadow = min(candle.open, candle.close) - candle.low
        body = abs(candle.close - candle.open)
        upper_shadow = candle.high - max(candle.open, candle.close)
        
        return (
            lower_shadow >= 2 * body and
            upper_shadow <= 0.3 * body and
            candle.close > candle.open
        )
```

**Option 2: As Confirmation Signals**
```python
# Combine EMA cross with Engulfing pattern
def entry_conditions(self):
    ema_cross = self.ema_20[-1] > self.ema_50[-1]
    bullish_engulfing = self.is_bullish_engulfing()
    
    return ema_cross and bullish_engulfing
```

**Option 3: As Pattern Indicators (library)**
```python
# Create reusable pattern detection library
from indicators.patterns import (
    detect_hammer,
    detect_engulfing,
    detect_morning_star,
    detect_doji
)

# Use in any strategy
class MyStrategy(Strategy):
    def entry_conditions(self):
        hammer = detect_hammer(self.data)
        oversold = self.rsi[-1] < 30
        return hammer and oversold
```

---

## 📁 Proposed File Structure

Add candlestick patterns as a new indicator category:

```
engine/
├── indicators/
│   ├── technical/        # Existing (RSI, EMA, etc.)
│   └── patterns/         # NEW: Candlestick patterns
│       ├── __init__.py
│       ├── reversal.py   # hammer, engulfing, stars
│       ├── continuation.py  # marubozu, soldiers/crows
│       └── indecision.py    # doji, spinning_top, harami
```

---

## 🎯 Priority Patterns for Implementation

**Phase 1: Core Reversal (High Impact)**
1. ✅ Hammer / Shooting Star
2. ✅ Bullish / Bearish Engulfing
3. ✅ Morning / Evening Star

**Phase 2: Indecision Filters**
4. ✅ Doji (all types)
5. ✅ Spinning Top

**Phase 3: Continuation**
6. ✅ Marubozu
7. ✅ Three Soldiers / Crows

**Phase 4: Advanced**
8. Harami
9. Piercing / Dark Cloud
10. Custom multi-candle patterns

---

## 📊 Backtesting Strategy Combinations

Test patterns with existing strategies:

| Strategy Type | Pattern Filter | Expected Impact |
|--------------|----------------|-----------------|
| Mean Reversion | Hammer @ RSI < 30 | Higher Win Rate |
| Mean Reversion | Shooting Star @ RSI > 70 | Better exits |
| Trend Following | Marubozu + ADX > 25 | Stronger entries |
| Breakout | Engulfing after consolidation | Confirm breakouts |
| Any | Doji filter (avoid entry) | Reduce choppy losses |

---

## 🚀 Next Steps

1. **Create pattern detection library** (`engine/indicators/patterns/`)
2. **Add pattern parameters to strategy JSON** (e.g., `"use_hammer_filter": true`)
3. **Backtest existing strategies WITH/WITHOUT patterns** → measure improvement
4. **Document pattern performance** per instrument/timeframe
5. **Add to optimization space** (e.g., optimize shadow ratio thresholds)

---

## 📚 References

- **Candlestick Charting Explained** (Gregory L. Morris)
- **Japanese Candlestick Charting Techniques** (Steve Nison)
- **TA-Lib Pattern Recognition** (open source implementation reference)

---

_Created: 2026-03-21_  
_Status: Ideas / Not Implemented_  
_Next: Build `engine/indicators/patterns/` library_
