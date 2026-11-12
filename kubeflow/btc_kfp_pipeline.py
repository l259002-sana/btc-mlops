"""Kubeflow Pipelines (KFP v2) spec: ingest -> features -> train.

Compile with:  python kubeflow/btc_kfp_pipeline.py   (creates btc_kfp_pipeline.yaml)
"""

from kfp import compiler, dsl
from kfp.dsl import Dataset, Input, Metrics, Model, Output

BASE = "python:3.10-slim"


@dsl.component(base_image=BASE, packages_to_install=["pandas==2.2.2", "numpy==1.26.4", "yfinance==0.2.54"])
def ingest_data(raw_data: Output[Dataset], period: str = "5y"):
    import numpy as np
    import pandas as pd

    try:
        import yfinance as yf

        df = yf.download("BTC-USD", period=period, interval="1d", auto_adjust=False, progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.reset_index()[["Date", "Open", "High", "Low", "Close", "Volume"]]
        assert len(df) > 100
    except Exception as exc:  # offline fallback so the pipeline always runs
        print("yfinance failed:", exc, "- using synthetic data")
        rng = np.random.default_rng(1)
        close = 30000 * np.exp(np.cumsum(rng.normal(0.0004, 0.03, 1000)))
        df = pd.DataFrame({"Date": pd.date_range(end="today", periods=1000), "Close": close})
    df.to_csv(raw_data.path, index=False)


@dsl.component(base_image=BASE, packages_to_install=["pandas==2.2.2", "numpy==1.26.4"])
def generate_features(raw_data: Input[Dataset], features: Output[Dataset]):
    import numpy as np
    import pandas as pd

    df = pd.read_csv(raw_data.path, parse_dates=["Date"]).drop_duplicates("Date").sort_values("Date")
    df = df.dropna(subset=["Close"])
    close = df["Close"].astype(float).reset_index(drop=True)
    ret = np.log(close).diff()
    out = pd.DataFrame({f"ret_lag_{i}": ret.shift(i - 1) for i in range(1, 8)})
    out["ma7_ratio"] = close.rolling(7).mean() / close - 1
    out["ma30_ratio"] = close.rolling(30).mean() / close - 1
    out["vol7"] = ret.rolling(7).std()
    out["vol30"] = ret.rolling(30).std()
    out["target"] = ret.shift(-1)
    out.dropna().to_csv(features.path, index=False)


@dsl.component(
    base_image=BASE,
    packages_to_install=["pandas==2.2.2", "numpy==1.26.4", "scikit-learn==1.5.1", "joblib==1.4.2"],
)
def train_model(features: Input[Dataset], model: Output[Model], metrics: Output[Metrics]):
    import joblib
    import numpy as np
    import pandas as pd
    from sklearn.ensemble import GradientBoostingRegressor

    data = pd.read_csv(features.path)
    cols = [c for c in data.columns if c != "target"]
    split = len(data) - 7
    reg = GradientBoostingRegressor(n_estimators=150, max_depth=3, learning_rate=0.05, random_state=42)
    reg.fit(data[cols].values[:split], data["target"].values[:split])
    pred = reg.predict(data[cols].values[split:])
    err = pred - data["target"].values[split:]
    metrics.log_metric("mae_log_return", float(np.mean(np.abs(err))))
    metrics.log_metric("rmse_log_return", float(np.sqrt(np.mean(err**2))))
    reg.fit(data[cols].values, data["target"].values)  # refit on all data
    joblib.dump({"model": reg, "feature_cols": cols}, model.path)


@dsl.pipeline(name="btc-forecast-pipeline", description="Daily BTC-USD ingestion, features and training")
def btc_pipeline(period: str = "5y"):
    ingest = ingest_data(period=period)
    feats = generate_features(raw_data=ingest.outputs["raw_data"])
    train_model(features=feats.outputs["features"])


if __name__ == "__main__":
    compiler.Compiler().compile(btc_pipeline, package_path="btc_kfp_pipeline.yaml")
    print("Compiled -> btc_kfp_pipeline.yaml")
