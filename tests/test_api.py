"""Automated tests for the Cloud Incident Prediction FastAPI application."""

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src import api
from src.preprocess import FEATURE_COLUMNS


VALID_TELEMETRY = {
    "cpu_usage_pct": 85,
    "memory_usage_pct": 90,
    "error_rate_pct": 5.5,
    "p95_latency_ms": 1800,
    "pod_restarts": 3,
}


class FakeModel:
    """A predictable replacement for the trained classifier in unit tests."""

    classes_ = np.array([0, 1])
    feature_names_in_ = np.array(FEATURE_COLUMNS)

    def __init__(self):
        self.last_features = None

    def predict(self, features):
        self.last_features = features.copy()
        return np.array([1])

    def predict_proba(self, features):
        return np.array([[0.12, 0.88]])


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Start the FastAPI app with a fake model; no MLflow or .joblib needed."""
    fake_path = tmp_path / "incident_model.joblib"
    fake_path.touch()  # Satisfy the existence check in the app's lifespan.
    model = FakeModel()

    monkeypatch.setattr(api, "MODEL_PATH", fake_path)
    monkeypatch.setattr(api.joblib, "load", lambda path: model)

    # Using a context manager runs FastAPI startup and shutdown.
    with TestClient(api.app) as test_client:
        yield test_client, model


def test_health(client):
    test_client, _ = client
    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "model_loaded": True}


def test_valid_prediction(client):
    test_client, _ = client
    response = test_client.post("/predict", json=VALID_TELEMETRY)

    assert response.status_code == 200
    assert response.json() == {
        "prediction": 1,
        "incident_probability": 0.88,
        "prediction_window_minutes": 30,
    }


def test_input_feature_order(client):
    test_client, model = client
    response = test_client.post("/predict", json=VALID_TELEMETRY)

    assert response.status_code == 200
    assert list(model.last_features.columns) == FEATURE_COLUMNS
    assert model.last_features.iloc[0].to_dict() == VALID_TELEMETRY


@pytest.mark.parametrize(
    "field, invalid_value",
    [
        ("cpu_usage_pct", 101),
        ("memory_usage_pct", -1),
        ("error_rate_pct", 101),
        ("p95_latency_ms", -100),
        ("pod_restarts", -2),
    ],
)
def test_invalid_metric_range(client, field, invalid_value):
    test_client, _ = client
    payload = {**VALID_TELEMETRY, field: invalid_value}

    response = test_client.post("/predict", json=payload)
    assert response.status_code == 422


def test_missing_required_feature(client):
    test_client, _ = client
    payload = VALID_TELEMETRY.copy()
    payload.pop("cpu_usage_pct")

    response = test_client.post("/predict", json=payload)
    assert response.status_code == 422


def test_unknown_feature_rejected(client):
    test_client, _ = client
    payload = {**VALID_TELEMETRY, "unknown_metric": 123}

    response = test_client.post("/predict", json=payload)
    assert response.status_code == 422


def test_real_model_if_available():
    """Optional smoke test for the local trained artifact, if present."""
    if not api.MODEL_PATH.is_file():
        pytest.skip("Local trained model artifact is not available")

    # Load only a model produced by our trusted local training pipeline.
    with TestClient(api.app) as test_client:
        response = test_client.post("/predict", json=VALID_TELEMETRY)

    assert response.status_code == 200
    prediction = response.json()
    assert prediction["prediction"] in (0, 1)
    assert 0 <= prediction["incident_probability"] <= 1
    assert prediction["prediction_window_minutes"] == 30
