"""Dukascopy data downloader via dukascopy-node CLI.

Uses `npx dukascopy-node` as a subprocess (same approach as cbot-farm) so that
ALL asset classes are supported: forex, metals, energies, commodities, and
equity indices (S&P 500, DAX, FTSE …).

Canonical Parquet path: <data_dir>/<INSTRUMENT>/<TIMEFRAME>.parquet
Columns stored: Open, High, Low, Close, Volume  (title-case, timezone-naive datetime index)

Incremental mode: if a Parquet file already exists, only bars after the last
cached timestamp are fetched and merged in before re-saving.

Prerequisites
-------------
  Node.js / npx must be available in PATH.
  dukascopy-node is installed on demand via npx (no global install required).
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import tempfile
import time
from datetime import datetime, timezone

import pandas as pd

from src.data.instruments import resolve_instrument, resolve_timeframe

logger = logging.getLogger(__name__)

# dukascopy-node CLI output file name pattern:
# <instrument>-<timeframe>-bid-<from>-<to>.json
_FILE_PATTERN = "{instrument}-{timeframe}-bid-{date_from}-{date_to}.json"


class DukascopyDownloader:
    """Download and cache OHLCV data using the dukascopy-node CLI."""

    def __init__(
        self,
        data_dir: str,
        price_type: str = "bid",
        batch_pause_ms: int = 1000,
        retries: int = 2,
        npx_cmd: str = "npx",
    ) -> None:
        """
        Parameters
        ----------
        data_dir      : Root directory for Parquet cache.
        price_type    : "bid" (default) or "ask".
        batch_pause_ms: Pause between dukascopy-node batch requests (ms).
        retries       : Number of download retries on failure.
        npx_cmd       : Path/name of the npx executable.
        """
        self.data_dir = data_dir
        self.price_type = price_type
        self.batch_pause_ms = batch_pause_ms
        self.retries = retries
        self.npx_cmd = npx_cmd

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download(
        self,
        instrument: str,
        timeframe: str,
        start: datetime,
        end: datetime,
        force: bool = False,
    ) -> pd.DataFrame:
        """Fetch candles for *instrument/timeframe* between *start* and *end*.

        Incremental: if a cached Parquet already exists and *force* is False,
        only bars after the last cached bar are fetched and merged.

        Returns the complete (merged) DataFrame.
        """
        parquet_path = self._parquet_path(instrument, timeframe)
        existing = self._load_existing(parquet_path)

        fetch_start = _ensure_utc(start)
        fetch_end   = _ensure_utc(end)

        if existing is not None and not force:
            last_ts = existing.index.max()
            if last_ts.tz_localize(None) >= fetch_end.replace(tzinfo=None):
                logger.info(
                    "%s/%s already cached up to %s — skipping",
                    instrument, timeframe, last_ts.date(),
                )
                return existing
            fetch_start = last_ts.replace(tzinfo=timezone.utc)
            logger.info(
                "%s/%s cached to %s; fetching forward to %s",
                instrument, timeframe, last_ts.date(), fetch_end.date(),
            )
        else:
            logger.info(
                "Fetching %s/%s  %s → %s",
                instrument, timeframe, fetch_start.date(), fetch_end.date(),
            )

        raw = self._fetch_via_node(instrument, timeframe, fetch_start, fetch_end)

        if raw is None or raw.empty:
            logger.warning("%s/%s: no data returned", instrument, timeframe)
            return existing if existing is not None else pd.DataFrame()

        if existing is not None and not force:
            combined = pd.concat([existing, raw])
            combined = combined[~combined.index.duplicated(keep="last")]
            combined.sort_index(inplace=True)
        else:
            combined = raw

        os.makedirs(os.path.dirname(parquet_path), exist_ok=True)
        combined.to_parquet(parquet_path)
        logger.info(
            "%s/%s → %s  (%d bars, %s → %s)",
            instrument, timeframe, parquet_path, len(combined),
            combined.index.min().date(), combined.index.max().date(),
        )
        return combined

    def download_many(
        self,
        instruments: list[str],
        timeframes: list[str],
        start: datetime,
        end: datetime,
        force: bool = False,
        on_progress: "callable[[str, str, int, int], None] | None" = None,
    ) -> dict[tuple[str, str], pd.DataFrame]:
        """Download all instrument × timeframe combinations."""
        combos = [(i, t) for i in instruments for t in timeframes]
        total  = len(combos)
        results: dict[tuple[str, str], pd.DataFrame] = {}

        for idx, (instrument, timeframe) in enumerate(combos, 1):
            if on_progress:
                on_progress(instrument, timeframe, idx, total)
            try:
                df = self.download(instrument, timeframe, start, end, force=force)
                results[(instrument, timeframe)] = df
            except Exception as exc:
                logger.error("Failed %s/%s: %s", instrument, timeframe, exc)

        return results

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fetch_via_node(
        self,
        instrument: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame | None:
        """Call dukascopy-node, parse JSON output, return DataFrame or None."""
        feed_id = resolve_instrument(instrument)
        dk_tf   = resolve_timeframe(timeframe)
        date_from = start.strftime("%Y-%m-%d")
        date_to   = end.strftime("%Y-%m-%d")

        with tempfile.TemporaryDirectory() as tmpdir:
            cmd = [
                self.npx_cmd, "dukascopy-node",
                "-i",   feed_id,
                "-from", date_from,
                "-to",   date_to,
                "-t",    dk_tf,
                "-p",    self.price_type,
                "-f",    "json",
                "-v",                           # include volumes
                "-in",                          # inline / compact output
                "-s",                           # silent header
                "-dir",  tmpdir,
                "-bp",   str(self.batch_pause_ms),
                "-r",    str(self.retries),
            ]

            logger.debug("CMD: %s", " ".join(cmd))

            try:
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
            except FileNotFoundError:
                raise RuntimeError(
                    f"'{self.npx_cmd}' not found — install Node.js and ensure npx is in PATH"
                )
            except subprocess.TimeoutExpired:
                raise RuntimeError(f"dukascopy-node timed out for {instrument}/{timeframe}")

            if proc.returncode != 0:
                raise RuntimeError(
                    f"dukascopy-node failed for {instrument}/{timeframe}:\n"
                    f"{(proc.stderr or proc.stdout).strip()[-500:]}"
                )

            # Find the generated JSON file
            json_files = sorted(
                [f for f in os.listdir(tmpdir) if f.endswith(".json")],
                key=lambda f: os.path.getmtime(os.path.join(tmpdir, f)),
            )
            if not json_files:
                logger.warning("No JSON file produced for %s/%s", instrument, timeframe)
                return None

            json_path = os.path.join(tmpdir, json_files[-1])
            return _parse_json_to_df(json_path)

    def _parquet_path(self, instrument: str, timeframe: str) -> str:
        return os.path.join(
            self.data_dir,
            instrument.upper(),
            f"{timeframe.upper()}.parquet",
        )

    def _load_existing(self, path: str) -> pd.DataFrame | None:
        if not os.path.exists(path):
            return None
        df = pd.read_parquet(path)
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        elif df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_json_to_df(json_path: str) -> pd.DataFrame:
    """Parse dukascopy-node JSON output to a OHLCV DataFrame."""
    with open(json_path, encoding="utf-8") as fh:
        rows = json.load(fh)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
    df = df.set_index("timestamp")
    df.index.name = "datetime"

    # Normalise column names to title-case (Open, High, Low, Close, Volume)
    df.columns = [c.capitalize() for c in df.columns]

    # Ensure Volume column exists
    if "Volume" not in df.columns:
        df["Volume"] = 0.0

    return df


def _ensure_utc(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
