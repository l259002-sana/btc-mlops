# Report Template (4-6 pages, export to PDF)

**Title page**: course, assignment, group members + roll numbers, GitHub repo URL, Docker Hub URL.

## 1. Architecture (0.5 page)
Paste the diagram from README.md (redraw in draw.io/Excalidraw if you like). Explain: data source (yfinance),
model (GradientBoosting on lagged log-returns, recursive 7-day forecast), why the Airflow gate only registers a
model when validation MAPE <= 15%, how the API reloads, why PVC keeps models across restarts.

## 2. Part A: Flask API (1 page)
Screenshots: `pytest -v` passing; curl `/health`, `/predict`, `/metrics`; a 400 error example
(`curl -X POST .../predict -d '{"forecast_days": 0}' -H 'Content-Type: application/json'`).

## 3. Part B: Docker + CI/CD (1 page)
Screenshots: `docker build` output, `docker images` (size), `docker compose ps`, GitHub Actions green run (both jobs),
Docker Hub repo showing `latest` and the SHA tag. Mention: multi-stage, non-root uid 10001, python:3.10-slim, cached layers.

## 4. Part C: Airflow + Kubeflow (1 page)
Screenshots: Airflow DAG graph (all green), task log for `train_evaluate` (metrics), API `/health` model_version
before/after. Kubeflow: compiled `btc_kfp_pipeline.yaml` snippet (3 components).

## 5. Part D: Kubernetes (1.5 pages)
Screenshots: `kubectl get pods,svc,hpa,ingress,pvc,cm,secret`; `kubectl describe deployment` (probes, resources);
HPA watch before/during/after load; curl through Ingress with Host `btcforecast.local`.

## 6. Part E: Verification (0.5 page)
Pod deletion + replacement timeline; end-to-end run (Airflow trigger -> Actions success -> live prediction JSON).

## 7. Performance analysis
Table of MAE/RMSE/MAPE from `/metrics`; discuss that BTC is near-random-walk so MAPE of a few % over 7 days is
reasonable; note limitations (recursive error accumulation, no exogenous features) and future work (Prophet/LSTM, drift monitoring).
Load test: requests/sec, replicas reached, time to scale up/down.
