#!/usr/bin/env bash
# One-shot: install kind, create cluster, ingress-nginx, metrics-server, build image, deploy everything.
# Works in GitHub Codespaces (Docker + kubectl are preinstalled there).
# Usage: ./scripts/kind_up.sh [dockerhub_user]
set -euo pipefail
cd "$(dirname "$0")/.."
USER_NAME="${1:-local}"
IMAGE="${USER_NAME}/btc-forecast-api:latest"

if ! command -v kind >/dev/null; then
  curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.23.0/kind-linux-amd64
  chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind
fi
if ! command -v kubectl >/dev/null; then
  curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
  chmod +x kubectl && sudo mv kubectl /usr/local/bin/
fi

kind get clusters | grep -q '^btc$' || kind create cluster --name btc --config kind-config.yaml

echo ">> ingress-nginx"
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/main/deploy/static/provider/kind/deploy.yaml
echo ">> metrics-server (needed by the HPA)"
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch -n kube-system deployment metrics-server --type=json \
  -p '[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

echo ">> build + load image"
docker build -f app/Dockerfile -t "$IMAGE" .
kind load docker-image "$IMAGE" --name btc

echo ">> deploy"
sed "s#DOCKERHUB_USER/btc-forecast-api:latest#${IMAGE}#" k8s/deployment.yaml > /tmp/deployment.yaml
kubectl wait -n ingress-nginx --for=condition=ready pod -l app.kubernetes.io/component=controller --timeout=180s
kubectl apply -f k8s/configmap-secret.yaml -f k8s/pvc.yaml
kubectl apply -f /tmp/deployment.yaml -f k8s/service.yaml -f k8s/hpa.yaml
kubectl apply -f k8s/ingress.yaml
kubectl rollout status deployment/btc-forecast-api --timeout=300s

grep -q btcforecast.local /etc/hosts || echo "127.0.0.1 btcforecast.local" | sudo tee -a /etc/hosts
echo
echo "Done. Try:"
echo "  curl http://btcforecast.local:8080/health"
echo "  curl -X POST http://btcforecast.local:8080/predict -H 'Content-Type: application/json' -d '{}'"
echo "  curl http://localhost:30080/metrics     # via NodePort"
