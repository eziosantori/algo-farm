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


def load_ohlcv(data_dir: str, instrument: str, timeframe: str) -> pd.DataFrame:
    """Load OHLCV data from a Parquet file.

    Expected path: <data_dir>/<instrument>/<timeframe>.parquet
    Returns DataFrame with columns: Open, High, Low, Close, Volume (datetime index).
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
    return df
