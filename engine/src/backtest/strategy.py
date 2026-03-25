"""StrategyComposer: generates a backtesting.Strategy subclass at runtime."""
from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd
from backtesting import Strategy  # type: ignore[import-untyped]

from src.backtest.indicators import IndicatorRegistry
from src.models import (
    EntryAnchoredVwapExit, PatternGroup, PositionManagement, RuleDef, SignalGate,
    StrategyDefinition, SuppressionGate, TradingHours, TriggerHold,
)

logger = logging.getLogger(__name__)


class StrategyComposer:
    def build_class(
        self,
        definition: StrategyDefinition,
        params: dict[str, Any],
        instrument: str = "",
        timeframe: str = "",
    ) -> type:
        """Build a backtesting.Strategy subclass from a StrategyDefinition.

        ``instrument`` and ``timeframe`` are used to look up per-pair overrides
        from ``definition.param_overrides``; if absent or empty the global
        indicator params are used unchanged.
        """
        registry = IndicatorRegistry
        _pair_overrides = definition.param_overrides.get(instrument, {}).get(timeframe, {})

        # Mutable state shared between bars; reset when a trade closes.
        state: dict[str, Any] = {
            "in_trade": False,
            "direction": None,          # "long" | "short" | None
            "entry_price": 0.0,
            "initial_sl_dist": None,    # absolute price distance from entry to initial SL
            "scaled_out": False,
            "bars_in_trade": 0,
            # Signal-gate countdown: {indicator_name: bars_remaining}
            "gate_countdown": {g.indicator: 0 for g in definition.signal_gates},
            # Suppression-gate countdown: {indicator_name: bars_remaining}
            "suppression_countdown": {g.indicator: 0 for g in definition.suppression_gates},
            # Trigger-hold countdown: {indicator_name: bars_remaining}
            "trigger_hold_countdown": {h.indicator: 0 for h in definition.trigger_holds},
            # Last observed pattern score for position-sizing interpolation
            "pattern_score": 0.0,
            # Entry-anchored VWAP state (runtime only, active while a trade is open)
            "entry_avwap_weight_sum": 0.0,
            "entry_avwap_weighted_price_sum": 0.0,
            "entry_avwap_prev_value": np.nan,
            "entry_avwap_value": np.nan,
        }

        def init(self_bt: Strategy) -> None:  # type: ignore[type-arg]
            for ind_def in definition.indicators:
                fn = registry.get(ind_def.type)
                merged = {**ind_def.params, **params, **_pair_overrides}
                fn_param_names = _get_fn_params(fn)
                ind_params = {k: v for k, v in merged.items() if k in fn_param_names}
                if "timestamps" in fn_param_names:
                    # Session and HTF indicators — pass timestamps as a positional array
                    timestamps = np.array(self_bt.data.index, dtype="datetime64[ns]")  # type: ignore[attr-defined]
                    if "close" in fn_param_names and "volume" in fn_param_names:
                        indicator = self_bt.I(  # type: ignore[attr-defined]
                            fn,
                            self_bt.data.Open,
                            self_bt.data.High,
                            self_bt.data.Low,
                            self_bt.data.Close,
                            self_bt.data.Volume,
                            timestamps,
                            **ind_params,
                        )
                    elif "close" in fn_param_names:
                        # htf_pattern: first param is open_, rest = high, low, close, timestamps
                        indicator = self_bt.I(  # type: ignore[attr-defined]
                            fn,
                            self_bt.data.Open,
                            self_bt.data.High,
                            self_bt.data.Low,
                            self_bt.data.Close,
                            timestamps,
                            **ind_params,
                        )
                    elif "high" in fn_param_names and "low" in fn_param_names and "volume" in fn_param_names:
                        indicator = self_bt.I(  # type: ignore[attr-defined]
                            fn,
                            self_bt.data.Close,
                            self_bt.data.High,
                            self_bt.data.Low,
                            self_bt.data.Volume,
                            timestamps,
                            **ind_params,
                        )
                    elif "high" in fn_param_names and "low" in fn_param_names:
                        # session indicators with H/L (e.g. session_high, session_low)
                        indicator = self_bt.I(  # type: ignore[attr-defined]
                            fn,
                            self_bt.data.Close,
                            self_bt.data.High,
                            self_bt.data.Low,
                            timestamps,
                            **ind_params,
                        )
                    else:
                        # htf_ema, htf_sma, session_active
                        indicator = self_bt.I(fn, self_bt.data.Close, timestamps, **ind_params)  # type: ignore[attr-defined]
                elif "close" in fn_param_names:
                    # Candlestick patterns: _get_fn_params excludes the first arg (open_),
                    # so 'close' appearing in fn_param_names means OHLC signature.
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

            # --- Signal gates: tick down counters; override indicator value when active ---
            if definition.signal_gates:
                for gate in definition.signal_gates:
                    ind = getattr(self_bt, gate.indicator, None)
                    if ind is None:
                        continue
                    raw = float(ind[-1])
                    if not np.isnan(raw) and raw > 0:
                        # Pattern fired this bar — reset countdown
                        state["gate_countdown"][gate.indicator] = gate.active_for_bars
                    elif state["gate_countdown"].get(gate.indicator, 0) > 0:
                        # Pattern fired on a previous bar — keep synthetic value alive
                        state["gate_countdown"][gate.indicator] -= 1
                    # (if countdown == 0 and raw == 0, signal naturally expires)

            # --- Suppression gates: block entries when an indecision/reversal pattern fires ---
            if definition.suppression_gates:
                for sgate in definition.suppression_gates:
                    # Decrement first, then check if pattern fired this bar
                    if state["suppression_countdown"].get(sgate.indicator, 0) > 0:
                        state["suppression_countdown"][sgate.indicator] -= 1
                    ind = getattr(self_bt, sgate.indicator, None)
                    if ind is None:
                        continue
                    raw = float(ind[-1])
                    if not np.isnan(raw) and raw > sgate.threshold:
                        state["suppression_countdown"][sgate.indicator] = sgate.suppress_for_bars

            suppression_active = any(
                state["suppression_countdown"].get(sg.indicator, 0) > 0
                for sg in definition.suppression_gates
            )

            # --- Trigger holds: keep crosses_above/crosses_below active for N bars ---
            if definition.trigger_holds:
                for hold in definition.trigger_holds:
                    # Decrement first, then check if cross fired this bar
                    if state["trigger_hold_countdown"].get(hold.indicator, 0) > 0:
                        state["trigger_hold_countdown"][hold.indicator] -= 1
                    if _check_hold_trigger_fired(self_bt, hold.indicator, definition.entry_rules):
                        state["trigger_hold_countdown"][hold.indicator] = hold.hold_for_bars

            # --- Pattern groups: sum gate-adjusted scores for each group ---
            group_values: dict[str, float] = {}
            for grp in definition.pattern_groups:
                total = 0.0
                for pname in grp.patterns:
                    ind = getattr(self_bt, pname, None)
                    if ind is None:
                        continue
                    val = float(ind[-1])
                    # apply gate: if indicator is under an active countdown, treat as 1.0
                    if np.isnan(val) or val == 0.0:
                        if state["gate_countdown"].get(pname, 0) > 0:
                            val = 1.0
                        elif np.isnan(val):
                            val = 0.0
                    total += val
                group_values[grp.name] = total

            # --- Pattern-score sizing: capture pattern score for entry sizing ---
            state["pattern_score"] = 0.0
            if pm.risk_pct_min is not None and pm.risk_pct_max is not None:
                if pm.risk_pct_group is not None:
                    # Use named PatternGroup sum as sizing source (capped at 1.0)
                    state["pattern_score"] = min(group_values.get(pm.risk_pct_group, 0.0), 1.0)
                else:
                    # Fallback: max of individual indicator scores in (0, 1]
                    for ind_def in definition.indicators:
                        ind = getattr(self_bt, ind_def.name, None)
                        if ind is None:
                            continue
                        val = float(ind[-1])
                        if not np.isnan(val) and 0.0 < val <= 1.0:
                            state["pattern_score"] = max(state["pattern_score"], val)

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
                        _reset_entry_anchored_vwap_state(state)
                    return

            if not self_bt.position:  # type: ignore[attr-defined]
                # Detect trade-just-closed (e.g. SL hit internally)
                if state["in_trade"]:
                    state["in_trade"] = False
                    state["direction"] = None
                    state["scaled_out"] = False
                    state["bars_in_trade"] = 0
                    state["initial_sl_dist"] = None
                    _reset_entry_anchored_vwap_state(state)

                # --- Long entry ---
                if (
                    not suppression_active
                    and _evaluate_rules(
                        self_bt, definition.entry_rules,
                        state["gate_countdown"], group_values,
                        state["trigger_hold_countdown"],
                    )
                ):
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
                    _reset_entry_anchored_vwap_state(state)

                    trade_size = _compute_trade_size(pm, price, sl, float(self_bt.equity), state["pattern_score"])  # type: ignore[attr-defined]
                    self_bt.buy(size=trade_size, sl=sl, tp=tp)  # type: ignore[attr-defined]

                # --- Short entry (only when no long fired this bar) ---
                elif (
                    not suppression_active
                    and definition.entry_rules_short
                    and _evaluate_rules(
                        self_bt, definition.entry_rules_short,
                        state["gate_countdown"], group_values,
                        state["trigger_hold_countdown"],
                    )
                ):
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
                    _reset_entry_anchored_vwap_state(state)

                    trade_size = _compute_trade_size(pm, price, sl_short, float(self_bt.equity), state["pattern_score"])  # type: ignore[attr-defined]
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

                if pm.entry_anchored_vwap_exit is not None:
                    state["entry_avwap_prev_value"] = state["entry_avwap_value"]
                    state["entry_avwap_value"] = _update_entry_anchored_vwap(
                        self_bt,
                        state,
                        pm.entry_anchored_vwap_exit,
                    )

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

                # --- Dynamic exit: VWAP anchored at trade-open ---
                if _entry_anchored_vwap_exit_triggered(
                    self_bt,
                    pm.entry_anchored_vwap_exit,
                    state["entry_avwap_prev_value"],
                    state["entry_avwap_value"],
                    is_short,
                ):
                    self_bt.position.close()  # type: ignore[attr-defined]
                    return

                # --- Rule-based exit ---
                exit_rules = (
                    definition.exit_rules_short
                    if (is_short and definition.exit_rules_short)
                    else definition.exit_rules
                )
                if _evaluate_rules(self_bt, exit_rules, state["gate_countdown"], group_values):
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
    pattern_score: float = 0.0,
) -> float:
    """Compute position size to pass to Strategy.buy().

    Risk-based sizing (when ``pm.risk_pct`` is set and a SL is defined):
      - ``units = (equity × risk_pct) / sl_distance``
      - Returns an integer-like float representing units of the instrument.

    Pattern-score sizing (when ``pm.risk_pct_min`` and ``pm.risk_pct_max`` are set):
      - ``effective_risk = risk_pct_min + score × (risk_pct_max - risk_pct_min)``
      - Overrides ``pm.risk_pct`` when a pattern score is available.

    Fallback (no risk_pct / no SL):
      - Returns ``pm.size`` as a fractional equity allocation.
    """
    # Resolve effective risk_pct: pattern-score interpolation takes priority
    effective_risk: float | None = pm.risk_pct
    if pm.risk_pct_min is not None and pm.risk_pct_max is not None and 0.0 <= pattern_score <= 1.0:
        effective_risk = pm.risk_pct_min + pattern_score * (pm.risk_pct_max - pm.risk_pct_min)

    if effective_risk is not None and sl is not None:
        sl_distance = abs(price - sl)
        if sl_distance > 0:
            units = (equity * effective_risk) / sl_distance
            return max(1, round(units))
    return pm.size


def _reset_entry_anchored_vwap_state(state: dict[str, Any]) -> None:
    """Reset runtime VWAP state tied to the active trade."""
    state["entry_avwap_weight_sum"] = 0.0
    state["entry_avwap_weighted_price_sum"] = 0.0
    state["entry_avwap_prev_value"] = np.nan
    state["entry_avwap_value"] = np.nan


def _resolve_runtime_price_source(
    open_: float,
    high: float,
    low: float,
    close: float,
    price_source: str,
) -> float:
    """Resolve the current-bar price used for runtime AVWAP."""
    if price_source == "hlc3":
        return (high + low + close) / 3.0
    if price_source == "close":
        return close
    raise ValueError(f"Unsupported runtime AVWAP price_source '{price_source}'")


def _update_entry_anchored_vwap(
    strategy: Strategy,  # type: ignore[type-arg]
    state: dict[str, Any],
    cfg: EntryAnchoredVwapExit,
) -> float:
    """Update and return entry-anchored VWAP for the current open trade."""
    open_ = float(strategy.data.Open[-1])   # type: ignore[attr-defined]
    high = float(strategy.data.High[-1])    # type: ignore[attr-defined]
    low = float(strategy.data.Low[-1])      # type: ignore[attr-defined]
    close = float(strategy.data.Close[-1])  # type: ignore[attr-defined]
    volume = max(float(strategy.data.Volume[-1]), 0.0)  # type: ignore[attr-defined]

    if volume <= 0.0:
        return float(state["entry_avwap_value"])

    price = _resolve_runtime_price_source(open_, high, low, close, cfg.price_source)
    state["entry_avwap_weight_sum"] += volume
    state["entry_avwap_weighted_price_sum"] += price * volume
    return state["entry_avwap_weighted_price_sum"] / state["entry_avwap_weight_sum"]


def _entry_anchored_vwap_exit_triggered(
    strategy: Strategy,  # type: ignore[type-arg]
    cfg: EntryAnchoredVwapExit | None,
    prev_avwap: float,
    current_avwap: float,
    is_short: bool,
) -> bool:
    """Return True when price crosses the runtime entry-anchored VWAP exit line."""
    if cfg is None or np.isnan(prev_avwap) or np.isnan(current_avwap):
        return False
    if len(strategy.data.Close) < 2:  # type: ignore[attr-defined]
        return False

    prev_close = float(strategy.data.Close[-2])  # type: ignore[attr-defined]
    current_close = float(strategy.data.Close[-1])  # type: ignore[attr-defined]

    if is_short:
        return current_close > current_avwap and prev_close <= prev_avwap
    return current_close < current_avwap and prev_close >= prev_avwap


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


def _check_hold_trigger_fired(
    strategy: Strategy,  # type: ignore[type-arg]
    indicator: str,
    entry_rules: list[RuleDef],
) -> bool:
    """Return True if a crosses_above/crosses_below rule for *indicator* fired this bar.

    Used by the TriggerHold mechanism to reset the hold countdown when the cross is
    detected, regardless of whether other entry conditions are met.
    """
    ind = getattr(strategy, indicator, None)
    if ind is None or len(ind) < 2:
        return False
    for rule in entry_rules:
        if rule.indicator != indicator:
            continue
        if rule.condition == "crosses_above":
            if rule.compare_to is not None:
                other = getattr(strategy, rule.compare_to, None)
                if other is None or len(other) < 2:
                    continue
                if float(ind[-1]) > float(other[-1]) and float(ind[-2]) <= float(other[-2]):
                    return True
            elif rule.value is not None:
                if float(ind[-1]) > rule.value and float(ind[-2]) <= rule.value:
                    return True
        elif rule.condition == "crosses_below":
            if rule.compare_to is not None:
                other = getattr(strategy, rule.compare_to, None)
                if other is None or len(other) < 2:
                    continue
                if float(ind[-1]) < float(other[-1]) and float(ind[-2]) >= float(other[-2]):
                    return True
            elif rule.value is not None:
                if float(ind[-1]) < rule.value and float(ind[-2]) >= rule.value:
                    return True
    return False


def _evaluate_rules(
    strategy: Strategy,  # type: ignore[type-arg]
    rules: list[RuleDef],
    gate_countdown: dict[str, int] | None = None,
    group_values: dict[str, float] | None = None,
    trigger_hold_countdown: dict[str, int] | None = None,
) -> bool:
    """Evaluate all rules (AND logic). Returns True if all pass.

    gate_countdown:        pattern signals stay active for N bars after firing.
    group_values:          pre-computed PatternGroup sums (resolved when indicator not found).
    trigger_hold_countdown: crosses_above/crosses_below conditions stay active for N bars.
    """
    if not rules:
        return False
    for rule in rules:
        # --- Trigger hold: if a cross condition has an active hold, treat it as True ---
        if (
            trigger_hold_countdown
            and trigger_hold_countdown.get(rule.indicator, 0) > 0
            and rule.condition in ("crosses_above", "crosses_below")
        ):
            continue  # condition passes — hold still active

        ind = getattr(strategy, rule.indicator, None)
        if ind is None:
            # Not a real indicator — check pattern groups
            if group_values and rule.indicator in group_values:
                current = group_values[rule.indicator]
            else:
                logger.warning("Indicator '%s' not found on strategy", rule.indicator)
                return False
        else:
            current = float(ind[-1])
            # Signal gate: if indicator countdown > 0, treat 0.0/NaN as still active
            if gate_countdown and gate_countdown.get(rule.indicator, 0) > 0:
                if np.isnan(current) or current == 0.0:
                    current = 1.0
            elif np.isnan(current):
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
        if rule.compare_to_multiplier is not None:
            target *= rule.compare_to_multiplier
        if rule.compare_to_offset is not None:
            target += rule.compare_to_offset
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
