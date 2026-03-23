"""Instrument catalog and timeframe mapping for the dukascopy-node CLI.

Instrument IDs follow the dukascopy-node convention: lowercase, no separator
(e.g. "eurusd", "usa500idxusd").  The canonical symbols used inside algo-farm
(EURUSD, US500 …) are the dict keys.

Usage
-----
from src.data.instruments import resolve_instrument, resolve_timeframe

feed_id = resolve_instrument("US500")   # -> "usa500idxusd"
dk_tf   = resolve_timeframe("H1")       # -> "h1"
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# Instrument catalog
# ---------------------------------------------------------------------------
INSTRUMENTS: dict[str, dict[str, str]] = {
    # --- Forex majors -------------------------------------------------------
    "EURUSD": {"feed": "eurusd",        "description": "Euro / US Dollar"},
    "GBPUSD": {"feed": "gbpusd",        "description": "British Pound / US Dollar"},
    "USDJPY": {"feed": "usdjpy",        "description": "US Dollar / Japanese Yen"},
    "USDCHF": {"feed": "usdchf",        "description": "US Dollar / Swiss Franc"},
    "AUDUSD": {"feed": "audusd",        "description": "Australian Dollar / US Dollar"},
    "USDCAD": {"feed": "usdcad",        "description": "US Dollar / Canadian Dollar"},
    "NZDUSD": {"feed": "nzdusd",        "description": "New Zealand Dollar / US Dollar"},
    # --- Forex crosses ------------------------------------------------------
    "EURGBP": {"feed": "eurgbp",        "description": "Euro / British Pound"},
    "EURJPY": {"feed": "eurjpy",        "description": "Euro / Japanese Yen"},
    "GBPJPY": {"feed": "gbpjpy",        "description": "British Pound / Japanese Yen"},
    "EURCHF": {"feed": "eurchf",        "description": "Euro / Swiss Franc"},
    "AUDJPY": {"feed": "audjpy",        "description": "Australian Dollar / Japanese Yen"},
    # --- Metals -------------------------------------------------------------
    "XAUUSD": {"feed": "xauusd",        "description": "Gold Spot / US Dollar"},
    "XAGUSD": {"feed": "xagusd",        "description": "Silver Spot / US Dollar"},
    # --- Energies (commodities) ---------------------------------------------
    "BRENT":  {"feed": "brentcmdusd",   "description": "Brent Crude Oil (USD)"},
    "WTI":    {"feed": "lightcmdusd",   "description": "WTI Light Crude Oil (USD)"},
    "NATGAS": {"feed": "gascmdusd",     "description": "Natural Gas (USD)"},
    "COPPER": {"feed": "coppercmdusd",  "description": "Copper (USD)"},
    # --- Equity indices (available via dukascopy-node, not the free REST API)
    "US500":  {"feed": "usa500idxusd",  "description": "S&P 500 Index"},
    "NAS100": {"feed": "usatechidxusd", "description": "NASDAQ 100 Index"},
    "GER40":  {"feed": "deuidxeur",     "description": "DAX 40 Index"},
    "UK100":  {"feed": "gbridxgbp",     "description": "FTSE 100 Index"},
    "JPN225": {"feed": "jpnidxjpy",     "description": "Nikkei 225 Index"},
    "AUS200": {"feed": "ausidxaud",     "description": "ASX 200 Index"},
    # --- US stocks (top NASDAQ / liquid names) ------------------------------
    # Local equity parquet files include a non-zero Volume column, so
    # volume-based filters remain usable in the engine.
    "AAPL":   {"feed": "aaplususd",     "description": "Apple Inc."},
    "MSFT":   {"feed": "msftususd",     "description": "Microsoft Corp."},
    "NVDA":   {"feed": "nvdaususd",     "description": "NVIDIA Corp."},
    "AMZN":   {"feed": "amznususd",     "description": "Amazon.com Inc."},
    "TSLA":   {"feed": "tslaususd",     "description": "Tesla Inc."},
    "META":   {"feed": "metususd",      "description": "Meta Platforms Inc."},
    "GOOGL":  {"feed": "googlususd",    "description": "Alphabet Inc. (GOOGL)"},
    "NFLX":   {"feed": "nflxususd",     "description": "Netflix Inc."},
    "AMD":    {"feed": "amdususd",      "description": "Advanced Micro Devices"},
    "QCOM":   {"feed": "qcomususd",     "description": "Qualcomm Inc."},
    # --- Crypto (33 pairs via dukascopy-node vccy feed) ---------------------
    "BTCUSD": {"feed": "btcusd",        "description": "Bitcoin vs US Dollar"},
    "BTCEUR": {"feed": "btceur",        "description": "Bitcoin vs Euro"},
    "BTCGBP": {"feed": "btcgbp",        "description": "Bitcoin vs Pound Sterling"},
    "BTCCHF": {"feed": "btcchf",        "description": "Bitcoin vs Swiss Franc"},
    "ETHUSD": {"feed": "ethusd",        "description": "Ether vs US Dollar"},
    "ETHEUR": {"feed": "etheur",        "description": "Ethereum vs Euro"},
    "ETHGBP": {"feed": "ethgbp",        "description": "Ethereum vs Pound Sterling"},
    "ETHCHF": {"feed": "ethchf",        "description": "Ethereum vs Swiss Franc"},
    "LTCUSD": {"feed": "ltcusd",        "description": "Litecoin vs US Dollar"},
    "LTCEUR": {"feed": "ltceur",        "description": "Litecoin vs Euro"},
    "LTCGBP": {"feed": "ltcgbp",        "description": "Litecoin vs Pound Sterling"},
    "LTCCHF": {"feed": "ltcchf",        "description": "Litecoin vs Swiss Franc"},
    "BCHUSD": {"feed": "bchusd",        "description": "Bitcoin Cash vs US Dollar"},
    "BCHEUR": {"feed": "bcheur",        "description": "Bitcoin Cash vs Euro"},
    "BCHGBP": {"feed": "bchgbp",        "description": "Bitcoin Cash vs Pound Sterling"},
    "BCHCHF": {"feed": "bchchf",        "description": "Bitcoin Cash vs Swiss Franc"},
    "XLMUSD": {"feed": "xlmusd",        "description": "Stellar vs US Dollar"},
    "XLMEUR": {"feed": "xlmeur",        "description": "Stellar vs Euro"},
    "XLMGBP": {"feed": "xlmgbp",        "description": "Stellar vs Pound Sterling"},
    "XLMCHF": {"feed": "xlmchf",        "description": "Stellar vs Swiss Franc"},
    "ADAUSD": {"feed": "adausd",        "description": "Cardano vs US Dollar"},
    "EOSUSD": {"feed": "eosusd",        "description": "EOS vs US Dollar"},
    "TRXUSD": {"feed": "trxusd",        "description": "TRON vs US Dollar"},
    "LNKUSD": {"feed": "lnkusd",        "description": "Chainlink vs US Dollar"},
    "UNIUSD": {"feed": "uniusd",        "description": "Uniswap vs US Dollar"},
    "MKRUSD": {"feed": "mkrusd",        "description": "Maker vs US Dollar"},
    "YFIUSD": {"feed": "yfiusd",        "description": "Yearn.finance vs US Dollar"},
    "DSHUSD": {"feed": "dshusd",        "description": "Dashcoin vs US Dollar"},
    "BATUSD": {"feed": "batusd",        "description": "Basic Attention Token vs US Dollar"},
    "MATUSD": {"feed": "matusd",        "description": "Polygon vs US Dollar"},
    "ENJUSD": {"feed": "enjusd",        "description": "Enjin vs US Dollar"},
    "AVEUSD": {"feed": "aveusd",        "description": "Aave vs US Dollar"},
    "CMPUSD": {"feed": "cmpusd",        "description": "Compound vs US Dollar"},
}

# ---------------------------------------------------------------------------
# Timeframe mapping (algo-farm canonical → dukascopy-node flag value)
# ---------------------------------------------------------------------------
TIMEFRAMES: dict[str, str] = {
    "M1":  "m1",
    "M5":  "m5",
    "M10": "m10",
    "M15": "m15",
    "M30": "m30",
    "H1":  "h1",
    "H4":  "h4",
    "D1":  "d1",
    "W1":  "w1",
}


def resolve_instrument(symbol: str) -> str:
    """Return dukascopy-node feed ID for a canonical symbol (e.g. 'US500' -> 'usa500idxusd')."""
    symbol = symbol.upper()
    if symbol not in INSTRUMENTS:
        available = ", ".join(sorted(INSTRUMENTS.keys()))
        raise KeyError(f"Unknown instrument '{symbol}'. Available: {available}")
    return INSTRUMENTS[symbol]["feed"]


def resolve_timeframe(tf: str) -> str:
    """Return dukascopy-node timeframe flag for a canonical TF (e.g. 'H1' -> 'h1')."""
    tf = tf.upper()
    if tf not in TIMEFRAMES:
        available = ", ".join(TIMEFRAMES.keys())
        raise KeyError(f"Unknown timeframe '{tf}'. Available: {available}")
    return TIMEFRAMES[tf]


def list_instruments() -> list[dict[str, str]]:
    """Return sorted instrument list for display."""
    return [
        {"symbol": k, "feed": v["feed"], "description": v["description"]}
        for k, v in sorted(INSTRUMENTS.items())
    ]
