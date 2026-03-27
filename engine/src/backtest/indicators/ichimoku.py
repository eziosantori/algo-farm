"""Ichimoku Cloud indicators: tenkan, kijun, senkou_a, senkou_b, chikou."""
from __future__ import annotations

import numpy as np

from src.backtest.indicators import IndicatorRegistry


def _donchian_mid(high: np.ndarray, low: np.ndarray, period: int) -> np.ndarray:
    """(Highest high + Lowest low) / 2 over a rolling window."""
    n = len(high)
    result = np.full(n, np.nan, dtype=float)
    for i in range(period - 1, n):
        hh = np.max(high[i - period + 1 : i + 1])
        ll = np.min(low[i - period + 1 : i + 1])
        result[i] = (float(hh) + float(ll)) / 2.0
    return result


def _compute_ichimoku(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
    displacement: int = 26,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Core Ichimoku computation. Returns (tenkan, kijun, senkou_a, senkou_b, chikou).

    Senkou A/B are computed at the current bar (NOT shifted forward) to avoid
    future data leakage in backtesting. Chikou is close shifted backward by
    ``displacement`` bars.
    """
    close = np.asarray(close, dtype=float)
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)

    tenkan = _donchian_mid(high, low, tenkan_period)
    kijun = _donchian_mid(high, low, kijun_period)

    # Senkou Span A = (tenkan + kijun) / 2 at the current bar
    senkou_a = np.full_like(close, np.nan, dtype=float)
    valid = ~np.isnan(tenkan) & ~np.isnan(kijun)
    senkou_a[valid] = (tenkan[valid] + kijun[valid]) / 2.0

    # Senkou Span B = donchian mid over senkou_b_period at the current bar
    senkou_b = _donchian_mid(high, low, senkou_b_period)

    # Chikou Span = close shifted backward by displacement bars
    n = len(close)
    chikou = np.full(n, np.nan, dtype=float)
    if displacement < n:
        chikou[:n - displacement] = close[displacement:]

    return tenkan, kijun, senkou_a, senkou_b, chikou


@IndicatorRegistry.register("ichimoku_tenkan")
def ichimoku_tenkan(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
    displacement: int = 26,
) -> np.ndarray:
    """Ichimoku Tenkan-sen (Conversion Line)."""
    tenkan, _, _, _, _ = _compute_ichimoku(
        close, high, low, tenkan_period, kijun_period, senkou_b_period, displacement,
    )
    return tenkan


@IndicatorRegistry.register("ichimoku_kijun")
def ichimoku_kijun(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
    displacement: int = 26,
) -> np.ndarray:
    """Ichimoku Kijun-sen (Base Line)."""
    _, kijun, _, _, _ = _compute_ichimoku(
        close, high, low, tenkan_period, kijun_period, senkou_b_period, displacement,
    )
    return kijun


@IndicatorRegistry.register("ichimoku_senkou_a")
def ichimoku_senkou_a(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
    displacement: int = 26,
) -> np.ndarray:
    """Ichimoku Senkou Span A (Leading Span A). Not displaced forward."""
    _, _, senkou_a, _, _ = _compute_ichimoku(
        close, high, low, tenkan_period, kijun_period, senkou_b_period, displacement,
    )
    return senkou_a


@IndicatorRegistry.register("ichimoku_senkou_b")
def ichimoku_senkou_b(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
    displacement: int = 26,
) -> np.ndarray:
    """Ichimoku Senkou Span B (Leading Span B). Not displaced forward."""
    _, _, _, senkou_b, _ = _compute_ichimoku(
        close, high, low, tenkan_period, kijun_period, senkou_b_period, displacement,
    )
    return senkou_b


@IndicatorRegistry.register("ichimoku_chikou")
def ichimoku_chikou(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    tenkan_period: int = 9,
    kijun_period: int = 26,
    senkou_b_period: int = 52,
    displacement: int = 26,
) -> np.ndarray:
    """Ichimoku Chikou Span (Lagging Span). Close shifted backward by displacement bars."""
    _, _, _, _, chikou = _compute_ichimoku(
        close, high, low, tenkan_period, kijun_period, senkou_b_period, displacement,
    )
    return chikou
