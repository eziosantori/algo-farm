"""Unit tests for OHLCV passthrough indicators."""
from __future__ import annotations

import numpy as np
import pytest

from src.backtest.indicators import IndicatorRegistry
from src.models import IndicatorDef, StrategyDefinition, PositionManagement, RuleDef


# ---------------------------------------------------------------------------
# Registry registration
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["close", "open", "high", "low", "volume"])
def test_ohlcv_registered(name: str) -> None:
    fn = IndicatorRegistry.get(name)
    assert callable(fn)


# ---------------------------------------------------------------------------
# Passthrough correctness
# ---------------------------------------------------------------------------

CLOSE = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
OPEN  = np.array([0.9, 1.9, 2.9, 3.9, 4.9])
HIGH  = np.array([1.1, 2.1, 3.1, 4.1, 5.1])
LOW   = np.array([0.8, 1.8, 2.8, 3.8, 4.8])
VOLUME = np.array([100.0, 200.0, 300.0, 400.0, 500.0])


def test_close_passthrough() -> None:
    fn = IndicatorRegistry.get("close")
    result = fn(CLOSE)
    np.testing.assert_array_equal(result, CLOSE)


def test_open_passthrough() -> None:
    fn = IndicatorRegistry.get("open")
    result = fn(OPEN, HIGH, LOW, CLOSE)
    np.testing.assert_array_equal(result, OPEN)


def test_high_passthrough() -> None:
    fn = IndicatorRegistry.get("high")
    result = fn(CLOSE, HIGH, LOW)
    np.testing.assert_array_equal(result, HIGH)


def test_low_passthrough() -> None:
    fn = IndicatorRegistry.get("low")
    result = fn(CLOSE, HIGH, LOW)
    np.testing.assert_array_equal(result, LOW)


def test_volume_passthrough() -> None:
    fn = IndicatorRegistry.get("volume")
    result = fn(CLOSE, VOLUME)
    np.testing.assert_array_equal(result, VOLUME)


def test_passthrough_returns_float_dtype() -> None:
    fn = IndicatorRegistry.get("close")
    result = fn(np.array([1, 2, 3], dtype=int))
    assert result.dtype == float


# ---------------------------------------------------------------------------
# Pydantic validation
# ---------------------------------------------------------------------------

def _minimal_strategy(indicator_type: str) -> StrategyDefinition:
    return StrategyDefinition(
        version="1",
        name="test",
        variant="basic",
        indicators=[IndicatorDef(name="px", type=indicator_type, params={})],  # type: ignore[arg-type]
        entry_rules=[RuleDef(indicator="px", condition=">", value=1.0)],
        exit_rules=[RuleDef(indicator="px", condition="<", value=0.5)],
        position_management=PositionManagement(),
    )


@pytest.mark.parametrize("ind_type", ["close", "open", "high", "low", "volume"])
def test_pydantic_accepts_ohlcv_type(ind_type: str) -> None:
    sd = _minimal_strategy(ind_type)
    assert sd.indicators[0].type == ind_type
