"""Unit tests for candlestick pattern recognition (Phase D — float scores)."""

from __future__ import annotations

import numpy as np
import pytest

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
# Helpers
# ============================================================================


def _assert_float_range(arr: np.ndarray) -> None:
    """All finite values must be in [0, 1]."""
    finite = arr[np.isfinite(arr)]
    assert np.all(finite >= 0.0), f"Values below 0: {finite[finite < 0]}"
    assert np.all(finite <= 1.0), f"Values above 1: {finite[finite > 1]}"


# ============================================================================
# Return-type contracts (all 17 patterns)
# ============================================================================


def test_all_patterns_return_float_array() -> None:
    """Every pattern function must return a float array in [0, 1]."""
    rng = np.random.default_rng(42)
    n = 50
    base = 1.0 + np.cumsum(rng.normal(0, 0.001, n))
    o = base + rng.uniform(-0.002, 0.002, n)
    h = np.maximum(o, base) + rng.uniform(0, 0.003, n)
    l = np.minimum(o, base) - rng.uniform(0, 0.003, n)
    c = base
    atr = np.full(n, 0.005)

    fns = [
        lambda: shooting_star(o, h, l, c),
        lambda: bearish_engulfing(o, h, l, c),
        lambda: evening_star(o, h, l, c, atr),
        lambda: dark_cloud_cover(o, h, l, c),
        lambda: hammer(o, h, l, c),
        lambda: bullish_engulfing(o, h, l, c),
        lambda: morning_star(o, h, l, c, atr),
        lambda: piercing_pattern(o, h, l, c),
        lambda: bullish_marubozu(o, h, l, c, atr),
        lambda: bearish_marubozu(o, h, l, c, atr),
        lambda: three_white_soldiers(o, h, l, c),
        lambda: three_black_crows(o, h, l, c),
        lambda: doji(o, h, l, c, atr),
        lambda: dragonfly_doji(o, h, l, c, atr),
        lambda: gravestone_doji(o, h, l, c, atr),
        lambda: spinning_top(o, h, l, c, atr),
        lambda: harami(o, h, l, c, atr),
    ]

    for fn in fns:
        result = fn()
        assert result.dtype == float, f"Expected float dtype, got {result.dtype}"
        _assert_float_range(result)


# ============================================================================
# Score sanity: perfect pattern → score > 0.8
# ============================================================================


def test_hammer_perfect_scores_high() -> None:
    """A textbook hammer (lower shadow 8× body) should score > 0.8."""
    body = 0.001
    open_ = np.array([1.005])
    close = np.array([1.005 + body])  # bullish body at top
    high = np.array([close[0] + 0.0001])
    low = np.array([open_[0] - body * 8])  # 8× lower shadow

    result = hammer(open_, high, low, close)
    assert result[0] > 0.8, f"Expected score > 0.8, got {result[0]}"


def test_shooting_star_perfect_scores_high() -> None:
    """A textbook shooting star (upper shadow 8× body) should score > 0.8."""
    body = 0.001
    close = np.array([1.002])
    open_ = np.array([close[0] + body])  # bearish small body
    low = np.array([close[0] - 0.0001])
    high = np.array([open_[0] + body * 8])

    result = shooting_star(open_, high, low, close)
    assert result[0] > 0.8, f"Expected score > 0.8, got {result[0]}"


def test_bullish_engulfing_strong_scores_high() -> None:
    """Current body 3× previous body should score > 0.8."""
    # prev: bearish, body = 0.005
    # curr: bullish, body = 0.015 (3×)
    open_ = np.array([1.010, 1.000])
    close = np.array([1.005, 1.015])
    high = np.array([1.012, 1.016])
    low = np.array([1.004, 0.999])

    result = bullish_engulfing(open_, high, low, close)
    assert result[1] > 0.8, f"Expected score > 0.8, got {result[1]}"


def test_bearish_engulfing_strong_scores_high() -> None:
    """Current bearish body 3× previous bullish body should score > 0.8."""
    open_ = np.array([1.000, 1.015])
    close = np.array([1.010, 0.995])
    high = np.array([1.012, 1.017])
    low = np.array([0.999, 0.994])

    result = bearish_engulfing(open_, high, low, close)
    assert result[1] > 0.8, f"Expected score > 0.8, got {result[1]}"


def test_doji_perfect_scores_high() -> None:
    """A near-perfect doji (body ≈ 0) with ATR should score close to 1.0."""
    n = 5
    open_ = np.full(n, 1.0)
    close = np.full(n, 1.0 + 1e-7)  # negligible body
    high = np.full(n, 1.005)
    low = np.full(n, 0.995)
    atr = np.full(n, 0.005)

    result = doji(open_, high, low, close, atr, max_body_atr=0.1)
    assert result[-1] > 0.95, f"Expected score > 0.95, got {result[-1]}"


# ============================================================================
# Score sanity: barely-qualifying pattern → score < 0.35
# ============================================================================


def test_hammer_barely_qualifies_scores_low() -> None:
    """A hammer with exactly 2× lower shadow (minimum) should score < 0.35."""
    body = 0.002
    open_ = np.array([1.005])
    close = np.array([1.005 + body])
    high = np.array([close[0] + 0.0001])
    low = np.array([open_[0] - body * 2.0])  # exactly minimum

    result = hammer(open_, high, low, close)
    assert 0 < result[0] < 0.35, f"Expected score in (0, 0.35), got {result[0]}"


def test_shooting_star_barely_qualifies_scores_low() -> None:
    """A shooting star with exactly 2× upper shadow should score < 0.35."""
    body = 0.002
    close = np.array([1.002])
    open_ = np.array([close[0] + body])
    low = np.array([close[0] - 0.0001])
    high = np.array([open_[0] + body * 2.0])  # exactly minimum

    result = shooting_star(open_, high, low, close)
    assert 0 < result[0] < 0.35, f"Expected score in (0, 0.35), got {result[0]}"


# ============================================================================
# Non-qualifying conditions → score == 0.0
# ============================================================================


def test_hammer_no_lower_shadow_returns_zero() -> None:
    open_ = np.array([1.0])
    close = np.array([1.01])
    high = np.array([1.01])
    low = np.array([1.0])  # no lower shadow

    result = hammer(open_, high, low, close)
    assert result[0] == 0.0


def test_shooting_star_no_upper_shadow_returns_zero() -> None:
    open_ = np.array([1.01])
    close = np.array([1.0])
    high = np.array([1.01])
    low = np.array([0.99])

    result = shooting_star(open_, high, low, close)
    assert result[0] == 0.0


def test_bullish_engulfing_both_bullish_returns_zero() -> None:
    open_ = np.array([1.0, 1.005])
    close = np.array([1.01, 1.02])
    high = np.array([1.012, 1.022])
    low = np.array([0.999, 1.004])

    result = bullish_engulfing(open_, high, low, close)
    assert result[1] == 0.0


def test_bearish_engulfing_both_bearish_returns_zero() -> None:
    open_ = np.array([1.01, 1.005])
    close = np.array([1.00, 0.99])
    high = np.array([1.012, 1.006])
    low = np.array([0.998, 0.989])

    result = bearish_engulfing(open_, high, low, close)
    assert result[1] == 0.0


def test_doji_large_body_returns_zero() -> None:
    open_ = np.array([1.0])
    close = np.array([1.01])  # 1% body — too large
    high = np.array([1.011])
    low = np.array([0.999])
    atr = np.array([0.005])

    result = doji(open_, high, low, close, atr, max_body_atr=0.1)
    assert result[0] == 0.0


# ============================================================================
# Output length matches input
# ============================================================================


def test_output_length_equals_input_length() -> None:
    n = 20
    rng = np.random.default_rng(7)
    base = 1.0 + np.cumsum(rng.normal(0, 0.001, n))
    o = base + rng.uniform(-0.002, 0.002, n)
    h = np.maximum(o, base) + rng.uniform(0, 0.003, n)
    l = np.minimum(o, base) - rng.uniform(0, 0.003, n)
    c = base

    for fn in [hammer, shooting_star, bullish_engulfing, bearish_engulfing,
               morning_star, evening_star, doji, spinning_top, harami,
               bullish_marubozu, bearish_marubozu, three_white_soldiers,
               three_black_crows, piercing_pattern, dark_cloud_cover,
               dragonfly_doji, gravestone_doji]:
        result = fn(o, h, l, c)
        assert len(result) == n, f"{fn.__name__}: expected len {n}, got {len(result)}"


# ============================================================================
# IndicatorRegistry integration
# ============================================================================


def test_patterns_registered_in_registry() -> None:
    from src.backtest.indicators import IndicatorRegistry

    expected = [
        "hammer", "shooting_star", "bullish_engulfing", "bearish_engulfing",
        "morning_star", "evening_star", "piercing_pattern", "dark_cloud_cover",
        "bullish_marubozu", "bearish_marubozu", "three_white_soldiers", "three_black_crows",
        "doji", "dragonfly_doji", "gravestone_doji", "spinning_top", "harami",
    ]
    registered = IndicatorRegistry.list_all()
    for name in expected:
        assert name in registered, f"Pattern '{name}' not registered"


def test_no_float_suffix_variants_in_registry() -> None:
    from src.backtest.indicators import IndicatorRegistry

    registered = IndicatorRegistry.list_all()
    float_variants = [n for n in registered if n.endswith("_float")]
    assert float_variants == [], f"_float variants should not exist: {float_variants}"
