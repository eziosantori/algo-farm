"""Unit tests for session indicators and trading-hours logic."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.indicators import IndicatorRegistry
from src.backtest.indicators.session import session_active, session_high, session_low
from src.backtest.strategy import _is_within_trading_hours
from src.models import TradingHours


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ts_range(start: str, end: str, freq: str = "1h") -> np.ndarray:
    """Return a numpy datetime64 array from a pandas date_range."""
    return np.array(pd.date_range(start, end, freq=freq), dtype="datetime64[ns]")


def _ones(n: int) -> np.ndarray:
    return np.ones(n, dtype=float)


# ---------------------------------------------------------------------------
# session_active
# ---------------------------------------------------------------------------

class TestSessionActive:
    def test_all_within_session(self) -> None:
        # 8 bars from 08:00 to 15:00 on a Wednesday (2024-01-03)
        ts = _ts_range("2024-01-03 08:00", "2024-01-03 15:00", "1h")
        close = _ones(len(ts))
        result = session_active(close, ts, from_time="08:00", to_time="16:00")
        assert np.all(result == 1.0)

    def test_outside_session_is_zero(self) -> None:
        ts = _ts_range("2024-01-03 17:00", "2024-01-03 22:00", "1h")
        close = _ones(len(ts))
        result = session_active(close, ts, from_time="08:00", to_time="17:00")
        assert np.all(result == 0.0)

    def test_weekend_is_zero(self) -> None:
        # Saturday 2024-01-06 and Sunday 2024-01-07
        ts = _ts_range("2024-01-06 10:00", "2024-01-07 14:00", "2h")
        close = _ones(len(ts))
        result = session_active(close, ts, from_time="08:00", to_time="18:00")
        assert np.all(result == 0.0)

    def test_partial_session(self) -> None:
        # Mix: 06:00, 08:00, 10:00, 18:00 on Wed 2024-01-03
        ts = np.array(
            pd.DatetimeIndex(["2024-01-03 06:00", "2024-01-03 08:00",
                               "2024-01-03 10:00", "2024-01-03 18:00"]),
            dtype="datetime64[ns]",
        )
        close = _ones(4)
        result = session_active(close, ts, from_time="08:00", to_time="17:00")
        np.testing.assert_array_equal(result, [0.0, 1.0, 1.0, 0.0])

    def test_overnight_session(self) -> None:
        # 22:00 Mon → 02:00 Tue — overnight session 21:00–05:00
        ts = np.array(
            pd.DatetimeIndex([
                "2024-01-08 21:00",  # Mon 21:00 → within
                "2024-01-08 23:00",  # Mon 23:00 → within
                "2024-01-09 02:00",  # Tue 02:00 → within (< 05:00)
                "2024-01-09 06:00",  # Tue 06:00 → outside
            ]),
            dtype="datetime64[ns]",
        )
        close = _ones(4)
        result = session_active(close, ts, from_time="21:00", to_time="05:00")
        np.testing.assert_array_equal(result, [1.0, 1.0, 1.0, 0.0])

    def test_registered(self) -> None:
        fn = IndicatorRegistry.get("session_active")
        assert callable(fn)


# ---------------------------------------------------------------------------
# session_high
# ---------------------------------------------------------------------------

class TestSessionHigh:
    def _make_data(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Return (close, high, low, timestamps) for a simple 1-hour bar sequence.

        Bars:  00:00 01:00 02:00 03:00 04:00 05:00 06:00 07:00 08:00
        High:   1.0   2.0   3.0   2.5   1.5   1.0   1.0   1.5   2.0
        Session: [00:00, 05:00)
        """
        ts = _ts_range("2024-01-03 00:00", "2024-01-03 08:00", "1h")
        high = np.array([1.0, 2.0, 3.0, 2.5, 1.5, 1.0, 1.0, 1.5, 2.0])
        low  = np.ones(9) * 0.5
        close = high - 0.1
        return close, high, low, ts

    def test_running_max_within_session(self) -> None:
        close, high, low, ts = self._make_data()
        result = session_high(close, high, low, ts, from_time="00:00", to_time="05:00")
        # Indices 0-4 are within session (00:00–04:00 inclusive, 05:00 excluded)
        assert result[0] == pytest.approx(1.0)
        assert result[1] == pytest.approx(2.0)
        assert result[2] == pytest.approx(3.0)  # running max
        assert result[3] == pytest.approx(3.0)  # still 3.0
        assert result[4] == pytest.approx(3.0)

    def test_carry_forward_outside_session(self) -> None:
        close, high, low, ts = self._make_data()
        result = session_high(close, high, low, ts, from_time="00:00", to_time="05:00")
        # Bars 5–8 are outside session — should carry forward session max (3.0)
        for i in range(5, 9):
            assert result[i] == pytest.approx(3.0), f"bar {i} should carry 3.0"

    def test_nan_before_any_session(self) -> None:
        # Bars outside any session before the first session starts
        ts = _ts_range("2024-01-03 06:00", "2024-01-03 09:00", "1h")
        high = np.array([1.0, 1.5, 2.0, 1.8])
        low = np.ones(4) * 0.5
        close = high - 0.1
        result = session_high(close, high, low, ts, from_time="00:00", to_time="05:00")
        # All bars are after the session — but the session hasn't fired yet today
        # (no 00:00 bar) → NaN until a session bar has been seen
        assert np.all(np.isnan(result))

    def test_registered(self) -> None:
        fn = IndicatorRegistry.get("session_high")
        assert callable(fn)


# ---------------------------------------------------------------------------
# session_low
# ---------------------------------------------------------------------------

class TestSessionLow:
    def test_running_min_within_session(self) -> None:
        ts = _ts_range("2024-01-03 00:00", "2024-01-03 04:00", "1h")
        high = np.ones(5) * 2.0
        low = np.array([1.5, 1.0, 0.8, 0.9, 1.2])
        close = (high + low) / 2
        result = session_low(close, high, low, ts, from_time="00:00", to_time="05:00")
        assert result[0] == pytest.approx(1.5)
        assert result[1] == pytest.approx(1.0)
        assert result[2] == pytest.approx(0.8)  # running min
        assert result[3] == pytest.approx(0.8)
        assert result[4] == pytest.approx(0.8)

    def test_carry_forward_outside_session(self) -> None:
        ts = _ts_range("2024-01-03 00:00", "2024-01-03 07:00", "1h")
        high = np.ones(8) * 2.0
        low = np.array([1.5, 1.0, 0.8, 0.9, 1.2, 2.0, 1.8, 2.0])
        close = (high + low) / 2
        result = session_low(close, high, low, ts, from_time="00:00", to_time="05:00")
        # Bars 5-7 are outside session — carry forward min (0.8)
        assert result[5] == pytest.approx(0.8)
        assert result[6] == pytest.approx(0.8)
        assert result[7] == pytest.approx(0.8)

    def test_registered(self) -> None:
        fn = IndicatorRegistry.get("session_low")
        assert callable(fn)


# ---------------------------------------------------------------------------
# _is_within_trading_hours
# ---------------------------------------------------------------------------

class TestIsWithinTradingHours:
    def test_normal_session_inside(self) -> None:
        th = TradingHours(from_time="08:00", to_time="17:00")
        assert _is_within_trading_hours(pd.Timestamp("2024-01-03 10:00"), th)

    def test_normal_session_outside(self) -> None:
        th = TradingHours(from_time="08:00", to_time="17:00")
        assert not _is_within_trading_hours(pd.Timestamp("2024-01-03 18:00"), th)

    def test_boundary_from_is_inclusive(self) -> None:
        th = TradingHours(from_time="08:00", to_time="17:00")
        assert _is_within_trading_hours(pd.Timestamp("2024-01-03 08:00"), th)

    def test_boundary_to_is_exclusive(self) -> None:
        th = TradingHours(from_time="08:00", to_time="17:00")
        assert not _is_within_trading_hours(pd.Timestamp("2024-01-03 17:00"), th)

    def test_weekend_excluded_by_default(self) -> None:
        th = TradingHours(from_time="08:00", to_time="17:00")
        # Saturday
        assert not _is_within_trading_hours(pd.Timestamp("2024-01-06 10:00"), th)

    def test_custom_days_allows_weekend(self) -> None:
        th = TradingHours(from_time="08:00", to_time="17:00", days=[5, 6])  # Sat+Sun
        assert _is_within_trading_hours(pd.Timestamp("2024-01-06 10:00"), th)

    def test_overnight_session(self) -> None:
        th = TradingHours(from_time="22:00", to_time="05:00")
        assert _is_within_trading_hours(pd.Timestamp("2024-01-03 23:00"), th)
        assert _is_within_trading_hours(pd.Timestamp("2024-01-03 04:00"), th)
        assert not _is_within_trading_hours(pd.Timestamp("2024-01-03 06:00"), th)

    def test_day_filter_blocks_wrong_day(self) -> None:
        th = TradingHours(from_time="08:00", to_time="17:00", days=[0, 1])  # Mon+Tue only
        # Wednesday = weekday 2
        assert not _is_within_trading_hours(pd.Timestamp("2024-01-03 10:00"), th)

    def test_model_default_fields(self) -> None:
        th = TradingHours()
        assert th.from_time == "00:00"
        assert th.to_time == "23:59"
        assert th.days is None
        assert th.force_close is False
