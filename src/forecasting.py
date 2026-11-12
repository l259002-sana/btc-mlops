"""Recursive multi-step forecasting used by both training evaluation and the API."""

import numpy as np
import pandas as pd

from src.features import MIN_HISTORY, build_features


def recursive_forecast(model, feature_cols, close_history, steps: int = 7) -> list:
    """Predict `steps` future closing prices by feeding each prediction back in."""
    closes = [float(x) for x in close_history]
    if len(closes) < MIN_HISTORY:
        raise ValueError(f"Need at least {MIN_HISTORY} historical closes, got {len(closes)}")
    preds = []
    for _ in range(steps):
        feats = build_features(pd.Series(closes)).iloc[[-1]][feature_cols]
        next_ret = float(model.predict(feats.values)[0])
        next_close = closes[-1] * float(np.exp(next_ret))
        closes.append(next_close)
        preds.append(next_close)
    return preds
