"""Calculate backtest performance metrics from equity curve and trade list."""
from __future__ import annotations

import numpy as np

from src.models import BacktestMetrics


def calculate_metrics(
    equity_curve: np.ndarray,
    trades: list[dict[str, object]],
    bars_per_year: int = 252,
) -> BacktestMetrics:
    """Compute all 11 BacktestMetrics from equity curve and trade list."""
    if len(equity_curve) < 2:
        return _zero_metrics()

    initial = float(equity_curve[0])
    final = float(equity_curve[-1])

    # Total return
    total_return_pct = (final - initial) / initial * 100.0 if initial != 0 else 0.0

    # CAGR
    n_bars = len(equity_curve)
    years = n_bars / bars_per_year
    if initial > 0 and final > 0 and years > 0:
        cagr_pct = ((final / initial) ** (1.0 / years) - 1.0) * 100.0
    else:
        cagr_pct = 0.0

    # Max drawdown
    peak = np.maximum.accumulate(equity_curve)
    drawdowns = (equity_curve - peak) / np.where(peak != 0, peak, 1.0)
    max_drawdown_pct = float(np.min(drawdowns)) * 100.0  # negative value

    # Bar returns for Sharpe/Sortino
    bar_returns = np.diff(equity_curve) / np.where(equity_curve[:-1] != 0, equity_curve[:-1], 1.0)
    mean_ret = float(np.mean(bar_returns))
    std_ret = float(np.std(bar_returns, ddof=1)) if len(bar_returns) > 1 else 0.0

    sharpe_ratio = (mean_ret / std_ret * np.sqrt(bars_per_year)) if std_ret > 0 else 0.0

    negative_rets = bar_returns[bar_returns < 0]
    downside_std = float(np.std(negative_rets, ddof=1)) if len(negative_rets) > 1 else 0.0
    sortino_ratio = (mean_ret / downside_std * np.sqrt(bars_per_year)) if downside_std > 0 else 0.0

    # Calmar = CAGR / |max_drawdown|
    abs_dd = abs(max_drawdown_pct)
    calmar_ratio = (cagr_pct / abs_dd) if abs_dd > 0 else 0.0

    # Trade-level metrics
    total_trades = len(trades)
    if total_trades == 0:
        win_rate_pct = 0.0
        profit_factor = 0.0
        avg_trade_duration_bars = 0.0
        expectancy = 0.0
    else:
        pnls = [float(t.get("pnl", 0.0)) for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]

        win_rate_pct = len(wins) / total_trades * 100.0

        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0.0

        durations = [float(t.get("duration_bars", 0)) for t in trades]
        avg_trade_duration_bars = float(np.mean(durations)) if durations else 0.0

        expectancy = float(np.mean(pnls))

    return BacktestMetrics(
        total_return_pct=total_return_pct,
        sharpe_ratio=float(sharpe_ratio),
        sortino_ratio=float(sortino_ratio),
        calmar_ratio=float(calmar_ratio),
        max_drawdown_pct=max_drawdown_pct,
        win_rate_pct=win_rate_pct,
        profit_factor=profit_factor,
        total_trades=total_trades,
        avg_trade_duration_bars=avg_trade_duration_bars,
        cagr_pct=cagr_pct,
        expectancy=expectancy,
    )


def _zero_metrics() -> BacktestMetrics:
    return BacktestMetrics(
        total_return_pct=0.0,
        sharpe_ratio=0.0,
        sortino_ratio=0.0,
        calmar_ratio=0.0,
        max_drawdown_pct=0.0,
        win_rate_pct=0.0,
        profit_factor=0.0,
        total_trades=0,
        avg_trade_duration_bars=0.0,
        cagr_pct=0.0,
        expectancy=0.0,
    )
