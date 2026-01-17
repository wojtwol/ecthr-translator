"""Document management endpoints."""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import Optional
import uuid
from datetime import datetime
from pathlib import Path

from models.document import (
    Document as DocumentSchema,
    DocumentUploadResponse,
    DocumentStatus,
)
from models.document_stats import DocumentStats
from db.database import get_db
from db import models
from config import settings
from agents.format_handler import FormatHandler

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload a DOCX document for translation.

    Args:
        file: DOCX file to upload
        db: Database session

    Returns:
        DocumentUploadResponse with document ID and status
    """
    # Validate file extension
    if not file.filename.endswith(".docx"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file format. Only .docx files are allowed.",
        )

    # Generate document ID
    doc_id = f"doc_{uuid.uuid4().hex[:12]}"

    # Save file
    file_path = settings.upload_path / f"{doc_id}_{file.filename}"
    content = await file.read()
    file_path.write_bytes(content)

    # Create document record in database
    db_document = models.Document(
        id=doc_id,
        filename=file.filename,
        original_path=str(file_path),
        status=DocumentStatus.UPLOADED.value,
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)

    return DocumentUploadResponse(
        id=db_document.id,
        filename=db_document.filename,
        status=DocumentStatus(db_document.status),
        created_at=db_document.created_at,
    )


@router.get("/{document_id}", response_model=DocumentSchema)
async def get_document(document_id: str, db: Session = Depends(get_db)):
    """
    Get document status and metadata.

    Args:
        document_id: Document ID
        db: Database session

    Returns:
        Document with current status
    """
    db_document = db.query(models.Document).filter(models.Document.id == document_id).first()

    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")

    return db_document


@router.get("/{document_id}/analyze", response_model=DocumentStats)
async def analyze_document(document_id: str, db: Session = Depends(get_db)):
    """
    Analyze document and return statistics (word count, segments, etc.).

    Args:
        document_id: Document ID
        db: Database session

    Returns:
        DocumentStats with analysis results
    """
    db_document = db.query(models.Document).filter(models.Document.id == document_id).first()

    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        # Use FormatHandler to extract document structure
        handler = FormatHandler()
        extracted = handler.extract(db_document.original_path)

        segments = extracted.get("segments", [])

        # Calculate statistics
        total_words = 0
        total_chars = 0

        for segment in segments:
            text = segment.get("text", "")
            total_words += len(text.split())
            total_chars += len(text)

        # Estimate translation time (rough: ~250 words per minute for automated translation)
        estimated_time = max(1, int(total_words / 250))

        return DocumentStats(
            total_segments=len(segments),
            total_words=total_words,
            total_characters=total_chars,
            estimated_translation_time_minutes=estimated_time
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to analyze document: {str(e)}"
        )


@router.get("/{document_id}/download")
async def download_document(document_id: str, db: Session = Depends(get_db)):
    """
    Download translated document.

    Args:
        document_id: Document ID
        db: Database session

    Returns:
        Translated DOCX file
    """
    db_document = db.query(models.Document).filter(models.Document.id == document_id).first()

    if not db_document:
        raise HTTPException(status_code=404, detail="Document not found")

    if db_document.status != DocumentStatus.COMPLETED.value:
        raise HTTPException(
            status_code=400, detail="Document translation not completed yet"
        )

    if not db_document.translated_path:
        raise HTTPException(status_code=404, detail="Translated file not found")

    file_path = Path(db_document.translated_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Translated file not found")

    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"translated_{db_document.filename}",
    )
