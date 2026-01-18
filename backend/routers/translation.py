"""Translation job endpoints with full Orchestrator integration."""

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Dict, List
import uuid
from datetime import datetime
import asyncio
import logging

from models.translation_job import (
    TranslationJob,
    TranslationConfig,
    TranslationJobStartResponse,
    TranslationJobStatus,
    TranslationPhase,
)
from db.database import get_db
from db import models
from agents.orchestrator import Orchestrator
from routers.websocket import get_connection_manager
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/translation", tags=["translation"])

# Global orchestrator instance
orchestrator = None


def get_orchestrator():
    """Get or create orchestrator instance."""
    global orchestrator
    if orchestrator is None:
        orchestrator = Orchestrator()
    return orchestrator


@router.post("/{document_id}/start", response_model=TranslationJobStartResponse, status_code=202)
async def start_translation(
    document_id: str,
    config: TranslationConfig = TranslationConfig(),
    db: Session = Depends(get_db),
):
    """
    Start translation process for a document.

    Args:
        document_id: Document ID from path
        config: Translation configuration
        db: Database session

    Returns:
        TranslationJobStartResponse with job ID
    """

    # Check if document exists
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.status != "uploaded":
        raise HTTPException(
            status_code=400,
            detail=f"Document not ready for translation. Current status: {document.status}",
        )

    # Check if translation already in progress
    existing_job = (
        db.query(models.TranslationJob)
        .filter(
            models.TranslationJob.document_id == document_id,
            models.TranslationJob.status == TranslationJobStatus.IN_PROGRESS,
        )
        .first()
    )

    if existing_job:
        raise HTTPException(
            status_code=409, detail="Translation already in progress for this document"
        )

    # Create translation job
    job = models.TranslationJob(
        id=str(uuid.uuid4()),
        document_id=document_id,
        phase=TranslationPhase.ANALYSIS,
        status=TranslationJobStatus.IN_PROGRESS,
        progress=0.0,
        current_step="Starting translation...",
        started_at=datetime.now(),
    )
    db.add(job)

    # Update document status
    document.status = "translating"

    db.commit()
    db.refresh(job)

    # Start translation in background
    asyncio.create_task(
        _run_translation(job.id, document_id, str(document.original_path), config)
    )

    logger.info(f"Translation started for document {document_id}, job {job.id}")

    return TranslationJobStartResponse(
        job_id=job.id,
        document_id=document_id,
        status=job.status,
        phase=job.phase,
    )


@router.get("/{document_id}/status", response_model=TranslationJob)
async def get_translation_status(document_id: str, db: Session = Depends(get_db)):
    """
    Get translation job status for a document.

    Args:
        document_id: Document ID
        db: Database session

    Returns:
        TranslationJob with current status
    """
    # Find most recent job for document
    job = (
        db.query(models.TranslationJob)
        .filter(models.TranslationJob.document_id == document_id)
        .order_by(models.TranslationJob.created_at.desc())
        .first()
    )

    if not job:
        raise HTTPException(
            status_code=404, detail="No translation job found for this document"
        )

    return TranslationJob(
        id=job.id,
        document_id=job.document_id,
        phase=job.phase,
        status=job.status,
        progress=job.progress,
        current_step=job.current_step or "",
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
        created_at=job.created_at,
        stats={},
    )


@router.post("/{document_id}/finalize")
async def finalize_translation(document_id: str, db: Session = Depends(get_db)):
    """
    Finalize translation after user validation (Sprint 5).

    This triggers:
    1. Change Implementer - applies validated term changes
    2. QA Reviewer - quality control
    3. DOCX Reconstruction
    4. TM Auto-update

    Args:
        document_id: Document ID
        db: Database session

    Returns:
        Finalization result with QA report
    """
    # Find document
    document = db.query(models.Document).filter(models.Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Find translation job
    job = (
        db.query(models.TranslationJob)
        .filter(models.TranslationJob.document_id == document_id)
        .order_by(models.TranslationJob.created_at.desc())
        .first()
    )

    if not job:
        raise HTTPException(status_code=404, detail="No translation job found")

    if job.status != TranslationJobStatus.AWAITING_VALIDATION:
        raise HTTPException(
            status_code=400,
            detail=f"Translation not ready for finalization. Current status: {job.status}",
        )

    # Update job status
    job.status = TranslationJobStatus.FINALIZING
    job.phase = TranslationPhase.IMPLEMENTING
    job.progress = 0.9
    job.current_step = "Finalizing translation..."
    db.commit()

    # Start finalization in background
    asyncio.create_task(_run_finalization(job.id, document_id, db))

    logger.info(f"Finalization started for document {document_id}")

    return {
        "message": "Finalization started",
        "document_id": document_id,
        "job_id": job.id,
    }


async def _run_translation(
    job_id: str,
    document_id: str,
    source_path: str,
    config: TranslationConfig,
):
    """
    Run the actual translation using Orchestrator.

    Args:
        job_id: Translation job ID
        document_id: Document ID
        source_path: Path to source document
        config: Translation configuration
    """
    from db.database import SessionLocal

    db = SessionLocal()
    ws_manager = get_connection_manager()
    orch = get_orchestrator()

    try:
        # Get job
        job = db.query(models.TranslationJob).filter(models.TranslationJob.id == job_id).first()
        document = db.query(models.Document).filter(models.Document.id == document_id).first()

        # Check workflow mode
        from models.translation_job import TranslationWorkflowMode

        if config.workflow_mode == TranslationWorkflowMode.QUICK:
            # ============= QUICK WORKFLOW =============
            logger.info(f"[Job {job_id}] Starting QUICK workflow (no term validation)")

            # Phase 1: Analysis
            await ws_manager.broadcast_progress(document_id, "analysis", 0.2, "Analyzing document structure")
            job.phase = TranslationPhase.ANALYSIS
            job.progress = 0.2
            db.commit()

            # Phase 2: Translation
            await ws_manager.broadcast_progress(document_id, "translating", 0.5, "Translating with TM")
            job.phase = TranslationPhase.TRANSLATING
            job.progress = 0.5
            db.commit()

            # Run quick orchestrator
            result = await orch.process_quick(document_id, source_path)

            if result.status == "error":
                raise Exception(result.error)

            # Save translated segments
            logger.info(f"[Job {job_id}] Saving {len(result.segments)} segments")
            for idx, segment_data in enumerate(result.segments):
                db_segment = models.Segment(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    index=idx,
                    source_text=segment_data.get("text", ""),
                    target_text=segment_data.get("target_text", ""),
                    section_type=segment_data.get("section_type", "other"),
                    format_metadata=segment_data.get("formatting", {}),
                    status="translated",
                )
                db.add(db_segment)

            db.commit()

            # Mark as completed immediately
            job.status = TranslationJobStatus.COMPLETED
            job.phase = TranslationPhase.COMPLETED
            job.progress = 1.0
            job.current_step = "Translation complete"
            job.completed_at = datetime.now()

            document.status = "completed"
            document.translated_path = result.translated_path

            db.commit()

            await ws_manager.broadcast_translation_complete(document_id, job_id)
            logger.info(f"[Job {job_id}] Quick translation completed")

        else:
            # ============= FULL WORKFLOW (with validation) =============
            logger.info(f"[Job {job_id}] Starting FULL workflow (with term validation)")

            # Phase 1: Analysis
            await ws_manager.broadcast_progress(document_id, "analysis", 0.1, "Analyzing document structure")
            job.phase = TranslationPhase.ANALYSIS
            job.progress = 0.1
            db.commit()

            # Phase 2: Term Extraction
            await ws_manager.broadcast_progress(document_id, "term_extraction", 0.3, "Extracting terminology")
            job.phase = TranslationPhase.TERM_EXTRACTION
            job.progress = 0.3
            db.commit()

            # Phase 3: External Research
            if config.use_hudoc or config.use_curia:
                await ws_manager.broadcast_progress(document_id, "research", 0.5, "Searching HUDOC and CURIA")
                job.phase = TranslationPhase.RESEARCH
                job.progress = 0.5
                db.commit()

            # Phase 4: Translation
            await ws_manager.broadcast_progress(document_id, "translating", 0.7, "Translating segments")
            job.phase = TranslationPhase.TRANSLATING
            job.progress = 0.7
            db.commit()

            # Run orchestrator
            result = await orch.process(document_id, source_path)

            if result.status == "error":
                raise Exception(result.error)

            # Save extracted terms to database for user validation
            logger.info(f"[Job {job_id}] Saving {len(result.terms)} terms to database")
            for term_data in result.terms:
                db_term = models.Term(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    source_term=term_data.get("source_term", ""),
                    target_term=term_data.get("proposed_translation", ""),
                    original_proposal=term_data.get("proposed_translation", ""),
                    context=term_data.get("context", ""),
                    hudoc_reference=term_data.get("hudoc_reference"),
                    curia_reference=term_data.get("curia_reference"),
                    confidence_score=term_data.get("confidence_score", 0.0),
                    status="pending",  # User needs to validate
                )
                db.add(db_term)

            db.commit()
            logger.info(f"[Job {job_id}] Saved {len(result.terms)} terms for validation")

            # Save translated segments to database
            logger.info(f"[Job {job_id}] Saving {len(result.segments)} segments to database")
            for idx, segment_data in enumerate(result.segments):
                db_segment = models.Segment(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    index=idx,
                    source_text=segment_data.get("text", ""),
                    target_text=segment_data.get("target_text", ""),
                    section_type=segment_data.get("section_type", "other"),
                    format_metadata=segment_data.get("formatting", {}),
                    status="translated",
                )
                db.add(db_segment)

            db.commit()
            logger.info(f"[Job {job_id}] Saved {len(result.segments)} segments")

            # Move to validation phase
            job.status = TranslationJobStatus.AWAITING_VALIDATION
            job.phase = TranslationPhase.VALIDATION
            job.progress = 0.9
            job.current_step = "Awaiting user validation"

            document.status = "validating"

            db.commit()

            await ws_manager.broadcast_progress(
                document_id, "validation", 0.9, "Translation complete. Please validate terms."
            )

            # Notify frontend that translation is complete and ready for validation
            await ws_manager.broadcast_translation_complete(document_id, job_id)

            logger.info(f"[Job {job_id}] Translation complete, awaiting validation")

    except Exception as e:
        logger.error(f"[Job {job_id}] Translation failed: {e}", exc_info=True)

        job = db.query(models.TranslationJob).filter(models.TranslationJob.id == job_id).first()
        if job:
            job.status = TranslationJobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now()

        document = db.query(models.Document).filter(models.Document.id == document_id).first()
        if document:
            document.status = "error"

        db.commit()

        await ws_manager.broadcast_error(document_id, str(e))

    finally:
        db.close()


async def _run_finalization(job_id: str, document_id: str, db: Session):
    """
    Run finalization with Change Implementer and QA Reviewer (Sprint 5).

    Args:
        job_id: Translation job ID
        document_id: Document ID
        db: Database session
    """
    from db.database import SessionLocal

    db = SessionLocal()
    ws_manager = get_connection_manager()
    orch = get_orchestrator()

    try:
        logger.info(f"[Job {job_id}] Starting Sprint 5 finalization")

        job = db.query(models.TranslationJob).filter(models.TranslationJob.id == job_id).first()
        document = db.query(models.Document).filter(models.Document.id == document_id).first()

        # Get validated terms from database
        validated_terms = db.query(models.Term).filter(models.Term.document_id == document_id).all()

        terms_data = [
            {
                "id": term.id,
                "source_term": term.source_term,
                "target_term": term.target_term,
                "status": term.status,
                "original_proposal": term.original_proposal,
            }
            for term in validated_terms
        ]

        # Get segments from database
        db_segments = (
            db.query(models.Segment)
            .filter(models.Segment.document_id == document_id)
            .order_by(models.Segment.index)
            .all()
        )

        segments = [
            {
                "text": seg.source_text,
                "translated_text": seg.target_text,
                "source_text": seg.source_text,
                "section_type": seg.section_type,
                "formatting": seg.format_metadata or {},
            }
            for seg in db_segments
        ]

        # Get document metadata
        metadata = {
            "filename": document.filename,
            "original_path": str(document.original_path),
        }

        # Call Orchestrator.finalize()
        await ws_manager.broadcast_progress(document_id, "implementing", 0.92, "Implementing changes")

        result = await orch.finalize(
            document_id=document_id,
            segments=segments,
            validated_terms=terms_data,
            original_metadata=metadata,
        )

        if result.get("status") == "error":
            raise Exception(result.get("error", "Finalization failed"))

        if result.get("status") == "qa_failed":
            # QA found critical issues
            job.status = TranslationJobStatus.AWAITING_VALIDATION
            job.current_step = "QA review failed - please review issues"
            job.error_message = result.get("message")
            db.commit()

            await ws_manager.broadcast_error(
                document_id, "QA review found critical issues. Please review."
            )

            logger.warning(f"[Job {job_id}] QA review failed")
            return

        # Success!
        job.status = TranslationJobStatus.COMPLETED
        job.phase = TranslationPhase.COMPLETED
        job.progress = 1.0
        job.current_step = "Translation complete"
        job.completed_at = datetime.now()

        document.status = "completed"
        document.translated_path = result.get("translated_path")

        db.commit()

        await ws_manager.broadcast_translation_complete(document_id, job_id)

        logger.info(
            f"[Job {job_id}] Finalization complete. "
            f"TM updated: {result.get('tm_updated', 0)} terms"
        )

    except Exception as e:
        logger.error(f"[Job {job_id}] Finalization failed: {e}", exc_info=True)

        job = db.query(models.TranslationJob).filter(models.TranslationJob.id == job_id).first()
        if job:
            job.status = TranslationJobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now()

        db.commit()

        await ws_manager.broadcast_error(document_id, str(e))

    finally:
        db.close()
