"""Preprocessing step: clean raw data and add technical indicators."""

import os
from pathlib import Path

import pandas as pd

from src import etl_fetch
from src.features import clean, technical_indicators

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))


def preprocess(data_dir=None) -> Path:
    data_dir = Path(data_dir or DATA_DIR)
    df = clean(pd.read_csv(data_dir / "raw" / etl_fetch.RAW_FILE))
    out = data_dir / "processed" / "btc_usd_features.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    technical_indicators(df).to_csv(out, index=False)
    return out
