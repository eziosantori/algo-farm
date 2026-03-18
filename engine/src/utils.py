"""Utility functions: logging setup and OHLCV data loading."""
from __future__ import annotations

import logging
import os
import sys

import pandas as pd


def setup_logging(level: str = "INFO") -> None:
    """Configure logging to stderr only (stdout is reserved for JSONL)."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        stream=sys.stderr,
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        force=True,
    )


def load_ohlcv(
    data_dir: str,
    instrument: str,
    timeframe: str,
    date_from: str | None = None,
    date_to: str | None = None,
) -> pd.DataFrame:
    """Load OHLCV data from a Parquet file with optional date-range filtering.

    Expected path: <data_dir>/<instrument>/<timeframe>.parquet
    Returns DataFrame with columns: Open, High, Low, Close, Volume (datetime index).

    Args:
        date_from: ISO date string (YYYY-MM-DD). Bars before this date are dropped.
        date_to:   ISO date string (YYYY-MM-DD). Bars after  this date are dropped.
                   Both bounds are inclusive (end-of-day for date_to).
    """
    path = os.path.join(data_dir, instrument, f"{timeframe}.parquet")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Data file not found: {path}")
    df = pd.read_parquet(path)
    # Normalise column names to title case
    df.columns = [c.capitalize() for c in df.columns]
    required = {"Open", "High", "Low", "Close"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing columns in {path}: {missing}")
    if "Volume" not in df.columns:
        df["Volume"] = 0
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)
    if date_from:
        df = df[df.index >= pd.Timestamp(date_from)]
    if date_to:
        # inclusive upper bound: keep all bars up to end-of-day on date_to
        df = df[df.index < pd.Timestamp(date_to) + pd.Timedelta(days=1)]
    return df
