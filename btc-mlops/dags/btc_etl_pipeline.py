"""Daily BTC-USD ETL -> retrain -> evaluate -> register -> notify API."""

import logging
import os
import sys
from datetime import datetime, timedelta

import requests
from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator

sys.path.insert(0, os.getenv("PYTHONPATH", "/opt/airflow"))

log = logging.getLogger(__name__)

default_args = {"owner": "mlops", "retries": 2, "retry_delay": timedelta(minutes=5)}


def fetch_data(**_):
    from src.etl_fetch import fetch

    path = fetch()
    log.info("Raw data saved to %s", path)


def preprocess_data(**_):
    from src.preprocess import preprocess

    path = preprocess()
    log.info("Features saved to %s", path)


def train_and_evaluate(ti, **_):
    from src.train_forecast import train

    metrics = train()
    log.info("Metrics: %s", metrics)
    ti.xcom_push(key="metrics", value=metrics)
    return bool(metrics["registered"])  # ShortCircuit: only continue if model passed the threshold


def check_registered(ti, **_):
    metrics = ti.xcom_pull(task_ids="train_evaluate", key="metrics")
    return bool(metrics and metrics.get("registered"))


def reload_api(**_):
    url = os.getenv("API_RELOAD_URL", "http://api:5000/reload")
    resp = requests.post(url, headers={"X-API-Key": os.getenv("API_KEY", "")}, timeout=30)
    resp.raise_for_status()
    log.info("API reloaded: %s", resp.json())


with DAG(
    dag_id="btc_etl_pipeline",
    description="Daily BTC ETL, retraining and API reload",
    default_args=default_args,
    start_date=datetime(2024, 1, 1),
    schedule="@daily",
    catchup=False,
    tags=["btc", "mlops"],
) as dag:
    t_fetch = PythonOperator(task_id="fetch_data", python_callable=fetch_data)
    t_prep = PythonOperator(task_id="preprocess_features", python_callable=preprocess_data)
    t_train = PythonOperator(task_id="train_evaluate", python_callable=train_and_evaluate)
    t_gate = ShortCircuitOperator(task_id="model_passed_threshold", python_callable=check_registered)
    t_reload = PythonOperator(task_id="reload_api_model", python_callable=reload_api)

    t_fetch >> t_prep >> t_train >> t_gate >> t_reload
