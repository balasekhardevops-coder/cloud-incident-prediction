from pathlib import Path

import pandas as pd

# Columns used by the model
FEATURE_COLUMNS = [
    "cpu_usage_pct",
    "memory_usage_pct",
    "error_rate_pct",
    "p95_latency_ms",
    "pod_restarts",
]

TARGET_COLUMN = "incident_next_30m"
PREDICTION_WINDOW_MINUTES = 30


def load_and_preprocess_data():

    # 1. Find the CSV file
    project_root = Path(__file__).resolve().parents[1]
    file_path = project_root / "data" / "telemetry.csv"

    # 2. Load the dataset
    df = pd.read_csv(file_path)

    # 3. Validate required columns
    required = ["timestamp", *FEATURE_COLUMNS, TARGET_COLUMN]
    missing = set(required) - set(df.columns)

    if missing:
        raise ValueError(f"Missing columns: {missing}")

    # 4. Convert data to correct types
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    for column in FEATURE_COLUMNS + [TARGET_COLUMN]:
        df[column] = pd.to_numeric(df[column], errors="raise")

    # 5. Check for missing values
    if df[required].isnull().any().any():
        raise ValueError("Dataset contains missing values")

    # 6. Sort rows by timestamp
    df = df.sort_values("timestamp").reset_index(drop=True)

    # 7. Validate time intervals and target labels
    if df["timestamp"].duplicated().any():
        raise ValueError("Duplicate timestamps found")

    intervals = df["timestamp"].diff().dropna()

    if not intervals.eq(pd.Timedelta(minutes=1)).all():
        raise ValueError("Expected one measurement per minute")

    if not df[TARGET_COLUMN].isin([0, 1]).all():
        raise ValueError("Target must contain only 0 and 1")

    # 8. Calculate chronological split boundaries
    total_rows = len(df)
    train_end = int(total_rows * 0.70)
    val_end = int(total_rows * 0.85)
    gap = PREDICTION_WINDOW_MINUTES

    # 9. Create train, validation and test partitions
    train_df = df.iloc[:train_end]
    val_df = df.iloc[train_end + gap:val_end]
    test_df = df.iloc[val_end + gap:]

    if any(part.empty for part in [train_df, val_df, test_df]):
        raise ValueError("Not enough rows for chronological splits")

    # 9a. Ensure every split contains both normal and incident labels
    for name, split_df in [
        ("Training", train_df),
        ("Validation", val_df),
        ("Testing", test_df),
    ]:
        if split_df[TARGET_COLUMN].nunique() < 2:
            counts = split_df[TARGET_COLUMN].value_counts().sort_index().to_dict()
            raise ValueError(
                f"{name} split must contain both 0 and 1 labels; got {counts}"
            )

    # 10. Separate features (X) and labels (y)
    X_train = train_df[FEATURE_COLUMNS].copy()
    X_val = val_df[FEATURE_COLUMNS].copy()
    X_test = test_df[FEATURE_COLUMNS].copy()

    y_train = train_df[TARGET_COLUMN].copy()
    y_val = val_df[TARGET_COLUMN].copy()
    y_test = test_df[TARGET_COLUMN].copy()

    return X_train, X_val, X_test, y_train, y_val, y_test


# Run checks only when this file is executed directly
if __name__ == "__main__":

    X_train, X_val, X_test, y_train, y_val, y_test = (
        load_and_preprocess_data()
    )

    for name, X, y in [
        ("Training", X_train, y_train),
        ("Validation", X_val, y_val),
        ("Testing", X_test, y_test),
    ]:
        print(f"{name}: X={X.shape}, y={y.shape}")
        print(f"  Labels: {y.value_counts().sort_index().to_dict()}")
