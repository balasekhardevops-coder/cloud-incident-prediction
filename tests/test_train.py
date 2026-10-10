"""Unit tests for src/train.py, without a live MLflow server.

These tests exercise the real training orchestration while substituting tiny
classifiers and in-memory MLflow operations. No real model is overwritten.
"""

from contextlib import contextmanager
import importlib.util
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from src import preprocess


@pytest.fixture
def training_module(monkeypatch):
    """Import the actual MLflow-enabled train.py with fake MLflow modules.

    Our inference-only CI dependencies intentionally do not include MLflow.
    This avoids installing MLflow or connecting to its server for unit tests.
    """
    mlflow = ModuleType("mlflow")
    mlflow.__path__ = []
    mlflow_sklearn = ModuleType("mlflow.sklearn")
    mlflow_models = ModuleType("mlflow.models")

    mlflow.set_tracking_uri = Mock()
    mlflow.set_experiment = Mock()
    mlflow.log_params = Mock()
    mlflow.log_metrics = Mock()
    mlflow.log_artifact = Mock()
    mlflow.set_tag = Mock()
    mlflow_sklearn.log_model = Mock()
    mlflow_models.infer_signature = Mock(return_value="test-signature")
    mlflow.sklearn = mlflow_sklearn

    monkeypatch.setitem(sys.modules, "mlflow", mlflow)
    monkeypatch.setitem(sys.modules, "mlflow.sklearn", mlflow_sklearn)
    monkeypatch.setitem(sys.modules, "mlflow.models", mlflow_models)

    # train.py currently imports "preprocess" rather than "src.preprocess".
    monkeypatch.setitem(sys.modules, "preprocess", preprocess)

    filename = Path(__file__).resolve().parents[1] / "src" / "train.py"
    spec = importlib.util.spec_from_file_location("train_under_test", filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, mlflow


class PredeterminedModel:
    """Simple estimator that returns known classes and probabilities."""

    def __init__(self, predictions, incident_probabilities):
        self.predictions = np.asarray(predictions)
        self.incident_probabilities = np.asarray(incident_probabilities)

    def predict(self, X):
        assert len(X) == len(self.predictions)
        return self.predictions

    def predict_proba(self, X):
        assert len(X) == len(self.incident_probabilities)
        p = self.incident_probabilities
        return np.column_stack((1 - p, p))


def test_evaluate_calculates_correct_binary_metrics(training_module):
    train, _ = training_module
    X = pd.DataFrame({"cpu_usage_pct": [20, 90, 70, 55]})
    y = pd.Series([0, 1, 1, 0])
    model = PredeterminedModel([0, 1, 0, 1], [0.2, 0.8, 0.4, 0.7])

    scores = train.evaluate(model, X, y)

    assert scores["precision"] == pytest.approx(0.5)
    assert scores["recall"] == pytest.approx(0.5)
    assert scores["f1"] == pytest.approx(0.5)
    # Ranking: TP, FP, TP, TN. Average precision = (1 + 2/3)/2.
    assert scores["average_precision"] == pytest.approx(5 / 6)


def test_evaluate_handles_no_positive_predictions(training_module):
    train, _ = training_module
    X = pd.DataFrame({"cpu_usage_pct": [25, 65, 80]})
    y = pd.Series([0, 1, 1])
    model = PredeterminedModel([0, 0, 0], [0.1, 0.2, 0.3])

    scores = train.evaluate(model, X, y)

    assert scores["precision"] == 0
    assert scores["recall"] == 0
    assert scores["f1"] == 0
    assert 0 <= scores["average_precision"] <= 1


class StubClassifier:
    """Fake trainable classifier used to test orchestration, not ML quality."""

    def __init__(self, name, **parameters):
        self.name = name
        self.fits = []
        for key, value in parameters.items():
            setattr(self, key, value)
        if name == "Logistic Regression":
            self.named_steps = {
                "logisticregression": SimpleNamespace(
                    max_iter=1000, class_weight="balanced", random_state=42
                )
            }

    def fit(self, X, y):
        self.fits.append((X, y))
        return self

    def predict(self, X):
        return np.zeros(len(X), dtype=int)


@pytest.mark.parametrize(
    "logistic_f1, forest_f1, logistic_ap, forest_ap, expected_winner",
    [
        (0.70, 0.90, 0.99, 0.80, "Random Forest"),
        (0.95, 0.80, 0.70, 0.99, "Logistic Regression"),
        (0.80, 0.80, 0.85, 0.92, "Random Forest"),
    ],
)
def test_main_trains_logs_selects_and_saves_model(
    training_module,
    monkeypatch,
    tmp_path,
    capsys,
    logistic_f1,
    forest_f1,
    logistic_ap,
    forest_ap,
    expected_winner,
):
    train, mlflow = training_module

    X_train = pd.DataFrame({"cpu_usage_pct": [30, 50, 70, 90]})
    X_val = pd.DataFrame({"cpu_usage_pct": [45, 85]})
    X_test = pd.DataFrame({"cpu_usage_pct": [55, 95]})
    y_train = pd.Series([0, 0, 1, 1])
    y_val = pd.Series([0, 1])
    y_test = pd.Series([0, 1])
    splits = (X_train, X_val, X_test, y_train, y_val, y_test)
    monkeypatch.setattr(train, "load_and_preprocess_data", lambda: splits)

    logistic = StubClassifier("Logistic Regression")
    forest = StubClassifier(
        "Random Forest", n_estimators=200, max_depth=5,
        min_samples_leaf=5, class_weight="balanced", random_state=42
    )
    monkeypatch.setattr(train, "make_pipeline", lambda *args: logistic)
    monkeypatch.setattr(train, "RandomForestClassifier", lambda **kwargs: forest)

    calls = []

    def fake_evaluate(model, X, y):
        calls.append((model.name, X, y))
        assert X is not X_train  # Never score on training data for selection.
        if X is X_val:
            f1 = logistic_f1 if model is logistic else forest_f1
            ap = logistic_ap if model is logistic else forest_ap
            return {"precision": f1, "recall": f1, "f1": f1,
                    "average_precision": ap}
        assert X is X_test
        return {"precision": 0.75, "recall": 1.0, "f1": 0.86,
                "average_precision": 0.92}

    monkeypatch.setattr(train, "evaluate", fake_evaluate)

    opened_runs = []

    @contextmanager
    def fake_start_run(*, run_name=None, run_id=None):
        opened_runs.append((run_name, run_id))
        identifier = run_id or f"run-{run_name}"
        yield SimpleNamespace(info=SimpleNamespace(run_id=identifier))

    mlflow.start_run = fake_start_run

    # Redirect joblib output into pytest's temporary directory.
    fake_src = tmp_path / "src" / "train.py"
    monkeypatch.setattr(train, "__file__", str(fake_src))
    saved_models = []

    def fake_dump(model, path):
        saved_models.append((model, path))
        path.write_bytes(b"unit-test-placeholder")

    monkeypatch.setattr(train.joblib, "dump", fake_dump)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5443")

    train.main()

    assert logistic.fits == [(X_train, y_train)]
    assert forest.fits == [(X_train, y_train)]
    assert [(name, X) for name, X, _ in calls] == [
        ("Logistic Regression", X_val),
        ("Random Forest", X_val),
        (expected_winner, X_test),
    ]

    winner = forest if expected_winner == "Random Forest" else logistic
    assert saved_models == [
        (winner, tmp_path / "models" / "incident_model.joblib")
    ]
    assert saved_models[0][1].is_file()

    mlflow.set_tracking_uri.assert_called_once_with("http://localhost:5443")
    mlflow.set_experiment.assert_called_once_with(
        "Cloud Infrastructure Incident Prediction"
    )
    assert opened_runs == [
        ("Logistic Regression", None),
        ("Random Forest", None),
        (None, f"run-{expected_winner}"),
    ]

    logged_models = mlflow.sklearn.log_model.call_args_list
    assert len(logged_models) == 2
    assert logged_models[0].kwargs["skops_trusted_types"] is None
    assert logged_models[1].kwargs["skops_trusted_types"] == [
        "sklearn.tree._tree.Tree"
    ]

    metrics = [call.args[0] for call in mlflow.log_metrics.call_args_list]
    assert len(metrics) == 3
    assert metrics[0]["val_f1"] == logistic_f1
    assert metrics[1]["val_f1"] == forest_f1
    assert metrics[2]["test_recall"] == 1.0
    mlflow.set_tag.assert_called_once_with("selected_model", "true")
    mlflow.log_artifact.assert_called_once_with(
        str(tmp_path / "models" / "incident_model.joblib"),
        artifact_path="joblib",
    )
    assert f"Selected model: {expected_winner}" in capsys.readouterr().out
