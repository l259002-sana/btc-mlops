import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))


@pytest.fixture(scope="session")
def client(tmp_path_factory):
    import os

    base = tmp_path_factory.mktemp("btc")
    os.environ["MODEL_DIR"] = str(base / "models")
    os.environ["DATA_DIR"] = str(base / "data")
    os.environ["API_KEY"] = "test-key"

    from src import etl_fetch
    from src.train_forecast import train

    raw = base / "data" / "raw"
    raw.mkdir(parents=True)
    etl_fetch.synthetic_btc(600).to_csv(raw / etl_fetch.RAW_FILE, index=False)
    train(base / "data", base / "models", mape_threshold=1000)

    import app as api  # app/app.py

    api.app.config["TESTING"] = True
    return api.app.test_client()
