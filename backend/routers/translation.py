"""Translation job endpoints."""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict
import uuid
from datetime import datetime
import asyncio
import json

from ..models.translation_job import (
    TranslationJob,
    TranslationJobCreate,
    TranslationJobStartResponse,
    TranslationJobStatus,
    TranslationPhase,
    TranslationStats,
)

router = APIRouter(prefix="/translation", tags=["translation"])

# In-memory storage for Sprint 1
translation_jobs_db: Dict[str, dict] = {}
active_websockets: Dict[str, WebSocket] = {}


@router.post("/{document_id}/start", response_model=TranslationJobStartResponse, status_code=202)
async def start_translation(document_id: str, config: TranslationJobCreate):
    """
    Start translation process for a document.

    Args:
        document_id: Document ID
        config: Translation configuration

    Returns:
        TranslationJobStartResponse with job ID
    """
    # Check if document exists (will check actual DB in Sprint 2)
    # For now, just accept any document_id

    # Check if translation already in progress
    for job in translation_jobs_db.values():
        if (
            job["document_id"] == document_id
            and job["status"] == TranslationJobStatus.IN_PROGRESS
        ):
            raise HTTPException(
                status_code=409, detail="Translation already in progress for this document"
            )

    # Create job
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    now = datetime.now()

    job = {
        "id": job_id,
        "document_id": document_id,
        "phase": TranslationPhase.ANALYSIS,
        "status": TranslationJobStatus.IN_PROGRESS,
        "progress": 0.0,
        "current_step": "Starting translation...",
        "stats": {"segments_total": 0, "segments_translated": 0, "terms_extracted": 0},
        "error_message": None,
        "started_at": now,
        "completed_at": None,
        "created_at": now,
    }
    translation_jobs_db[job_id] = job

    # Start background task (placeholder for Sprint 2+)
    # In real implementation, this would trigger the Orchestrator
    asyncio.create_task(_simulate_translation(job_id))

    return TranslationJobStartResponse(
        job_id=job_id,
        document_id=document_id,
        status=TranslationJobStatus.IN_PROGRESS,
        phase=TranslationPhase.ANALYSIS,
    )


@router.get("/{document_id}/status", response_model=TranslationJob)
async def get_translation_status(document_id: str):
    """
    Get translation job status for a document.

    Args:
        document_id: Document ID

    Returns:
        TranslationJob with current status
    """
    # Find job for document
    job = None
    for j in translation_jobs_db.values():
        if j["document_id"] == document_id:
            job = j
            break

    if not job:
        raise HTTPException(status_code=404, detail="No translation job found for this document")

    return TranslationJob(**job)


@router.post("/{document_id}/finalize")
async def finalize_translation(document_id: str):
    """
    Finalize translation after user validation.

    Args:
        document_id: Document ID

    Returns:
        Success message
    """
    # Find job
    job = None
    for j in translation_jobs_db.values():
        if j["document_id"] == document_id:
            job = j
            break

    if not job:
        raise HTTPException(status_code=404, detail="No translation job found")

    if job["status"] != TranslationJobStatus.AWAITING_VALIDATION:
        raise HTTPException(status_code=400, detail="Translation not ready for finalization")

    # Update job status
    job["status"] = TranslationJobStatus.FINALIZING
    job["phase"] = TranslationPhase.IMPLEMENTING
    job["progress"] = 0.9

    # Trigger finalization (placeholder)
    asyncio.create_task(_simulate_finalization(job["id"]))

    return {"message": "Finalization started"}


@router.websocket("/ws/{document_id}")
async def websocket_translation_progress(websocket: WebSocket, document_id: str):
    """
    WebSocket endpoint for real-time translation progress updates.

    Args:
        websocket: WebSocket connection
        document_id: Document ID
    """
    await websocket.accept()
    active_websockets[document_id] = websocket

    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        if document_id in active_websockets:
            del active_websockets[document_id]


# Helper functions for Sprint 1 simulation
async def _simulate_translation(job_id: str):
    """Simulate translation process (placeholder for Sprint 2+)."""
    job = translation_jobs_db[job_id]
    phases = [
        (TranslationPhase.ANALYSIS, 0.2, "Analyzing document structure..."),
        (TranslationPhase.TERM_EXTRACTION, 0.4, "Extracting terms..."),
        (TranslationPhase.RESEARCH, 0.5, "Searching HUDOC and CURIA..."),
        (TranslationPhase.TRANSLATING, 0.9, "Translating segments..."),
    ]

    for phase, progress, step in phases:
        await asyncio.sleep(2)
        job["phase"] = phase
        job["progress"] = progress
        job["current_step"] = step

        # Send WebSocket update
        if job["document_id"] in active_websockets:
            ws = active_websockets[job["document_id"]]
            try:
                await ws.send_json({
                    "type": "progress",
                    "phase": phase,
                    "progress": progress,
                    "current_step": step,
                })
            except:
                pass

    # Move to validation phase
    job["status"] = TranslationJobStatus.AWAITING_VALIDATION
    job["phase"] = TranslationPhase.VALIDATION
    job["progress"] = 0.9


async def _simulate_finalization(job_id: str):
    """Simulate finalization process."""
    job = translation_jobs_db[job_id]
    await asyncio.sleep(2)
    job["phase"] = TranslationPhase.QA
    job["progress"] = 0.95
    await asyncio.sleep(2)
    job["status"] = TranslationJobStatus.COMPLETED
    job["phase"] = TranslationPhase.COMPLETED
    job["progress"] = 1.0
    job["completed_at"] = datetime.now()
