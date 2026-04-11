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
from routers.tm_management import get_tm_manager
from config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/translation", tags=["translation"])

# Global orchestrator instance
orchestrator = None


def get_orchestrator():
    """Get or create orchestrator instance, always using the current global TM Manager."""
    global orchestrator
    tm = get_tm_manager()
    if orchestrator is None:
        orchestrator = Orchestrator(tm_manager=tm)
    else:
        # Always sync with the latest TM Manager (user may have uploaded new TMs)
        orchestrator.tm_manager = tm
        orchestrator.translator.tm_manager = tm
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

    # Allow finalization when awaiting validation OR when completed (re-finalization after more edits)
    allowed_statuses = [TranslationJobStatus.AWAITING_VALIDATION, TranslationJobStatus.COMPLETED]
    if job.status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Translation not ready for finalization. Current status: {job.status}",
        )

    # Update job status
    job.status = TranslationJobStatus.FINALIZING
    job.phase = TranslationPhase.IMPLEMENTING
    job.progress = 0.9
    job.current_step = "Finalizing translation with validated terminology..."
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

            # Callback for live translation updates
            async def on_segment_translated_callback(segment_idx, total_segments, segment):
                logger.info(f"[Job {job_id}] Segment {segment_idx+1}/{total_segments} translated callback")
                progress_pct = 0.5 + (segment_idx + 1) / total_segments * 0.4  # 50% to 90%
                await ws_manager.send_message(
                    {
                        "type": "segment_translated",
                        "segment_index": segment_idx,
                        "total_segments": total_segments,
                        "source_text": segment.get("text", ""),
                        "target_text": segment.get("target_text", ""),
                        "progress": progress_pct
                    },
                    document_id
                )
                logger.info(f"[Job {job_id}] Segment {segment_idx+1} WebSocket message sent")

            # Run quick orchestrator
            logger.info(f"[Job {job_id}] Calling orchestrator.process_quick()")
            result = await orch.process_quick(
                document_id,
                source_path,
                use_hudoc=config.use_hudoc,
                use_curia=config.use_curia,
                use_iate=config.use_iate,
                on_segment_translated=on_segment_translated_callback,
                ws_manager=ws_manager
            )
            logger.info(f"[Job {job_id}] Orchestrator returned - status: {result.status}, segments: {len(result.segments)}")

            if result.status == "error":
                raise Exception(result.error)

            # Save translated segments
            logger.info(f"[Job {job_id}] Starting to save {len(result.segments)} segments to database")
            for idx, segment_data in enumerate(result.segments):
                # Preserve parent_type and other format info in format_metadata
                format_meta = segment_data.get("formatting", segment_data.get("format", {})).copy() if segment_data.get("formatting") or segment_data.get("format") else {}
                if segment_data.get("parent_type"):
                    format_meta["parent_type"] = segment_data.get("parent_type")
                if segment_data.get("footnote_id"):
                    format_meta["footnote_id"] = segment_data.get("footnote_id")
                if segment_data.get("endnote_id"):
                    format_meta["endnote_id"] = segment_data.get("endnote_id")

                db_segment = models.Segment(
                    id=str(uuid.uuid4()),
                    document_id=document_id,
                    index=idx,
                    source_text=segment_data.get("text", ""),
                    target_text=segment_data.get("target_text", ""),
                    section_type=segment_data.get("section_type", "other"),
                    format_metadata=format_meta,
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
            # ============= FULL WORKFLOW (with BATCH validation) =============
            logger.info(f"[Job {job_id}] Starting FULL workflow with progressive batch validation")

            # Phase 1: Analysis
            await ws_manager.broadcast_progress(document_id, "analysis", 0.1, "Analyzing document structure")
            job.phase = TranslationPhase.ANALYSIS
            job.progress = 0.1
            db.commit()

            # Track total segments for progress calculation
            segment_offset = 0  # Track how many segments we've saved

            # Define batch callback - saves terms and segments progressively
            async def on_batch_ready(batch_terms, batch_segments, is_last, batch_num, total_batches):
                nonlocal segment_offset

                from db.database import SessionLocal
                batch_db = SessionLocal()

                try:
                    # Calculate and send progress update
                    # Progress from 0.3 (start) to 0.9 (ready for validation)
                    progress = 0.3 + (batch_num / total_batches) * 0.6
                    await ws_manager.broadcast_progress(
                        document_id,
                        "translating",
                        progress,
                        f"Processing batch {batch_num}/{total_batches}..."
                    )

                    # Save terms from this batch
                    logger.info(f"[Job {job_id}] Batch {batch_num}/{total_batches} ready: {len(batch_terms)} terms, {len(batch_segments)} segments")

                    for term_data in batch_terms:
                        # Prepare references JSON with case law data
                        references = {}

                        # Add case law references from HUDOC, CURIA, IATE
                        if term_data.get("case_law_references"):
                            references["case_law_references"] = term_data.get("case_law_references")
                            references["reference_count"] = term_data.get("reference_count", 0)

                        # NOWE: Dodaj translation_options (wszystkie opcje tłumaczeń)
                        if term_data.get("translation_options"):
                            references["translation_options"] = term_data.get("translation_options")
                            references["options_count"] = term_data.get("options_count", 0)

                        # Legacy support for old format
                        if term_data.get("hudoc_reference"):
                            references["hudoc"] = term_data.get("hudoc_reference")
                        if term_data.get("curia_reference"):
                            references["curia"] = term_data.get("curia_reference")
                        if term_data.get("context"):
                            references["context"] = term_data.get("context")

                        # NOWA LOGIKA: Wybierz domyślne tłumaczenie z opcji
                        # Priorytet: TM > HUDOC > CURIA > IATE > AI Proposal
                        target_term = ""
                        source_type = "proposed"  # default
                        confidence = 0.5  # default

                        translation_options = term_data.get("translation_options", [])
                        if translation_options:
                            # Sortuj opcje według priorytetu
                            priority_order = {"tm_exact": 0, "hudoc": 1, "curia": 2, "iate": 3, "proposed": 4}
                            sorted_options = sorted(
                                translation_options,
                                key=lambda x: (priority_order.get(x.get("source_type", "proposed"), 999), -x.get("confidence", 0))
                            )

                            # Wybierz pierwszą (najwyższą w priorytecie)
                            best_option = sorted_options[0]
                            target_term = best_option.get("term_pl", "")
                            source_type = best_option.get("source_type", "proposed")
                            confidence = best_option.get("confidence", 0.5)
                        else:
                            # Fallback na starą logikę (dla kompatybilności wstecznej)
                            target_term = term_data.get("official_translation", term_data.get("proposed_translation", ""))
                            source_type = term_data.get("translation_source", term_data.get("source_type", "proposed"))
                            confidence = term_data.get("translation_confidence", term_data.get("confidence", 0.5))

                        db_term = models.Term(
                            id=str(uuid.uuid4()),
                            document_id=document_id,
                            source_term=term_data.get("source_term", ""),
                            target_term=target_term,
                            original_proposal=term_data.get("proposed_translation", ""),
                            source_type=source_type,
                            confidence=confidence,
                            references=references if references else None,
                            status="pending",
                        )
                        batch_db.add(db_term)

                    # Save segments from this batch
                    for idx, segment_data in enumerate(batch_segments):
                        # Preserve parent_type and other format info in format_metadata
                        format_meta = segment_data.get("formatting", segment_data.get("format", {})).copy() if segment_data.get("formatting") or segment_data.get("format") else {}
                        if segment_data.get("parent_type"):
                            format_meta["parent_type"] = segment_data.get("parent_type")
                        if segment_data.get("footnote_id"):
                            format_meta["footnote_id"] = segment_data.get("footnote_id")
                        if segment_data.get("endnote_id"):
                            format_meta["endnote_id"] = segment_data.get("endnote_id")

                        db_segment = models.Segment(
                            id=str(uuid.uuid4()),
                            document_id=document_id,
                            index=segment_offset + idx,
                            source_text=segment_data.get("text", ""),
                            target_text=segment_data.get("target_text", ""),
                            section_type=segment_data.get("section_type", "other"),
                            format_metadata=format_meta,
                            status="translated",
                        )
                        batch_db.add(db_segment)

                    batch_db.commit()
                    segment_offset += len(batch_segments)

                    # Notify frontend about new terms available for validation
                    await ws_manager.send_message(
                        {
                            "type": "batch_ready",
                            "data": {
                                "terms_count": len(batch_terms),
                                "segments_count": len(batch_segments),
                                "is_last": is_last,
                                "batch_num": batch_num,
                                "total_batches": total_batches,
                            }
                        },
                        document_id
                    )

                    logger.info(f"[Job {job_id}] Batch {batch_num}/{total_batches} saved: {len(batch_terms)} terms, {len(batch_segments)} segments")

                except Exception as e:
                    logger.error(f"Error in batch callback: {e}", exc_info=True)
                    batch_db.rollback()
                finally:
                    batch_db.close()

            # Phase 2-4: Progressive extraction, research, translation
            await ws_manager.broadcast_progress(
                document_id, "term_extraction", 0.3,
                "Starting batch processing... First batch of terms will be ready soon!"
            )
            job.phase = TranslationPhase.TERM_EXTRACTION
            job.progress = 0.3
            db.commit()

            # Run orchestrator in BATCH mode
            result = await orch.process_in_batches(
                document_id,
                source_path,
                on_batch_ready=on_batch_ready,
                batch_size=10,  # Process 10 segments at a time
                ws_manager=ws_manager
            )

            if result.status == "error":
                raise Exception(result.error)

            # Move to validation phase
            job.status = TranslationJobStatus.AWAITING_VALIDATION
            job.phase = TranslationPhase.VALIDATION
            job.progress = 0.9
            job.current_step = "Awaiting user validation"

            document.status = "validating"

            db.commit()

            await ws_manager.broadcast_progress(
                document_id, "validation", 0.9,
                f"Translation complete. {len(result.terms)} terms ready for validation."
            )

            # Notify frontend that translation is complete and ready for validation
            await ws_manager.broadcast_translation_complete(document_id, job_id)

            logger.info(f"[Job {job_id}] Batch translation complete, awaiting validation")

    except Exception as e:
        logger.error(f"[Job {job_id}] Translation failed: {e}", exc_info=True)

        job = db.query(models.TranslationJob).filter(models.TranslationJob.id == job_id).first()
        if job:
            job.status = TranslationJobStatus.ERROR
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

        segments = []
        for seg in db_segments:
            format_meta = seg.format_metadata or {}
            segment_dict = {
                "text": seg.source_text,
                "translated_text": seg.target_text,
                "source_text": seg.source_text,
                "section_type": seg.section_type,
                "formatting": format_meta,
                "format": format_meta,  # Some code uses "format" key
            }
            # Restore parent_type and note IDs from format_metadata
            if format_meta.get("parent_type"):
                segment_dict["parent_type"] = format_meta["parent_type"]
            if format_meta.get("footnote_id"):
                segment_dict["footnote_id"] = format_meta["footnote_id"]
            if format_meta.get("endnote_id"):
                segment_dict["endnote_id"] = format_meta["endnote_id"]
            segments.append(segment_dict)

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

        # Success - QA issues are included in qa_report but don't block completion
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
            job.status = TranslationJobStatus.ERROR
            job.error_message = str(e)
            job.completed_at = datetime.now()

        db.commit()

        await ws_manager.broadcast_error(document_id, str(e))

    finally:
        db.close()
