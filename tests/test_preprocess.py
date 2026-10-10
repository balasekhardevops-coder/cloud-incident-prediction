"""Tests for chronological preprocessing and validation of telemetry data."""

import numpy as np
import pandas as pd
import pytest

from src import preprocess


@pytest.fixture
def telemetry_csv(tmp_path, monkeypatch):
    """Create an isolated project directory with a realistic-shape CSV.

    Redirect preprocess.__file__ so the function reads this temporary CSV,
    never the developer's real data/telemetry.csv file.
    """
    (tmp_path / "src").mkdir()
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(preprocess, "__file__", str(tmp_path / "src" / "preprocess.py"))

    rows = 970
    minute = np.arange(rows)
    labels = np.zeros(rows, dtype=int)

    # Each future incident creates 30 positive labels before its event.
    for incident_at in [150, 350, 550, 750, 950]:
        labels[incident_at - 30 : incident_at] = 1

    df = pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=rows, freq="min"),
            "cpu_usage_pct": 35.0 + minute % 45,
            "memory_usage_pct": 40.0 + minute % 40,
            "error_rate_pct": (minute % 25) / 10.0,
            # Unique values make checking chronological order straightforward.
            "p95_latency_ms": 100.0 + minute,
            "pod_restarts": minute % 5,
            "incident_next_30m": labels,
        }
    )

    csv_path = data_dir / "telemetry.csv"
    df.to_csv(csv_path, index=False)
    return df, csv_path


def test_expected_split_shapes_and_label_counts(telemetry_csv):
    """The 970 rows produce 910 usable rows after two 30-row gaps."""
    X_train, X_val, X_test, y_train, y_val, y_test = (
        preprocess.load_and_preprocess_data()
    )

    assert X_train.shape == (679, 5)
    assert X_val.shape == (115, 5)
    assert X_test.shape == (116, 5)
    assert y_train.shape == (679,)
    assert y_val.shape == (115,)
    assert y_test.shape == (116,)

    assert y_train.value_counts().to_dict() == {0: 589, 1: 90}
    assert y_val.value_counts().to_dict() == {0: 85, 1: 30}
    assert y_test.value_counts().to_dict() == {0: 86, 1: 30}


def test_features_have_correct_names_and_no_target_leakage(telemetry_csv):
    X_train, X_val, X_test, _, _, _ = preprocess.load_and_preprocess_data()

    for features in (X_train, X_val, X_test):
        assert list(features.columns) == preprocess.FEATURE_COLUMNS
        assert preprocess.TARGET_COLUMN not in features.columns
        assert "timestamp" not in features.columns


def test_chronological_gaps_are_30_rows(telemetry_csv):
    """Validate exact row boundaries without exposing future target windows."""
    X_train, X_val, X_test, _, _, _ = preprocess.load_and_preprocess_data()

    assert (X_train.index[0], X_train.index[-1]) == (0, 678)
    assert (X_val.index[0], X_val.index[-1]) == (709, 823)
    assert (X_test.index[0], X_test.index[-1]) == (854, 969)

    assert X_val.index[0] - X_train.index[-1] - 1 == 30
    assert X_test.index[0] - X_val.index[-1] - 1 == 30
    assert len(X_train) + len(X_val) + len(X_test) == 910


def test_unsorted_csv_is_sorted_before_splitting(telemetry_csv):
    df, csv_path = telemetry_csv
    df.sample(frac=1, random_state=42).to_csv(csv_path, index=False)

    X_train, X_val, X_test, _, _, _ = preprocess.load_and_preprocess_data()

    assert X_train["p95_latency_ms"].iloc[0] == 100.0
    assert X_train["p95_latency_ms"].iloc[-1] == 778.0
    assert X_val["p95_latency_ms"].iloc[0] == 809.0
    assert X_test["p95_latency_ms"].iloc[0] == 954.0


@pytest.mark.parametrize("column", ["timestamp", "cpu_usage_pct", "incident_next_30m"])
def test_missing_required_column_raises(telemetry_csv, column):
    df, csv_path = telemetry_csv
    df.drop(columns=[column]).to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match="Missing columns"):
        preprocess.load_and_preprocess_data()


@pytest.mark.parametrize("column", ["cpu_usage_pct", "timestamp"])
def test_missing_value_raises(telemetry_csv, column):
    df, csv_path = telemetry_csv
    df.loc[10, column] = None
    df.to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match="missing values"):
        preprocess.load_and_preprocess_data()


def test_non_numeric_metric_raises(telemetry_csv):
    df, csv_path = telemetry_csv
    df["cpu_usage_pct"] = df["cpu_usage_pct"].astype(object)
    df.loc[10, "cpu_usage_pct"] = "not-a-number"
    df.to_csv(csv_path, index=False)

    with pytest.raises(ValueError):
        preprocess.load_and_preprocess_data()


def test_invalid_timestamp_raises(telemetry_csv):
    df, csv_path = telemetry_csv
    df["timestamp"] = df["timestamp"].astype(object)
    df.loc[10, "timestamp"] = "not-a-date"
    df.to_csv(csv_path, index=False)

    with pytest.raises(ValueError):
        preprocess.load_and_preprocess_data()


def test_duplicate_timestamp_raises(telemetry_csv):
    df, csv_path = telemetry_csv
    df.loc[10, "timestamp"] = df.loc[9, "timestamp"]
    df.to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match="Duplicate timestamps"):
        preprocess.load_and_preprocess_data()


def test_missing_minute_raises(telemetry_csv):
    df, csv_path = telemetry_csv
    df.drop(index=10).to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match="one measurement per minute"):
        preprocess.load_and_preprocess_data()


def test_nonbinary_label_raises(telemetry_csv):
    df, csv_path = telemetry_csv
    df.loc[10, "incident_next_30m"] = 2
    df.to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match="Target must contain only 0 and 1"):
        preprocess.load_and_preprocess_data()


def test_small_dataset_raises(telemetry_csv):
    df, csv_path = telemetry_csv
    df.head(50).to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match="Not enough rows"):
        preprocess.load_and_preprocess_data()


@pytest.mark.parametrize(
    "split_name,start,end",
    [("Training", 0, 679), ("Validation", 709, 824), ("Testing", 854, 970)],
)
def test_single_class_split_raises(telemetry_csv, split_name, start, end):
    """A useful evaluation split must contain both 0 and 1 labels."""
    df, csv_path = telemetry_csv
    df.loc[start : end - 1, "incident_next_30m"] = 0
    df.to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match=f"{split_name} split must contain both"):
        preprocess.load_and_preprocess_data()
