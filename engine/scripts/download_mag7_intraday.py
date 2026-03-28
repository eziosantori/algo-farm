#!/usr/bin/env python
"""Download M5 and M15 data for all MAG7 stocks from 2022 to today.

Uses quarterly chunking to stay well under the 300-second subprocess
timeout that dukascopy-node imposes per call.

Each quarter × instrument × timeframe combination is one subprocess call
(≤ 3 monthly HTTP requests, ~4,900 M5 bars/quarter), keeping runtime
safely below the timeout limit.

Usage
-----
# Full download (from engine/ directory):
python scripts/download_mag7_intraday.py

# Preview what would be downloaded without actually running it:
python scripts/download_mag7_intraday.py --dry-run

# Specific year range:
python scripts/download_mag7_intraday.py --from-year 2024 --to-year 2024

# Custom data directory:
python scripts/download_mag7_intraday.py --data-dir /path/to/data
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone, date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap — allow running from engine/ or repo root
# ---------------------------------------------------------------------------
_ENGINE_DIR = Path(__file__).resolve().parents[1]
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

from src.data.downloader import DukascopyDownloader
from src.utils import setup_logging

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MAG7 = ["AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA"]
TIMEFRAMES = ["M5", "M15"]

DEFAULT_FROM_YEAR = 2022
DEFAULT_DATA_DIR = str(_ENGINE_DIR / "data")

# 2 seconds between batch chunks — more conservative than the default 1s
BATCH_PAUSE_MS = 2000

# Pause between instrument downloads to avoid rate-limiting (seconds)
INTER_DOWNLOAD_PAUSE = 3.0

# Quarter boundaries (month, day) — one subprocess call per quarter keeps
# M5 data well under the 300-second dukascopy-node timeout.
_QUARTERS: list[tuple[int, int]] = [(1, 1), (4, 1), (7, 1), (10, 1)]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _quarter_ranges(from_year: int, to_year: int) -> list[tuple[date, date]]:
    """Return quarterly (start, end) date pairs covering from_year → to_year.

    Each quarter is a separate subprocess call so M5 data (~4900 bars/quarter)
    stays well under the 300-second dukascopy-node timeout.
    """
    today = date.today()
    pairs: list[tuple[date, date]] = []

    for y in range(from_year, to_year + 1):
        for qi, (qm, qd) in enumerate(_QUARTERS):
            start = date(y, qm, qd)
            if start > today:
                break
            # End = day before next quarter start (or Dec 31 for Q4)
            if qi + 1 < len(_QUARTERS):
                nm, nd = _QUARTERS[qi + 1]
                end_raw = date(y, nm, nd) - timedelta(days=1)
            else:
                end_raw = date(y, 12, 31)
            end = min(end_raw, today)
            pairs.append((start, end))

    return pairs


def _to_dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def _summarise(data_dir: str) -> None:
    """Print a table of downloaded files with bar counts and date ranges."""
    import pandas as pd

    root = Path(data_dir)
    header = f"{'Symbol':<8}  {'TF':<4}  {'Bars':>7}  {'From':<12}  {'To':<12}"
    print()
    print("=" * len(header))
    print("Final summary")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for sym in MAG7:
        for tf in TIMEFRAMES:
            p = root / sym / f"{tf}.parquet"
            if p.exists():
                df = pd.read_parquet(p)
                print(
                    f"{sym:<8}  {tf:<4}  {len(df):>7}  "
                    f"{df.index.min().date()}  {df.index.max().date()}"
                )
            else:
                print(f"{sym:<8}  {tf:<4}  {'MISSING':>7}")
    print("=" * len(header))


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Download MAG7 intraday (M5/M15) data from Dukascopy, year by year.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--from-year", type=int, default=DEFAULT_FROM_YEAR,
        help=f"First year to download (default: {DEFAULT_FROM_YEAR})",
    )
    parser.add_argument(
        "--to-year", type=int, default=datetime.now().year,
        help="Last year to download (default: current year)",
    )
    parser.add_argument(
        "--data-dir", default=DEFAULT_DATA_DIR,
        help=f"Root directory for Parquet cache (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be downloaded without actually doing it",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    setup_logging(args.log_level)

    years = _quarter_ranges(args.from_year, args.to_year)
    total_combos = len(MAG7) * len(TIMEFRAMES) * len(years)

    print(f"MAG7 intraday download plan")
    print(f"  Instruments : {', '.join(MAG7)}")
    print(f"  Timeframes  : {', '.join(TIMEFRAMES)}")
    print(f"  Years       : {args.from_year} → {args.to_year}")
    print(f"  Data dir    : {args.data_dir}")
    print(f"  Dry run     : {args.dry_run}")
    print(f"  Total calls : {total_combos} (instrument × timeframe × year)")
    print()

    if args.dry_run:
        for sym in MAG7:
            for tf in TIMEFRAMES:
                for (start, end) in years:
                    print(f"  [DRY-RUN] {sym}/{tf}  {start} → {end}")
        return 0

    downloader = DukascopyDownloader(
        data_dir=args.data_dir,
        batch_pause_ms=BATCH_PAUSE_MS,
        retries=3,
    )

    done = 0
    errors: list[str] = []

    for sym in MAG7:
        for tf in TIMEFRAMES:
            for (start, end) in years:
                done += 1
                label = f"[{done}/{total_combos}] {sym}/{tf}  {start} → {end}"
                print(label, flush=True)

                try:
                    df = downloader.download(
                        instrument=sym,
                        timeframe=tf,
                        start=_to_dt(start),
                        end=_to_dt(end),
                    )
                    if df is not None and not df.empty:
                        print(
                            f"  ✓  {len(df)} bars cached  "
                            f"(file range: {df.index.min().date()} → {df.index.max().date()})"
                        )
                    else:
                        print(f"  ⚠  No data returned (market may be closed in this range)")
                except Exception as exc:
                    msg = f"  ✗  FAILED: {exc}"
                    print(msg)
                    logger.error("Failed %s/%s %s→%s: %s", sym, tf, start, end, exc)
                    errors.append(f"{sym}/{tf} {start}→{end}: {exc}")

                if done < total_combos:
                    time.sleep(INTER_DOWNLOAD_PAUSE)

    _summarise(args.data_dir)

    if errors:
        print(f"\n{len(errors)} error(s) occurred:")
        for e in errors:
            print(f"  • {e}")
        return 1

    print("\nAll downloads completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
