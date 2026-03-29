"""Session-aware indicators: session_active, session_high, session_low, VWAP variants."""
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


def _resolve_price_source(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    price_source: str,
) -> np.ndarray:
    """Resolve the base price series used in VWAP calculations."""
    close_f = close.astype(float)
    high_f = high.astype(float)
    low_f = low.astype(float)

    if price_source == "hlc3":
        return (high_f + low_f + close_f) / 3.0
    if price_source == "close":
        return close_f
    raise ValueError(f"Unsupported price_source '{price_source}'. Use 'hlc3' or 'close'.")


def _bands_from_weighted_state(
    weight_sum: float,
    weighted_price_sum: float,
    weighted_price_sq_sum: float,
    num_std: float,
) -> tuple[float, float, float]:
    """Return (center, upper, lower) from cumulative weighted moments."""
    if weight_sum <= 0.0:
        return np.nan, np.nan, np.nan

    center = weighted_price_sum / weight_sum
    variance = max(weighted_price_sq_sum / weight_sum - center * center, 0.0)
    sigma = float(np.sqrt(variance))
    return center, center + num_std * sigma, center - num_std * sigma


def _compute_session_vwap_bands(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    timestamps: np.ndarray,
    from_time: str,
    to_time: str,
    price_source: str,
    num_std: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute session VWAP bands with daily reset and post-session carry."""
    result = np.full((3, len(close)), np.nan, dtype=float)
    price = _resolve_price_source(close, high, low, price_source)
    vol = volume.astype(float)
    from_min = _parse_time(from_time)
    to_min = _parse_time(to_time)

    day_key: int | None = None
    weight_sum = 0.0
    weighted_price_sum = 0.0
    weighted_price_sq_sum = 0.0
    last_center = np.nan
    last_upper = np.nan
    last_lower = np.nan

    for i, raw_ts in enumerate(timestamps):
        ts = pd.Timestamp(raw_ts)
        current_day = ts.date().toordinal()
        if current_day != day_key:
            day_key = current_day
            weight_sum = 0.0
            weighted_price_sum = 0.0
            weighted_price_sq_sum = 0.0
            last_center = np.nan
            last_upper = np.nan
            last_lower = np.nan

        if _within_window(_bar_minutes(ts), from_min, to_min):
            w = max(float(vol[i]), 0.0)
            if w > 0.0 and not np.isnan(price[i]):
                weighted_price = float(price[i]) * w
                weight_sum += w
                weighted_price_sum += weighted_price
                weighted_price_sq_sum += weighted_price * float(price[i])
                last_center, last_upper, last_lower = _bands_from_weighted_state(
                    weight_sum,
                    weighted_price_sum,
                    weighted_price_sq_sum,
                    num_std,
                )
            if weight_sum > 0.0:
                result[0, i] = last_center
                result[1, i] = last_upper
                result[2, i] = last_lower
        elif weight_sum > 0.0:
            result[0, i] = last_center
            result[1, i] = last_upper
            result[2, i] = last_lower

    return result[0], result[1], result[2]


def _compute_anchored_vwap_bands(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    timestamps: np.ndarray,
    anchor_mode: str,
    anchor_time: str,
    from_time: str,
    to_time: str,
    price_source: str,
    num_std: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Compute daily anchored VWAP bands from the chosen intraday anchor."""
    if anchor_mode not in {"start_hour", "session_open"}:
        raise ValueError(
            f"Unsupported anchor_mode '{anchor_mode}'. Use 'start_hour' or 'session_open'."
        )

    result = np.full((3, len(close)), np.nan, dtype=float)
    price = _resolve_price_source(close, high, low, price_source)
    vol = volume.astype(float)
    anchor_min = _parse_time(anchor_time)
    from_min = _parse_time(from_time)
    to_min = _parse_time(to_time)

    day_key: int | None = None
    anchor_started = False
    weight_sum = 0.0
    weighted_price_sum = 0.0
    weighted_price_sq_sum = 0.0

    for i, raw_ts in enumerate(timestamps):
        ts = pd.Timestamp(raw_ts)
        current_day = ts.date().toordinal()
        if current_day != day_key:
            day_key = current_day
            anchor_started = False
            weight_sum = 0.0
            weighted_price_sum = 0.0
            weighted_price_sq_sum = 0.0

        if not anchor_started:
            bar_min = _bar_minutes(ts)
            if anchor_mode == "start_hour":
                anchor_started = bar_min >= anchor_min
            else:
                anchor_started = _within_window(bar_min, from_min, to_min)

        if not anchor_started:
            continue

        w = max(float(vol[i]), 0.0)
        if w > 0.0 and not np.isnan(price[i]):
            weighted_price = float(price[i]) * w
            weight_sum += w
            weighted_price_sum += weighted_price
            weighted_price_sq_sum += weighted_price * float(price[i])

        if weight_sum > 0.0:
            result[0, i], result[1, i], result[2, i] = _bands_from_weighted_state(
                weight_sum,
                weighted_price_sum,
                weighted_price_sq_sum,
                num_std,
            )

    return result[0], result[1], result[2]


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


@IndicatorRegistry.register("session_return")
def session_return(
    open_: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    close: np.ndarray,
    timestamps: np.ndarray,
    from_time: str = "14:30",
    to_time: str = "21:00",
) -> np.ndarray:
    """Prior-session return: (session_close - session_open) / session_open.

    - During the session: running return from the session's first-bar open price.
    - After the session ends: carry-forward of the completed session return until
      the next session starts.
    - Before the first session has been seen: NaN.

    The value is a decimal fraction (e.g. 0.008 = +0.8%, -0.005 = -0.5%).
    Use it in entry rules to gate on prior-session direction and magnitude.

    Parameters
    ----------
    open_:      Bar open price array (first positional arg — matched by OHLC dispatch).
    high:       Bar high price array (not used; required by OHLC dispatch).
    low:        Bar low price array (not used; required by OHLC dispatch).
    close:      Bar close price array.
    timestamps: numpy datetime64[ns] array aligned with the price arrays.
    from_time:  Session start in 'HH:MM' UTC (inclusive). Default: '14:30' (US RTH open).
    to_time:    Session end   in 'HH:MM' UTC (exclusive). Default: '21:00' (US RTH close).
    """
    result = np.full(len(close), np.nan, dtype=float)
    from_min = _parse_time(from_time)
    to_min = _parse_time(to_time)

    session_open_price: float = np.nan
    last_carry: float = np.nan
    last_session_key: tuple[int, int] | None = None

    for i, raw_ts in enumerate(timestamps):
        ts = pd.Timestamp(raw_ts)
        bm = _bar_minutes(ts)
        date_key = ts.date().toordinal()

        if _within_window(bm, from_min, to_min):
            session_key = (date_key, from_min)
            if session_key != last_session_key:
                # New session — anchor return to the first bar's open price
                session_open_price = float(open_[i])
                last_session_key = session_key

            if not np.isnan(session_open_price) and session_open_price != 0.0:
                running_return = (float(close[i]) - session_open_price) / session_open_price
                last_carry = running_return
                result[i] = running_return
        else:
            # Outside session — carry forward the completed session return
            if not np.isnan(last_carry):
                result[i] = last_carry

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


@IndicatorRegistry.register("vwap")
def vwap(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    timestamps: np.ndarray,
    from_time: str = "00:00",
    to_time: str = "23:59",
    price_source: str = "hlc3",
    num_std: float = 1.0,
) -> np.ndarray:
    """Session VWAP with daily reset and post-session carry-forward."""
    center, _, _ = _compute_session_vwap_bands(
        close, high, low, volume, timestamps, from_time, to_time, price_source, num_std
    )
    return center


@IndicatorRegistry.register("vwap_upper")
def vwap_upper(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    timestamps: np.ndarray,
    from_time: str = "00:00",
    to_time: str = "23:59",
    price_source: str = "hlc3",
    num_std: float = 1.0,
) -> np.ndarray:
    """Upper session VWAP band using cumulative volume-weighted deviation."""
    _, upper, _ = _compute_session_vwap_bands(
        close, high, low, volume, timestamps, from_time, to_time, price_source, num_std
    )
    return upper


@IndicatorRegistry.register("vwap_lower")
def vwap_lower(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    timestamps: np.ndarray,
    from_time: str = "00:00",
    to_time: str = "23:59",
    price_source: str = "hlc3",
    num_std: float = 1.0,
) -> np.ndarray:
    """Lower session VWAP band using cumulative volume-weighted deviation."""
    _, _, lower = _compute_session_vwap_bands(
        close, high, low, volume, timestamps, from_time, to_time, price_source, num_std
    )
    return lower


@IndicatorRegistry.register("anchored_vwap")
def anchored_vwap(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    timestamps: np.ndarray,
    anchor_mode: str = "start_hour",
    anchor_time: str = "00:00",
    from_time: str = "00:00",
    to_time: str = "23:59",
    price_source: str = "hlc3",
    num_std: float = 1.0,
) -> np.ndarray:
    """Daily anchored VWAP from a time anchor or session-open anchor."""
    center, _, _ = _compute_anchored_vwap_bands(
        close,
        high,
        low,
        volume,
        timestamps,
        anchor_mode,
        anchor_time,
        from_time,
        to_time,
        price_source,
        num_std,
    )
    return center


@IndicatorRegistry.register("anchored_vwap_upper")
def anchored_vwap_upper(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    timestamps: np.ndarray,
    anchor_mode: str = "start_hour",
    anchor_time: str = "00:00",
    from_time: str = "00:00",
    to_time: str = "23:59",
    price_source: str = "hlc3",
    num_std: float = 1.0,
) -> np.ndarray:
    """Upper daily anchored VWAP band."""
    _, upper, _ = _compute_anchored_vwap_bands(
        close,
        high,
        low,
        volume,
        timestamps,
        anchor_mode,
        anchor_time,
        from_time,
        to_time,
        price_source,
        num_std,
    )
    return upper


@IndicatorRegistry.register("anchored_vwap_lower")
def anchored_vwap_lower(
    close: np.ndarray,
    high: np.ndarray,
    low: np.ndarray,
    volume: np.ndarray,
    timestamps: np.ndarray,
    anchor_mode: str = "start_hour",
    anchor_time: str = "00:00",
    from_time: str = "00:00",
    to_time: str = "23:59",
    price_source: str = "hlc3",
    num_std: float = 1.0,
) -> np.ndarray:
    """Lower daily anchored VWAP band."""
    _, _, lower = _compute_anchored_vwap_bands(
        close,
        high,
        low,
        volume,
        timestamps,
        anchor_mode,
        anchor_time,
        from_time,
        to_time,
        price_source,
        num_std,
    )
    return lower
