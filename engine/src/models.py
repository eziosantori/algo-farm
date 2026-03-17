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


class ScaleOut(BaseModel):
    """Partial-close configuration: close a portion of the trade once profit reaches trigger_r × initial risk."""

    trigger_r: float = 1.5    # close when profit >= trigger_r × initial SL distance
    volume_pct: int = 50      # percentage of position to close (1–99)


class PositionManagement(BaseModel):
    size: float = 0.02
    sl_pips: float | None = None
    tp_pips: float | None = None
    max_open_trades: int = 1
    # M9 — Advanced Position Management (all optional, backward-compatible)
    risk_pct: float | None = None                               # risk % of equity per trade (e.g. 0.01 = 1%); requires a defined SL
    sl_atr_mult: float | None = None                            # ATR-based SL at entry: entry ± atr × sl_atr_mult
    trailing_sl: Literal["atr", "supertrend"] | None = None    # trailing stop type
    trailing_sl_atr_mult: float = 2.0                          # multiplier for ATR trailing SL
    scale_out: ScaleOut | None = None                          # partial-close config
    time_exit_bars: int | None = None                          # close losing trade after N bars


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
