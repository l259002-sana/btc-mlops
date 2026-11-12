"""Flask REST API serving the 7-day BTC-USD close price forecast."""

import hmac
import json
import logging
import os
import sys
import threading
import time
from datetime import timedelta
from pathlib import Path

import joblib
import pandas as pd
from flask import Flask, jsonify, request

# Works both in the container (/app) and from the repo root / app folder.
_here = Path(__file__).resolve().parent
for _p in (_here, _here.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from src.features import MIN_HISTORY  # noqa: E402
from src.forecasting import recursive_forecast  # noqa: E402

MAX_DAYS = 14

app = Flask(__name__)
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
log = logging.getLogger("btc-api")

START_TIME = time.time()
_lock = threading.Lock()
_state = {"artifact": None, "history": None, "metrics": {}}


def model_dir() -> Path:
    return Path(os.getenv("MODEL_DIR", "models"))


def load_model() -> None:
    """(Re)load model, recent history and metrics from the model directory."""
    d = model_dir()
    artifact = joblib.load(d / "model.joblib")
    history = pd.read_csv(d / "history.csv", parse_dates=["Date"])
    metrics = {}
    if (d / "metrics.json").exists():
        metrics = json.loads((d / "metrics.json").read_text())
    with _lock:
        _state.update(artifact=artifact, history=history, metrics=metrics)
    log.info("Loaded model %s", artifact["version"])


def ensure_loaded() -> bool:
    if _state["artifact"] is None:
        try:
            load_model()
        except Exception:
            log.exception("Model not available yet")
            return False
    return True


def error(message: str, status: int):
    return jsonify({"error": message}), status


@app.get("/health")
def health():
    loaded = ensure_loaded()
    return jsonify(
        {
            "status": "ok",
            "uptime_seconds": round(time.time() - START_TIME, 1),
            "model_version": _state["artifact"]["version"] if loaded else None,
            "model_loaded": loaded,
            "stage": os.getenv("MODEL_STAGE", "dev"),
        }
    )


@app.post("/predict")
def predict():
    try:
        payload = request.get_json(silent=True)
        if payload is None:
            payload = {}
        if not isinstance(payload, dict):
            return error("JSON body must be an object", 400)

        days = payload.get("forecast_days", 7)
        if isinstance(days, bool) or not isinstance(days, int) or not 1 <= days <= MAX_DAYS:
            return error(f"forecast_days must be an integer between 1 and {MAX_DAYS}", 400)

        if not ensure_loaded():
            return error("Model not loaded yet", 503)

        history = payload.get("history")
        if history is None:
            hist_df = _state["history"]
            closes, last_date = hist_df["Close"].tolist(), hist_df["Date"].iloc[-1]
        else:
            if not isinstance(history, list) or len(history) < MIN_HISTORY:
                return error(f"history must be a list of at least {MIN_HISTORY} closing prices", 400)
            if any(isinstance(x, bool) or not isinstance(x, (int, float)) or x <= 0 for x in history):
                return error("history must contain only positive numbers", 400)
            closes, last_date = history, pd.Timestamp.utcnow().tz_localize(None).normalize()

        art = _state["artifact"]
        preds = recursive_forecast(art["model"], art["feature_cols"], closes, days)
        dates = [(last_date + timedelta(days=i + 1)).strftime("%Y-%m-%d") for i in range(days)]
        return jsonify(
            {
                "model_version": art["version"],
                "forecast_days": days,
                "predictions": [{"date": d, "predicted_close": round(p, 2)} for d, p in zip(dates, preds)],
            }
        )
    except ValueError as exc:
        return error(str(exc), 400)
    except Exception:
        log.exception("Unhandled error in /predict")
        return error("Internal server error", 500)


@app.get("/metrics")
def metrics():
    if not ensure_loaded():
        return error("Model not loaded yet", 503)
    m = _state["metrics"]
    return jsonify({k: m.get(k) for k in ("mae", "rmse", "mape", "trained_at", "model_version", "last_data_date")})


@app.post("/reload")
def reload_model():
    """Called by the Airflow DAG after retraining. Protected by API_KEY (from K8s Secret)."""
    expected = os.getenv("API_KEY", "")
    given = request.headers.get("X-API-Key", "")
    if expected and not hmac.compare_digest(expected, given):
        return error("Unauthorized", 401)
    try:
        load_model()
        return jsonify({"status": "reloaded", "model_version": _state["artifact"]["version"]})
    except Exception:
        log.exception("Reload failed")
        return error("Reload failed", 500)


@app.errorhandler(404)
def not_found(_):
    return error("Not found", 404)


@app.errorhandler(405)
def bad_method(_):
    return error("Method not allowed", 405)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")))
