"""Feature engineering shared by training and serving (avoids train/serve skew)."""

import numpy as np
import pandas as pd

N_LAGS = 7
MIN_HISTORY = 40


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Sort, de-duplicate, drop invalid rows."""
    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.drop_duplicates("Date").sort_values("Date")
    df = df.dropna(subset=["Close"])
    df = df[df["Close"] > 0]
    return df.reset_index(drop=True)


def build_features(close: pd.Series) -> pd.DataFrame:
    """Features at time t use only information up to t. Target = next-day log return."""
    close = close.astype(float).reset_index(drop=True)
    ret = np.log(close).diff()
    feats = {f"ret_lag_{i}": ret.shift(i - 1) for i in range(1, N_LAGS + 1)}
    feats["ma7_ratio"] = close.rolling(7).mean() / close - 1
    feats["ma30_ratio"] = close.rolling(30).mean() / close - 1
    feats["vol7"] = ret.rolling(7).std()
    feats["vol30"] = ret.rolling(30).std()
    out = pd.DataFrame(feats)
    out["target"] = ret.shift(-1)
    return out


def technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Human-readable indicators saved by the preprocessing step."""
    out = df.copy()
    out["ma_7"] = out["Close"].rolling(7).mean()
    out["ma_30"] = out["Close"].rolling(30).mean()
    out["log_return"] = np.log(out["Close"]).diff()
    out["volatility_7"] = out["log_return"].rolling(7).std()
    out["volatility_30"] = out["log_return"].rolling(30).std()
    return out
