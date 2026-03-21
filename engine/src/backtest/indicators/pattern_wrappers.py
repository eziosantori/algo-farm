"""Float wrappers for candlestick pattern indicators.

Pattern indicators return boolean arrays, but backtesting.Strategy expects float.
These wrappers convert bool → float (True=1.0, False=0.0) for compatibility.
"""

from __future__ import annotations

import numpy as np

from src.backtest.indicators import IndicatorRegistry
from src.backtest.indicators.patterns import (
    bearish_engulfing,
    bearish_marubozu,
    bullish_engulfing,
    bullish_marubozu,
    dark_cloud_cover,
    doji,
    dragonfly_doji,
    evening_star,
    gravestone_doji,
    hammer,
    harami,
    morning_star,
    piercing_pattern,
    shooting_star,
    spinning_top,
    three_black_crows,
    three_white_soldiers,
)


def _bool_to_float(arr: np.ndarray) -> np.ndarray:
    """Convert boolean array to float (True=1.0, False=0.0)."""
    return arr.astype(float)


# --- Reversal patterns (bullish) ---


@IndicatorRegistry.register("hammer_float")
def hammer_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    min_lower_shadow_ratio: float = 2.0,
    max_upper_shadow_ratio: float = 0.3,
) -> np.ndarray:
    """Hammer pattern (returns 1.0 where detected, 0.0 otherwise)."""
    return _bool_to_float(hammer(open_, high, low, close, min_lower_shadow_ratio, max_upper_shadow_ratio))


@IndicatorRegistry.register("bullish_engulfing_float")
def bullish_engulfing_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Bullish Engulfing (float)."""
    return _bool_to_float(bullish_engulfing(open_, high, low, close))


@IndicatorRegistry.register("morning_star_float")
def morning_star_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    min_first_body_atr: float = 2.0,
    max_middle_body_atr: float = 0.5,
) -> np.ndarray:
    """Morning Star (float)."""
    return _bool_to_float(morning_star(open_, high, low, close, atr, min_first_body_atr, max_middle_body_atr))


@IndicatorRegistry.register("piercing_pattern_float")
def piercing_pattern_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Piercing Pattern (float)."""
    return _bool_to_float(piercing_pattern(open_, high, low, close))


# --- Reversal patterns (bearish) ---


@IndicatorRegistry.register("shooting_star_float")
def shooting_star_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    min_upper_shadow_ratio: float = 2.0,
    max_lower_shadow_ratio: float = 0.3,
) -> np.ndarray:
    """Shooting Star (float)."""
    return _bool_to_float(shooting_star(open_, high, low, close, min_upper_shadow_ratio, max_lower_shadow_ratio))


@IndicatorRegistry.register("bearish_engulfing_float")
def bearish_engulfing_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Bearish Engulfing (float)."""
    return _bool_to_float(bearish_engulfing(open_, high, low, close))


@IndicatorRegistry.register("evening_star_float")
def evening_star_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    min_first_body_atr: float = 2.0,
    max_middle_body_atr: float = 0.5,
) -> np.ndarray:
    """Evening Star (float)."""
    return _bool_to_float(evening_star(open_, high, low, close, atr, min_first_body_atr, max_middle_body_atr))


@IndicatorRegistry.register("dark_cloud_cover_float")
def dark_cloud_cover_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Dark Cloud Cover (float)."""
    return _bool_to_float(dark_cloud_cover(open_, high, low, close))


# --- Continuation patterns ---


@IndicatorRegistry.register("bullish_marubozu_float")
def bullish_marubozu_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    min_body_pct: float = 0.95,
    min_body_atr: float = 1.5,
) -> np.ndarray:
    """Bullish Marubozu (float)."""
    return _bool_to_float(bullish_marubozu(open_, high, low, close, atr, min_body_pct, min_body_atr))


@IndicatorRegistry.register("bearish_marubozu_float")
def bearish_marubozu_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    min_body_pct: float = 0.95,
    min_body_atr: float = 1.5,
) -> np.ndarray:
    """Bearish Marubozu (float)."""
    return _bool_to_float(bearish_marubozu(open_, high, low, close, atr, min_body_pct, min_body_atr))


@IndicatorRegistry.register("three_white_soldiers_float")
def three_white_soldiers_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Three White Soldiers (float)."""
    return _bool_to_float(three_white_soldiers(open_, high, low, close))


@IndicatorRegistry.register("three_black_crows_float")
def three_black_crows_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
) -> np.ndarray:
    """Three Black Crows (float)."""
    return _bool_to_float(three_black_crows(open_, high, low, close))


# --- Indecision patterns ---


@IndicatorRegistry.register("doji_float")
def doji_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    max_body_atr: float = 0.1,
) -> np.ndarray:
    """Doji (float)."""
    return _bool_to_float(doji(open_, high, low, close, atr, max_body_atr))


@IndicatorRegistry.register("dragonfly_doji_float")
def dragonfly_doji_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    max_body_atr: float = 0.1,
    max_upper_shadow_ratio: float = 0.1,
) -> np.ndarray:
    """Dragonfly Doji (float)."""
    return _bool_to_float(dragonfly_doji(open_, high, low, close, atr, max_body_atr, max_upper_shadow_ratio))


@IndicatorRegistry.register("gravestone_doji_float")
def gravestone_doji_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    max_body_atr: float = 0.1,
    max_lower_shadow_ratio: float = 0.1,
) -> np.ndarray:
    """Gravestone Doji (float)."""
    return _bool_to_float(gravestone_doji(open_, high, low, close, atr, max_body_atr, max_lower_shadow_ratio))


@IndicatorRegistry.register("spinning_top_float")
def spinning_top_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    max_body_atr: float = 0.5,
) -> np.ndarray:
    """Spinning Top (float)."""
    return _bool_to_float(spinning_top(open_, high, low, close, atr, max_body_atr))


@IndicatorRegistry.register("harami_float")
def harami_float(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    atr: np.ndarray | None = None,
    min_prev_body_atr: float = 2.0,
) -> np.ndarray:
    """Harami (float)."""
    return _bool_to_float(harami(open_, high, low, close, atr, min_prev_body_atr))
