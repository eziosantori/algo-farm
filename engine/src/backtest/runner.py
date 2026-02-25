"""BacktestRunner: orchestrates a single backtest run."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from backtesting import Backtest  # type: ignore[import-untyped]

from src.backtest.strategy import StrategyComposer
from src.metrics import calculate_metrics
from src.models import BacktestMetrics, StrategyDefinition


@dataclass
class RunResult:
    metrics: BacktestMetrics
    trades: list[dict[str, object]]
    equity_curve: list[float]


class BacktestRunner:
    def run(
        self,
        ohlcv: pd.DataFrame,
        definition: StrategyDefinition,
        params: dict[str, object],
    ) -> RunResult:
        strategy_cls = StrategyComposer().build_class(definition, params)
        bt = Backtest(ohlcv, strategy_cls, cash=10_000, commission=0.0002)
        stats = bt.run()
        trades = self._extract_trades(stats._trades)
        equity = stats._equity_curve["Equity"].tolist()
        metrics = calculate_metrics(np.array(equity, dtype=float), trades)
        return RunResult(metrics=metrics, trades=trades, equity_curve=equity)

    def _extract_trades(self, trades_df: pd.DataFrame) -> list[dict[str, object]]:
        if trades_df is None or len(trades_df) == 0:
            return []
        result: list[dict[str, object]] = []
        for _, row in trades_df.iterrows():
            entry_bar = int(row.get("EntryBar", 0))
            exit_bar = int(row.get("ExitBar", 0))
            result.append(
                {
                    "entry_bar": entry_bar,
                    "exit_bar": exit_bar,
                    "duration_bars": exit_bar - entry_bar,
                    "pnl": float(row.get("PnL", 0.0)),
                    "return_pct": float(row.get("ReturnPct", 0.0)),
                    "entry_price": float(row.get("EntryPrice", 0.0)),
                    "exit_price": float(row.get("ExitPrice", 0.0)),
                    "size": float(row.get("Size", 0.0)),
                }
            )
        return result
