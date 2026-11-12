"""Train the 7-day BTC close forecasting model, evaluate it, and register artifacts."""

import json
import logging
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor

from src import etl_fetch
from src.features import build_features, clean
from src.forecasting import recursive_forecast

log = logging.getLogger("train")

HORIZON = 7
DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
MODEL_DIR = Path(os.getenv("MODEL_DIR", "models"))
MAPE_THRESHOLD = float(os.getenv("MAPE_THRESHOLD", "15.0"))


def _fit(close: pd.Series):
    data = build_features(close).dropna()
    cols = [c for c in data.columns if c != "target"]
    model = GradientBoostingRegressor(n_estimators=150, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=42)
    model.fit(data[cols].values, data["target"].values)
    return model, cols


def evaluate(close: pd.Series) -> dict:
    """Hold out the latest 7 days, forecast them, compute MAE / RMSE / MAPE."""
    train_close, test_close = close.iloc[:-HORIZON], close.iloc[-HORIZON:].values
    model, cols = _fit(train_close)
    preds = np.array(recursive_forecast(model, cols, train_close.values, HORIZON))
    err = preds - test_close
    return {
        "mae": float(np.mean(np.abs(err))),
        "rmse": float(np.sqrt(np.mean(err**2))),
        "mape": float(np.mean(np.abs(err / test_close)) * 100),
    }


def _atomic_write(write_fn, dest: Path):
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=dest.parent)
    os.close(fd)
    write_fn(tmp)
    os.replace(tmp, dest)  # atomic: readers never see a half-written file


def train(data_dir=None, model_dir=None, mape_threshold=None) -> dict:
    data_dir, model_dir = Path(data_dir or DATA_DIR), Path(model_dir or MODEL_DIR)
    threshold = MAPE_THRESHOLD if mape_threshold is None else mape_threshold

    raw = data_dir / "raw" / etl_fetch.RAW_FILE
    if not raw.exists():
        etl_fetch.fetch(data_dir)
    df = clean(pd.read_csv(raw))
    close = df["Close"].reset_index(drop=True)

    metrics = evaluate(close)
    metrics.update(
        {
            "threshold_mape": threshold,
            "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "n_rows": int(len(df)),
            "last_data_date": str(df["Date"].iloc[-1].date()),
        }
    )
    passed = metrics["mape"] <= threshold
    metrics["registered"] = passed
    log.info("Validation metrics: %s", metrics)

    first_model = not (model_dir / "model.joblib").exists()
    if passed or first_model:  # always keep *a* model so the API can start
        model, cols = _fit(close)
        version = datetime.now(timezone.utc).strftime("v%Y%m%d%H%M%S")
        metrics["model_version"] = version
        metrics["registered"] = True
        artifact = {"model": model, "feature_cols": cols, "version": version}
        _atomic_write(lambda p: joblib.dump(artifact, p), model_dir / "model.joblib")
        history = df[["Date", "Close"]].tail(120)
        _atomic_write(lambda p: history.to_csv(p, index=False), model_dir / "history.csv")
        _atomic_write(
            lambda p: Path(p).write_text(json.dumps(metrics, indent=2)),
            model_dir / "metrics.json",
        )
        shutil.copy(model_dir / "model.joblib", model_dir / f"model_{version}.joblib")
    else:
        log.warning("MAPE %.2f above threshold %.2f; keeping previous model", metrics["mape"], threshold)
    return metrics


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(train(), indent=2))
