"""StrategyComposer: generates a backtesting.Strategy subclass at runtime."""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
from backtesting import Strategy  # type: ignore[import-untyped]

from src.backtest.indicators import IndicatorRegistry
from src.models import RuleDef, StrategyDefinition

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
            "entry_price": 0.0,
            "initial_sl_dist": None,  # price distance from entry to initial SL
            "scaled_out": False,
            "bars_in_trade": 0,
        }

        def init(self_bt: Strategy) -> None:  # type: ignore[type-arg]
            for ind_def in definition.indicators:
                fn = registry.get(ind_def.type)
                merged = {**ind_def.params, **params}
                fn_param_names = _get_fn_params(fn)
                ind_params = {k: v for k, v in merged.items() if k in fn_param_names}
                if "high" in fn_param_names and "low" in fn_param_names:
                    indicator = self_bt.I(  # type: ignore[attr-defined]
                        fn,
                        self_bt.data.Close,
                        self_bt.data.High,
                        self_bt.data.Low,
                        **ind_params,
                    )
                else:
                    indicator = self_bt.I(fn, self_bt.data.Close, **ind_params)  # type: ignore[attr-defined]
                setattr(self_bt, ind_def.name, indicator)

        def next(self_bt: Strategy) -> None:  # type: ignore[type-arg]
            pm = definition.position_management

            if not self_bt.position:  # type: ignore[attr-defined]
                # Detect trade-just-closed (e.g. SL hit internally)
                if state["in_trade"]:
                    state["in_trade"] = False
                    state["scaled_out"] = False
                    state["bars_in_trade"] = 0
                    state["initial_sl_dist"] = None

                if _evaluate_rules(self_bt, definition.entry_rules):
                    price = float(self_bt.data.Close[-1])  # type: ignore[attr-defined]

                    # Determine SL at entry
                    sl: float | None = None
                    if pm.sl_pips:
                        sl = price - pm.sl_pips * 0.0001
                    elif pm.sl_atr_mult is not None:
                        atr_ind = _find_indicator_by_type(self_bt, definition, "atr")
                        if atr_ind is not None:
                            atr_val = float(atr_ind[-1])
                            if not np.isnan(atr_val):
                                sl = price - atr_val * pm.sl_atr_mult

                    # Determine TP at entry
                    tp: float | None = None
                    if pm.tp_pips:
                        tp = price + pm.tp_pips * 0.0001

                    state["entry_price"] = price
                    state["initial_sl_dist"] = (price - sl) if sl is not None else None
                    state["in_trade"] = True
                    state["scaled_out"] = False
                    state["bars_in_trade"] = 0

                    self_bt.buy(sl=sl, tp=tp)  # type: ignore[attr-defined]

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

                # --- Trailing SL: ATR-based ---
                if pm.trailing_sl == "atr":
                    atr_ind = _find_indicator_by_type(self_bt, definition, "atr")
                    if atr_ind is not None:
                        atr_val = float(atr_ind[-1])
                        if not np.isnan(atr_val):
                            new_sl = float(self_bt.data.Close[-1]) - atr_val * pm.trailing_sl_atr_mult  # type: ignore[attr-defined]
                            if trade.sl is None or new_sl > trade.sl:
                                trade.sl = new_sl

                # --- Trailing SL: SuperTrend line ---
                elif pm.trailing_sl == "supertrend":
                    st_ind = _find_indicator_by_type(self_bt, definition, "supertrend")
                    if st_ind is not None:
                        st_val = float(st_ind[-1])
                        if not np.isnan(st_val):
                            if trade.sl is None or st_val > trade.sl:
                                trade.sl = st_val

                # --- Scale-out: partial close at target R-multiple ---
                if (
                    pm.scale_out is not None
                    and not state["scaled_out"]
                    and state["initial_sl_dist"]
                ):
                    so = pm.scale_out
                    profit = float(self_bt.data.Close[-1]) - state["entry_price"]  # type: ignore[attr-defined]
                    if profit >= so.trigger_r * state["initial_sl_dist"]:
                        trade.close(portion=so.volume_pct / 100)
                        state["scaled_out"] = True
                        # Move remaining position SL to breakeven
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
                if _evaluate_rules(self_bt, definition.exit_rules):
                    self_bt.position.close()  # type: ignore[attr-defined]

        return type(
            "DynamicStrategy",
            (Strategy,),
            {"init": init, "next": next},
        )


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
    if cond == "crosses_above" and rule.compare_to is not None:
        other = getattr(strategy, rule.compare_to, None)
        if other is None or len(other) < 2:
            return False
        return float(current) > float(other[-1]) and float(strategy.__dict__.get(rule.indicator, [current, current])[-2] if hasattr(strategy, rule.indicator) else current) <= float(other[-2])  # type: ignore[attr-defined]
    if cond == "crosses_below" and rule.compare_to is not None:
        other = getattr(strategy, rule.compare_to, None)
        if other is None or len(other) < 2:
            return False
        return current < float(other[-1])
    return False
