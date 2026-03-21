"""Unit tests for candlestick pattern recognition."""

from __future__ import annotations

import numpy as np
import pytest

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


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture()
def bullish_candle() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Simple bullish candle: O=1.0, H=1.1, L=0.9, C=1.05."""
    return (
        np.array([1.0]),
        np.array([1.1]),
        np.array([0.9]),
        np.array([1.05]),
    )


@pytest.fixture()
def bearish_candle() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Simple bearish candle: O=1.0, H=1.1, L=0.9, C=0.95."""
    return (
        np.array([1.0]),
        np.array([1.1]),
        np.array([0.9]),
        np.array([0.95]),
    )


# ============================================================================
# REVERSAL PATTERNS - BEARISH
# ============================================================================


def test_shooting_star_detects_valid_pattern() -> None:
    """Shooting star: small body at bottom, long upper shadow."""
    # O=1.00, H=1.20, L=0.998, C=1.01 → upper_shadow=0.19, body=0.01, lower=0.002
    # lower/body = 0.2 ✓
    open_ = np.array([1.00])
    high = np.array([1.20])
    low = np.array([0.998])
    close = np.array([1.01])

    result = shooting_star(open_, high, low, close, min_upper_shadow_ratio=2.0)
    assert result[0] == True


def test_shooting_star_rejects_no_upper_shadow() -> None:
    """No upper shadow → not a shooting star."""
    open_ = np.array([1.00])
    high = np.array([1.05])
    low = np.array([0.95])
    close = np.array([1.05])  # close == high

    result = shooting_star(open_, high, low, close)
    assert result[0] == False


def test_bearish_engulfing_detects_valid_pattern() -> None:
    """Bearish engulfing: prev bullish → curr bearish engulfs."""
    # Candle 1: O=1.00, C=1.05 (bullish)
    # Candle 2: O=1.08, C=0.98 (bearish, engulfs 1)
    open_ = np.array([1.00, 1.08])
    high = np.array([1.06, 1.10])
    low = np.array([0.99, 0.97])
    close = np.array([1.05, 0.98])

    result = bearish_engulfing(open_, high, low, close)
    assert result[0] == False  # no previous candle
    assert result[1] == True


def test_bearish_engulfing_rejects_both_bullish() -> None:
    """Both candles bullish → no engulfing."""
    open_ = np.array([1.00, 1.02])
    high = np.array([1.05, 1.08])
    low = np.array([0.99, 1.01])
    close = np.array([1.04, 1.07])

    result = bearish_engulfing(open_, high, low, close)
    assert result[1] == False


def test_evening_star_detects_valid_pattern() -> None:
    """Evening star: large bullish → small indecision → large bearish."""
    # C1: O=1.00, C=1.10 (bullish, large)
    # C2: O=1.11, C=1.12 (small body)
    # C3: O=1.09, C=0.98 (bearish, penetrates below 1.05 midpoint)
    open_ = np.array([1.00, 1.11, 1.09])
    high = np.array([1.11, 1.13, 1.10])
    low = np.array([0.99, 1.10, 0.97])
    close = np.array([1.10, 1.12, 0.98])

    result = evening_star(open_, high, low, close)
    assert result[2] == True


def test_evening_star_rejects_no_penetration() -> None:
    """Third candle doesn't penetrate below midpoint → not evening star."""
    open_ = np.array([1.00, 1.11, 1.09])
    high = np.array([1.11, 1.13, 1.10])
    low = np.array([0.99, 1.10, 1.06])
    close = np.array([1.10, 1.12, 1.07])  # closes above midpoint 1.05

    result = evening_star(open_, high, low, close)
    assert result[2] == False


def test_dark_cloud_cover_detects_valid_pattern() -> None:
    """Dark cloud: bullish → bearish gaps up, closes below midpoint."""
    # C1: O=1.00, H=1.10, C=1.09 (bullish)
    # C2: O=1.12 (gap up), C=1.03 (below midpoint 1.045)
    open_ = np.array([1.00, 1.12])
    high = np.array([1.10, 1.13])
    low = np.array([0.99, 1.02])
    close = np.array([1.09, 1.03])

    result = dark_cloud_cover(open_, high, low, close)
    assert result[1] == True


def test_dark_cloud_cover_rejects_no_gap() -> None:
    """No gap up → not dark cloud."""
    open_ = np.array([1.00, 1.05])  # no gap
    high = np.array([1.10, 1.08])
    low = np.array([0.99, 1.02])
    close = np.array([1.09, 1.03])

    result = dark_cloud_cover(open_, high, low, close)
    assert result[1] == False


# ============================================================================
# REVERSAL PATTERNS - BULLISH
# ============================================================================


def test_hammer_detects_valid_pattern() -> None:
    """Hammer: small body at top, long lower shadow."""
    # O=1.00, H=1.005, L=0.90, C=0.99 → lower_shadow=0.09, body=0.01, upper=0.005
    # upper/body = 0.5 (fails if max_upper_shadow_ratio=0.3)
    # Better: O=1.00, H=1.002, L=0.90, C=0.99 → upper=0.002, upper/body=0.2 ✓
    open_ = np.array([1.00])
    high = np.array([1.002])
    low = np.array([0.90])
    close = np.array([0.99])

    result = hammer(open_, high, low, close, min_lower_shadow_ratio=2.0)
    assert result[0] == True


def test_hammer_rejects_no_lower_shadow() -> None:
    """No lower shadow → not a hammer."""
    open_ = np.array([1.00])
    high = np.array([1.05])
    low = np.array([0.95])
    close = np.array([0.95])  # close == low

    result = hammer(open_, high, low, close)
    assert result[0] == False


def test_bullish_engulfing_detects_valid_pattern() -> None:
    """Bullish engulfing: prev bearish → curr bullish engulfs."""
    # C1: O=1.00, C=0.95 (bearish)
    # C2: O=0.93, C=1.02 (bullish, engulfs 1)
    open_ = np.array([1.00, 0.93])
    high = np.array([1.01, 1.03])
    low = np.array([0.94, 0.92])
    close = np.array([0.95, 1.02])

    result = bullish_engulfing(open_, high, low, close)
    assert result[1] == True


def test_morning_star_detects_valid_pattern() -> None:
    """Morning star: large bearish → small → large bullish."""
    # C1: O=1.00, C=0.90 (bearish, large)
    # C2: O=0.89, C=0.88 (small body)
    # C3: O=0.91, C=1.02 (bullish, penetrates above 0.95 midpoint)
    open_ = np.array([1.00, 0.89, 0.91])
    high = np.array([1.01, 0.90, 1.03])
    low = np.array([0.89, 0.87, 0.90])
    close = np.array([0.90, 0.88, 1.02])

    result = morning_star(open_, high, low, close)
    assert result[2] == True


def test_piercing_pattern_detects_valid_pattern() -> None:
    """Piercing: bearish → bullish gaps down, closes above midpoint."""
    # C1: O=1.00, L=0.90, C=0.91 (bearish)
    # C2: O=0.88 (gap down), C=0.97 (above midpoint 0.955)
    open_ = np.array([1.00, 0.88])
    high = np.array([1.01, 0.98])
    low = np.array([0.90, 0.87])
    close = np.array([0.91, 0.97])

    result = piercing_pattern(open_, high, low, close)
    assert result[1] == True


# ============================================================================
# CONTINUATION PATTERNS
# ============================================================================


def test_bullish_marubozu_detects_valid_pattern() -> None:
    """Bullish marubozu: long bullish candle, no shadows."""
    # O=1.00, H=1.10, L=1.00, C=1.10 → body=0.10, range=0.10 → 100% body
    open_ = np.array([1.00])
    high = np.array([1.10])
    low = np.array([1.00])
    close = np.array([1.10])

    result = bullish_marubozu(open_, high, low, close, min_body_pct=0.95)
    assert result[0] == True


def test_bullish_marubozu_rejects_small_body() -> None:
    """Small body → not marubozu."""
    open_ = np.array([1.00])
    high = np.array([1.10])
    low = np.array([0.95])
    close = np.array([1.01])  # body = 0.01, range = 0.15 → 6.7%

    result = bullish_marubozu(open_, high, low, close, min_body_pct=0.95)
    assert result[0] == False


def test_bearish_marubozu_detects_valid_pattern() -> None:
    """Bearish marubozu: long bearish candle, no shadows."""
    open_ = np.array([1.10])
    high = np.array([1.10])
    low = np.array([1.00])
    close = np.array([1.00])

    result = bearish_marubozu(open_, high, low, close, min_body_pct=0.95)
    assert result[0] == True


def test_three_white_soldiers_detects_valid_pattern() -> None:
    """Three white soldiers: 3 consecutive bullish candles."""
    # All bullish, each opens within prev body, closes near high
    open_ = np.array([1.00, 1.02, 1.04])
    high = np.array([1.05, 1.07, 1.09])
    low = np.array([0.99, 1.01, 1.03])
    close = np.array([1.04, 1.06, 1.08])

    result = three_white_soldiers(open_, high, low, close)
    assert result[2] == True


def test_three_white_soldiers_rejects_one_bearish() -> None:
    """One bearish candle → not three white soldiers."""
    open_ = np.array([1.00, 1.02, 1.06])
    high = np.array([1.05, 1.07, 1.08])
    low = np.array([0.99, 1.01, 1.03])
    close = np.array([1.04, 1.06, 1.04])  # third is bearish

    result = three_white_soldiers(open_, high, low, close)
    assert result[2] == False


def test_three_black_crows_detects_valid_pattern() -> None:
    """Three black crows: 3 consecutive bearish candles."""
    open_ = np.array([1.10, 1.08, 1.06])
    high = np.array([1.11, 1.09, 1.07])
    low = np.array([1.05, 1.03, 1.01])
    close = np.array([1.06, 1.04, 1.02])

    result = three_black_crows(open_, high, low, close)
    assert result[2] == True


# ============================================================================
# INDECISION PATTERNS
# ============================================================================


def test_doji_detects_valid_pattern_with_atr() -> None:
    """Doji: open ≈ close (small body)."""
    # O=1.00, C=1.001 → body=0.001, ATR=0.02 → body < 10% ATR
    open_ = np.array([1.00])
    high = np.array([1.05])
    low = np.array([0.95])
    close = np.array([1.001])
    atr = np.array([0.02])

    result = doji(open_, high, low, close, atr, max_body_atr=0.1)
    assert result[0] == True


def test_doji_rejects_large_body() -> None:
    """Large body → not a doji."""
    open_ = np.array([1.00])
    high = np.array([1.10])
    low = np.array([0.95])
    close = np.array([1.05])
    atr = np.array([0.05])

    result = doji(open_, high, low, close, atr, max_body_atr=0.1)
    assert result[0] == False


def test_dragonfly_doji_detects_valid_pattern() -> None:
    """Dragonfly doji: doji with long lower shadow, no upper shadow."""
    # O≈C=1.00, H=1.01, L=0.90 → long lower, minimal upper
    open_ = np.array([1.00])
    high = np.array([1.01])
    low = np.array([0.90])
    close = np.array([1.001])
    atr = np.array([0.05])

    result = dragonfly_doji(open_, high, low, close, atr)
    assert result[0] == True


def test_gravestone_doji_detects_valid_pattern() -> None:
    """Gravestone doji: doji with long upper shadow, no lower shadow."""
    # O≈C=1.00, H=1.10, L=0.99 → long upper, minimal lower
    open_ = np.array([1.00])
    high = np.array([1.10])
    low = np.array([0.99])
    close = np.array([1.001])
    atr = np.array([0.05])

    result = gravestone_doji(open_, high, low, close, atr)
    assert result[0] == True


def test_spinning_top_detects_valid_pattern() -> None:
    """Spinning top: small body, long shadows both sides."""
    # O=1.00, C=1.01 (small body), H=1.10, L=0.90 (long shadows)
    open_ = np.array([1.00])
    high = np.array([1.10])
    low = np.array([0.90])
    close = np.array([1.01])
    atr = np.array([0.05])

    result = spinning_top(open_, high, low, close, atr, max_body_atr=0.5)
    assert result[0] == True


def test_spinning_top_rejects_large_body() -> None:
    """Large body → not a spinning top."""
    open_ = np.array([1.00])
    high = np.array([1.10])
    low = np.array([0.90])
    close = np.array([1.08])
    atr = np.array([0.05])

    result = spinning_top(open_, high, low, close, atr, max_body_atr=0.5)
    assert result[0] == False


def test_harami_detects_valid_pattern() -> None:
    """Harami: large candle → small inside candle."""
    # C1: O=1.00, H=1.20, L=0.90, C=1.10 (large)
    # C2: O=1.05, H=1.08, L=1.02, C=1.06 (inside)
    open_ = np.array([1.00, 1.05])
    high = np.array([1.20, 1.08])
    low = np.array([0.90, 1.02])
    close = np.array([1.10, 1.06])
    atr = np.array([0.10, 0.10])

    result = harami(open_, high, low, close, atr, min_prev_body_atr=2.0)
    assert result[1] == True


def test_harami_rejects_not_inside() -> None:
    """Second candle not inside → not harami."""
    open_ = np.array([1.00, 1.05])
    high = np.array([1.20, 1.25])  # breaks above prev high
    low = np.array([0.90, 1.02])
    close = np.array([1.10, 1.06])

    result = harami(open_, high, low, close)
    assert result[1] == False


# ============================================================================
# REGISTRY TESTS
# ============================================================================


def test_all_patterns_registered() -> None:
    """Verify all patterns are registered in IndicatorRegistry."""
    patterns = [
        "hammer",
        "shooting_star",
        "bullish_engulfing",
        "bearish_engulfing",
        "morning_star",
        "evening_star",
        "piercing_pattern",
        "dark_cloud_cover",
        "bullish_marubozu",
        "bearish_marubozu",
        "three_white_soldiers",
        "three_black_crows",
        "doji",
        "dragonfly_doji",
        "gravestone_doji",
        "spinning_top",
        "harami",
    ]

    for pattern in patterns:
        fn = IndicatorRegistry.get(pattern)
        assert callable(fn), f"Pattern '{pattern}' not registered"


def test_pattern_returns_boolean_array() -> None:
    """All patterns should return boolean arrays."""
    open_ = np.array([1.00, 1.02, 1.04])
    high = np.array([1.05, 1.07, 1.09])
    low = np.array([0.99, 1.01, 1.03])
    close = np.array([1.04, 1.06, 1.08])

    result = hammer(open_, high, low, close)
    assert result.dtype == bool
    assert len(result) == len(close)


def test_pattern_handles_empty_input() -> None:
    """Patterns should handle empty arrays gracefully."""
    empty = np.array([])

    result = hammer(empty, empty, empty, empty)
    assert len(result) == 0


def test_pattern_handles_single_candle() -> None:
    """Patterns should work with single candle (when applicable)."""
    open_ = np.array([1.00])
    high = np.array([1.02])
    low = np.array([0.90])
    close = np.array([0.99])

    result = hammer(open_, high, low, close)
    assert len(result) == 1
    assert isinstance(result[0], (bool, np.bool_))


# ============================================================================
# EDGE CASES
# ============================================================================


def test_patterns_handle_zero_range_candle() -> None:
    """Patterns should handle candles with zero range (H=L)."""
    open_ = np.array([1.00])
    high = np.array([1.00])
    low = np.array([1.00])
    close = np.array([1.00])

    # Should not crash, just return False
    result = hammer(open_, high, low, close)
    assert result[0] == False


def test_patterns_handle_nan_values() -> None:
    """Patterns should handle NaN values gracefully."""
    open_ = np.array([1.00, np.nan])
    high = np.array([1.05, np.nan])
    low = np.array([0.95, np.nan])
    close = np.array([1.02, np.nan])

    result = hammer(open_, high, low, close)
    # First candle valid, second should be False (NaN handling)
    assert len(result) == 2


def test_atr_optional_parameter() -> None:
    """Patterns with ATR parameter should work with and without it."""
    open_ = np.array([1.00])
    high = np.array([1.02])
    low = np.array([0.98])
    close = np.array([1.001])

    # Without ATR
    result_no_atr = doji(open_, high, low, close)
    assert len(result_no_atr) == 1

    # With ATR
    atr = np.array([0.05])
    result_with_atr = doji(open_, high, low, close, atr)
    assert len(result_with_atr) == 1
