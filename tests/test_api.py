def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.get_json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert "uptime_seconds" in body and body["model_version"]


def test_predict_default_seven_days(client):
    r = client.post("/predict", json={})
    assert r.status_code == 200
    preds = r.get_json()["predictions"]
    assert len(preds) == 7
    assert all(p["predicted_close"] > 0 and p["date"] for p in preds)


def test_predict_without_body(client):
    assert client.post("/predict").status_code == 200


def test_predict_custom_history(client):
    history = [30000 + i * 10 for i in range(60)]
    r = client.post("/predict", json={"history": history, "forecast_days": 3})
    assert r.status_code == 200
    assert len(r.get_json()["predictions"]) == 3


def test_predict_bad_forecast_days(client):
    assert client.post("/predict", json={"forecast_days": 0}).status_code == 400
    assert client.post("/predict", json={"forecast_days": "x"}).status_code == 400
    assert client.post("/predict", json={"forecast_days": 999}).status_code == 400


def test_predict_bad_history(client):
    assert client.post("/predict", json={"history": [1, 2, 3]}).status_code == 400
    assert client.post("/predict", json={"history": ["a"] * 50}).status_code == 400
    assert client.post("/predict", json=[1, 2]).status_code == 400


def test_metrics(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    body = r.get_json()
    assert body["mae"] >= 0 and body["rmse"] >= 0 and body["mape"] >= 0


def test_reload_requires_key(client):
    assert client.post("/reload").status_code == 401
    r = client.post("/reload", headers={"X-API-Key": "test-key"})
    assert r.status_code == 200


def test_unknown_route(client):
    assert client.get("/nope").status_code == 404
