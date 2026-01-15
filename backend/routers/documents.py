"""Document management endpoints."""

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from typing import Optional
import uuid
from datetime import datetime
from pathlib import Path

from ..models.document import (
    Document,
    DocumentUploadResponse,
    DocumentStatus,
)
from ..config import settings

router = APIRouter(prefix="/documents", tags=["documents"])

# In-memory storage for Sprint 1 (will be replaced with database in Sprint 2)
documents_db = {}


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a DOCX document for translation.

    Args:
        file: DOCX file to upload

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

    # Create document record
    now = datetime.now()
    doc = {
        "id": doc_id,
        "filename": file.filename,
        "original_path": str(file_path),
        "translated_path": None,
        "status": DocumentStatus.UPLOADED,
        "created_at": now,
        "updated_at": now,
    }
    documents_db[doc_id] = doc

    return DocumentUploadResponse(
        id=doc_id,
        filename=file.filename,
        status=DocumentStatus.UPLOADED,
        created_at=now,
    )


@router.get("/{document_id}", response_model=Document)
async def get_document(document_id: str):
    """
    Get document status and metadata.

    Args:
        document_id: Document ID

    Returns:
        Document with current status
    """
    if document_id not in documents_db:
        raise HTTPException(status_code=404, detail="Document not found")

    return Document(**documents_db[document_id])


@router.get("/{document_id}/download")
async def download_document(document_id: str):
    """
    Download translated document.

    Args:
        document_id: Document ID

    Returns:
        Translated DOCX file
    """
    if document_id not in documents_db:
        raise HTTPException(status_code=404, detail="Document not found")

    doc = documents_db[document_id]

    if doc["status"] != DocumentStatus.COMPLETED:
        raise HTTPException(
            status_code=400, detail="Document translation not completed yet"
        )

    if not doc["translated_path"]:
        raise HTTPException(status_code=404, detail="Translated file not found")

    file_path = Path(doc["translated_path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Translated file not found")

    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"translated_{doc['filename']}",
    )
