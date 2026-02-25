"""Shared pytest fixtures."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.storage.db import init_db


@pytest.fixture()
def synthetic_ohlcv() -> pd.DataFrame:
    """500-bar synthetic OHLCV DataFrame."""
    rng = np.random.default_rng(42)
    n = 500
    close = 1.1 + np.cumsum(rng.normal(0, 0.0003, n))
    high = close + np.abs(rng.normal(0.001, 0.0005, n))
    low = close - np.abs(rng.normal(0.001, 0.0005, n))
    open_p = np.roll(close, 1)
    open_p[0] = close[0]
    volume = rng.integers(1000, 9000, n).astype(float)
    dates = pd.date_range("2020-01-01", periods=n, freq="h")
    df = pd.DataFrame(
        {"Open": open_p, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=dates,
    )
    df["High"] = df[["Open", "High", "Close"]].max(axis=1)
    df["Low"] = df[["Open", "Low", "Close"]].min(axis=1)
    return df


@pytest.fixture()
def in_memory_db() -> sqlite3.Connection:
    """In-memory SQLite DB with all tables created."""
    conn = init_db(":memory:")
    yield conn  # type: ignore[misc]
    conn.close()


@pytest.fixture()
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
