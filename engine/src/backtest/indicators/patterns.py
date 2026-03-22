"""Candlestick pattern recognition indicators.

All pattern functions return a float array in [0, 1] where:
- 0.0  = pattern not detected at that bar
- >0.0 = pattern detected; higher value = stronger / more textbook-like signal
- NaN  = insufficient data (first N bars of multi-candle patterns)

Scoring approach by category
─────────────────────────────
Single-shadow (hammer, shooting_star):
    score = clip(shadow_ratio / ideal_ratio, 0, 1)
    barely-qualifying ≈ 0.25-0.30; textbook perfect ≈ 1.0

Engulfing (bullish_engulfing, bearish_engulfing):
    score = clip(current_body / prev_body / 2.0, 0, 1)
    2× engulf = perfect; exactly qualifies ≈ 0.25

Multi-candle (morning_star, evening_star):
    composite of three sub-scores, averaged

Marubozu / three-candle continuation:
    body_ratio (body/total_range) mapped to [0, 1]

Indecision (doji, spinning_top, harami):
    score = 1.0 − clip(body / threshold, 0, 1)
    tinier body → higher score

All implementations are vectorised with NumPy (no Python for-loops).
"""

from __future__ import annotations

import numpy as np

from src.backtest.indicators import IndicatorRegistry

# ────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────────────────────────────────────


def _safe_div(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Element-wise a / b, returning 0.0 where b == 0 (no divide-by-zero warning)."""
    safe_b = np.where(b != 0, b, 1.0)
    return np.where(b != 0, a / safe_b, 0.0)


# ============================================================================
# REVERSAL PATTERNS — Bearish
# ============================================================================


@IndicatorRegistry.register("shooting_star")
def shooting_star(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    min_upper_shadow_ratio: float = 2.0,
    max_lower_shadow_ratio: float = 0.3,
) -> np.ndarray:
    """Shooting Star pattern (bearish reversal).

    Structure: small body at bottom, long upper shadow (≥ min_upper_shadow_ratio × body),
    minimal lower shadow (≤ max_lower_shadow_ratio × body).

    Score = clip(upper_shadow / body / (4 × min_upper_shadow_ratio), 0, 1).
    A shadow that is exactly the minimum threshold scores ≈ 0.25.
    """
    body = np.abs(close - open_)
    upper_shadow = high - np.maximum(open_, close)
    lower_shadow = np.minimum(open_, close) - low

    upper_ratio = _safe_div(upper_shadow, body)
    lower_ratio = _safe_div(lower_shadow, body)

    ideal_ratio = 4.0 * min_upper_shadow_ratio
    raw_score = np.clip(_safe_div(upper_shadow, body * ideal_ratio), 0.0, 1.0)

    valid = (body > 0) & (upper_ratio >= min_upper_shadow_ratio) & (lower_ratio <= max_lower_shadow_ratio)
    return np.where(valid, raw_score, 0.0).astype(float)


@IndicatorRegistry.register("bearish_engulfing")
def bearish_engulfing(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Bearish Engulfing pattern (2-candle bearish reversal).

    Score = clip(current_bearish_body / (2 × prev_bullish_body), 0, 1).
    A body exactly equal to the previous bar scores 0.5; 2× = perfect (1.0).
    """
    n = len(close)
    result = np.zeros(n, dtype=float)
    if n < 2:
        return result

    prev_body = np.abs(close[:-1] - open_[:-1])
    curr_body = np.abs(close[1:] - open_[1:])

    prev_bullish = close[:-1] > open_[:-1]
    curr_bearish = close[1:] < open_[1:]
    engulfs = (open_[1:] > close[:-1]) & (close[1:] < open_[:-1])

    raw_score = np.clip(_safe_div(curr_body, 2.0 * prev_body), 0.0, 1.0)
    valid = prev_bullish & curr_bearish & engulfs
    result[1:] = np.where(valid, raw_score, 0.0)
    return result


@IndicatorRegistry.register("evening_star")
def evening_star(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    min_first_body_atr: float = 2.0,
    max_middle_body_atr: float = 0.5,
) -> np.ndarray:
    """Evening Star pattern (3-candle bearish reversal).

    Score = average of three sub-scores:
      1. First candle: how much its body exceeds the indecision threshold
      2. Middle candle: how small its body is (1 − relative_body)
      3. Third candle: how deep it penetrates below the first candle's midpoint
    """
    n = len(close)
    result = np.zeros(n, dtype=float)
    if n < 3:
        return result

    body0 = np.abs(close[:-2] - open_[:-2])    # candle i-2
    body1 = np.abs(close[1:-1] - open_[1:-1])  # candle i-1 (middle)
    body2 = np.abs(close[2:] - open_[2:])      # candle i   (confirmation)

    c1_bullish = close[:-2] > open_[:-2]
    c2_small = body1 < body0 * 0.5
    c3_bearish = close[2:] < open_[2:]
    c3_penetrates = close[2:] < (open_[:-2] + close[:-2]) / 2.0

    # Sub-score 1: first candle body relative to middle candle (bigger gap = stronger)
    s1 = np.clip(_safe_div(body0, np.maximum(body1, 1e-10) * 4.0), 0.0, 1.0)
    # Sub-score 2: middle candle smallness (relative to first)
    s2 = 1.0 - np.clip(_safe_div(body1, body0), 0.0, 1.0)
    # Sub-score 3: penetration depth
    midpoint = (open_[:-2] + close[:-2]) / 2.0
    c1_range = np.abs(close[:-2] - open_[:-2])
    s3 = np.clip(_safe_div(midpoint - close[2:], np.maximum(c1_range, 1e-10)), 0.0, 1.0)

    composite = (s1 + s2 + s3) / 3.0

    structural = c1_bullish & c2_small & c3_bearish & c3_penetrates

    if atr is not None:
        a0 = atr[:-2]
        a1 = atr[1:-1]
        safe_a0 = np.where(a0 > 0, a0, np.inf)
        safe_a1 = np.where(a1 > 0, a1, np.inf)
        atr_ok = (body0 >= min_first_body_atr * safe_a0) & (body1 <= max_middle_body_atr * safe_a1)
        structural = structural & atr_ok

    result[2:] = np.where(structural, composite, 0.0)
    return result


@IndicatorRegistry.register("dark_cloud_cover")
def dark_cloud_cover(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Dark Cloud Cover (2-candle bearish reversal).

    Score = clip(penetration_depth / prev_body, 0, 1) where
    penetration_depth = how far the bearish candle closes below the prev midpoint.
    """
    n = len(close)
    result = np.zeros(n, dtype=float)
    if n < 2:
        return result

    prev_bullish = close[:-1] > open_[:-1]
    gap_up = open_[1:] > high[:-1]
    curr_bearish = close[1:] < open_[1:]
    midpoint = (open_[:-1] + close[:-1]) / 2.0
    penetrates = close[1:] < midpoint

    prev_body = np.abs(close[:-1] - open_[:-1])
    penetration = midpoint - close[1:]
    raw_score = np.clip(_safe_div(penetration, np.maximum(prev_body, 1e-10)), 0.0, 1.0)

    valid = prev_bullish & gap_up & curr_bearish & penetrates
    result[1:] = np.where(valid, raw_score, 0.0)
    return result


# ============================================================================
# REVERSAL PATTERNS — Bullish
# ============================================================================


@IndicatorRegistry.register("hammer")
def hammer(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    min_lower_shadow_ratio: float = 2.0,
    max_upper_shadow_ratio: float = 0.3,
) -> np.ndarray:
    """Hammer pattern (bullish reversal).

    Structure: small body at top, long lower shadow (≥ min_lower_shadow_ratio × body),
    minimal upper shadow (≤ max_upper_shadow_ratio × body).

    Score = clip(lower_shadow / body / (4 × min_lower_shadow_ratio), 0, 1).
    """
    body = np.abs(close - open_)
    upper_shadow = high - np.maximum(open_, close)
    lower_shadow = np.minimum(open_, close) - low

    lower_ratio = _safe_div(lower_shadow, body)
    upper_ratio = _safe_div(upper_shadow, body)

    ideal_ratio = 4.0 * min_lower_shadow_ratio
    raw_score = np.clip(_safe_div(lower_shadow, body * ideal_ratio), 0.0, 1.0)

    valid = (body > 0) & (lower_ratio >= min_lower_shadow_ratio) & (upper_ratio <= max_upper_shadow_ratio)
    return np.where(valid, raw_score, 0.0).astype(float)


@IndicatorRegistry.register("bullish_engulfing")
def bullish_engulfing(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Bullish Engulfing pattern (2-candle bullish reversal).

    Score = clip(current_bullish_body / (2 × prev_bearish_body), 0, 1).
    """
    n = len(close)
    result = np.zeros(n, dtype=float)
    if n < 2:
        return result

    prev_body = np.abs(close[:-1] - open_[:-1])
    curr_body = np.abs(close[1:] - open_[1:])

    prev_bearish = close[:-1] < open_[:-1]
    curr_bullish = close[1:] > open_[1:]
    engulfs = (open_[1:] < close[:-1]) & (close[1:] > open_[:-1])

    raw_score = np.clip(_safe_div(curr_body, 2.0 * prev_body), 0.0, 1.0)
    valid = prev_bearish & curr_bullish & engulfs
    result[1:] = np.where(valid, raw_score, 0.0)
    return result


@IndicatorRegistry.register("morning_star")
def morning_star(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    min_first_body_atr: float = 2.0,
    max_middle_body_atr: float = 0.5,
) -> np.ndarray:
    """Morning Star pattern (3-candle bullish reversal).

    Score = average of three sub-scores (symmetrical to evening_star).
    """
    n = len(close)
    result = np.zeros(n, dtype=float)
    if n < 3:
        return result

    body0 = np.abs(close[:-2] - open_[:-2])
    body1 = np.abs(close[1:-1] - open_[1:-1])

    c1_bearish = close[:-2] < open_[:-2]
    c2_small = body1 < body0 * 0.5
    c3_bullish = close[2:] > open_[2:]
    c3_penetrates = close[2:] > (open_[:-2] + close[:-2]) / 2.0

    s1 = np.clip(_safe_div(body0, np.maximum(body1, 1e-10) * 4.0), 0.0, 1.0)
    s2 = 1.0 - np.clip(_safe_div(body1, body0), 0.0, 1.0)
    midpoint = (open_[:-2] + close[:-2]) / 2.0
    c1_range = np.abs(close[:-2] - open_[:-2])
    s3 = np.clip(_safe_div(close[2:] - midpoint, np.maximum(c1_range, 1e-10)), 0.0, 1.0)

    composite = (s1 + s2 + s3) / 3.0
    structural = c1_bearish & c2_small & c3_bullish & c3_penetrates

    if atr is not None:
        a0 = atr[:-2]
        a1 = atr[1:-1]
        safe_a0 = np.where(a0 > 0, a0, np.inf)
        safe_a1 = np.where(a1 > 0, a1, np.inf)
        atr_ok = (body0 >= min_first_body_atr * safe_a0) & (body1 <= max_middle_body_atr * safe_a1)
        structural = structural & atr_ok

    result[2:] = np.where(structural, composite, 0.0)
    return result


@IndicatorRegistry.register("piercing_pattern")
def piercing_pattern(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Piercing Pattern (2-candle bullish reversal).

    Score = penetration above prev midpoint, clipped to [0, 1].
    """
    n = len(close)
    result = np.zeros(n, dtype=float)
    if n < 2:
        return result

    prev_bearish = close[:-1] < open_[:-1]
    gap_down = open_[1:] < low[:-1]
    curr_bullish = close[1:] > open_[1:]
    midpoint = (open_[:-1] + close[:-1]) / 2.0
    penetrates = close[1:] > midpoint

    prev_body = np.abs(close[:-1] - open_[:-1])
    penetration = close[1:] - midpoint
    raw_score = np.clip(_safe_div(penetration, np.maximum(prev_body, 1e-10)), 0.0, 1.0)

    valid = prev_bearish & gap_down & curr_bullish & penetrates
    result[1:] = np.where(valid, raw_score, 0.0)
    return result


# ============================================================================
# CONTINUATION PATTERNS
# ============================================================================


@IndicatorRegistry.register("bullish_marubozu")
def bullish_marubozu(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    min_body_pct: float = 0.95,
    min_body_atr: float = 1.5,
) -> np.ndarray:
    """Bullish Marubozu (strong bullish continuation).

    Score = body_pct_of_range, only when the qualifying conditions are met.
    """
    body = close - open_
    total_range = high - low

    is_bullish = close > open_
    body_ratio = _safe_div(body, total_range)
    body_pct_ok = body_ratio >= min_body_pct

    if atr is not None:
        atr_ok = (atr <= 0) | (body >= min_body_atr * atr)
        valid = is_bullish & body_pct_ok & atr_ok
    else:
        valid = is_bullish & body_pct_ok

    raw_score = np.clip(body_ratio, 0.0, 1.0)
    return np.where(valid, raw_score, 0.0).astype(float)


@IndicatorRegistry.register("bearish_marubozu")
def bearish_marubozu(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    min_body_pct: float = 0.95,
    min_body_atr: float = 1.5,
) -> np.ndarray:
    """Bearish Marubozu (strong bearish continuation).

    Score = body_pct_of_range, only when qualifying conditions are met.
    """
    body = open_ - close
    total_range = high - low

    is_bearish = close < open_
    body_ratio = _safe_div(body, total_range)
    body_pct_ok = body_ratio >= min_body_pct

    if atr is not None:
        atr_ok = (atr <= 0) | (body >= min_body_atr * atr)
        valid = is_bearish & body_pct_ok & atr_ok
    else:
        valid = is_bearish & body_pct_ok

    raw_score = np.clip(body_ratio, 0.0, 1.0)
    return np.where(valid, raw_score, 0.0).astype(float)


@IndicatorRegistry.register("three_white_soldiers")
def three_white_soldiers(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Three White Soldiers (3-candle bullish continuation).

    Score = min of the three body-to-range ratios (weakest link).
    """
    n = len(close)
    result = np.zeros(n, dtype=float)
    if n < 3:
        return result

    # All three bullish
    b0 = close[:-2] > open_[:-2]
    b1 = close[1:-1] > open_[1:-1]
    b2 = close[2:] > open_[2:]

    # Each opens within previous body
    open_in_1 = (open_[1:-1] > open_[:-2]) & (open_[1:-1] < close[:-2])
    open_in_2 = (open_[2:] > open_[1:-1]) & (open_[2:] < close[1:-1])

    # Close near high: upper shadow < 30% of body for each
    for shift in range(3):
        sl = slice(shift, n - 2 + shift) if shift < 2 else slice(shift, n)
        upper_shadow = high[sl] - close[sl]
        body_arr = close[sl] - open_[sl]
        # upper_shadow > 0.3 * body disqualifies; already handled by b0/b1/b2

    upper_shadow_0 = high[:-2] - close[:-2]
    upper_shadow_1 = high[1:-1] - close[1:-1]
    upper_shadow_2 = high[2:] - close[2:]
    body_0 = close[:-2] - open_[:-2]
    body_1 = close[1:-1] - open_[1:-1]
    body_2 = close[2:] - open_[2:]

    small_upper_0 = upper_shadow_0 <= 0.3 * np.maximum(body_0, 1e-10)
    small_upper_1 = upper_shadow_1 <= 0.3 * np.maximum(body_1, 1e-10)
    small_upper_2 = upper_shadow_2 <= 0.3 * np.maximum(body_2, 1e-10)

    total_range_0 = np.maximum(high[:-2] - low[:-2], 1e-10)
    total_range_1 = np.maximum(high[1:-1] - low[1:-1], 1e-10)
    total_range_2 = np.maximum(high[2:] - low[2:], 1e-10)

    r0 = np.clip(body_0 / total_range_0, 0.0, 1.0)
    r1 = np.clip(body_1 / total_range_1, 0.0, 1.0)
    r2 = np.clip(body_2 / total_range_2, 0.0, 1.0)

    composite = np.minimum(np.minimum(r0, r1), r2)
    valid = b0 & b1 & b2 & open_in_1 & open_in_2 & small_upper_0 & small_upper_1 & small_upper_2
    result[2:] = np.where(valid, composite, 0.0)
    return result


@IndicatorRegistry.register("three_black_crows")
def three_black_crows(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Three Black Crows (3-candle bearish continuation).

    Score = min of the three body-to-range ratios (weakest link).
    """
    n = len(close)
    result = np.zeros(n, dtype=float)
    if n < 3:
        return result

    b0 = close[:-2] < open_[:-2]
    b1 = close[1:-1] < open_[1:-1]
    b2 = close[2:] < open_[2:]

    open_in_1 = (open_[1:-1] < open_[:-2]) & (open_[1:-1] > close[:-2])
    open_in_2 = (open_[2:] < open_[1:-1]) & (open_[2:] > close[1:-1])

    lower_shadow_0 = close[:-2] - low[:-2]
    lower_shadow_1 = close[1:-1] - low[1:-1]
    lower_shadow_2 = close[2:] - low[2:]
    body_0 = open_[:-2] - close[:-2]
    body_1 = open_[1:-1] - close[1:-1]
    body_2 = open_[2:] - close[2:]

    small_lower_0 = lower_shadow_0 <= 0.3 * np.maximum(body_0, 1e-10)
    small_lower_1 = lower_shadow_1 <= 0.3 * np.maximum(body_1, 1e-10)
    small_lower_2 = lower_shadow_2 <= 0.3 * np.maximum(body_2, 1e-10)

    total_range_0 = np.maximum(high[:-2] - low[:-2], 1e-10)
    total_range_1 = np.maximum(high[1:-1] - low[1:-1], 1e-10)
    total_range_2 = np.maximum(high[2:] - low[2:], 1e-10)

    r0 = np.clip(body_0 / total_range_0, 0.0, 1.0)
    r1 = np.clip(body_1 / total_range_1, 0.0, 1.0)
    r2 = np.clip(body_2 / total_range_2, 0.0, 1.0)

    composite = np.minimum(np.minimum(r0, r1), r2)
    valid = b0 & b1 & b2 & open_in_1 & open_in_2 & small_lower_0 & small_lower_1 & small_lower_2
    result[2:] = np.where(valid, composite, 0.0)
    return result


# ============================================================================
# INDECISION PATTERNS
# ============================================================================


@IndicatorRegistry.register("doji")
def doji(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    max_body_atr: float = 0.1,
) -> np.ndarray:
    """Doji pattern (indecision).

    Score = 1.0 − clip(body / threshold, 0, 1).
    Perfect doji (zero body) = 1.0; barely-qualifying = near 0.
    """
    body = np.abs(close - open_)

    if atr is not None:
        threshold = np.where(atr > 0, max_body_atr * atr, np.inf)
        score = 1.0 - np.clip(_safe_div(body, np.where(threshold > 0, threshold, 1.0)), 0.0, 1.0)
        valid = body <= threshold
    else:
        # Fallback: body < 0.1% of price
        safe_close = np.where(close > 0, close, np.inf)
        threshold_pct = 0.001 * safe_close
        score = 1.0 - np.clip(_safe_div(body, threshold_pct), 0.0, 1.0)
        valid = (close > 0) & (body / np.where(close > 0, close, 1.0) <= 0.001)

    return np.where(valid, score, 0.0).astype(float)


@IndicatorRegistry.register("dragonfly_doji")
def dragonfly_doji(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    max_body_atr: float = 0.1,
    max_upper_shadow_ratio: float = 0.1,
) -> np.ndarray:
    """Dragonfly Doji (bullish doji: long lower shadow, no upper shadow).

    Score = doji_score × lower_shadow_fraction_of_range.
    """
    doji_score = doji(open_, high, low, close, atr, max_body_atr)

    upper_shadow = high - np.maximum(open_, close)
    lower_shadow = np.minimum(open_, close) - low
    total_range = np.maximum(high - low, 1e-10)

    has_long_lower = lower_shadow > 0.5 * total_range
    has_minimal_upper = upper_shadow <= max_upper_shadow_ratio * total_range
    is_doji = doji_score > 0

    lower_frac = np.clip(_safe_div(lower_shadow, total_range), 0.0, 1.0)
    composite = doji_score * lower_frac

    valid = is_doji & has_long_lower & has_minimal_upper
    return np.where(valid, composite, 0.0).astype(float)


@IndicatorRegistry.register("gravestone_doji")
def gravestone_doji(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    max_body_atr: float = 0.1,
    max_lower_shadow_ratio: float = 0.1,
) -> np.ndarray:
    """Gravestone Doji (bearish doji: long upper shadow, no lower shadow).

    Score = doji_score × upper_shadow_fraction_of_range.
    """
    doji_score = doji(open_, high, low, close, atr, max_body_atr)

    upper_shadow = high - np.maximum(open_, close)
    lower_shadow = np.minimum(open_, close) - low
    total_range = np.maximum(high - low, 1e-10)

    has_long_upper = upper_shadow > 0.5 * total_range
    has_minimal_lower = lower_shadow <= max_lower_shadow_ratio * total_range
    is_doji = doji_score > 0

    upper_frac = np.clip(_safe_div(upper_shadow, total_range), 0.0, 1.0)
    composite = doji_score * upper_frac

    valid = is_doji & has_long_upper & has_minimal_lower
    return np.where(valid, composite, 0.0).astype(float)


@IndicatorRegistry.register("spinning_top")
def spinning_top(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    max_body_atr: float = 0.5,
) -> np.ndarray:
    """Spinning Top (indecision: small body, long shadows on both sides).

    Score = 1.0 − clip(body / threshold, 0, 1), only when both shadows exceed the body.
    """
    body = np.abs(close - open_)
    upper_shadow = high - np.maximum(open_, close)
    lower_shadow = np.minimum(open_, close) - low

    if atr is not None:
        threshold = np.where(atr > 0, max_body_atr * atr, np.inf)
        score = 1.0 - np.clip(_safe_div(body, np.where(threshold > 0, threshold, 1.0)), 0.0, 1.0)
        small_body = body < threshold
    else:
        safe_close = np.where(close > 0, close, np.inf)
        threshold = 0.01 * safe_close
        score = 1.0 - np.clip(_safe_div(body, threshold), 0.0, 1.0)
        small_body = (close > 0) & (body / np.where(close > 0, close, 1.0) < 0.01)

    long_shadows = (upper_shadow > body) & (lower_shadow > body)
    valid = small_body & long_shadows
    return np.where(valid, score, 0.0).astype(float)


@IndicatorRegistry.register("harami")
def harami(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    min_prev_body_atr: float = 2.0,
) -> np.ndarray:
    """Harami pattern (inside bar / indecision).

    Score = 1.0 − clip(current_range / prev_range, 0, 1):
    tighter inside bar → higher score.
    """
    n = len(close)
    result = np.zeros(n, dtype=float)
    if n < 2:
        return result

    prev_range = np.maximum(high[:-1] - low[:-1], 1e-10)
    curr_range = high[1:] - low[1:]

    inside = (high[1:] < high[:-1]) & (low[1:] > low[:-1])
    raw_score = 1.0 - np.clip(_safe_div(curr_range, prev_range), 0.0, 1.0)

    if atr is not None:
        prev_large = (high[:-1] - low[:-1]) >= min_prev_body_atr * np.where(atr[:-1] > 0, atr[:-1], 0.0)
        valid = inside & prev_large
    else:
        valid = inside & (prev_range > 0)

    result[1:] = np.where(valid, raw_score, 0.0)
    return result
