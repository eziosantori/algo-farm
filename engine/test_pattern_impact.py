"""Test impact of candlestick patterns on EMA Cross strategy.

Runs baseline (EMA cross only) vs pattern-enhanced (EMA cross + Hammer/Shooting Star)
on stocks and indices to measure performance improvement.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from src.backtest.runner import BacktestRunner
from src.models import StrategyDefinition
from src.utils import load_ohlcv

# Test instruments and timeframes
INSTRUMENTS = ["NVDA", "TSLA", "MSFT", "AAPL", "META", "GOOGL", "AMZN", "NAS100", "US500"]
TIMEFRAMES = ["D1", "H1"]

# Strategies to compare
STRATEGIES = {
    "baseline": "strategies/draft/ema_cross_baseline.json",
    "with_patterns": "strategies/draft/ema_cross_hammer_filter.json",
}

DATA_DIR = "data"


def load_strategy_definition(path: str) -> StrategyDefinition:
    """Load and validate strategy JSON as StrategyDefinition."""
    with open(path, "r") as f:
        data = json.load(f)
    return StrategyDefinition.model_validate(data)


def run_backtest(strategy_name: str, definition: StrategyDefinition, instrument: str, timeframe: str) -> dict:
    """Run backtest and return metrics."""
    print(f"  Running {strategy_name} on {instrument} {timeframe}...", flush=True)
    
    try:
        # Load OHLCV data
        ohlcv = load_ohlcv(DATA_DIR, instrument, timeframe)
        
        # Run backtest with empty params (use defaults from strategy)
        runner = BacktestRunner()
        result = runner.run(ohlcv, definition, params={})
        
        # Extract key metrics from BacktestMetrics
        metrics_obj = result.metrics
        metrics = {
            "sharpe": metrics_obj.sharpe_ratio,
            "return_pct": metrics_obj.total_return_pct,
            "win_rate_pct": metrics_obj.win_rate_pct,
            "num_trades": metrics_obj.total_trades,
            "max_dd_pct": metrics_obj.max_drawdown_pct,
        }
        return metrics
    
    except Exception as e:
        print(f"    ✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return {
            "sharpe": None,
            "return_pct": None,
            "win_rate_pct": None,
            "num_trades": None,
            "max_dd_pct": None,
        }


def main() -> None:
    print("=" * 80)
    print("PATTERN IMPACT TEST: EMA Cross Baseline vs Pattern-Enhanced")
    print("=" * 80)
    print()
    
    # Load strategies as StrategyDefinition objects
    strategies = {}
    for name, path in STRATEGIES.items():
        print(f"Loading {name} from {path}...")
        strategies[name] = load_strategy_definition(path)
    print()
    
    # Results storage
    results = []
    
    # Run backtests
    for instrument in INSTRUMENTS:
        for timeframe in TIMEFRAMES:
            print(f"\n{instrument} {timeframe}")
            print("-" * 40)
            
            row = {"instrument": instrument, "timeframe": timeframe}
            
            for strategy_name, definition in strategies.items():
                metrics = run_backtest(strategy_name, definition, instrument, timeframe)
                
                # Store with prefix
                for metric, value in metrics.items():
                    row[f"{strategy_name}_{metric}"] = value
                
                if metrics["sharpe"] is not None:
                    print(f"    {strategy_name}: Sharpe={metrics['sharpe']:.3f}, Return={metrics['return_pct']:.1f}%, WinRate={metrics['win_rate_pct']:.1f}%, Trades={metrics['num_trades']}")
            
            results.append(row)
    
    # Save results
    df = pd.DataFrame(results)
    output_path = "pattern_impact_results.csv"
    df.to_csv(output_path, index=False)
    print(f"\n✓ Results saved to {output_path}")
    
    # Summary comparison
    print("\n" + "=" * 80)
    print("SUMMARY: Pattern Impact")
    print("=" * 80)
    
    # Calculate average improvement
    valid = df[df["baseline_sharpe"].notna() & df["with_patterns_sharpe"].notna()]
    
    if len(valid) > 0:
        avg_sharpe_baseline = valid["baseline_sharpe"].mean()
        avg_sharpe_patterns = valid["with_patterns_sharpe"].mean()
        avg_return_baseline = valid["baseline_return_pct"].mean()
        avg_return_patterns = valid["with_patterns_return_pct"].mean()
        avg_wr_baseline = valid["baseline_win_rate_pct"].mean()
        avg_wr_patterns = valid["with_patterns_win_rate_pct"].mean()
        
        print(f"\nAverage Sharpe Ratio:")
        print(f"  Baseline:       {avg_sharpe_baseline:.3f}")
        print(f"  With Patterns:  {avg_sharpe_patterns:.3f}")
        print(f"  Improvement:    {(avg_sharpe_patterns - avg_sharpe_baseline):.3f} ({((avg_sharpe_patterns / avg_sharpe_baseline - 1) * 100):.1f}%)")
        
        print(f"\nAverage Return:")
        print(f"  Baseline:       {avg_return_baseline:.1f}%")
        print(f"  With Patterns:  {avg_return_patterns:.1f}%")
        print(f"  Improvement:    {(avg_return_patterns - avg_return_baseline):.1f}%")
        
        print(f"\nAverage Win Rate:")
        print(f"  Baseline:       {avg_wr_baseline:.1f}%")
        print(f"  With Patterns:  {avg_wr_patterns:.1f}%")
        print(f"  Improvement:    {(avg_wr_patterns - avg_wr_baseline):.1f}%")
        
        # Best performers
        print("\n" + "-" * 80)
        print("Top 5 Improvements (Sharpe):")
        print("-" * 80)
        valid["sharpe_improvement"] = valid["with_patterns_sharpe"] - valid["baseline_sharpe"]
        top5 = valid.nlargest(5, "sharpe_improvement")[["instrument", "timeframe", "baseline_sharpe", "with_patterns_sharpe", "sharpe_improvement"]]
        print(top5.to_string(index=False))
    else:
        print("\n⚠️  No valid results to compare.")


if __name__ == "__main__":
    main()
