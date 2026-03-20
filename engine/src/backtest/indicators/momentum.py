"""Momentum indicators: rsi, stoch, cci, williamsr, obv."""
from __future__ import annotations

import numpy as np

from src.backtest.indicators import IndicatorRegistry


@IndicatorRegistry.register("rsi")
def rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Relative Strength Index."""
    result = np.full_like(close, np.nan, dtype=float)
    if len(close) < period + 1:
        return result
    deltas = np.diff(close.astype(float))
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)

    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    for i in range(period, len(close)):
        idx = i - 1  # index in deltas
        avg_gain = (avg_gain * (period - 1) + gains[idx]) / period
        avg_loss = (avg_loss * (period - 1) + losses[idx]) / period
        if avg_loss == 0:
            result[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - 100.0 / (1.0 + rs)
    return result


@IndicatorRegistry.register("stoch")
def stoch(
    close: np.ndarray,
    high: np.ndarray | None = None,
    low: np.ndarray | None = None,
    k_period: int = 14,
    d_period: int = 3,
) -> np.ndarray:
    """Stochastic %K. Returns %K line."""
    if high is None:
        high = close
    if low is None:
        low = close
    result = np.full_like(close, np.nan, dtype=float)
    for i in range(k_period - 1, len(close)):
        h = np.max(high[i - k_period + 1 : i + 1])
        lo = np.min(low[i - k_period + 1 : i + 1])
        if h != lo:
            result[i] = (close[i] - lo) / (h - lo) * 100.0
        else:
            result[i] = 50.0
    return result


@IndicatorRegistry.register("cci")
def cci(
    close: np.ndarray,
    high: np.ndarray | None = None,
    low: np.ndarray | None = None,
    period: int = 20,
) -> np.ndarray:
    """Commodity Channel Index."""
    if high is None:
        high = close
    if low is None:
        low = close
    result = np.full_like(close, np.nan, dtype=float)
    for i in range(period - 1, len(close)):
        tp = (high[i - period + 1 : i + 1] + low[i - period + 1 : i + 1] + close[i - period + 1 : i + 1]) / 3.0
        mean_tp = np.mean(tp)
        mad = np.mean(np.abs(tp - mean_tp))
        if mad > 0:
            result[i] = (tp[-1] - mean_tp) / (0.015 * mad)
        else:
            result[i] = 0.0
    return result


@IndicatorRegistry.register("williamsr")
def williamsr(
    close: np.ndarray,
    high: np.ndarray | None = None,
    low: np.ndarray | None = None,
    period: int = 14,
) -> np.ndarray:
    """Williams %R."""
    if high is None:
        high = close
    if low is None:
        low = close
    result = np.full_like(close, np.nan, dtype=float)
    for i in range(period - 1, len(close)):
        h = np.max(high[i - period + 1 : i + 1])
        lo = np.min(low[i - period + 1 : i + 1])
        if h != lo:
            result[i] = (h - close[i]) / (h - lo) * -100.0
        else:
            result[i] = -50.0
    return result


@IndicatorRegistry.register("roc")
def roc(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Rate of Change (%). Returns (close[i] - close[i-period]) / close[i-period] * 100."""
    result = np.full_like(close, np.nan, dtype=float)
    for i in range(period, len(close)):
        prev = float(close[i - period])
        if prev != 0:
            result[i] = (float(close[i]) - prev) / prev * 100.0
        else:
            result[i] = 0.0
    return result


@IndicatorRegistry.register("volume_sma")
def volume_sma(close: np.ndarray, volume: np.ndarray | None = None, period: int = 20) -> np.ndarray:
    """Simple Moving Average of volume over *period* bars.

    Parameters
    ----------
    close:   Close price array (shape driver — values are not used).
    volume:  Volume array aligned with close. Falls back to ones if absent.
    period:  Lookback window for the average.
    """
    if volume is None:
        volume = np.ones_like(close)
    result = np.full(len(volume), np.nan, dtype=float)
    for i in range(period - 1, len(volume)):
        result[i] = np.mean(volume[i - period + 1 : i + 1])
    return result


@IndicatorRegistry.register("obv")
def obv(close: np.ndarray, volume: np.ndarray | None = None) -> np.ndarray:
    """On Balance Volume. If volume not provided, uses ones."""
    if volume is None:
        volume = np.ones_like(close)
    result = np.zeros_like(close, dtype=float)
    result[0] = float(volume[0])
    for i in range(1, len(close)):
        if close[i] > close[i - 1]:
            result[i] = result[i - 1] + volume[i]
        elif close[i] < close[i - 1]:
            result[i] = result[i - 1] - volume[i]
        else:
            result[i] = result[i - 1]
    return result
