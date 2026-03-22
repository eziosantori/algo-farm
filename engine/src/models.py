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
        "bollinger_upper",
        "bollinger_lower",
        "bollinger_basis",
        "momentum",
        "adx",
        "cci",
        "obv",
        "williamsr",
        "roc",
        "volume_sma",
        # Phase D — higher-timeframe indicators
        "htf_ema",
        "htf_sma",
        "supertrend",
        "supertrend_direction",
        # Phase B — session indicators
        "session_active",
        "session_high",
        "session_low",
        # Phase B2 — fakeout indicators
        "range_fakeout_short",
        "range_fakeout_long",
        # Phase D — candlestick patterns (intensity score, float [0,1])
        "hammer",
        "shooting_star",
        "bullish_engulfing",
        "bearish_engulfing",
        "morning_star",
        "evening_star",
        "piercing_pattern",
        "dark_cloud_cover",
        "bullish_marubozu",
        "bearish_marubozu",
        "three_white_soldiers",
        "three_black_crows",
        "doji",
        "dragonfly_doji",
        "gravestone_doji",
        "spinning_top",
        "harami",
        # Phase D — HTF pattern wrapper
        "htf_pattern",
    ]
    params: dict[str, Any]


class SignalGate(BaseModel):
    """Keep a pattern signal active for N bars after it fires.

    Once a pattern indicator fires (score > 0), StrategyComposer holds the
    value for ``active_for_bars`` bars so entry rules can still trigger.
    """

    indicator: str       # must match a name in StrategyDefinition.indicators
    active_for_bars: int  # how many bars the signal stays "on" after detection


class RuleDef(BaseModel):
    indicator: str
    condition: str
    value: float | None = None
    compare_to: str | None = None


class TradingHours(BaseModel):
    """Restrict trading to a specific UTC time window and/or set of weekdays."""

    from_time: str = "00:00"        # session start 'HH:MM' UTC (inclusive)
    to_time: str = "23:59"          # session end   'HH:MM' UTC (exclusive)
    days: list[int] | None = None   # allowed weekdays: 0=Mon…4=Fri; None = Mon–Fri
    force_close: bool = False       # close open position when session ends


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
    risk_pct: float | None = None                               # base risk % of equity per trade; requires a defined SL
    risk_pct_min: float | None = None                           # D4 pattern-sizing: minimum risk % (used with risk_pct_max)
    risk_pct_max: float | None = None                           # D4 pattern-sizing: maximum risk % (interpolated by pattern score)
    sl_atr_mult: float | None = None                            # ATR-based SL at entry: entry ± atr × sl_atr_mult
    tp_atr_mult: float | None = None                            # ATR-based TP at entry: entry + atr × tp_atr_mult
    trailing_sl: Literal["atr", "supertrend"] | None = None    # trailing stop type
    trailing_sl_atr_mult: float = 2.0                          # multiplier for ATR trailing SL
    scale_out: ScaleOut | None = None                          # partial-close config
    time_exit_bars: int | None = None                          # close losing trade after N bars
    trading_hours: TradingHours | None = None                  # session gate (UTC)


class StrategyDefinition(BaseModel):
    version: str
    name: str
    variant: Literal["basic", "advanced"]
    indicators: list[IndicatorDef]
    entry_rules: list[RuleDef]
    exit_rules: list[RuleDef]
    position_management: PositionManagement
    # Phase C — short-side execution (optional; empty = long-only strategy)
    entry_rules_short: list[RuleDef] = []
    exit_rules_short: list[RuleDef] = []
    # Phase D — signal gates: keep pattern signals active for N bars
    signal_gates: list[SignalGate] = []


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
