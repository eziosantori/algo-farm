"""StrategyComposer: generates a backtesting.Strategy subclass at runtime."""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from backtesting import Strategy  # type: ignore[import-untyped]

from src.backtest.indicators import IndicatorRegistry
from src.models import PositionManagement, RuleDef, StrategyDefinition, TradingHours

logger = logging.getLogger(__name__)


class StrategyComposer:
    def build_class(
        self,
        definition: StrategyDefinition,
        params: dict[str, Any],
    ) -> type:
        """Build a backtesting.Strategy subclass from a StrategyDefinition."""
        registry = IndicatorRegistry

        # Mutable state shared between bars; reset when a trade closes.
        state: dict[str, Any] = {
            "in_trade": False,
            "direction": None,          # "long" | "short" | None
            "entry_price": 0.0,
            "initial_sl_dist": None,    # absolute price distance from entry to initial SL
            "scaled_out": False,
            "bars_in_trade": 0,
        }

        def init(self_bt: Strategy) -> None:  # type: ignore[type-arg]
            for ind_def in definition.indicators:
                fn = registry.get(ind_def.type)
                merged = {**ind_def.params, **params}
                fn_param_names = _get_fn_params(fn)
                ind_params = {k: v for k, v in merged.items() if k in fn_param_names}
                if "timestamps" in fn_param_names:
                    # Session indicators — pass timestamps as a positional array
                    timestamps = np.array(self_bt.data.index, dtype="datetime64[ns]")  # type: ignore[attr-defined]
                    if "high" in fn_param_names and "low" in fn_param_names:
                        indicator = self_bt.I(  # type: ignore[attr-defined]
                            fn,
                            self_bt.data.Close,
                            self_bt.data.High,
                            self_bt.data.Low,
                            timestamps,
                            **ind_params,
                        )
                    else:
                        indicator = self_bt.I(fn, self_bt.data.Close, timestamps, **ind_params)  # type: ignore[attr-defined]
                elif "high" in fn_param_names and "low" in fn_param_names and "close" in fn_param_names:
                    # Candlestick patterns: require OHLC (open_ is first param, excluded by _get_fn_params)
                    indicator = self_bt.I(  # type: ignore[attr-defined]
                        fn,
                        self_bt.data.Open,
                        self_bt.data.High,
                        self_bt.data.Low,
                        self_bt.data.Close,
                        **ind_params,
                    )
                elif "high" in fn_param_names and "low" in fn_param_names:
                    indicator = self_bt.I(  # type: ignore[attr-defined]
                        fn,
                        self_bt.data.Close,
                        self_bt.data.High,
                        self_bt.data.Low,
                        **ind_params,
                    )
                elif "volume" in fn_param_names:
                    indicator = self_bt.I(  # type: ignore[attr-defined]
                        fn,
                        self_bt.data.Close,
                        self_bt.data.Volume,
                        **ind_params,
                    )
                else:
                    indicator = self_bt.I(fn, self_bt.data.Close, **ind_params)  # type: ignore[attr-defined]
                setattr(self_bt, ind_def.name, indicator)

        def next(self_bt: Strategy) -> None:  # type: ignore[type-arg]
            pm = definition.position_management

            # --- Session gate: respect trading_hours before any other logic ---
            if pm.trading_hours is not None:
                bar_dt = self_bt.data.index[-1]  # type: ignore[attr-defined]
                if not _is_within_trading_hours(bar_dt, pm.trading_hours):
                    if pm.trading_hours.force_close and self_bt.position:  # type: ignore[attr-defined]
                        self_bt.position.close()  # type: ignore[attr-defined]
                        state["in_trade"] = False
                        state["scaled_out"] = False
                        state["bars_in_trade"] = 0
                        state["initial_sl_dist"] = None
                    return

            if not self_bt.position:  # type: ignore[attr-defined]
                # Detect trade-just-closed (e.g. SL hit internally)
                if state["in_trade"]:
                    state["in_trade"] = False
                    state["direction"] = None
                    state["scaled_out"] = False
                    state["bars_in_trade"] = 0
                    state["initial_sl_dist"] = None

                # --- Long entry ---
                if _evaluate_rules(self_bt, definition.entry_rules):
                    price = float(self_bt.data.Close[-1])  # type: ignore[attr-defined]

                    sl: float | None = None
                    if pm.sl_pips:
                        sl = price - pm.sl_pips * 0.0001
                    elif pm.sl_atr_mult is not None:
                        atr_ind = _find_indicator_by_type(self_bt, definition, "atr")
                        if atr_ind is not None:
                            atr_val = float(atr_ind[-1])
                            if not np.isnan(atr_val):
                                sl = price - atr_val * pm.sl_atr_mult

                    tp: float | None = None
                    if pm.tp_pips:
                        tp = price + pm.tp_pips * 0.0001
                    elif pm.tp_atr_mult is not None:
                        atr_ind = _find_indicator_by_type(self_bt, definition, "atr")
                        if atr_ind is not None:
                            atr_val = float(atr_ind[-1])
                            if not np.isnan(atr_val):
                                tp = price + atr_val * pm.tp_atr_mult

                    state["entry_price"] = price
                    state["initial_sl_dist"] = abs(price - sl) if sl is not None else None
                    state["in_trade"] = True
                    state["direction"] = "long"
                    state["scaled_out"] = False
                    state["bars_in_trade"] = 0

                    trade_size = _compute_trade_size(pm, price, sl, float(self_bt.equity))  # type: ignore[attr-defined]
                    self_bt.buy(size=trade_size, sl=sl, tp=tp)  # type: ignore[attr-defined]

                # --- Short entry (only when no long fired this bar) ---
                elif definition.entry_rules_short and _evaluate_rules(self_bt, definition.entry_rules_short):
                    price = float(self_bt.data.Close[-1])  # type: ignore[attr-defined]

                    sl_short: float | None = None
                    if pm.sl_pips:
                        sl_short = price + pm.sl_pips * 0.0001
                    elif pm.sl_atr_mult is not None:
                        atr_ind = _find_indicator_by_type(self_bt, definition, "atr")
                        if atr_ind is not None:
                            atr_val = float(atr_ind[-1])
                            if not np.isnan(atr_val):
                                sl_short = price + atr_val * pm.sl_atr_mult

                    tp_short: float | None = None
                    if pm.tp_pips:
                        tp_short = price - pm.tp_pips * 0.0001
                    elif pm.tp_atr_mult is not None:
                        atr_ind = _find_indicator_by_type(self_bt, definition, "atr")
                        if atr_ind is not None:
                            atr_val = float(atr_ind[-1])
                            if not np.isnan(atr_val):
                                tp_short = price - atr_val * pm.tp_atr_mult

                    state["entry_price"] = price
                    state["initial_sl_dist"] = abs(price - sl_short) if sl_short is not None else None
                    state["in_trade"] = True
                    state["direction"] = "short"
                    state["scaled_out"] = False
                    state["bars_in_trade"] = 0

                    trade_size = _compute_trade_size(pm, price, sl_short, float(self_bt.equity))  # type: ignore[attr-defined]
                    self_bt.sell(size=trade_size, sl=sl_short, tp=tp_short)  # type: ignore[attr-defined]

            else:
                if not state["in_trade"]:
                    # Position opened this bar — initialise state
                    state["in_trade"] = True
                    state["bars_in_trade"] = 0

                state["bars_in_trade"] += 1
                trades = list(self_bt.trades)  # type: ignore[attr-defined]
                if not trades:
                    return
                trade = trades[0]
                is_short = trade.size < 0

                # --- Trailing SL: ATR-based ---
                if pm.trailing_sl == "atr":
                    atr_ind = _find_indicator_by_type(self_bt, definition, "atr")
                    if atr_ind is not None:
                        atr_val = float(atr_ind[-1])
                        if not np.isnan(atr_val):
                            close_val = float(self_bt.data.Close[-1])  # type: ignore[attr-defined]
                            if is_short:
                                new_sl = close_val + atr_val * pm.trailing_sl_atr_mult
                                if trade.sl is None or new_sl < trade.sl:
                                    trade.sl = new_sl
                            else:
                                new_sl = close_val - atr_val * pm.trailing_sl_atr_mult
                                if trade.sl is None or new_sl > trade.sl:
                                    trade.sl = new_sl

                # --- Trailing SL: SuperTrend line ---
                elif pm.trailing_sl == "supertrend":
                    st_ind = _find_indicator_by_type(self_bt, definition, "supertrend")
                    if st_ind is not None:
                        st_val = float(st_ind[-1])
                        if not np.isnan(st_val):
                            if is_short:
                                if trade.sl is None or st_val < trade.sl:
                                    trade.sl = st_val
                            else:
                                if trade.sl is None or st_val > trade.sl:
                                    trade.sl = st_val

                # --- Scale-out: partial close at target R-multiple ---
                if (
                    pm.scale_out is not None
                    and not state["scaled_out"]
                    and state["initial_sl_dist"]
                ):
                    so = pm.scale_out
                    close_val = float(self_bt.data.Close[-1])  # type: ignore[attr-defined]
                    profit = (state["entry_price"] - close_val) if is_short else (close_val - state["entry_price"])
                    if profit >= so.trigger_r * state["initial_sl_dist"]:
                        trade.close(portion=so.volume_pct / 100)
                        state["scaled_out"] = True
                        remaining = list(self_bt.trades)  # type: ignore[attr-defined]
                        if remaining:
                            remaining[0].sl = state["entry_price"]

                # --- Time-based exit: close losing trade after N bars ---
                if pm.time_exit_bars and state["bars_in_trade"] >= pm.time_exit_bars:
                    remaining = list(self_bt.trades)  # type: ignore[attr-defined]
                    if remaining and remaining[0].pl <= 0:
                        self_bt.position.close()  # type: ignore[attr-defined]
                        return

                # --- Rule-based exit ---
                exit_rules = (
                    definition.exit_rules_short
                    if (is_short and definition.exit_rules_short)
                    else definition.exit_rules
                )
                if _evaluate_rules(self_bt, exit_rules):
                    self_bt.position.close()  # type: ignore[attr-defined]

        return type(
            "DynamicStrategy",
            (Strategy,),
            {"init": init, "next": next},
        )


def _compute_trade_size(
    pm: PositionManagement,
    price: float,
    sl: float | None,
    equity: float,
) -> float:
    """Compute position size to pass to Strategy.buy().

    Risk-based sizing (when ``pm.risk_pct`` is set and a SL is defined):
      - ``units = (equity × risk_pct) / sl_distance``
      - Returns an integer-like float representing units of the instrument.
      - Example: equity=10 000, risk_pct=0.01, SL 20 pips (0.0020)
        → units = 100 / 0.0020 = 50 000 units.

    Fallback (``pm.risk_pct`` is None, or no SL provided, or sl_distance ≤ 0):
      - Returns ``pm.size`` as a fractional equity allocation (0 < size < 1).
      - backtesting.py interprets fractions as "invest size × equity".
    """
    if pm.risk_pct is not None and sl is not None:
        sl_distance = abs(price - sl)   # works for both long (sl < price) and short (sl > price)
        if sl_distance > 0:
            units = (equity * pm.risk_pct) / sl_distance
            return max(1, round(units))  # backtesting.py requires a whole number when size > 1
    return pm.size


def _get_fn_params(fn: Any) -> set[str]:
    """Return set of parameter names for a function (excluding the first positional arg)."""
    import inspect
    sig = inspect.signature(fn)
    params = list(sig.parameters.keys())
    return set(params[1:]) if params else set()


def _find_indicator_by_type(
    self_bt: Strategy,  # type: ignore[type-arg]
    definition: StrategyDefinition,
    ind_type: str,
) -> Any | None:
    """Return the first indicator attribute of the given type, or None."""
    for ind_def in definition.indicators:
        if ind_def.type == ind_type:
            return getattr(self_bt, ind_def.name, None)
    return None


def _evaluate_rules(strategy: Strategy, rules: list[RuleDef]) -> bool:  # type: ignore[type-arg]
    """Evaluate all rules (AND logic). Returns True if all pass."""
    if not rules:
        return False
    for rule in rules:
        ind = getattr(strategy, rule.indicator, None)
        if ind is None:
            logger.warning("Indicator '%s' not found on strategy", rule.indicator)
            return False
        current = float(ind[-1])
        if np.isnan(current):
            return False
        if not _check_condition(strategy, rule, current):
            return False
    return True


def _check_condition(strategy: Strategy, rule: RuleDef, current: float) -> bool:  # type: ignore[type-arg]
    cond = rule.condition

    if rule.value is not None:
        target: float | None = rule.value
    elif rule.compare_to is not None:
        other_ind = getattr(strategy, rule.compare_to, None)
        if other_ind is None:
            return False
        target = float(other_ind[-1])
        if np.isnan(target):
            return False
    else:
        target = None

    if cond == ">" and target is not None:
        return current > target
    if cond == "<" and target is not None:
        return current < target
    if cond == ">=" and target is not None:
        return current >= target
    if cond == "<=" and target is not None:
        return current <= target
    if cond == "crosses_above":
        ind_self = getattr(strategy, rule.indicator, None)
        if ind_self is None or len(ind_self) < 2:
            return False
        if rule.compare_to is not None:
            other = getattr(strategy, rule.compare_to, None)
            if other is None or len(other) < 2:
                return False
            return float(ind_self[-1]) > float(other[-1]) and float(ind_self[-2]) <= float(other[-2])
        if rule.value is not None:
            return float(ind_self[-1]) > rule.value and float(ind_self[-2]) <= rule.value
        return False
    if cond == "crosses_below":
        ind_self = getattr(strategy, rule.indicator, None)
        if ind_self is None or len(ind_self) < 2:
            return False
        if rule.compare_to is not None:
            other = getattr(strategy, rule.compare_to, None)
            if other is None or len(other) < 2:
                return False
            return float(ind_self[-1]) < float(other[-1]) and float(ind_self[-2]) >= float(other[-2])
        if rule.value is not None:
            return float(ind_self[-1]) < rule.value and float(ind_self[-2]) >= rule.value
        return False
    return False


def _is_within_trading_hours(bar_dt: Any, th: TradingHours) -> bool:
    """Return True if bar_dt falls inside the configured trading hours window.

    Handles overnight sessions (from_time > to_time, e.g. 22:00–06:00).
    Weekends (Saturday/Sunday) are always outside unless explicitly included in ``days``.
    """
    ts = pd.Timestamp(bar_dt)

    # Day-of-week check
    allowed_days = th.days if th.days is not None else list(range(5))  # Mon–Fri default
    if ts.weekday() not in allowed_days:
        return False

    from_min = int(th.from_time.split(":")[0]) * 60 + int(th.from_time.split(":")[1])
    to_min = int(th.to_time.split(":")[0]) * 60 + int(th.to_time.split(":")[1])
    bar_min = ts.hour * 60 + ts.minute

    if from_min < to_min:
        return from_min <= bar_min < to_min
    # Overnight session (from > to)
    return bar_min >= from_min or bar_min < to_min
