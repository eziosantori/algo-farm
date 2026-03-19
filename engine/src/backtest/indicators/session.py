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
