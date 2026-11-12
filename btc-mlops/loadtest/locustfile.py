"""Optional Locust load test:  locust -f loadtest/locustfile.py --host http://localhost:8080"""

from locust import HttpUser, between, task


class ForecastUser(HttpUser):
    wait_time = between(0.0, 0.1)

    @task(5)
    def predict(self):
        self.client.post("/predict", json={"forecast_days": 7})

    @task(1)
    def health(self):
        self.client.get("/health")
