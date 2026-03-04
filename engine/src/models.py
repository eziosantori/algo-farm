"""Pydantic models for StrategyDefinition, ParamGrid, BacktestMetrics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel


class IndicatorDef(BaseModel):
    name: str
    type: Literal[
        "sma",
        "ema",
        "macd",
        "rsi",
        "stoch",
        "atr",
        "bollinger_bands",
        "momentum",
        "adx",
        "cci",
        "obv",
        "williamsr",
        "supertrend",
        "supertrend_direction",
    ]
    params: dict[str, Any]


class RuleDef(BaseModel):
    indicator: str
    condition: str
    value: float | None = None
    compare_to: str | None = None


class PositionManagement(BaseModel):
    size: float = 0.02
    sl_pips: float | None = None
    tp_pips: float | None = None
    max_open_trades: int = 1


class StrategyDefinition(BaseModel):
    version: str
    name: str
    variant: Literal["basic", "advanced"]
    indicators: list[IndicatorDef]
    entry_rules: list[RuleDef]
    exit_rules: list[RuleDef]
    position_management: PositionManagement


@dataclass
class BacktestMetrics:
    total_return_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_pct: float
    win_rate_pct: float
    profit_factor: float
    total_trades: int
    avg_trade_duration_bars: float
    cagr_pct: float
    expectancy: float
