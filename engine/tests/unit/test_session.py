"""Unit tests for session indicators and trading-hours logic."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.backtest.indicators import IndicatorRegistry
from src.backtest.indicators.session import (
    anchored_vwap,
    anchored_vwap_lower,
    anchored_vwap_upper,
    range_fakeout_long,
    range_fakeout_short,
    session_active,
    session_high,
    session_low,
    session_return,
    vwap,
    vwap_lower,
    vwap_upper,
)
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
# session_return
# ---------------------------------------------------------------------------

class TestSessionReturn:
    """Tests for session_return indicator (prior-session return carry-forward)."""

    def _make_data(
        self,
        session_opens: list[float],
        session_closes: list[float],
        post_closes: list[float],
        session_start: str = "14:00",
        session_end: str = "20:00",
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Build OHLC + timestamps for a session followed by post-session bars.

        Session bars run from session_start for len(session_opens) hours.
        Post-session bars run immediately after for len(post_closes) hours.
        """
        session_ts = list(
            pd.date_range("2024-01-03 " + session_start, periods=len(session_opens), freq="1h")
        )
        post_ts = list(
            pd.date_range(
                pd.Timestamp("2024-01-03 " + session_start)
                + pd.Timedelta(hours=len(session_opens)),
                periods=len(post_closes),
                freq="1h",
            )
        )
        ts = np.array(session_ts + post_ts, dtype="datetime64[ns]")
        open_ = np.array(session_opens + [post_closes[0]] * len(post_closes), dtype=float)
        close = np.array(session_closes + post_closes, dtype=float)
        high = close + 0.5
        low = close - 0.5
        return open_, high, low, close, ts

    def test_running_return_within_session(self) -> None:
        # Session open = 100.0, closes = 101.0, 102.0, 103.0
        # Expected returns: +1%, +2%, +3%
        open_, high, low, close, ts = self._make_data(
            session_opens=[100.0, 101.0, 102.0],
            session_closes=[101.0, 102.0, 103.0],
            post_closes=[99.0],
        )
        result = session_return(open_, high, low, close, ts, from_time="14:00", to_time="17:00")
        assert result[0] == pytest.approx(0.01)   # (101-100)/100
        assert result[1] == pytest.approx(0.02)   # (102-100)/100
        assert result[2] == pytest.approx(0.03)   # (103-100)/100

    def test_carry_forward_completed_return(self) -> None:
        # Session closes at +2% → all post-session bars carry +2%
        open_, high, low, close, ts = self._make_data(
            session_opens=[100.0, 101.0],
            session_closes=[101.0, 102.0],
            post_closes=[99.0, 98.0, 97.0],
        )
        result = session_return(open_, high, low, close, ts, from_time="14:00", to_time="16:00")
        # Post-session bars (indices 2, 3, 4) carry the final session return (+2%)
        assert result[2] == pytest.approx(0.02)
        assert result[3] == pytest.approx(0.02)
        assert result[4] == pytest.approx(0.02)

    def test_nan_before_first_session(self) -> None:
        # Bars that start outside the session before any session has fired → NaN
        ts = np.array(
            pd.DatetimeIndex([
                "2024-01-03 08:00",
                "2024-01-03 09:00",
                "2024-01-03 10:00",
            ]),
            dtype="datetime64[ns]",
        )
        open_ = np.array([100.0, 100.0, 100.0])
        close = np.array([101.0, 102.0, 103.0])
        high = close + 0.5
        low = close - 0.5
        result = session_return(open_, high, low, close, ts, from_time="14:00", to_time="17:00")
        assert np.all(np.isnan(result))

    def test_negative_return(self) -> None:
        # Session open = 100, final close = 98 → -2%
        open_, high, low, close, ts = self._make_data(
            session_opens=[100.0, 99.0],
            session_closes=[99.0, 98.0],
            post_closes=[97.0, 96.0],
        )
        result = session_return(open_, high, low, close, ts, from_time="14:00", to_time="16:00")
        assert result[1] == pytest.approx(-0.02)   # (98-100)/100 within session
        assert result[2] == pytest.approx(-0.02)   # carry-forward post-session
        assert result[3] == pytest.approx(-0.02)

    def test_new_session_resets_anchor(self) -> None:
        # Day 1: session open=100, close=105 → +5%
        # Day 2: session open=200, close=202 → +1%
        ts = np.array(
            pd.DatetimeIndex([
                "2024-01-03 14:00",   # day1 session bar 0
                "2024-01-03 15:00",   # day1 session bar 1
                "2024-01-03 22:00",   # day1 post-session
                "2024-01-04 14:00",   # day2 session bar 0
                "2024-01-04 15:00",   # day2 session bar 1
                "2024-01-04 22:00",   # day2 post-session
            ]),
            dtype="datetime64[ns]",
        )
        open_ = np.array([100.0, 103.0, 105.0, 200.0, 201.0, 202.0])
        close = np.array([103.0, 105.0, 105.0, 201.0, 202.0, 202.0])
        high = close + 0.5
        low = close - 0.5
        result = session_return(open_, high, low, close, ts, from_time="14:00", to_time="16:00")
        # Day1 session: open=100, close=105 → +5%
        assert result[1] == pytest.approx(0.05)
        # Day1 post-session: carry +5%
        assert result[2] == pytest.approx(0.05)
        # Day2 session: new anchor at open=200; bar1 close=202 → +1%
        assert result[4] == pytest.approx(0.01)
        # Day2 post-session: carry +1%
        assert result[5] == pytest.approx(0.01)

    def test_output_length_matches_input(self) -> None:
        open_, high, low, close, ts = self._make_data(
            session_opens=[100.0, 101.0],
            session_closes=[101.0, 102.0],
            post_closes=[99.0, 98.0],
        )
        result = session_return(open_, high, low, close, ts, from_time="14:00", to_time="16:00")
        assert len(result) == len(close)

    def test_minimum_move_filter_logic(self) -> None:
        # Simulate how the indicator is used: compare against ±0.005 threshold
        open_, high, low, close, ts = self._make_data(
            session_opens=[100.0, 100.5],
            session_closes=[100.3, 100.6],   # final: (100.6 - 100.0) / 100.0 = +0.6%
            post_closes=[99.0, 98.5, 98.0],
        )
        result = session_return(open_, high, low, close, ts, from_time="14:00", to_time="16:00")
        # Post-session: carry = +0.006. Rule: result > 0.005 → SHORT setup fires
        for i in range(2, 5):
            assert result[i] > 0.005

    def test_registered(self) -> None:
        fn = IndicatorRegistry.get("session_return")
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
# VWAP / Anchored VWAP
# ---------------------------------------------------------------------------

class TestVwapIndicators:
    def test_vwap_resets_daily_and_carries_after_session(self) -> None:
        ts = np.array(
            pd.DatetimeIndex([
                "2024-01-03 07:00",
                "2024-01-03 08:00",
                "2024-01-03 09:00",
                "2024-01-03 10:00",
                "2024-01-03 11:00",
                "2024-01-04 07:00",
                "2024-01-04 08:00",
            ]),
            dtype="datetime64[ns]",
        )
        close = np.array([90.0, 100.0, 110.0, 120.0, 130.0, 95.0, 200.0])
        high = close.copy()
        low = close.copy()
        volume = np.array([1.0, 1.0, 1.0, 2.0, 1.0, 1.0, 4.0])

        result = vwap(
            close,
            high,
            low,
            volume,
            ts,
            from_time="08:00",
            to_time="11:00",
            price_source="close",
        )

        assert np.isnan(result[0])
        assert result[1] == pytest.approx(100.0)
        assert result[2] == pytest.approx(105.0)
        assert result[3] == pytest.approx(112.5)
        assert result[4] == pytest.approx(112.5)
        assert np.isnan(result[5])
        assert result[6] == pytest.approx(200.0)

    def test_vwap_handles_zero_volume_without_infs(self) -> None:
        ts = _ts_range("2024-01-03 08:00", "2024-01-03 10:00", "1h")
        close = np.array([100.0, 110.0, 120.0])
        high = close.copy()
        low = close.copy()
        volume = np.array([0.0, 0.0, 2.0])

        result = vwap(
            close,
            high,
            low,
            volume,
            ts,
            from_time="08:00",
            to_time="11:00",
            price_source="close",
        )

        assert np.isnan(result[0])
        assert np.isnan(result[1])
        assert result[2] == pytest.approx(120.0)
        assert not np.isinf(result).any()

    def test_vwap_price_source_changes_result(self) -> None:
        ts = _ts_range("2024-01-03 08:00", "2024-01-03 09:00", "1h")
        close = np.array([100.0, 100.0])
        high = np.array([110.0, 140.0])
        low = np.array([90.0, 80.0])
        volume = np.array([1.0, 1.0])

        result_close = vwap(close, high, low, volume, ts, price_source="close")
        result_hlc3 = vwap(close, high, low, volume, ts, price_source="hlc3")

        assert result_close[-1] == pytest.approx(100.0)
        assert result_hlc3[-1] == pytest.approx((100.0 + (140.0 + 80.0 + 100.0) / 3.0) / 2.0)
        assert result_hlc3[-1] != pytest.approx(result_close[-1])

    def test_vwap_bands_follow_weighted_stddev(self) -> None:
        ts = _ts_range("2024-01-03 08:00", "2024-01-03 09:00", "1h")
        close = np.array([100.0, 110.0])
        high = close.copy()
        low = close.copy()
        volume = np.array([1.0, 1.0])

        center = vwap(close, high, low, volume, ts, price_source="close", num_std=1.0)
        upper = vwap_upper(close, high, low, volume, ts, price_source="close", num_std=1.0)
        lower = vwap_lower(close, high, low, volume, ts, price_source="close", num_std=1.0)

        assert center[0] == pytest.approx(100.0)
        assert upper[0] == pytest.approx(100.0)
        assert lower[0] == pytest.approx(100.0)
        assert center[1] == pytest.approx(105.0)
        assert upper[1] == pytest.approx(110.0)
        assert lower[1] == pytest.approx(100.0)
        assert np.all(upper >= center)
        assert np.all(center >= lower)

    def test_vwap_num_std_scales_band_distance(self) -> None:
        ts = _ts_range("2024-01-03 08:00", "2024-01-03 09:00", "1h")
        close = np.array([100.0, 110.0])
        high = close.copy()
        low = close.copy()
        volume = np.array([1.0, 1.0])

        upper_1 = vwap_upper(close, high, low, volume, ts, price_source="close", num_std=1.0)
        upper_2 = vwap_upper(close, high, low, volume, ts, price_source="close", num_std=2.0)
        center = vwap(close, high, low, volume, ts, price_source="close", num_std=1.0)

        assert upper_2[-1] - center[-1] == pytest.approx(2 * (upper_1[-1] - center[-1]))

    def test_anchored_vwap_start_hour_stays_nan_before_anchor_and_resets(self) -> None:
        ts = np.array(
            pd.DatetimeIndex([
                "2024-01-03 08:00",
                "2024-01-03 09:00",
                "2024-01-03 10:00",
                "2024-01-04 08:00",
                "2024-01-04 09:00",
            ]),
            dtype="datetime64[ns]",
        )
        close = np.array([90.0, 100.0, 120.0, 80.0, 200.0])
        high = close.copy()
        low = close.copy()
        volume = np.ones(len(close))

        result = anchored_vwap(
            close,
            high,
            low,
            volume,
            ts,
            anchor_mode="start_hour",
            anchor_time="09:00",
            price_source="close",
        )

        assert np.isnan(result[0])
        assert result[1] == pytest.approx(100.0)
        assert result[2] == pytest.approx(110.0)
        assert np.isnan(result[3])
        assert result[4] == pytest.approx(200.0)

    def test_anchored_vwap_session_open_accumulates_after_window(self) -> None:
        ts = _ts_range("2024-01-03 08:00", "2024-01-03 11:00", "1h")
        close = np.array([90.0, 100.0, 120.0, 140.0])
        high = close.copy()
        low = close.copy()
        volume = np.ones(len(close))

        result = anchored_vwap(
            close,
            high,
            low,
            volume,
            ts,
            anchor_mode="session_open",
            from_time="09:00",
            to_time="10:00",
            price_source="close",
        )

        assert np.isnan(result[0])
        assert result[1] == pytest.approx(100.0)
        assert result[2] == pytest.approx(110.0)
        assert result[3] == pytest.approx(120.0)

    def test_anchored_vwap_bands_registered(self) -> None:
        for name in {
            "vwap",
            "vwap_upper",
            "vwap_lower",
            "anchored_vwap",
            "anchored_vwap_upper",
            "anchored_vwap_lower",
        }:
            assert callable(IndicatorRegistry.get(name))

    def test_anchored_vwap_bands_bound_center(self) -> None:
        ts = _ts_range("2024-01-03 08:00", "2024-01-03 10:00", "1h")
        close = np.array([90.0, 100.0, 120.0])
        high = close.copy()
        low = close.copy()
        volume = np.ones(len(close))

        center = anchored_vwap(
            close,
            high,
            low,
            volume,
            ts,
            anchor_mode="start_hour",
            anchor_time="09:00",
            price_source="close",
        )
        upper = anchored_vwap_upper(
            close,
            high,
            low,
            volume,
            ts,
            anchor_mode="start_hour",
            anchor_time="09:00",
            price_source="close",
        )
        lower = anchored_vwap_lower(
            close,
            high,
            low,
            volume,
            ts,
            anchor_mode="start_hour",
            anchor_time="09:00",
            price_source="close",
        )

        valid = ~np.isnan(center)
        assert np.all(upper[valid] >= center[valid])
        assert np.all(center[valid] >= lower[valid])


# ---------------------------------------------------------------------------
# range_fakeout_short
# ---------------------------------------------------------------------------

class TestRangeFakeoutShort:
    """Asian session: 00:00–07:00. Execution window: 07:00+."""

    def _make_data(
        self,
        session_highs_close: list[float],
        post_session_close: list[float],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Build arrays where session bars have close == high - 0.1 and post-session bars
        have the supplied close values.

        Session: 00:00–06:00 (7 bars, indices 0–6).
        Post-session: 07:00–12:00 (6 bars, indices 7–12).
        """
        session_ts = list(pd.date_range("2024-01-03 00:00", periods=7, freq="1h"))
        post_ts = list(pd.date_range("2024-01-03 07:00", periods=len(post_session_close), freq="1h"))
        ts = np.array(session_ts + post_ts, dtype="datetime64[ns]")

        n_session = len(session_ts)
        n_post = len(post_session_close)
        n = n_session + n_post

        # Session bars: close = supplied values, high = close + 0.1
        high = np.ones(n) * 2.0
        low  = np.ones(n) * 0.5
        close = np.ones(n) * 1.0

        for k, v in enumerate(session_highs_close):
            close[k] = v
            high[k] = v + 0.1

        for k, v in enumerate(post_session_close):
            close[n_session + k] = v

        return close, high, low, ts

    def test_fakeout_detected(self) -> None:
        # Session high ≈ 2.1 (max high in session bars: close=2.0 → high=2.1)
        # Post bar 0: close=2.5 (breaks above session_high=2.1) → breakout
        # Post bar 1: close=1.9 (back below 2.1) → fakeout!
        close, high, low, ts = self._make_data(
            session_highs_close=[1.0, 1.5, 2.0, 1.8, 1.6, 1.4, 1.2],
            post_session_close=[2.5, 1.9, 1.9],
        )
        result = range_fakeout_short(
            close, high, low, ts, from_time="00:00", to_time="07:00", lookback_bars=5
        )
        # Index 7 = first post bar (close=2.5, breakout — NOT a fakeout yet)
        # Index 8 = second post bar (close=1.9, fakeout confirmed)
        assert result[8] == pytest.approx(1.0)

    def test_no_fakeout_when_price_stays_above(self) -> None:
        # Price breaks above and stays above — no re-entry
        close, high, low, ts = self._make_data(
            session_highs_close=[1.0, 1.5, 2.0, 1.8, 1.6, 1.4, 1.2],
            post_session_close=[2.5, 2.6, 2.7],
        )
        result = range_fakeout_short(
            close, high, low, ts, from_time="00:00", to_time="07:00", lookback_bars=5
        )
        assert np.all(result == 0.0)

    def test_no_fakeout_when_no_breakout_in_window(self) -> None:
        # Price is below session_high throughout — never broke above
        close, high, low, ts = self._make_data(
            session_highs_close=[1.0, 1.5, 2.0, 1.8, 1.6, 1.4, 1.2],
            post_session_close=[1.8, 1.7, 1.6],  # always below session_high ~2.1
        )
        result = range_fakeout_short(
            close, high, low, ts, from_time="00:00", to_time="07:00", lookback_bars=5
        )
        assert np.all(result == 0.0)

    def test_zero_during_session(self) -> None:
        # Fakeout indicator must be 0 during the defining session itself
        close, high, low, ts = self._make_data(
            session_highs_close=[1.0, 1.5, 2.0, 1.8, 1.6, 1.4, 1.2],
            post_session_close=[2.5, 1.9],
        )
        result = range_fakeout_short(
            close, high, low, ts, from_time="00:00", to_time="07:00", lookback_bars=5
        )
        # Session indices 0–6 must all be 0
        assert np.all(result[:7] == 0.0)

    def test_registered(self) -> None:
        fn = IndicatorRegistry.get("range_fakeout_short")
        assert callable(fn)


# ---------------------------------------------------------------------------
# range_fakeout_long
# ---------------------------------------------------------------------------

class TestRangeFakeoutLong:
    """Mirror of TestRangeFakeoutShort for bullish fakeout."""

    def _make_data(
        self,
        session_lows_close: list[float],
        post_session_close: list[float],
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        session_ts = list(pd.date_range("2024-01-03 00:00", periods=7, freq="1h"))
        post_ts = list(pd.date_range("2024-01-03 07:00", periods=len(post_session_close), freq="1h"))
        ts = np.array(session_ts + post_ts, dtype="datetime64[ns]")

        n_session = len(session_ts)
        n = n_session + len(post_session_close)

        high = np.ones(n) * 2.0
        low  = np.ones(n) * 1.0
        close = np.ones(n) * 1.5

        for k, v in enumerate(session_lows_close):
            close[k] = v
            low[k] = v - 0.1  # session low ≈ min(close) - 0.1

        for k, v in enumerate(post_session_close):
            close[n_session + k] = v

        return close, high, low, ts

    def test_fakeout_detected(self) -> None:
        # Session low ≈ 0.9 (min low among session bars: close=1.0 → low=0.9)
        # Post bar 0: close=0.7 (breaks below session_low) → breakdown
        # Post bar 1: close=1.1 (recovers above session_low=0.9) → bullish fakeout!
        close, high, low, ts = self._make_data(
            session_lows_close=[1.5, 1.2, 1.0, 1.1, 1.3, 1.4, 1.5],
            post_session_close=[0.7, 1.1, 1.1],
        )
        result = range_fakeout_long(
            close, high, low, ts, from_time="00:00", to_time="07:00", lookback_bars=5
        )
        assert result[8] == pytest.approx(1.0)

    def test_no_fakeout_when_price_stays_below(self) -> None:
        close, high, low, ts = self._make_data(
            session_lows_close=[1.5, 1.2, 1.0, 1.1, 1.3, 1.4, 1.5],
            post_session_close=[0.7, 0.6, 0.5],
        )
        result = range_fakeout_long(
            close, high, low, ts, from_time="00:00", to_time="07:00", lookback_bars=5
        )
        assert np.all(result == 0.0)

    def test_registered(self) -> None:
        fn = IndicatorRegistry.get("range_fakeout_long")
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
