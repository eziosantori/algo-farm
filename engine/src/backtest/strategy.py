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

        def init(self_bt: Strategy) -> None:  # type: ignore[type-arg]
            for ind_def in definition.indicators:
                fn = registry.get(ind_def.type)
                merged = {**ind_def.params, **params}
                # Extract period/params relevant for this indicator
                ind_params = {k: v for k, v in merged.items() if k in _get_fn_params(fn)}
                indicator = self_bt.I(fn, self_bt.data.Close, **ind_params)  # type: ignore[attr-defined]
                setattr(self_bt, ind_def.name, indicator)

        def next(self_bt: Strategy) -> None:  # type: ignore[type-arg]
            # Evaluate entry rules if no position open
            if not self_bt.position:  # type: ignore[attr-defined]
                if _evaluate_rules(self_bt, definition.entry_rules):
                    sl_pips = definition.position_management.sl_pips
                    tp_pips = definition.position_management.tp_pips
                    price = self_bt.data.Close[-1]  # type: ignore[attr-defined]
                    sl = price - sl_pips * 0.0001 if sl_pips else None
                    tp = price + tp_pips * 0.0001 if tp_pips else None
                    self_bt.buy(sl=sl, tp=tp)  # type: ignore[attr-defined]
            else:
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
    if cond == ">" and rule.value is not None:
        return current > rule.value
    if cond == "<" and rule.value is not None:
        return current < rule.value
    if cond == ">=" and rule.value is not None:
        return current >= rule.value
    if cond == "<=" and rule.value is not None:
        return current <= rule.value
    if cond == "crosses_above" and rule.compare_to is not None:
        other = getattr(strategy, rule.compare_to, None)
        if other is None or len(other) < 2:
            return False
        return float(ind_prev := current) > float(other[-1]) and float(strategy.__dict__.get(rule.indicator, [current, current])[-2] if hasattr(strategy, rule.indicator) else current) <= float(other[-2])  # type: ignore[attr-defined]
    if cond == "crosses_below" and rule.compare_to is not None:
        other = getattr(strategy, rule.compare_to, None)
        if other is None or len(other) < 2:
            return False
        return current < float(other[-1])
    return False
