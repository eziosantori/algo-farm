from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np


class IndicatorRegistry:
    _registry: dict[str, Callable[..., Any]] = {}

    @classmethod
    def register(cls, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            cls._registry[name] = fn
            return fn

        return decorator

    @classmethod
    def get(cls, name: str) -> Callable[..., Any]:
        if name not in cls._registry:
            raise KeyError(f"Indicator '{name}' not registered")
        return cls._registry[name]

    @classmethod
    def list_all(cls) -> list[str]:
        return list(cls._registry.keys())


# Import modules to trigger registration
from src.backtest.indicators import trend, momentum, volatility, session  # noqa: E402, F401

__all__ = ["IndicatorRegistry"]
