"""Train classifiers and record their experiments in MLflow."""

import os
from pathlib import Path

import joblib
import mlflow
import mlflow.sklearn
from mlflow.models import infer_signature
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

try:
    from .preprocess import load_and_preprocess_data
except ImportError:
    from preprocess import load_and_preprocess_data


def evaluate(model, X, y):
    """Calculate incident-classification metrics."""
    predictions = model.predict(X)
    probabilities = model.predict_proba(X)[:, 1]

    return {
        "precision": precision_score(y, predictions, zero_division=0),
        "recall": recall_score(y, predictions, zero_division=0),
        "f1": f1_score(y, predictions, zero_division=0),
        "average_precision": average_precision_score(y, probabilities),
    }


def main():
    # 1. Connect to the local MLflow server and choose an experiment.
    tracking_uri = os.getenv("MLFLOW_TRACKING_URI", "http://127.0.0.1:5443")
    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("Cloud Infrastructure Incident Prediction")

    # 2. Load the same chronological splits used in earlier training.
    X_train, X_val, X_test, y_train, y_val, y_test = (
        load_and_preprocess_data()
    )

    print(
        f"Training: {X_train.shape}, "
        f"validation: {X_val.shape}, test: {X_test.shape}"
    )

    # 3. Define the same two classifiers as before.
    models = {
        "Logistic Regression": make_pipeline(
            StandardScaler(),
            LogisticRegression(
                max_iter=1000,
                class_weight="balanced",
                random_state=42,
            ),
        ),
        "Random Forest": RandomForestClassifier(
            n_estimators=200,
            max_depth=5,
            min_samples_leaf=5,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        ),
    }

    validation_scores = {}
    run_ids = {}

    # 4. Create one MLflow run per trained classifier.
    for name, model in models.items():
        with mlflow.start_run(run_name=name) as run:
            model.fit(X_train, y_train)
            scores = evaluate(model, X_val, y_val)
            validation_scores[name] = scores
            run_ids[name] = run.info.run_id

            mlflow.log_params({
                "algorithm": name,
                "train_rows": len(X_train),
                "validation_rows": len(X_val),
                "test_rows": len(X_test),
                "feature_count": X_train.shape[1],
                "prediction_window_minutes": 30,
            })

            if name == "Logistic Regression":
                classifier = model.named_steps["logisticregression"]
                mlflow.log_params({
                    "scaler": "StandardScaler",
                    "max_iter": classifier.max_iter,
                    "class_weight": classifier.class_weight,
                    "random_state": classifier.random_state,
                })
            else:
                mlflow.log_params({
                    "n_estimators": model.n_estimators,
                    "max_depth": model.max_depth,
                    "min_samples_leaf": model.min_samples_leaf,
                    "class_weight": model.class_weight,
                    "random_state": model.random_state,
                })

            mlflow.log_metrics({
                f"val_{metric}": float(value)
                for metric, value in scores.items()
            })

            # Describe expected inputs/outputs and store the trained model.
            example = X_train.head(3)
            signature = infer_signature(example, model.predict(example))
            mlflow.sklearn.log_model(
                sk_model=model,
                name="model",
                signature=signature,
                input_example=example,
                # Only trust scikit-learn's internal tree type for our locally trained RF.
                skops_trusted_types=(
                    ["sklearn.tree._tree.Tree"] if name == "Random Forest" else None
                ),
            )

            print(f"\n{name} — validation (run: {run.info.run_id})")
            for metric, value in scores.items():
                print(f"  {metric}: {value:.3f}")

    # 5. Select the model using validation results only.
    best_name = max(
        validation_scores,
        key=lambda name: (
            validation_scores[name]["f1"],
            validation_scores[name]["average_precision"],
        ),
    )
    best_model = models[best_name]

    # 6. Evaluate the selected model on the untouched test set.
    test_scores = evaluate(best_model, X_test, y_test)
    print(f"\nSelected model: {best_name}")
    print("Test metrics:")
    for metric, value in test_scores.items():
        print(f"  {metric}: {value:.3f}")
    print("Test confusion matrix [[TN, FP], [FN, TP]]:")
    print(confusion_matrix(y_test, best_model.predict(X_test), labels=[0, 1]))

    # 7. Continue saving the winning classifier as a local joblib file.
    model_path = (
        Path(__file__).resolve().parents[1]
        / "models"
        / "incident_model.joblib"
    )
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(best_model, model_path)
    print(f"Saved fitted model: {model_path}")

    # 8. Add test metrics and the joblib artifact to the winner's run.
    with mlflow.start_run(run_id=run_ids[best_name]):
        mlflow.log_metrics({
            f"test_{metric}": float(value)
            for metric, value in test_scores.items()
        })
        mlflow.set_tag("selected_model", "true")
        mlflow.log_artifact(str(model_path), artifact_path="joblib")

    print(f"MLflow experiment: {tracking_uri}")


if __name__ == "__main__":
    main()
