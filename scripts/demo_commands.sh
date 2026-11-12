#!/usr/bin/env bash
# Commands for the report screenshots (E1 chaos test, D5 load test). Run section by section.
set -x
kubectl get pods,svc,hpa,ingress,pvc,configmap,secret

# --- E1: self-healing ---
POD=$(kubectl get pods -l app=btc-forecast-api -o jsonpath='{.items[0].metadata.name}')
kubectl delete pod "$POD"
kubectl get pods -l app=btc-forecast-api -w   # Ctrl+C after the replacement is Running 1/1

# --- D5: autoscaling (open a 2nd terminal for the watch) ---
#   kubectl get hpa --watch
kubectl apply -f k8s/loadgen.yaml
#   ...wait 2-4 minutes, screenshot HPA watch + `kubectl get pods`...
kubectl delete -f k8s/loadgen.yaml   # then watch it scale back down (~5 min)
