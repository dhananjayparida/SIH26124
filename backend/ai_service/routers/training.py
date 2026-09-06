"""
FastAPI Router for Active Learning, Model Training, Video Recordings & Defect Records (SIH26124).
"""

import threading
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, Query, HTTPException
from fastapi.responses import FileResponse
from typing import Dict, Any, Optional

from ai_engine.training.trainer import global_model_trainer
from ai_engine.training.dataset_manager import global_dataset_manager
from ai_engine.perception.video_recorder import global_video_recorder, RECORDINGS_DIR
from ai_engine.perception.defect_recorder import global_defect_ledger

router = APIRouter(prefix="/model", tags=["Model Training, Recordings & Defect Records"])


def _run_training_worker(epochs: int, batch_size: int, dataset_type: str):
    global_model_trainer.train(epochs=epochs, batch_size=batch_size, dataset_type=dataset_type)


@router.post("/train")
def trigger_training(
    epochs: int = Query(default=5, ge=1, le=100, description="Number of training epochs"),
    batch_size: int = Query(default=8, ge=1, le=64, description="Training batch size"),
    dataset: str = Query(default="best", description="'best' (5-class benchmark) or 'active'")
):
    """
    Triggers asynchronous fine-tuning on the best road safety dataset
    (potholes, missing zebra crossings, vehicles).
    """
    if global_model_trainer.training_status["is_training"]:
        return {
            "status": "in_progress",
            "message": "Model training is already running",
            "progress": global_model_trainer.training_status
        }

    t = threading.Thread(
        target=_run_training_worker,
        args=(epochs, batch_size, dataset),
        daemon=True
    )
    t.start()

    return {
        "status": "started",
        "message": f"Training initiated on {epochs} epochs using {dataset} dataset",
        "epochs": epochs,
        "batch_size": batch_size,
        "dataset": dataset
    }


@router.get("/training-status")
def get_training_status() -> Dict[str, Any]:
    """
    Returns live training progress, loss, and evaluation metrics.
    """
    return global_model_trainer.training_status


@router.post("/dataset/prepare")
def prepare_best_dataset():
    """
    Generates or verifies the curated 5-class benchmark dataset and writes data.yaml.
    """
    yaml_path = global_dataset_manager.prepare_dataset()
    return {
        "status": "success",
        "data_yaml": str(yaml_path),
        "classes": list(global_dataset_manager.dataset_dir.parent.glob("**/*")) if False else [
            "pothole", "crack", "no_zebracrossing", "zebra_crossing", "vehicle"
        ]
    }


# ==========================================
# VIDEO RECORDINGS ENDPOINTS
# ==========================================

@router.get("/recordings")
def list_video_recordings():
    """
    Lists all saved mobile dashcam MP4/AVI video recordings with duration and defect stats.
    """
    recordings = global_video_recorder.list_recordings()
    return {
        "recordings": recordings,
        "total": len(recordings)
    }


@router.get("/recordings/{filename}")
def get_video_recording(filename: str):
    """
    Streams or downloads a specific recorded video file.
    """
    file_path = RECORDINGS_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Recording {filename} not found")

    media_type = "video/mp4" if filename.endswith(".mp4") else "video/x-msvideo"
    return FileResponse(path=file_path, media_type=media_type, filename=filename)


@router.post("/recordings/finalize")
def finalize_video_recordings():
    """
    Forces immediate finalization and disk flush of any active recording sessions.
    """
    global_video_recorder.finalize_all()
    return {
        "status": "success",
        "message": "All active video recording sessions finalized and saved."
    }


# ==========================================
# DEFECT RECORDS LEDGER ENDPOINTS
# ==========================================

@router.get("/defect-records")
def list_defect_records(
    defect_type: Optional[str] = Query(default=None, description="Filter by defect type: pothole, no_zebracrossing, vehicle"),
    severity: Optional[str] = Query(default=None, description="Filter by severity: LOW, MEDIUM, HIGH"),
    device_id: Optional[str] = Query(default=None, description="Filter by capturing vehicle device ID"),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0, description="Minimum confidence threshold"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0)
):
    """
    Queries persistent defect records (potholes, missing zebra crossings, vehicles).
    """
    records = global_defect_ledger.list_defects(
        defect_type=defect_type,
        severity=severity,
        device_id=device_id,
        min_confidence=min_confidence,
        limit=limit,
        offset=offset
    )
    return {
        "records": records,
        "count": len(records),
        "limit": limit,
        "offset": offset
    }


@router.get("/defect-records/summary")
def get_defect_records_summary():
    """
    Returns aggregated defect metrics (potholes, missing zebra crossings, detected vehicles).
    """
    return global_defect_ledger.get_summary()
