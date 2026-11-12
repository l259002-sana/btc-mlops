#!/bin/sh
# Train an initial model if the (PVC-backed) model dir is empty. flock prevents
# several replicas starting at the same time from all training simultaneously.
set -e
mkdir -p "$MODEL_DIR" "$DATA_DIR"
if [ ! -f "$MODEL_DIR/model.joblib" ]; then
  echo "No model found in $MODEL_DIR - training initial model..."
  flock "$MODEL_DIR/.train.lock" sh -c \
    "[ -f '$MODEL_DIR/model.joblib' ] || python -m src.train_forecast"
fi
exec gunicorn --bind "0.0.0.0:${PORT:-5000}" --workers "${WEB_WORKERS:-2}" --timeout 120 \
  --access-logfile - app:app
