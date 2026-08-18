"""
ML Metrics API — exposes pre-trained model evaluation metrics and retraining endpoint.

GET  /api/ml/metrics  — returns the contents of ml/model_metrics.json
POST /api/ml/train    — triggers retraining via train_models.py
"""
import json
import logging
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ml", tags=["ML — Anomaly Detection"])

# Resolve paths relative to this file
_BACKEND_DIR = Path(__file__).parent.parent          # backend/
_ML_DIR      = _BACKEND_DIR.parent / "ml"            # ml/
_METRICS_PATH = _ML_DIR / "model_metrics.json"
_TRAIN_SCRIPT = _ML_DIR / "train_models.py"


@router.get("/metrics", summary="Get ML model evaluation metrics")
async def get_ml_metrics():
    """
    Returns the latest model_metrics.json produced by train_models.py.

    Includes IsolationForest (precision, recall, F1, ROC-AUC) and
    RandomForestClassifier (weighted F1, accuracy, per-class F1, confusion matrix).
    """
    if not _METRICS_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                "model_metrics.json not found. "
                "Run POST /api/ml/train to generate it."
            ),
        )
    try:
        with open(_METRICS_PATH) as f:
            metrics = json.load(f)
        return JSONResponse(content=metrics)
    except Exception as e:
        logger.exception("Failed to read model_metrics.json")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/train", summary="Trigger ML model retraining")
async def trigger_training():
    """
    Runs train_models.py synchronously and returns the resulting metrics.

    Retrains both IsolationForest and RandomForestClassifier on 2000 synthetic
    pipeline-run records, saves all pkl artefacts, and updates model_metrics.json.
    """
    if not _TRAIN_SCRIPT.exists():
        raise HTTPException(
            status_code=500,
            detail=f"Training script not found at {_TRAIN_SCRIPT}",
        )
    try:
        result = subprocess.run(
            [sys.executable, str(_TRAIN_SCRIPT)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            logger.error("train_models.py failed:\n%s", result.stderr)
            raise HTTPException(
                status_code=500,
                detail={"error": "Training failed", "stderr": result.stderr[-2000:]},
            )

        # Load and return fresh metrics
        if _METRICS_PATH.exists():
            with open(_METRICS_PATH) as f:
                metrics = json.load(f)
        else:
            metrics = {}

        return JSONResponse(
            content={
                "status": "ok",
                "message": "Models retrained successfully",
                "stdout": result.stdout[-3000:],
                "metrics": metrics,
            }
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=504, detail="Training timed out (120s limit)")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error during retraining")
        raise HTTPException(status_code=500, detail=str(e))
