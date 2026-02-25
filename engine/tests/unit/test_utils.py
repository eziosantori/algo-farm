"""Unit tests for src/utils.py."""
from __future__ import annotations

import logging
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.utils import load_ohlcv, setup_logging


def test_setup_logging_configures_root_logger() -> None:
    setup_logging("DEBUG")
    root = logging.getLogger()
    assert root.level == logging.DEBUG


def test_setup_logging_info_level() -> None:
    setup_logging("INFO")
    root = logging.getLogger()
    assert root.level == logging.INFO


def test_load_ohlcv_success(tmp_path: Path) -> None:
    instrument_dir = tmp_path / "EURUSD"
    instrument_dir.mkdir()
    df = pd.DataFrame(
        {
            "open": [1.1, 1.2],
            "high": [1.15, 1.25],
            "low": [1.05, 1.15],
            "close": [1.12, 1.22],
            "volume": [1000.0, 2000.0],
        },
        index=pd.date_range("2020-01-01", periods=2, freq="h"),
    )
    df.to_parquet(instrument_dir / "H1.parquet")
    result = load_ohlcv(str(tmp_path), "EURUSD", "H1")
    assert set(result.columns) >= {"Open", "High", "Low", "Close", "Volume"}
    assert len(result) == 2
    assert isinstance(result.index, pd.DatetimeIndex)


def test_load_ohlcv_file_not_found(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_ohlcv(str(tmp_path), "UNKNOWN", "H1")


def test_load_ohlcv_adds_volume_if_missing(tmp_path: Path) -> None:
    instrument_dir = tmp_path / "TEST"
    instrument_dir.mkdir()
    df = pd.DataFrame(
        {
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [1.05],
        },
        index=pd.date_range("2020-01-01", periods=1, freq="h"),
    )
    df.to_parquet(instrument_dir / "H1.parquet")
    result = load_ohlcv(str(tmp_path), "TEST", "H1")
    assert "Volume" in result.columns
    assert result["Volume"].iloc[0] == 0
