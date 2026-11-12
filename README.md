# BTC-USD 7-Day Forecast: Production MLOps Pipeline

Flask API + Docker + GitHub Actions + Airflow + Kubeflow Pipelines + Kubernetes (kind/Minikube).

```
yfinance -> Airflow DAG (fetch -> features -> train/evaluate -> threshold gate -> POST /reload)
                                   |                                   |
                              models/ (PVC) <---------------- Flask+Gunicorn (3 pods, HPA 2-8)
GitHub push -> Actions (flake8, black, pytest -> docker build -> Docker Hub :sha + :latest)
Client -> Ingress (btcforecast.local) -> Service :80 -> Pods :5000
```

## 0. You need NO local installs: use GitHub Codespaces
1. Create a GitHub account, a Docker Hub account (+ access token), and a new **public** repo.
2. Upload this project to the repo (drag-and-drop the unzipped files on github.com, or use Codespaces below).
3. Repo -> **Code -> Codespaces -> Create codespace on main** (pick 4-core if available).
   You get VS Code in the browser with Docker, git and kubectl preinstalled.
4. Repo -> **Settings -> Secrets and variables -> Actions**: add `DOCKER_USERNAME` and `DOCKER_PASSWORD`
   (use a Docker Hub access token as the password).

## 1. Part A: run API + tests (in the Codespace terminal)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
black . && flake8 app src dags kubeflow tests    # format once before first push
pytest -v                                         # screenshot this
python -m src.train_forecast                      # trains model (falls back to synthetic data if offline)
MODEL_DIR=models gunicorn --bind 0.0.0.0:5000 app:app &
curl localhost:5000/health; curl -X POST localhost:5000/predict -H 'Content-Type: application/json' -d '{}'; curl localhost:5000/metrics
```

## 2. Part B: Docker, Compose, CI/CD
```bash
docker build -f app/Dockerfile -t btc-forecast-api .      # screenshot the build output
mkdir -p shared && chmod -R 777 shared
docker compose up airflow-init && docker compose up -d    # API :5000, Airflow :8080 (admin/admin)
```
`git push` to `main` -> Actions tab shows lint, tests, build, push (screenshot green run + Docker Hub tags).

## 3. Part C: Airflow + Kubeflow
- Airflow UI (forward port 8080 in Codespaces): unpause `btc_etl_pipeline`, click **Trigger DAG**, screenshot the Graph view (all green).
  After it finishes: `curl localhost:5000/health` shows a new `model_version` (the reload step worked).
- Kubeflow: `pip install kfp && python kubeflow/btc_kfp_pipeline.py` -> produces `btc_kfp_pipeline.yaml`. Commit it.
  (Running it needs a Kubeflow cluster; the assignment only requires authoring + compiling.)

## 4. Parts D & E: Kubernetes
Stop compose first (`docker compose down`) to free memory, then:
```bash
./scripts/kind_up.sh YOUR_DOCKERHUB_USER       # creates cluster, ingress-nginx, metrics-server, deploys all manifests
kubectl get pods,svc,hpa,ingress,pvc,cm,secret
curl http://btcforecast.local:8080/health
curl -X POST http://btcforecast.local:8080/predict -H 'Content-Type: application/json' -d '{}'
```
To deploy the image from Docker Hub instead of the local build, edit the `image:` line in `k8s/deployment.yaml`
and remove the `kind load` step.

- **E1 self-healing**: `kubectl delete pod <name>` then `kubectl get pods -w`.
- **D5 autoscaling**: terminal 1 `kubectl get hpa --watch`; terminal 2 `kubectl apply -f k8s/loadgen.yaml`;
  wait 2-4 min until REPLICAS grows toward 8 and screenshot; `kubectl delete -f k8s/loadgen.yaml` to stop.
  (Note: Deployment starts at 3 replicas; once the HPA is active it keeps 2-8.)
- Using Minikube instead: `minikube addons enable ingress metrics-server`, `minikube image load`, add `$(minikube ip) btcforecast.local` to /etc/hosts.

See `docs/REPORT_TEMPLATE.md` for the screenshot checklist and report outline (4-6 pages).

## Layout
```
app/ (app.py, Dockerfile, entrypoint.sh)   src/ (etl_fetch, features, forecasting, train_forecast, preprocess)
dags/btc_etl_pipeline.py                   kubeflow/btc_kfp_pipeline.py
k8s/ (configmap-secret, pvc, deployment, service, hpa, ingress, loadgen)
.github/workflows/ci_cd.yml  docker-compose.yml  tests/  scripts/  loadtest/
```
