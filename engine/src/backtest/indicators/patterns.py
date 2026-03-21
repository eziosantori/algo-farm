"""Candlestick pattern recognition indicators.

All pattern functions return a boolean array where:
- True = pattern detected at that bar
- False = pattern not detected
- NaN = insufficient data to detect

Pattern detection uses OHLC data and optional ATR for body size thresholds.
"""

from __future__ import annotations

import numpy as np

from src.backtest.indicators import IndicatorRegistry


# ============================================================================
# REVERSAL PATTERNS (Bearish)
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

    Structure: Small body at bottom, long upper shadow (≥2x body), minimal lower shadow.

    Parameters
    ----------
    open_:  Opening prices
    high:   High prices
    low:    Low prices
    close:  Closing prices
    min_upper_shadow_ratio: Minimum ratio of upper_shadow / body (default 2.0)
    max_lower_shadow_ratio: Maximum ratio of lower_shadow / body (default 0.3)

    Returns
    -------
    Boolean array: True where shooting star detected.
    """
    result = np.full(len(close), False, dtype=bool)

    body = np.abs(close - open_)
    upper_shadow = high - np.maximum(open_, close)
    lower_shadow = np.minimum(open_, close) - low

    for i in range(len(close)):
        if body[i] == 0:
            continue  # Doji, not shooting star

        has_long_upper = upper_shadow[i] >= min_upper_shadow_ratio * body[i]
        has_small_lower = lower_shadow[i] <= max_lower_shadow_ratio * body[i]

        result[i] = has_long_upper and has_small_lower

    return result


@IndicatorRegistry.register("bearish_engulfing")
def bearish_engulfing(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Bearish Engulfing pattern (2-candle bearish reversal).

    Structure:
    - Previous candle: bullish (close > open)
    - Current candle: bearish (close < open) AND completely engulfs previous body

    Returns
    -------
    Boolean array: True at index i if candle i engulfs i-1.
    """
    result = np.full(len(close), False, dtype=bool)

    for i in range(1, len(close)):
        prev_bullish = close[i - 1] > open_[i - 1]
        curr_bearish = close[i] < open_[i]
        engulfs = open_[i] > close[i - 1] and close[i] < open_[i - 1]

        result[i] = prev_bullish and curr_bearish and engulfs

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

    Structure:
    1. Large bullish candle
    2. Small-body candle (indecision)
    3. Large bearish candle closing below first candle's midpoint

    Parameters
    ----------
    atr:  Average True Range for body size validation (optional)
    min_first_body_atr: Minimum body size for first candle (in ATR multiples)
    max_middle_body_atr: Maximum body size for middle candle (in ATR multiples)

    Returns
    -------
    Boolean array: True at index i if evening star completes at i.
    """
    result = np.full(len(close), False, dtype=bool)

    for i in range(2, len(close)):
        c1_bullish = close[i - 2] > open_[i - 2]
        c2_small = abs(close[i - 1] - open_[i - 1]) < abs(close[i - 2] - open_[i - 2]) * 0.5
        c3_bearish = close[i] < open_[i]
        c3_penetrates = close[i] < (open_[i - 2] + close[i - 2]) / 2.0

        # Optional ATR validation
        if atr is not None:
            if atr[i] == 0:
                continue
            c1_large_enough = abs(close[i - 2] - open_[i - 2]) >= min_first_body_atr * atr[i - 2]
            c2_small_enough = abs(close[i - 1] - open_[i - 1]) <= max_middle_body_atr * atr[i - 1]
            result[i] = c1_bullish and c2_small and c3_bearish and c3_penetrates and c1_large_enough and c2_small_enough
        else:
            result[i] = c1_bullish and c2_small and c3_bearish and c3_penetrates

    return result


@IndicatorRegistry.register("dark_cloud_cover")
def dark_cloud_cover(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Dark Cloud Cover pattern (2-candle bearish reversal).

    Structure:
    - Previous: bullish candle
    - Current: bearish candle opening above prev high, closing below prev midpoint
    """
    result = np.full(len(close), False, dtype=bool)

    for i in range(1, len(close)):
        prev_bullish = close[i - 1] > open_[i - 1]
        gap_up = open_[i] > high[i - 1]
        deep_penetration = close[i] < (open_[i - 1] + close[i - 1]) / 2.0
        curr_bearish = close[i] < open_[i]

        result[i] = prev_bullish and gap_up and deep_penetration and curr_bearish

    return result


# ============================================================================
# REVERSAL PATTERNS (Bullish)
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

    Structure: Small body at top, long lower shadow (≥2x body), minimal upper shadow.

    Parameters
    ----------
    min_lower_shadow_ratio: Minimum ratio of lower_shadow / body (default 2.0)
    max_upper_shadow_ratio: Maximum ratio of upper_shadow / body (default 0.3)

    Returns
    -------
    Boolean array: True where hammer detected.
    """
    result = np.full(len(close), False, dtype=bool)

    body = np.abs(close - open_)
    upper_shadow = high - np.maximum(open_, close)
    lower_shadow = np.minimum(open_, close) - low

    for i in range(len(close)):
        if body[i] == 0:
            continue  # Doji, not hammer

        has_long_lower = lower_shadow[i] >= min_lower_shadow_ratio * body[i]
        has_small_upper = upper_shadow[i] <= max_upper_shadow_ratio * body[i]

        result[i] = has_long_lower and has_small_upper

    return result


@IndicatorRegistry.register("bullish_engulfing")
def bullish_engulfing(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Bullish Engulfing pattern (2-candle bullish reversal).

    Structure:
    - Previous candle: bearish (close < open)
    - Current candle: bullish (close > open) AND completely engulfs previous body
    """
    result = np.full(len(close), False, dtype=bool)

    for i in range(1, len(close)):
        prev_bearish = close[i - 1] < open_[i - 1]
        curr_bullish = close[i] > open_[i]
        engulfs = open_[i] < close[i - 1] and close[i] > open_[i - 1]

        result[i] = prev_bearish and curr_bullish and engulfs

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

    Structure:
    1. Large bearish candle
    2. Small-body candle (indecision)
    3. Large bullish candle closing above first candle's midpoint

    Parameters
    ----------
    atr:  Average True Range for body size validation (optional)
    min_first_body_atr: Minimum body size for first candle (in ATR multiples)
    max_middle_body_atr: Maximum body size for middle candle (in ATR multiples)
    """
    result = np.full(len(close), False, dtype=bool)

    for i in range(2, len(close)):
        c1_bearish = close[i - 2] < open_[i - 2]
        c2_small = abs(close[i - 1] - open_[i - 1]) < abs(close[i - 2] - open_[i - 2]) * 0.5
        c3_bullish = close[i] > open_[i]
        c3_penetrates = close[i] > (open_[i - 2] + close[i - 2]) / 2.0

        # Optional ATR validation
        if atr is not None:
            if atr[i] == 0:
                continue
            c1_large_enough = abs(close[i - 2] - open_[i - 2]) >= min_first_body_atr * atr[i - 2]
            c2_small_enough = abs(close[i - 1] - open_[i - 1]) <= max_middle_body_atr * atr[i - 1]
            result[i] = c1_bearish and c2_small and c3_bullish and c3_penetrates and c1_large_enough and c2_small_enough
        else:
            result[i] = c1_bearish and c2_small and c3_bullish and c3_penetrates

    return result


@IndicatorRegistry.register("piercing_pattern")
def piercing_pattern(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Piercing Pattern (2-candle bullish reversal).

    Structure:
    - Previous: bearish candle
    - Current: bullish candle opening below prev low, closing above prev midpoint
    """
    result = np.full(len(close), False, dtype=bool)

    for i in range(1, len(close)):
        prev_bearish = close[i - 1] < open_[i - 1]
        gap_down = open_[i] < low[i - 1]
        deep_penetration = close[i] > (open_[i - 1] + close[i - 1]) / 2.0
        curr_bullish = close[i] > open_[i]

        result[i] = prev_bearish and gap_down and deep_penetration and curr_bullish

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
    """Bullish Marubozu pattern (strong bullish continuation).

    Structure: Long bullish candle with minimal/no shadows.

    Parameters
    ----------
    min_body_pct: Minimum body size as % of total range (default 95%)
    min_body_atr: Minimum body size in ATR multiples (if ATR provided)
    """
    result = np.full(len(close), False, dtype=bool)

    body = close - open_
    total_range = high - low

    for i in range(len(close)):
        if total_range[i] == 0:
            continue

        is_bullish = close[i] > open_[i]
        body_ratio = body[i] / total_range[i]
        body_large_enough = body_ratio >= min_body_pct

        if atr is not None and atr[i] > 0:
            body_large_enough = body_large_enough and body[i] >= min_body_atr * atr[i]

        result[i] = is_bullish and body_large_enough

    return result


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
    """Bearish Marubozu pattern (strong bearish continuation).

    Structure: Long bearish candle with minimal/no shadows.
    """
    result = np.full(len(close), False, dtype=bool)

    body = open_ - close  # bearish body
    total_range = high - low

    for i in range(len(close)):
        if total_range[i] == 0:
            continue

        is_bearish = close[i] < open_[i]
        body_ratio = body[i] / total_range[i]
        body_large_enough = body_ratio >= min_body_pct

        if atr is not None and atr[i] > 0:
            body_large_enough = body_large_enough and body[i] >= min_body_atr * atr[i]

        result[i] = is_bearish and body_large_enough

    return result


@IndicatorRegistry.register("three_white_soldiers")
def three_white_soldiers(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Three White Soldiers (3-candle bullish continuation).

    Structure: 3 consecutive bullish candles, each opening within previous body, closing near high.
    """
    result = np.full(len(close), False, dtype=bool)

    for i in range(2, len(close)):
        # All three bullish
        all_bullish = (close[i - 2] > open_[i - 2]) and (close[i - 1] > open_[i - 1]) and (close[i] > open_[i])

        # Each opens within previous body
        open_in_body_1 = open_[i - 1] > open_[i - 2] and open_[i - 1] < close[i - 2]
        open_in_body_2 = open_[i] > open_[i - 1] and open_[i] < close[i - 1]

        # Close near high (upper shadow < 30% of body)
        for j in range(i - 2, i + 1):
            upper_shadow = high[j] - close[j]
            body = close[j] - open_[j]
            if body > 0 and upper_shadow > 0.3 * body:
                all_bullish = False

        result[i] = all_bullish and open_in_body_1 and open_in_body_2

    return result


@IndicatorRegistry.register("three_black_crows")
def three_black_crows(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Three Black Crows (3-candle bearish continuation).

    Structure: 3 consecutive bearish candles, each opening within previous body, closing near low.
    """
    result = np.full(len(close), False, dtype=bool)

    for i in range(2, len(close)):
        # All three bearish
        all_bearish = (close[i - 2] < open_[i - 2]) and (close[i - 1] < open_[i - 1]) and (close[i] < open_[i])

        # Each opens within previous body
        open_in_body_1 = open_[i - 1] < open_[i - 2] and open_[i - 1] > close[i - 2]
        open_in_body_2 = open_[i] < open_[i - 1] and open_[i] > close[i - 1]

        # Close near low (lower shadow < 30% of body)
        for j in range(i - 2, i + 1):
            lower_shadow = close[j] - low[j]
            body = open_[j] - close[j]
            if body > 0 and lower_shadow > 0.3 * body:
                all_bearish = False

        result[i] = all_bearish and open_in_body_1 and open_in_body_2

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

    Structure: Open ≈ Close (very small body), any shadow length.

    Parameters
    ----------
    atr:  Average True Range for body size threshold
    max_body_atr: Maximum body size in ATR multiples (default 0.1 = 10% of ATR)
    """
    result = np.full(len(close), False, dtype=bool)

    body = np.abs(close - open_)

    if atr is not None:
        for i in range(len(close)):
            if atr[i] > 0:
                result[i] = body[i] <= max_body_atr * atr[i]
    else:
        # Fallback: body < 0.1% of price
        for i in range(len(close)):
            if close[i] > 0:
                result[i] = body[i] / close[i] <= 0.001

    return result


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
    """Dragonfly Doji (bullish doji with long lower shadow, no upper shadow)."""
    result = np.full(len(close), False, dtype=bool)

    is_doji = doji(open_, high, low, close, atr, max_body_atr)
    upper_shadow = high - np.maximum(open_, close)
    lower_shadow = np.minimum(open_, close) - low

    for i in range(len(close)):
        if not is_doji[i]:
            continue

        total_range = high[i] - low[i]
        if total_range == 0:
            continue

        has_long_lower = lower_shadow[i] > 0.5 * total_range
        has_minimal_upper = upper_shadow[i] <= max_upper_shadow_ratio * total_range

        result[i] = has_long_lower and has_minimal_upper

    return result


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
    """Gravestone Doji (bearish doji with long upper shadow, no lower shadow)."""
    result = np.full(len(close), False, dtype=bool)

    is_doji = doji(open_, high, low, close, atr, max_body_atr)
    upper_shadow = high - np.maximum(open_, close)
    lower_shadow = np.minimum(open_, close) - low

    for i in range(len(close)):
        if not is_doji[i]:
            continue

        total_range = high[i] - low[i]
        if total_range == 0:
            continue

        has_long_upper = upper_shadow[i] > 0.5 * total_range
        has_minimal_lower = lower_shadow[i] <= max_lower_shadow_ratio * total_range

        result[i] = has_long_upper and has_minimal_lower

    return result


@IndicatorRegistry.register("spinning_top")
def spinning_top(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    max_body_atr: float = 0.5,
) -> np.ndarray:
    """Spinning Top pattern (indecision with long shadows).

    Structure: Small body, long shadows on both sides.
    """
    result = np.full(len(close), False, dtype=bool)

    body = np.abs(close - open_)
    upper_shadow = high - np.maximum(open_, close)
    lower_shadow = np.minimum(open_, close) - low

    for i in range(len(close)):
        small_body = False
        if atr is not None and atr[i] > 0:
            small_body = body[i] < max_body_atr * atr[i]
        elif close[i] > 0:
            small_body = body[i] / close[i] < 0.01  # body < 1% of price

        long_shadows = upper_shadow[i] > body[i] and lower_shadow[i] > body[i]

        result[i] = small_body and long_shadows

    return result


@IndicatorRegistry.register("harami")
def harami(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    min_prev_body_atr: float = 2.0,
) -> np.ndarray:
    """Harami pattern (inside bar, indecision).

    Structure: Large candle followed by small candle completely inside previous range.
    """
    result = np.full(len(close), False, dtype=bool)

    for i in range(1, len(close)):
        prev_large = (high[i - 1] - low[i - 1]) > 0
        inside = high[i] < high[i - 1] and low[i] > low[i - 1]

        if atr is not None and atr[i - 1] > 0:
            prev_large = (high[i - 1] - low[i - 1]) >= min_prev_body_atr * atr[i - 1]

        result[i] = prev_large and inside

    return result
