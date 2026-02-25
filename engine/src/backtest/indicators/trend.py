"""Trend indicators: sma, ema, macd."""
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
