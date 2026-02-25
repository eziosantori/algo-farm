#!/usr/bin/env python3
"""Generate synthetic OHLCV Parquet fixtures for testing.

Run once: python tests/fixtures/generate_fixtures.py
Output: tests/fixtures/data_cache/EURUSD/{H1,D1}.parquet
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd


def generate_synthetic_ohlcv(
    n_bars: int = 500,
    seed: int = 42,
    base_price: float = 1.1000,
    pip_value: float = 0.0001,
) -> pd.DataFrame:
    """Generate realistic synthetic OHLCV data using sine wave + trend + noise."""
    rng = np.random.default_rng(seed)

    t = np.arange(n_bars)
    sine = np.sin(2 * np.pi * t / 50) * 0.005
    trend = t * 0.00001
    noise = rng.normal(0, pip_value * 3, n_bars)
    close = base_price + sine + trend + np.cumsum(noise * 0.3)

    # Generate OHLC from close
    bar_range = np.abs(rng.normal(pip_value * 10, pip_value * 5, n_bars)).clip(pip_value)
    high = close + bar_range * rng.uniform(0.3, 0.7, n_bars)
    low = close - bar_range * rng.uniform(0.3, 0.7, n_bars)
    open_price = np.roll(close, 1)
    open_price[0] = close[0] - bar_range[0] * 0.1
    volume = rng.integers(100, 10000, n_bars).astype(float)

    dates = pd.date_range("2020-01-01", periods=n_bars, freq="h")
    df = pd.DataFrame(
        {
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=dates,
    )
    # Ensure high >= close/open and low <= close/open
    df["high"] = df[["open", "high", "close"]].max(axis=1)
    df["low"] = df[["open", "low", "close"]].min(axis=1)
    return df


def generate_daily_ohlcv(n_bars: int = 500, seed: int = 99) -> pd.DataFrame:
    df = generate_synthetic_ohlcv(n_bars=n_bars, seed=seed)
    df.index = pd.date_range("2020-01-01", periods=n_bars, freq="D")
    return df


def main() -> None:
    base_dir = Path(__file__).parent / "data_cache" / "EURUSD"
    base_dir.mkdir(parents=True, exist_ok=True)

    h1 = generate_synthetic_ohlcv(n_bars=500, seed=42)
    h1.to_parquet(base_dir / "H1.parquet")
    print(f"Generated H1: {len(h1)} bars → {base_dir / 'H1.parquet'}")

    d1 = generate_daily_ohlcv(n_bars=500, seed=99)
    d1.to_parquet(base_dir / "D1.parquet")
    print(f"Generated D1: {len(d1)} bars → {base_dir / 'D1.parquet'}")


if __name__ == "__main__":
    main()
