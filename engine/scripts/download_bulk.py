#!/usr/bin/env python
"""Bulk Dukascopy data downloader with timeout-safe chunking.

``download.py`` (the main CLI) fetches a full date range in a single
dukascopy-node subprocess call, which works fine for H1/H4/D1 but hits the
300-second timeout for high-resolution timeframes (M5, M15) over multi-year
windows (~19,700 bars/year for M5).

This script splits the range into smaller **chunks** (quarterly by default)
so each subprocess call stays well under the timeout:

  Timeframe | Bars/quarter | Typical subprocess time
  ----------|--------------|-------------------------
  M5        | ~4,900       | ~35s  ✓
  M15       | ~1,640       | ~20s  ✓
  H1        | ~410         | ~10s  ✓

Use this script whenever you need to bulk-download multiple instruments or
timeframes covering more than 1 year for M5/M15, or more than 3 years for H1.

Named instrument groups (pass as --instruments value):

  MAG7          AAPL AMZN GOOGL META MSFT NVDA TSLA
  FOREX_MAJORS  EURUSD GBPUSD USDJPY USDCHF AUDUSD USDCAD NZDUSD
  FOREX_CROSSES EURGBP EURJPY GBPJPY EURCHF AUDJPY
  INDICES       US500 NAS100 GER40 UK100 JPN225 AUS200
  METALS        XAUUSD XAGUSD
  CRYPTO_MAJOR  BTCUSD ETHUSD LTCUSD

Groups can be mixed with explicit symbols: --instruments MAG7,EURUSD,XAUUSD

Usage
-----
# Download M5+M15 for all MAG7 from 2022 to today (quarterly chunks):
python scripts/download_bulk.py --instruments MAG7 --timeframes M5,M15

# Preview without downloading:
python scripts/download_bulk.py --instruments MAG7 --timeframes M5,M15 --dry-run

# H1 for forex majors + gold (annual chunks are fine for H1):
python scripts/download_bulk.py \\
    --instruments FOREX_MAJORS,XAUUSD --timeframes H1 \\
    --from-year 2020 --chunk-size year

# Mix groups + individual symbols:
python scripts/download_bulk.py \\
    --instruments MAG7,EURUSD,XAUUSD --timeframes M5,M15,H1 \\
    --from-year 2023

# Monthly chunks for very granular control (M1 or unreliable network):
python scripts/download_bulk.py \\
    --instruments AAPL,MSFT --timeframes M1 --chunk-size month
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime, timezone, date, timedelta
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap — allow running from engine/ or project root
# ---------------------------------------------------------------------------
_ENGINE_DIR = Path(__file__).resolve().parents[1]
if str(_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(_ENGINE_DIR))

from src.data.downloader import DukascopyDownloader
from src.utils import setup_logging

# ---------------------------------------------------------------------------
# Named instrument groups
# ---------------------------------------------------------------------------

INSTRUMENT_GROUPS: dict[str, list[str]] = {
    "MAG7":          ["AAPL", "AMZN", "GOOGL", "META", "MSFT", "NVDA", "TSLA"],
    "FOREX_MAJORS":  ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD", "NZDUSD"],
    "FOREX_CROSSES": ["EURGBP", "EURJPY", "GBPJPY", "EURCHF", "AUDJPY"],
    "INDICES":       ["US500", "NAS100", "GER40", "UK100", "JPN225", "AUS200"],
    "METALS":        ["XAUUSD", "XAGUSD"],
    "CRYPTO_MAJOR":  ["BTCUSD", "ETHUSD", "LTCUSD"],
}

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_FROM_YEAR  = 2022
DEFAULT_DATA_DIR   = str(_ENGINE_DIR / "data")
DEFAULT_CHUNK_SIZE = "quarter"

# Conservative batch pause inside dukascopy-node (between monthly requests)
BATCH_PAUSE_MS = 2000

# Pause between subprocess calls to avoid rate-limiting
INTER_CALL_PAUSE = 3.0

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Chunk helpers
# ---------------------------------------------------------------------------

def _resolve_instruments(spec: str) -> list[str]:
    """Expand group names and individual symbols into a deduplicated list.

    Accepts a comma-separated string like "MAG7,EURUSD,XAUUSD".
    Group names are case-insensitive. Unknown tokens are passed through as-is
    (the downloader will raise if the symbol is invalid).
    """
    seen: dict[str, None] = {}  # ordered set
    for token in spec.split(","):
        token = token.strip().upper()
        if not token:
            continue
        if token in INSTRUMENT_GROUPS:
            for sym in INSTRUMENT_GROUPS[token]:
                seen[sym] = None
        else:
            seen[token] = None
    return list(seen)


def _make_chunks(
    from_year: int,
    to_year: int,
    chunk_size: str,
) -> list[tuple[date, date]]:
    """Return (start, end) date pairs covering from_year → to_year.

    chunk_size choices:
      quarter — 3-month windows (default; recommended for M5/M15)
      month   — 1-month windows (safest; use for M1 or unreliable networks)
      year    — annual windows  (fast; safe for H1/H4/D1 only)
    """
    today = date.today()

    if chunk_size == "year":
        starts = [date(y, 1, 1) for y in range(from_year, to_year + 1)]
        ends   = [date(y, 12, 31) for y in range(from_year, to_year + 1)]
    elif chunk_size == "quarter":
        starts, ends = [], []
        q_starts = [(1, 1), (4, 1), (7, 1), (10, 1)]
        for y in range(from_year, to_year + 1):
            for qi, (qm, qd) in enumerate(q_starts):
                s = date(y, qm, qd)
                if qi + 1 < len(q_starts):
                    nm, nd = q_starts[qi + 1]
                    e = date(y, nm, nd) - timedelta(days=1)
                else:
                    e = date(y, 12, 31)
                starts.append(s)
                ends.append(e)
    elif chunk_size == "month":
        starts, ends = [], []
        for y in range(from_year, to_year + 1):
            for m in range(1, 13):
                s = date(y, m, 1)
                # last day of month
                if m == 12:
                    e = date(y, 12, 31)
                else:
                    e = date(y, m + 1, 1) - timedelta(days=1)
                starts.append(s)
                ends.append(e)
    else:
        raise ValueError(f"Unknown chunk_size '{chunk_size}'. Use: quarter, month, year")

    pairs = []
    for s, e in zip(starts, ends):
        if s > today:
            break
        pairs.append((s, min(e, today)))
    return pairs


def _to_dt(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

def _summarise(instruments: list[str], timeframes: list[str], data_dir: str) -> None:
    """Print bar counts and date ranges for every downloaded file."""
    import pandas as pd

    root = Path(data_dir)
    header = f"{'Symbol':<8}  {'TF':<4}  {'Bars':>7}  {'From':<12}  {'To':<12}"
    print()
    print("=" * len(header))
    print("Final summary")
    print("=" * len(header))
    print(header)
    print("-" * len(header))
    for sym in instruments:
        for tf in timeframes:
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
    group_list = ", ".join(INSTRUMENT_GROUPS.keys())
    parser = argparse.ArgumentParser(
        prog="download_bulk",
        description=(
            "Bulk Dukascopy downloader with timeout-safe chunking. "
            "Splits large date ranges into smaller windows so each "
            "dukascopy-node subprocess call stays under the 300s timeout."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--instruments",
        default="MAG7",
        metavar="SPEC",
        help=(
            f"Comma-separated symbols or group names. "
            f"Named groups: {group_list}. "
            f"Example: 'MAG7,EURUSD,XAUUSD'. (default: MAG7)"
        ),
    )
    parser.add_argument(
        "--timeframes",
        default="M5,M15",
        metavar="TF,...",
        help="Comma-separated timeframes. Example: 'M5,M15,H1'. (default: M5,M15)",
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
        "--chunk-size",
        choices=["quarter", "month", "year"],
        default=DEFAULT_CHUNK_SIZE,
        help=(
            "Window size per subprocess call. "
            "'quarter' = recommended for M5/M15; "
            "'month' = safest for M1 or slow networks; "
            "'year' = fast, safe for H1/H4/D1 only. "
            f"(default: {DEFAULT_CHUNK_SIZE})"
        ),
    )
    parser.add_argument(
        "--data-dir", default=DEFAULT_DATA_DIR, metavar="DIR",
        help=f"Root directory for Parquet cache (default: {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "--pause", type=float, default=INTER_CALL_PAUSE, metavar="SECS",
        help=f"Seconds to wait between subprocess calls (default: {INTER_CALL_PAUSE})",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be downloaded without actually running it",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )
    args = parser.parse_args()

    setup_logging(args.log_level)

    instruments = _resolve_instruments(args.instruments)
    timeframes  = [tf.strip().upper() for tf in args.timeframes.split(",") if tf.strip()]
    chunks      = _make_chunks(args.from_year, args.to_year, args.chunk_size)
    total       = len(instruments) * len(timeframes) * len(chunks)

    print("Bulk download plan")
    print(f"  Instruments : {', '.join(instruments)}")
    print(f"  Timeframes  : {', '.join(timeframes)}")
    print(f"  Years       : {args.from_year} → {args.to_year}")
    print(f"  Chunk size  : {args.chunk_size}  ({len(chunks)} chunks)")
    print(f"  Data dir    : {args.data_dir}")
    print(f"  Dry run     : {args.dry_run}")
    print(f"  Total calls : {total}  (instruments × timeframes × chunks)")
    print()

    if args.dry_run:
        for sym in instruments:
            for tf in timeframes:
                for start, end in chunks:
                    print(f"  [DRY-RUN]  {sym}/{tf}  {start} → {end}")
        return 0

    downloader = DukascopyDownloader(
        data_dir=args.data_dir,
        batch_pause_ms=BATCH_PAUSE_MS,
        retries=3,
    )

    done   = 0
    errors: list[str] = []

    for sym in instruments:
        for tf in timeframes:
            for start, end in chunks:
                done += 1
                print(f"[{done}/{total}] {sym}/{tf}  {start} → {end}", flush=True)

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
                        print("  ⚠  No data returned (market may be closed in this range)")
                except Exception as exc:
                    print(f"  ✗  FAILED: {exc}")
                    logger.error("Failed %s/%s %s→%s: %s", sym, tf, start, end, exc)
                    errors.append(f"{sym}/{tf} {start}→{end}: {exc}")

                if done < total:
                    time.sleep(args.pause)

    _summarise(instruments, timeframes, args.data_dir)

    if errors:
        print(f"\n{len(errors)} error(s) occurred:")
        for e in errors:
            print(f"  • {e}")
        return 1

    print("\nAll downloads completed successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
