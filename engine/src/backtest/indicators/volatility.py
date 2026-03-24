"""Volatility indicators: atr, atr_robust, atr_gaussian, bollinger_bands, adx."""
from __future__ import annotations

import numpy as np

from src.backtest.indicators import IndicatorRegistry


@IndicatorRegistry.register("atr")
def atr(
    close: np.ndarray,
    high: np.ndarray | None = None,
    low: np.ndarray | None = None,
    period: int = 14,
) -> np.ndarray:
    """Average True Range."""
    if high is None:
        high = close
    if low is None:
        low = close
    result = np.full_like(close, np.nan, dtype=float)
    n = len(close)
    if n < 2:
        return result
    tr = _compute_true_range(close, high, low)
    if period > n:
        return result
    result[period - 1] = np.mean(tr[:period])
    for i in range(period, n):
        result[i] = (result[i - 1] * (period - 1) + tr[i]) / period
    return result


def _compute_true_range(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
) -> np.ndarray:
    """Compute raw True Range array (same logic as atr)."""
    n = len(close)
    tr = np.zeros(n, dtype=float)
    tr[0] = float(high[0]) - float(low[0])
    for i in range(1, n):
        tr[i] = max(
            float(high[i]) - float(low[i]),
            abs(float(high[i]) - float(close[i - 1])),
            abs(float(low[i]) - float(close[i - 1])),
        )
    return tr


@IndicatorRegistry.register("atr_robust")
def atr_robust(
    close: np.ndarray,
    high: np.ndarray | None = None,
    low: np.ndarray | None = None,
    period: int = 14,
    n_sigma: float = 2.0,
) -> np.ndarray:
    """Robust ATR: excludes True Range outliers beyond n_sigma std before averaging.

    For each rolling window of ``period`` bars, TR values further than
    ``n_sigma`` standard deviations from the window mean are dropped before
    computing the average.  This reduces the influence of volatility spikes
    caused by news events or data gaps.
    """
    if high is None:
        high = close
    if low is None:
        low = close
    n = len(close)
    result = np.full(n, np.nan, dtype=float)
    if n < period:
        return result
    tr = _compute_true_range(close, high, low)
    for i in range(period - 1, n):
        window = tr[i - period + 1 : i + 1]
        mean_w = float(np.mean(window))
        std_w = float(np.std(window, ddof=1)) if period > 1 else 0.0
        if std_w > 0.0:
            mask = np.abs(window - mean_w) <= n_sigma * std_w
            filtered = window[mask]
            result[i] = float(np.mean(filtered)) if len(filtered) > 0 else mean_w
        else:
            result[i] = mean_w
    return result


@IndicatorRegistry.register("atr_gaussian")
def atr_gaussian(
    close: np.ndarray,
    high: np.ndarray | None = None,
    low: np.ndarray | None = None,
    period: int = 14,
    n_sigma: float = 2.0,
    sigma_factor: float = 0.4,
) -> np.ndarray:
    """Gaussian-weighted ATR with outlier exclusion.

    Combines two effects:
    1. Outlier exclusion — TR values beyond ``n_sigma`` std from the window mean
       are dropped (same as ``atr_robust``).
    2. Gaussian kernel — remaining TR values are averaged with bell-curve weights
       centred on the most recent bar, so recent volatility carries more weight
       than older bars.

    The bell width is ``sigma = period * sigma_factor`` (default 0.4 → for
    period=14 σ≈5.6).  Higher ``sigma_factor`` → flatter bell → closer to
    equal weighting; lower → sharper peak on recent bars.
    """
    if high is None:
        high = close
    if low is None:
        low = close
    n = len(close)
    result = np.full(n, np.nan, dtype=float)
    if n < period:
        return result
    tr = _compute_true_range(close, high, low)
    sigma = period * sigma_factor
    # indices 0 = oldest bar, period-1 = most recent bar
    indices = np.arange(period, dtype=float)
    weights = np.exp(-0.5 * ((indices - (period - 1)) / sigma) ** 2)
    for i in range(period - 1, n):
        window = tr[i - period + 1 : i + 1]
        mean_w = float(np.mean(window))
        std_w = float(np.std(window, ddof=1)) if period > 1 else 0.0
        if std_w > 0.0:
            mask = np.abs(window - mean_w) <= n_sigma * std_w
            w_filtered = weights[mask]
            tr_filtered = window[mask]
        else:
            w_filtered = weights
            tr_filtered = window
        total_w = float(np.sum(w_filtered))
        if len(tr_filtered) > 0 and total_w > 0.0:
            result[i] = float(np.sum(tr_filtered * w_filtered) / total_w)
        else:
            result[i] = mean_w
    return result


def _bollinger_components(
    close: np.ndarray,
    period: int = 20,
    num_std: float = 2.0,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Shared Bollinger computation. Returns (upper, basis, lower)."""
    upper = np.full_like(close, np.nan, dtype=float)
    basis = np.full_like(close, np.nan, dtype=float)
    lower = np.full_like(close, np.nan, dtype=float)
    for i in range(period - 1, len(close)):
        window = close[i - period + 1 : i + 1].astype(float)
        mid = float(np.mean(window))
        std = float(np.std(window, ddof=1))
        basis[i] = mid
        upper[i] = mid + num_std * std
        lower[i] = mid - num_std * std
    return upper, basis, lower


@IndicatorRegistry.register("bollinger_bands")
def bollinger_bands(
    close: np.ndarray,
    period: int = 20,
    num_std: float = 2.0,
) -> np.ndarray:
    """Bollinger Band width (upper - lower). Kept for backward compatibility."""
    upper, _, lower = _bollinger_components(close, period, num_std)
    result = np.full_like(close, np.nan, dtype=float)
    valid = ~np.isnan(upper)
    result[valid] = upper[valid] - lower[valid]
    return result


@IndicatorRegistry.register("bollinger_upper")
def bollinger_upper(
    close: np.ndarray,
    period: int = 20,
    num_std: float = 2.0,
) -> np.ndarray:
    """Bollinger upper band: basis + num_std × std."""
    upper, _, _ = _bollinger_components(close, period, num_std)
    return upper


@IndicatorRegistry.register("bollinger_lower")
def bollinger_lower(
    close: np.ndarray,
    period: int = 20,
    num_std: float = 2.0,
) -> np.ndarray:
    """Bollinger lower band: basis - num_std × std."""
    _, _, lower = _bollinger_components(close, period, num_std)
    return lower


@IndicatorRegistry.register("bollinger_basis")
def bollinger_basis(
    close: np.ndarray,
    period: int = 20,
) -> np.ndarray:
    """Bollinger basis (SMA of close over period)."""
    _, basis, _ = _bollinger_components(close, period)
    return basis


@IndicatorRegistry.register("adx")
def adx(
    close: np.ndarray,
    high: np.ndarray | None = None,
    low: np.ndarray | None = None,
    period: int = 14,
) -> np.ndarray:
    """Average Directional Index."""
    if high is None:
        high = close
    if low is None:
        low = close
    n = len(close)
    result = np.full(n, np.nan, dtype=float)
    if n < period * 2:
        return result

    plus_dm = np.zeros(n, dtype=float)
    minus_dm = np.zeros(n, dtype=float)
    tr_arr = np.zeros(n, dtype=float)

    for i in range(1, n):
        up_move = float(high[i]) - float(high[i - 1])
        down_move = float(low[i - 1]) - float(low[i])
        plus_dm[i] = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm[i] = down_move if (down_move > up_move and down_move > 0) else 0.0
        tr_arr[i] = max(
            float(high[i]) - float(low[i]),
            abs(float(high[i]) - float(close[i - 1])),
            abs(float(low[i]) - float(close[i - 1])),
        )

    # Smooth with Wilder's method
    smooth_tr = np.zeros(n, dtype=float)
    smooth_plus = np.zeros(n, dtype=float)
    smooth_minus = np.zeros(n, dtype=float)
    smooth_tr[period] = np.sum(tr_arr[1 : period + 1])
    smooth_plus[period] = np.sum(plus_dm[1 : period + 1])
    smooth_minus[period] = np.sum(minus_dm[1 : period + 1])

    for i in range(period + 1, n):
        smooth_tr[i] = smooth_tr[i - 1] - smooth_tr[i - 1] / period + tr_arr[i]
        smooth_plus[i] = smooth_plus[i - 1] - smooth_plus[i - 1] / period + plus_dm[i]
        smooth_minus[i] = smooth_minus[i - 1] - smooth_minus[i - 1] / period + minus_dm[i]

    dx = np.zeros(n, dtype=float)
    for i in range(period, n):
        if smooth_tr[i] > 0:
            pdi = smooth_plus[i] / smooth_tr[i] * 100.0
            mdi = smooth_minus[i] / smooth_tr[i] * 100.0
            denom = pdi + mdi
            dx[i] = abs(pdi - mdi) / denom * 100.0 if denom > 0 else 0.0

    # ADX = smoothed DX
    adx_start = period * 2 - 1
    if adx_start < n:
        result[adx_start] = np.mean(dx[period:adx_start + 1])
        for i in range(adx_start + 1, n):
            result[i] = (result[i - 1] * (period - 1) + dx[i]) / period

    return result
