"""Listing 6-5: the detector as a FastAPI scoring service.

This wraps the trained model and its scaler behind one endpoint. The live
OpenTelemetry path posts a window of features, the service scales them with the
SAME scaler fit at training time, and returns an anomaly score. That score is
what the Chapter 5 confidence gate reads: detection is one stage of the loop, not
the whole loop. Serving infrastructure at scale is Chapter 11; this is the
minimal working artifact.

The seam that makes it work end to end: run_smoke.py persists the fitted detector
(model, scaler, and column order) to a joblib artifact, and this service loads
that artifact at startup. Point DETECTOR_ARTIFACT at the file if it is not at the
default path.

Run: python run_smoke.py                 # trains and writes artifacts/detector.joblib
     uvicorn serving.score_service:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import joblib
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Where run_smoke.py persisted the fitted detector, scaler, and column order.
ARTIFACT_PATH = os.environ.get("DETECTOR_ARTIFACT", "artifacts/detector.joblib")

# In production these load from the model registry (Part III). Here a module
# global stands in for the trained detector and its fitted scaler.
_STATE: dict = {"scorer": None, "scaler": None, "feature_names": []}


def configure(scorer, scaler, feature_names):
    """Wire in a scoring function f(X)->scores, the scaler, and column order."""
    _STATE.update(scorer=scorer, scaler=scaler, feature_names=list(feature_names))


def load_detector(path=ARTIFACT_PATH):
    """Load the artifact run_smoke.py saved and wire it into the service.

    The saved Isolation Forest scores LOWER for more anomalous points, so the
    scoring function negates score_samples to match the convention the loop reads.
    """
    bundle = joblib.load(path)
    model = bundle["model"]
    configure(lambda x: -model.score_samples(x), bundle["scaler"],
              bundle["feature_names"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.path.exists(ARTIFACT_PATH):
        load_detector()
    yield


app = FastAPI(title="anomaly-detector", lifespan=lifespan)


class ScoreRequest(BaseModel):
    service_name: str
    features: dict[str, float]  # one window of {column: value}


class ScoreResponse(BaseModel):
    service_name: str
    anomaly_score: float


@app.post("/score", response_model=ScoreResponse)
def score(req: ScoreRequest) -> ScoreResponse:
    if _STATE["scorer"] is None:  # artifact missing: /healthz reports ready=false
        raise HTTPException(status_code=503, detail="detector not loaded")
    names = _STATE["feature_names"]
    row = np.array([[req.features.get(n, 0.0) for n in names]], dtype="float32")
    x = _STATE["scaler"].transform(row)
    value = float(_STATE["scorer"](x)[0])
    return ScoreResponse(service_name=req.service_name, anomaly_score=value)


@app.get("/healthz")
def healthz() -> dict:
    return {"ready": _STATE["scorer"] is not None}
