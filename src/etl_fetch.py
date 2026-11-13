"""Fetch daily BTC-USD OHLCV data and store it as raw CSV."""

import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
import requests

log = logging.getLogger("etl_fetch")

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
RAW_FILE = "btc_usd_raw.csv"
COLUMNS = ["Date", "Open", "High", "Low", "Close", "Volume"]


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
    df = df.reset_index()[COLUMNS]
    df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
    return df


def fetch_binance(days: int = 1500) -> pd.DataFrame:
    """Binance public API (no key needed): BTCUSDT daily candles."""
    url = "https://api.binance.com/api/v3/klines"
    rows, end = [], None
    while len(rows) < days:
        params = {"symbol": "BTCUSDT", "interval": "1d", "limit": 1000}
        if end is not None:
            params["endTime"] = end
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        rows = batch + rows
        end = batch[0][0] - 1
        if len(batch) < 1000:
            break
    df = pd.DataFrame(rows).iloc[:, :6]
    df.columns = ["ts", "Open", "High", "Low", "Close", "Volume"]
    df["Date"] = pd.to_datetime(df["ts"], unit="ms")
    for col in ["Open", "High", "Low", "Close", "Volume"]:
        df[col] = df[col].astype(float)
    return df[COLUMNS]


def fetch_coingecko(days: int = 365) -> pd.DataFrame:
    """CoinGecko public API: daily close and volume (open/high/low = close)."""
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    resp = requests.get(url, params={"vs_currency": "usd", "days": days, "interval": "daily"}, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    prices = pd.DataFrame(data["prices"], columns=["ts", "Close"])
    vols = pd.DataFrame(data["total_volumes"], columns=["ts", "Volume"])
    df = prices.merge(vols, on="ts")
    df["Date"] = pd.to_datetime(df["ts"], unit="ms").dt.normalize()
    df["Open"] = df["High"] = df["Low"] = df["Close"]
    return df[COLUMNS]


def fetch(data_dir: Path = None, allow_synthetic: bool = True) -> Path:
    """Download data and write it to <data_dir>/raw/btc_usd_raw.csv. Returns the path."""
    data_dir = Path(data_dir or DATA_DIR)
    out = data_dir / "raw" / RAW_FILE
    out.parent.mkdir(parents=True, exist_ok=True)

    df = None
    for name, source in [("yfinance", fetch_yfinance), ("binance", fetch_binance), ("coingecko", fetch_coingecko)]:
        try:
            candidate = source()
            if candidate is not None and len(candidate) > 100:
                df = candidate
                log.info("Fetched %d rows from %s", len(df), name)
                break
        except Exception as exc:  # network down, rate limit, region block, ...
            log.warning("%s fetch failed: %s", name, exc)
    if df is None:
        if not allow_synthetic:
            raise RuntimeError("All live data sources failed")
        log.warning("All live sources failed; using SYNTHETIC data")
        df = synthetic_btc()
    df.to_csv(out, index=False)
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(fetch())
