"""
FastAPI AI & Fusion Service Entry Point.
Runs perception, spatio-temporal fusion, urban memory persistence, and geospatial APIs.
"""

from pathlib import Path
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .routers import ingest, events, fleet, urban, training


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure evidence storage exists and tables are initialized
    evidence_dir = Path("data/evidence")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    init_db()
    print("[AI Service] Database initialized and evidence directory ready.")
    yield


app = FastAPI(
    title="SIH26124 Urban Intelligence AI Service",
    description="Fleet-Sourced Urban Evidence Fusion Platform API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration for Gateway and Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv(
        "AI_ALLOWED_ORIGINS",
        "http://127.0.0.1:5000,http://localhost:5000,http://127.0.0.1:3000,http://localhost:3000"
    ).split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount evidence snapshots for visual inspection
evidence_path = Path("data/evidence")
evidence_path.mkdir(parents=True, exist_ok=True)
app.mount("/evidence", StaticFiles(directory=str(evidence_path)), name="evidence")

# Mount recorded dashcam videos for direct video streaming
recordings_path = Path("data/video_recordings")
recordings_path.mkdir(parents=True, exist_ok=True)
app.mount("/recordings-media", StaticFiles(directory=str(recordings_path)), name="recordings-media")

# Include Routers
app.include_router(ingest.router)
app.include_router(events.router)
app.include_router(fleet.router)
app.include_router(urban.router)
app.include_router(training.router)


@app.get("/")
def root():
    return {
        "service": "SIH26124 Urban Intelligence AI Service",
        "status": "online",
        "endpoints": [
            "/docs",
            "/ingest/packet",
            "/events",
            "/fleet/status",
            "/road-segments/health",
            "/maintenance/queue",
            "/hud/summary"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.ai_service.main:app", host="127.0.0.1", port=8000, reload=True)
