"""Unit tests for _compute_trade_size (risk-based and fractional position sizing)."""
from __future__ import annotations

import pytest

from src.backtest.strategy import _compute_trade_size
from src.models import PositionManagement


# ---------------------------------------------------------------------------
# Risk-based sizing (risk_pct set + SL defined)
# ---------------------------------------------------------------------------

def test_risk_based_size_with_fixed_sl_pips() -> None:
    """With risk_pct=1% and 20-pip SL, size = risk_amount / sl_distance."""
    pm = PositionManagement(size=0.02, sl_pips=20, risk_pct=0.01)
    price = 1.1000
    sl = price - 20 * 0.0001  # 1.0980
    equity = 10_000.0
    size = _compute_trade_size(pm, price, sl, equity)
    # risk_amount = 100, sl_distance = 0.0020 → 50_000 units
    assert abs(size - 50_000.0) < 1.0


def test_risk_based_size_scales_linearly_with_equity() -> None:
    """Doubling equity doubles position size (same risk %)."""
    pm = PositionManagement(size=0.02, sl_pips=20, risk_pct=0.01)
    price, sl = 1.1000, 1.0980
    size_10k = _compute_trade_size(pm, price, sl, 10_000.0)
    size_20k = _compute_trade_size(pm, price, sl, 20_000.0)
    assert abs(size_20k - 2 * size_10k) < 1.0


def test_risk_based_size_scales_linearly_with_risk_pct() -> None:
    """Doubling risk_pct doubles position size."""
    price, sl = 1.1000, 1.0980
    pm1 = PositionManagement(size=0.02, risk_pct=0.01)
    pm2 = PositionManagement(size=0.02, risk_pct=0.02)
    size1 = _compute_trade_size(pm1, price, sl, 10_000.0)
    size2 = _compute_trade_size(pm2, price, sl, 10_000.0)
    assert abs(size2 - 2 * size1) < 1.0


def test_risk_based_size_inversely_proportional_to_sl_distance() -> None:
    """Wider SL → smaller position size (same risk amount)."""
    pm = PositionManagement(size=0.02, risk_pct=0.01)
    price = 1.1000
    sl_tight = price - 0.0010   # 10 pips → larger size
    sl_wide  = price - 0.0040   # 40 pips → smaller size
    size_tight = _compute_trade_size(pm, price, sl_tight, 10_000.0)
    size_wide  = _compute_trade_size(pm, price, sl_wide,  10_000.0)
    assert size_tight > size_wide
    assert abs(size_tight - 4 * size_wide) < 1.0


def test_risk_based_formula_correctness() -> None:
    """Verify formula: size = equity × risk_pct / (price - sl)."""
    equity, risk_pct = 15_000.0, 0.02
    price, sl = 1.2500, 1.2400  # 100-pip SL = 0.0100
    pm = PositionManagement(size=0.05, risk_pct=risk_pct)
    expected = (equity * risk_pct) / (price - sl)  # 15000*0.02 / 0.01 = 30_000
    size = _compute_trade_size(pm, price, sl, equity)
    assert abs(size - expected) < 0.01


# ---------------------------------------------------------------------------
# Fallback to fractional sizing
# ---------------------------------------------------------------------------

def test_fallback_to_size_when_risk_pct_not_set() -> None:
    """Without risk_pct, returns pm.size (fractional equity allocation)."""
    pm = PositionManagement(size=0.02)
    size = _compute_trade_size(pm, 1.1000, None, 10_000.0)
    assert size == 0.02


def test_fallback_to_size_when_sl_is_none() -> None:
    """risk_pct set but no SL → cannot compute risk, fallback to size."""
    pm = PositionManagement(size=0.05, risk_pct=0.01)
    size = _compute_trade_size(pm, 1.1000, None, 10_000.0)
    assert size == 0.05


def test_fallback_to_size_when_sl_equals_price() -> None:
    """Edge case: sl_distance = 0 (SL at entry price) → fallback to avoid div-by-zero."""
    pm = PositionManagement(size=0.02, risk_pct=0.01)
    size = _compute_trade_size(pm, 1.1000, 1.1000, 10_000.0)
    assert size == 0.02


def test_fallback_to_size_when_sl_above_price() -> None:
    """Edge case: sl > price (invalid for long) → sl_distance negative → fallback."""
    pm = PositionManagement(size=0.02, risk_pct=0.01)
    size = _compute_trade_size(pm, 1.1000, 1.1100, 10_000.0)  # sl above entry
    assert size == 0.02


def test_fractional_size_is_returned_unchanged() -> None:
    """When no risk_pct, the raw pm.size value is returned exactly."""
    for frac in [0.01, 0.05, 0.10]:
        pm = PositionManagement(size=frac)
        size = _compute_trade_size(pm, 1.0000, None, 5_000.0)
        assert size == frac
