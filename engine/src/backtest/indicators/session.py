"""Session-aware indicators: session_active, session_high, session_low."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest.indicators import IndicatorRegistry


def _parse_time(t: str) -> int:
    """Parse 'HH:MM' → minutes since midnight."""
    parts = t.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def _bar_minutes(ts: pd.Timestamp) -> int:
    return ts.hour * 60 + ts.minute


def _within_window(bar_min: int, from_min: int, to_min: int) -> bool:
    """True if bar_min is inside [from_min, to_min). Handles overnight windows."""
    if from_min < to_min:
        return from_min <= bar_min < to_min
    # Overnight session (e.g. 22:00 → 06:00)
    return bar_min >= from_min or bar_min < to_min


@IndicatorRegistry.register("session_active")
def session_active(
    close: np.ndarray,
    timestamps: np.ndarray,
    from_time: str = "08:00",
    to_time: str = "17:00",
) -> np.ndarray:
    """Binary indicator: 1.0 if bar timestamp is within the specified UTC window, else 0.0.

    Weekends (Saturday/Sunday) always return 0.0.

    Parameters
    ----------
    close:      Close price array (shape driver — values are not used).
    timestamps: numpy datetime64 array aligned with close.
    from_time:  Session start in 'HH:MM' UTC (inclusive).
    to_time:    Session end   in 'HH:MM' UTC (exclusive).
    """
    result = np.zeros(len(close), dtype=float)
    from_min = _parse_time(from_time)
    to_min = _parse_time(to_time)
    for i, raw_ts in enumerate(timestamps):
        ts = pd.Timestamp(raw_ts)
        if ts.weekday() >= 5:  # Sat=5, Sun=6
            continue
        if _within_window(_bar_minutes(ts), from_min, to_min):
            result[i] = 1.0
    return result


@IndicatorRegistry.register("session_high")
def session_high(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    timestamps: np.ndarray,
    from_time: str = "00:00",
    to_time: str = "07:00",
) -> np.ndarray:
    """Rolling session high.

    - Within the session window: running maximum of ``high`` since the session started today.
    - Outside the session window: carry-forward of the most recently completed session high.
    - Returns NaN until the first session bar is seen.

    Parameters
    ----------
    from_time:  Session start in 'HH:MM' UTC (inclusive).
    to_time:    Session end   in 'HH:MM' UTC (exclusive).
    """
    result = np.full(len(close), np.nan, dtype=float)
    from_min = _parse_time(from_time)
    to_min = _parse_time(to_time)

    running_high: float = np.nan
    last_carry: float = np.nan
    last_session_key: tuple[int, int] | None = None  # (date_ordinal, from_min)

    for i, raw_ts in enumerate(timestamps):
        ts = pd.Timestamp(raw_ts)
        bm = _bar_minutes(ts)
        date_key = ts.date().toordinal()

        if _within_window(bm, from_min, to_min):
            session_key = (date_key, from_min)
            if session_key != last_session_key:
                # New session started — reset accumulator
                running_high = float(high[i])
                last_session_key = session_key
            else:
                running_high = max(running_high, float(high[i]))
            last_carry = running_high
            result[i] = running_high
        else:
            # Outside session — carry forward last completed value
            if not np.isnan(last_carry):
                result[i] = last_carry

    return result


@IndicatorRegistry.register("range_fakeout_short")
def range_fakeout_short(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    timestamps: np.ndarray,
    from_time: str = "00:00",
    to_time: str = "07:00",
    lookback_bars: int = 5,
) -> np.ndarray:
    """Bearish fakeout signal: price briefly broke above session_high then closed back below.

    Returns 1.0 on bar ``i`` when ALL of:
    1. Current bar is OUTSIDE the defining session (execution window).
    2. Within the last ``lookback_bars`` bars, ``close`` went ABOVE ``session_high`` (breakout).
    3. Current ``close`` is NOW BELOW ``session_high`` (re-entry inside range).

    Parameters
    ----------
    from_time:      Session start 'HH:MM' UTC that defines the range.
    to_time:        Session end   'HH:MM' UTC.
    lookback_bars:  How many past bars to scan for the initial breakout.
    """
    sh = session_high(close, high, low, timestamps, from_time, to_time)
    result = np.zeros(len(close), dtype=float)
    from_min = _parse_time(from_time)
    to_min = _parse_time(to_time)

    for i in range(lookback_bars, len(close)):
        ts = pd.Timestamp(timestamps[i])
        if _within_window(_bar_minutes(ts), from_min, to_min):
            continue
        if np.isnan(sh[i]) or close[i] >= sh[i]:
            continue
        for j in range(i - lookback_bars, i):
            if not np.isnan(sh[j]) and close[j] > sh[j]:
                result[i] = 1.0
                break
    return result


@IndicatorRegistry.register("range_fakeout_long")
def range_fakeout_long(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    timestamps: np.ndarray,
    from_time: str = "00:00",
    to_time: str = "07:00",
    lookback_bars: int = 5,
) -> np.ndarray:
    """Bullish fakeout signal: price briefly broke below session_low then recovered above.

    Returns 1.0 on bar ``i`` when ALL of:
    1. Current bar is OUTSIDE the defining session (execution window).
    2. Within the last ``lookback_bars`` bars, ``close`` went BELOW ``session_low`` (breakdown).
    3. Current ``close`` is NOW ABOVE ``session_low`` (recovery inside range).

    Parameters
    ----------
    from_time:      Session start 'HH:MM' UTC that defines the range.
    to_time:        Session end   'HH:MM' UTC.
    lookback_bars:  How many past bars to scan for the initial breakdown.
    """
    sl = session_low(close, high, low, timestamps, from_time, to_time)
    result = np.zeros(len(close), dtype=float)
    from_min = _parse_time(from_time)
    to_min = _parse_time(to_time)

    for i in range(lookback_bars, len(close)):
        ts = pd.Timestamp(timestamps[i])
        if _within_window(_bar_minutes(ts), from_min, to_min):
            continue
        if np.isnan(sl[i]) or close[i] <= sl[i]:
            continue
        for j in range(i - lookback_bars, i):
            if not np.isnan(sl[j]) and close[j] < sl[j]:
                result[i] = 1.0
                break
    return result


@IndicatorRegistry.register("session_low")
def session_low(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    timestamps: np.ndarray,
    from_time: str = "00:00",
    to_time: str = "07:00",
) -> np.ndarray:
    """Rolling session low.

    Mirror of ``session_high``: tracks the running minimum of ``low`` within the session window
    and carries it forward outside the window.
    """
    result = np.full(len(close), np.nan, dtype=float)
    from_min = _parse_time(from_time)
    to_min = _parse_time(to_time)

    running_low: float = np.nan
    last_carry: float = np.nan
    last_session_key: tuple[int, int] | None = None

    for i, raw_ts in enumerate(timestamps):
        ts = pd.Timestamp(raw_ts)
        bm = _bar_minutes(ts)
        date_key = ts.date().toordinal()

        if _within_window(bm, from_min, to_min):
            session_key = (date_key, from_min)
            if session_key != last_session_key:
                running_low = float(low[i])
                last_session_key = session_key
            else:
                running_low = min(running_low, float(low[i]))
            last_carry = running_low
            result[i] = running_low
        else:
            if not np.isnan(last_carry):
                result[i] = last_carry

    return result
