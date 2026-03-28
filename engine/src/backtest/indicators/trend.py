"""Trend indicators: sma, ema, macd, supertrend, htf_ema, htf_sma, htf_pattern."""
from __future__ import annotations

import numpy as np
import pandas as pd

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


# ---------------------------------------------------------------------------
# Higher-Timeframe (HTF) indicators
# ---------------------------------------------------------------------------

_TF_MINUTES: dict[str, int] = {
    "M1": 1, "M5": 5, "M10": 10, "M15": 15, "M30": 30,
    "H1": 60, "H4": 240, "D1": 1440, "W1": 10080,
}


def _detect_base_tf(timestamps: np.ndarray) -> str:
    """Infer the base timeframe from bar spacing.

    Uses the 10th percentile of non-weekend gaps so that session-based assets
    (stocks with 1–2 bars/day) are detected correctly even when overnight gaps
    would skew a simple median toward a higher timeframe.
    """
    ts = pd.to_datetime(timestamps)
    diffs = ts[1:] - ts[:-1]
    # Filter out weekend/holiday gaps (> 2 days)
    mask = diffs < pd.Timedelta(days=2)
    if mask.any():
        minutes_arr = diffs[mask].total_seconds().values / 60.0
        # p10 captures the typical intrabar spacing even for 1-bar/day session data
        ref_minutes = int(np.percentile(minutes_arr, 10))
    else:
        ref_minutes = int(diffs.median().total_seconds() // 60)
    # Find closest matching timeframe
    best_tf = "H1"
    best_diff = abs(60 - ref_minutes)
    for tf, minutes in _TF_MINUTES.items():
        diff = abs(minutes - ref_minutes)
        if diff < best_diff:
            best_diff = diff
            best_tf = tf
    return best_tf


def _resample_and_compute(
    close: np.ndarray,
    timestamps: np.ndarray,
    timeframe: str,
    compute_fn: str,
    period: int,
    base_timeframe: str | None = None,
) -> np.ndarray:
    """Resample *close* to a higher timeframe, compute an indicator, and forward-fill back.

    Parameters
    ----------
    close:          Close prices at the base timeframe.
    timestamps:     Datetime64 array aligned with close.
    timeframe:      Target higher timeframe (e.g. "H4", "D1").
    compute_fn:     "ema" or "sma".
    period:         Indicator period applied on the resampled bars.
    base_timeframe: Optional explicit base timeframe (e.g. "H4"). When provided,
                    skips auto-detection — use this for session-based assets (stocks)
                    where sparse bars can confuse the heuristic.

    Returns
    -------
    np.ndarray of same length as *close*, with the HTF indicator value
    forward-filled onto each base-timeframe bar.
    """
    if timeframe not in _TF_MINUTES:
        raise ValueError(f"Unknown timeframe '{timeframe}'. Supported: {list(_TF_MINUTES.keys())}")

    if base_timeframe is not None:
        if base_timeframe not in _TF_MINUTES:
            raise ValueError(
                f"Unknown base_timeframe '{base_timeframe}'. Supported: {list(_TF_MINUTES.keys())}"
            )
        base_tf = base_timeframe
        base_min = _TF_MINUTES[base_tf]
    else:
        base_tf = _detect_base_tf(timestamps)
        base_min = _TF_MINUTES[base_tf]

    target_min = _TF_MINUTES[timeframe]

    if target_min <= base_min:
        raise ValueError(
            f"HTF timeframe '{timeframe}' ({target_min}m) must be larger "
            f"than base timeframe '{base_tf}' ({base_min}m)"
        )

    # Build a pandas Series indexed by timestamp, resample to target TF close
    ts_index = pd.DatetimeIndex(timestamps)
    ser = pd.Series(close.astype(float), index=ts_index)

    # Map timeframe to pandas resample rule
    resample_rule = f"{target_min}min" if target_min < 1440 else f"{target_min // 1440}D"
    if timeframe == "W1":
        resample_rule = "W-FRI"

    htf_close = ser.resample(resample_rule).last().dropna()

    if len(htf_close) < period:
        return np.full(len(close), np.nan, dtype=float)

    # Compute indicator on HTF bars
    htf_values = htf_close.values
    if compute_fn == "ema":
        htf_indicator = ema(htf_values, period)
    else:
        htf_indicator = sma(htf_values, period)

    # Build a Series of HTF indicator values, then reindex to base timestamps with ffill
    htf_series = pd.Series(htf_indicator, index=htf_close.index)
    result_series = htf_series.reindex(ts_index, method="ffill")

    return result_series.to_numpy(dtype=float)


@IndicatorRegistry.register("htf_ema")
def htf_ema(
    close: np.ndarray,
    timestamps: np.ndarray,
    period: int = 50,
    timeframe: str = "H4",
    base_timeframe: str | None = None,
) -> np.ndarray:
    """EMA computed on a higher timeframe and forward-filled to the base timeframe.

    Parameters
    ----------
    close:          Close price array at the base timeframe.
    timestamps:     Datetime64 array aligned with close.
    period:         EMA period applied on the resampled HTF bars.
    timeframe:      Target higher timeframe (e.g. "H4", "D1").
    base_timeframe: Optional explicit base timeframe override (e.g. "H4").
                    Useful for session-based assets (stocks) with sparse bars.
    """
    return _resample_and_compute(close, timestamps, timeframe, "ema", period, base_timeframe)


@IndicatorRegistry.register("htf_sma")
def htf_sma(
    close: np.ndarray,
    timestamps: np.ndarray,
    period: int = 50,
    timeframe: str = "H4",
    base_timeframe: str | None = None,
) -> np.ndarray:
    """SMA computed on a higher timeframe and forward-filled to the base timeframe.

    Parameters
    ----------
    close:          Close price array at the base timeframe.
    timestamps:     Datetime64 array aligned with close.
    period:         SMA period applied on the resampled HTF bars.
    timeframe:      Target higher timeframe (e.g. "H4", "D1").
    base_timeframe: Optional explicit base timeframe override (e.g. "H4").
                    Useful for session-based assets (stocks) with sparse bars.
    """
    return _resample_and_compute(close, timestamps, timeframe, "sma", period, base_timeframe)


@IndicatorRegistry.register("htf_pattern")
def htf_pattern(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    timestamps: np.ndarray,
    base_pattern: str = "hammer",
    timeframe: str = "D1",
) -> np.ndarray:
    """Evaluate a candlestick pattern on a higher timeframe and forward-fill to base TF.

    The pattern score (float [0, 1]) is computed on the resampled HTF OHLC bars,
    then forward-filled onto every base-timeframe bar until the next HTF bar closes.

    Parameters
    ----------
    open_:        Open price array at the base timeframe.
    high:         High price array at the base timeframe.
    low:          Low price array at the base timeframe.
    close:        Close price array at the base timeframe.
    timestamps:   Datetime64 array aligned with OHLC.
    base_pattern: Name of a registered candlestick pattern (e.g. "hammer").
    timeframe:    Target higher timeframe (e.g. "D1", "H4").
    """
    from src.backtest.indicators import IndicatorRegistry as _Reg

    if timeframe not in _TF_MINUTES:
        raise ValueError(f"Unknown timeframe '{timeframe}'. Supported: {list(_TF_MINUTES.keys())}")

    base_tf = _detect_base_tf(timestamps)
    base_min = _TF_MINUTES[base_tf]
    target_min = _TF_MINUTES[timeframe]

    if target_min <= base_min:
        raise ValueError(
            f"HTF timeframe '{timeframe}' ({target_min}m) must be larger "
            f"than base timeframe '{base_tf}' ({base_min}m)"
        )

    ts_index = pd.DatetimeIndex(timestamps)
    resample_rule = f"{target_min}min" if target_min < 1440 else f"{target_min // 1440}D"
    if timeframe == "W1":
        resample_rule = "W-FRI"

    df = pd.DataFrame(
        {"open": open_.astype(float), "high": high.astype(float), "low": low.astype(float), "close": close.astype(float)},
        index=ts_index,
    )

    htf_df = df.resample(resample_rule).agg({"open": "first", "high": "max", "low": "min", "close": "last"}).dropna()

    if len(htf_df) < 1:
        return np.full(len(close), np.nan, dtype=float)

    pattern_fn = _Reg.get(base_pattern)
    htf_scores = pattern_fn(
        htf_df["open"].values,
        htf_df["high"].values,
        htf_df["low"].values,
        htf_df["close"].values,
    )

    htf_series = pd.Series(htf_scores, index=htf_df.index)
    result_series = htf_series.reindex(ts_index, method="ffill")
    return result_series.to_numpy(dtype=float)
