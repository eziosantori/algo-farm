"""OHLCV passthrough indicators — expose raw price/volume columns as named indicators."""
from __future__ import annotations

import numpy as np

from src.backtest.indicators import IndicatorRegistry


@IndicatorRegistry.register("close")
def close_passthrough(close: np.ndarray) -> np.ndarray:
    """Return raw Close prices (passthrough)."""
    return close.astype(float)


@IndicatorRegistry.register("volume")
def volume_passthrough(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    """Return raw Volume values (passthrough)."""
    return volume.astype(float)


@IndicatorRegistry.register("high")
def high_passthrough(close: np.ndarray, high: np.ndarray, low: np.ndarray) -> np.ndarray:
    """Return raw High prices (passthrough)."""
    return high.astype(float)


@IndicatorRegistry.register("low")
def low_passthrough(close: np.ndarray, high: np.ndarray, low: np.ndarray) -> np.ndarray:
    """Return raw Low prices (passthrough)."""
    return low.astype(float)


@IndicatorRegistry.register("open")
def open_passthrough(open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """Return raw Open prices (passthrough).

    Signature uses ``open_`` as first arg so that ``_get_fn_params`` (which excludes
    the first positional arg) sees ``high``, ``low``, and ``close`` in ``fn_param_names``.
    The ``"close" in fn_param_names`` dispatch branch then passes
    ``(data.Open, data.High, data.Low, data.Close)`` — matching this signature exactly.
    """
    return open_.astype(float)
