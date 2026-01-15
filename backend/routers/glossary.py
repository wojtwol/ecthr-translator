"""Glossary management endpoints."""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict
import uuid
from datetime import datetime

from ..models.term import (
    Term,
    TermUpdate,
    TermStatus,
    GlossaryResponse,
    GlossaryStats,
)

router = APIRouter(prefix="/glossary", tags=["glossary"])

# In-memory storage for Sprint 1
terms_db: Dict[str, dict] = {}


@router.get("/{document_id}", response_model=GlossaryResponse)
async def get_glossary(
    document_id: str,
    status: str = Query("all", description="Filter by status: all, pending, approved, edited, rejected"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
):
    """
    Get glossary terms for a document.

    Args:
        document_id: Document ID
        status: Filter by term status
        page: Page number
        per_page: Items per page

    Returns:
        GlossaryResponse with terms and statistics
    """
    # Filter terms for this document
    doc_terms = [t for t in terms_db.values() if t["document_id"] == document_id]

    # Calculate stats
    stats = GlossaryStats(
        total=len(doc_terms),
        pending=len([t for t in doc_terms if t["status"] == TermStatus.PENDING]),
        approved=len([t for t in doc_terms if t["status"] == TermStatus.APPROVED]),
        edited=len([t for t in doc_terms if t["status"] == TermStatus.EDITED]),
        rejected=len([t for t in doc_terms if t["status"] == TermStatus.REJECTED]),
    )

    # Filter by status if requested
    if status != "all":
        try:
            status_enum = TermStatus(status)
            doc_terms = [t for t in doc_terms if t["status"] == status_enum]
        except ValueError:
            pass

    # Pagination
    start = (page - 1) * per_page
    end = start + per_page
    paginated_terms = doc_terms[start:end]

    return GlossaryResponse(
        total=len(doc_terms),
        stats=stats,
        terms=[Term(**t) for t in paginated_terms],
    )


@router.put("/{document_id}/{term_id}", response_model=Term)
async def update_term(document_id: str, term_id: str, update: TermUpdate):
    """
    Update a term (approve, edit, or reject).

    Args:
        document_id: Document ID
        term_id: Term ID
        update: Term update data

    Returns:
        Updated term
    """
    if term_id not in terms_db:
        raise HTTPException(status_code=404, detail="Term not found")

    term = terms_db[term_id]

    if term["document_id"] != document_id:
        raise HTTPException(status_code=404, detail="Term not found in this document")

    # Save original proposal if this is the first edit
    if term["original_proposal"] is None and update.status == TermStatus.EDITED:
        term["original_proposal"] = term["target_term"]

    # Update term
    term["target_term"] = update.target_term
    term["status"] = update.status
    term["updated_at"] = datetime.now()

    return Term(**term)


@router.post("/{document_id}/approve-all")
async def approve_all_pending(document_id: str):
    """
    Approve all pending terms for a document.

    Args:
        document_id: Document ID

    Returns:
        Count of approved terms
    """
    doc_terms = [t for t in terms_db.values() if t["document_id"] == document_id]
    pending_terms = [t for t in doc_terms if t["status"] == TermStatus.PENDING]

    count = 0
    for term in pending_terms:
        term["status"] = TermStatus.APPROVED
        term["updated_at"] = datetime.now()
        count += 1

    return {"message": f"Approved {count} terms", "count": count}
