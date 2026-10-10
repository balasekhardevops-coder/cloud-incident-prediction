
"""Serve the trained cloud incident classifier through FastAPI."""

from contextlib import asynccontextmanager
from pathlib import Path

import joblib
import pandas as pd
from fastapi import FastAPI, Request
from pydantic import BaseModel, ConfigDict, Field

try:
    from .preprocess import FEATURE_COLUMNS
except ImportError:
    from preprocess import FEATURE_COLUMNS


MODEL_PATH = (
    Path(__file__).resolve().parents[1]
    / "models"
    / "incident_model.joblib"
)


class TelemetryInput(BaseModel):
    """Current infrastructure metrics sent by an API client."""

    model_config = ConfigDict(
        extra="forbid",
        allow_inf_nan=False
    )

    cpu_usage_pct: float = Field(ge=0, le=100)
    memory_usage_pct: float = Field(ge=0, le=100)
    error_rate_pct: float = Field(ge=0, le=100)
    p95_latency_ms: float = Field(ge=0)
    pod_restarts: int = Field(ge=0)


class PredictionOutput(BaseModel):
    """Response returned to the API client."""

    prediction: int
    incident_probability: float
    prediction_window_minutes: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load the trained model once when the API starts."""

    if not MODEL_PATH.is_file():
        raise RuntimeError(
            f"Model not found: {MODEL_PATH}. "
            "Run python src/train.py first."
        )

    # Load only artifacts from a trusted source
    model = joblib.load(MODEL_PATH)

    if list(model.classes_) != [0, 1]:
        raise RuntimeError(
            "Expected a binary classifier with classes [0, 1]"
        )

    if list(model.feature_names_in_) != FEATURE_COLUMNS:
        raise RuntimeError(
            "Saved model features do not match preprocessing"
        )

    app.state.model = model
    yield


app = FastAPI(
    title="Cloud Incident Prediction API",
    description="Predict an incident within the next 30 minutes.",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": True}


@app.post("/predict", response_model=PredictionOutput)
def predict(payload: TelemetryInput, request: Request):

    features = pd.DataFrame(
        [payload.model_dump()],
        columns=FEATURE_COLUMNS
    )

    model = request.app.state.model

    label = int(model.predict(features)[0])
    probability = float(model.predict_proba(features)[0, 1])

    return PredictionOutput(
        prediction=label,
        incident_probability=round(probability, 4),
        prediction_window_minutes=30,
    )
