"""Fetch daily BTC-USD OHLCV data and store it as raw CSV."""

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("etl_fetch")

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
RAW_FILE = "btc_usd_raw.csv"


def synthetic_btc(days: int = 1000, seed: int = 42) -> pd.DataFrame:
    """Offline fallback: geometric random walk that looks like BTC prices."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range(end=pd.Timestamp.utcnow().normalize().tz_localize(None), periods=days)
    close = 30000 * np.exp(np.cumsum(rng.normal(0.0004, 0.03, days)))
    return pd.DataFrame(
        {
            "Date": idx,
            "Open": close * (1 + rng.normal(0, 0.005, days)),
            "High": close * 1.01,
            "Low": close * 0.99,
            "Close": close,
            "Volume": rng.uniform(1e9, 5e10, days),
        }
    )


def fetch_yfinance(period: str = "5y") -> pd.DataFrame:
    import yfinance as yf

    df = yf.download("BTC-USD", period=period, interval="1d", auto_adjust=False, progress=False)
    if df is None or df.empty:
        raise RuntimeError("yfinance returned no data")
    if isinstance(df.columns, pd.MultiIndex):  # newer yfinance versions
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index()[["Date", "Open", "High", "Low", "Close", "Volume"]]
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df


def fetch(data_dir: Path = None, allow_synthetic: bool = True) -> Path:
    """Download data and write it to <data_dir>/raw/btc_usd_raw.csv. Returns the path."""
    data_dir = Path(data_dir or DATA_DIR)
    out = data_dir / "raw" / RAW_FILE
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        df = fetch_yfinance()
        log.info("Fetched %d rows from yfinance", len(df))
    except Exception as exc:  # network down, rate limit, ...
        if not allow_synthetic:
            raise
        log.warning("Live fetch failed (%s); using synthetic data", exc)
        df = synthetic_btc()
    df.to_csv(out, index=False)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(fetch())
