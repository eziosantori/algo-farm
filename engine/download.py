#!/usr/bin/env python
"""algo-farm data downloader — fetches OHLCV candles from Dukascopy via dukascopy-node.

Requires Node.js / npx in PATH.  dukascopy-node is pulled via npx automatically.

Examples
--------
# Download H1 + M15 + M30 for forex + gold + indices
python download.py \\
    --instruments EURUSD GBPUSD XAUUSD US500 GER40 \\
    --timeframes H1 M15 M30 D1 \\
    --from 2022-01-01 --to 2024-12-31 \\
    --data-dir ./data

# List available instruments and timeframes
python download.py --list-instruments

# Incremental update (only fetches missing bars)
python download.py --instruments EURUSD XAUUSD US500 \\
    --timeframes H1 --from 2022-01-01 --to 2024-12-31 --data-dir ./data

# Force full re-download
python download.py --instruments EURUSD --timeframes D1 \\
    --from 2020-01-01 --to 2024-12-31 --data-dir ./data --force
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone

from src.utils import setup_logging
from src.data.instruments import list_instruments, TIMEFRAMES
from src.data.downloader import DukascopyDownloader

DEFAULT_DATA_DIR = "./data"


def _parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="algo-farm-download",
        description="Download OHLCV data from Dukascopy free feed and cache as Parquet.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    p.add_argument(
        "--instruments", nargs="+", metavar="SYM",
        help="Canonical symbols to download (e.g. EURUSD XAUUSD BRENT).",
    )
    p.add_argument(
        "--timeframes", nargs="+", metavar="TF",
        help=f"Timeframes to download. Available: {', '.join(TIMEFRAMES)}",
    )
    p.add_argument("--from", dest="start", metavar="YYYY-MM-DD", help="Start date (inclusive).")
    p.add_argument("--to",   dest="end",   metavar="YYYY-MM-DD", help="End date (inclusive).")
    p.add_argument(
        "--data-dir", default=DEFAULT_DATA_DIR, metavar="DIR",
        help=f"Root directory for Parquet cache (default: {DEFAULT_DATA_DIR}).",
    )
    p.add_argument("--offer-side", choices=["BID", "ASK"], default="BID")
    p.add_argument("--force", action="store_true", help="Re-download even if cache exists.")
    p.add_argument("--list-instruments", action="store_true", help="Print available instruments and exit.")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p


def _print_instruments() -> None:
    instruments = list_instruments()
    col_w = [10, 20, 40]
    header = f"{'Symbol':<{col_w[0]}}  {'Feed ID':<{col_w[1]}}  {'Description'}"
    print(header)
    print("-" * (sum(col_w) + 4))
    for row in instruments:
        print(f"{row['symbol']:<{col_w[0]}}  {row['feed']:<{col_w[1]}}  {row['description']}")


def _progress_callback(instrument: str, timeframe: str, done: int, total: int) -> None:
    print(f"[{done}/{total}] {instrument}/{timeframe} ...", flush=True)


def main() -> int:
    parser = _build_parser()
    args   = parser.parse_args()

    setup_logging(args.log_level)

    if args.list_instruments:
        _print_instruments()
        return 0

    # Validate required args for download mode
    missing = []
    if not args.instruments: missing.append("--instruments")
    if not args.timeframes:  missing.append("--timeframes")
    if not args.start:       missing.append("--from")
    if not args.end:         missing.append("--to")
    if missing:
        parser.error(f"Missing required arguments: {', '.join(missing)}")

    start = _parse_date(args.start)
    end   = _parse_date(args.end)

    if start >= end:
        parser.error("--from must be earlier than --to")

    downloader = DukascopyDownloader(
        data_dir=args.data_dir,
        price_type=args.offer_side.lower(),
    )

    print(
        f"Downloading {len(args.instruments)} instrument(s) × "
        f"{len(args.timeframes)} timeframe(s)  "
        f"[{args.start} → {args.end}]  →  {args.data_dir}"
    )

    results = downloader.download_many(
        instruments=args.instruments,
        timeframes=args.timeframes,
        start=start,
        end=end,
        force=args.force,
        on_progress=_progress_callback,
    )

    # Summary table
    ok     = {k: v for k, v in results.items() if not v.empty}
    failed = len(results) - len(ok)
    print()
    print(f"{'Instrument':<10}  {'TF':<5}  {'Bars':>7}  {'From':<12}  {'To':<12}")
    print("-" * 55)
    for (instrument, tf), df in sorted(ok.items()):
        print(
            f"{instrument:<10}  {tf:<5}  {len(df):>7}  "
            f"{df.index.min().date()!s:<12}  {df.index.max().date()!s:<12}"
        )
    if failed:
        print(f"\n{failed} download(s) failed — check logs above.")
    print(f"\nData saved to: {args.data_dir}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
