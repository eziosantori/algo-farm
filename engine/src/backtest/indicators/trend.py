"""Trend indicators: sma, ema, macd, supertrend."""
from __future__ import annotations

import numpy as np

from src.backtest.indicators import IndicatorRegistry


@IndicatorRegistry.register("sma")
def sma(close: np.ndarray, period: int = 20) -> np.ndarray:
    """Simple Moving Average."""
    result = np.full_like(close, np.nan, dtype=float)
    for i in range(period - 1, len(close)):
        result[i] = np.mean(close[i - period + 1 : i + 1])
    return result


@IndicatorRegistry.register("ema")
def ema(close: np.ndarray, period: int = 20) -> np.ndarray:
    """Exponential Moving Average."""
    result = np.full_like(close, np.nan, dtype=float)
    k = 2.0 / (period + 1)
    # Find first valid index
    start = period - 1
    if start >= len(close):
        return result
    result[start] = np.mean(close[:period])
    for i in range(start + 1, len(close)):
        result[i] = close[i] * k + result[i - 1] * (1 - k)
    return result


@IndicatorRegistry.register("macd")
def macd(
    close: np.ndarray,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> np.ndarray:
    """MACD line (fast EMA - slow EMA). Returns MACD line only."""
    fast = ema(close, fast_period)
    slow = ema(close, slow_period)
    return fast - slow


def _compute_supertrend(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    period: int,
    multiplier: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Core SuperTrend algorithm. Returns (st_line, direction) arrays.

    direction: +1.0 = uptrend, -1.0 = downtrend, NaN = warmup.
    """
    from src.backtest.indicators.volatility import atr as _atr  # lazy to avoid circular import

    close = np.asarray(close, dtype=float)
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    n = len(close)

    st_line = np.full(n, np.nan, dtype=float)
    direction = np.full(n, np.nan, dtype=float)

    start = period - 1
    if start >= n:
        return st_line, direction

    atr_vals = _atr(close, high, low, period)
    hl2 = (high + low) / 2.0
    basic_upper = hl2 + multiplier * atr_vals
    basic_lower = hl2 - multiplier * atr_vals

    final_upper = np.full(n, np.nan, dtype=float)
    final_lower = np.full(n, np.nan, dtype=float)

    # Initialise at first valid ATR bar
    final_upper[start] = basic_upper[start]
    final_lower[start] = basic_lower[start]
    direction[start] = -1.0
    st_line[start] = final_upper[start]

    for i in range(start + 1, n):
        # Update final bands
        if basic_upper[i] < final_upper[i - 1] or close[i - 1] > final_upper[i - 1]:
            final_upper[i] = basic_upper[i]
        else:
            final_upper[i] = final_upper[i - 1]

        if basic_lower[i] > final_lower[i - 1] or close[i - 1] < final_lower[i - 1]:
            final_lower[i] = basic_lower[i]
        else:
            final_lower[i] = final_lower[i - 1]

        # Determine direction and SuperTrend line
        prev_dir = direction[i - 1]
        if prev_dir == -1.0:
            if close[i] > final_upper[i]:
                direction[i] = 1.0
                st_line[i] = final_lower[i]
            else:
                direction[i] = -1.0
                st_line[i] = final_upper[i]
        else:
            if close[i] < final_lower[i]:
                direction[i] = -1.0
                st_line[i] = final_upper[i]
            else:
                direction[i] = 1.0
                st_line[i] = final_lower[i]

    return st_line, direction


@IndicatorRegistry.register("supertrend")
def supertrend(
    close: np.ndarray,
    high: np.ndarray | None = None,
    low: np.ndarray | None = None,
    period: int = 10,
    multiplier: float = 3.0,
) -> np.ndarray:
    """SuperTrend line value. Gracefully falls back to close when high/low are absent."""
    if high is None:
        high = close
    if low is None:
        low = close
    st_line, _ = _compute_supertrend(close, high, low, period, multiplier)
    return st_line


@IndicatorRegistry.register("supertrend_direction")
def supertrend_direction(
    close: np.ndarray,
    high: np.ndarray | None = None,
    low: np.ndarray | None = None,
    period: int = 10,
    multiplier: float = 3.0,
) -> np.ndarray:
    """SuperTrend direction: +1.0 uptrend, -1.0 downtrend. Use in entry/exit rules."""
    if high is None:
        high = close
    if low is None:
        low = close
    _, direction = _compute_supertrend(close, high, low, period, multiplier)
    return direction
