"""Glossary management endpoints."""

from fastapi import APIRouter, HTTPException, Query, Depends
from typing import List, Dict
from sqlalchemy.orm import Session
import uuid
from datetime import datetime

from models.term import (
    Term,
    TermUpdate,
    TermStatus,
    GlossaryResponse,
    GlossaryStats,
)
from db.database import get_db
from db import models

router = APIRouter(prefix="/glossary", tags=["glossary"])


@router.get("/{document_id}", response_model=GlossaryResponse)
async def get_glossary(
    document_id: str,
    status: str = Query("all", description="Filter by status: all, pending, approved, edited, rejected"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Get glossary terms for a document.

    Args:
        document_id: Document ID
        status: Filter by term status
        page: Page number
        per_page: Items per page
        db: Database session

    Returns:
        GlossaryResponse with terms and statistics
    """
    # Get all terms for this document from database
    query = db.query(models.Term).filter(models.Term.document_id == document_id)

    all_terms = query.all()

    # Calculate stats
    stats = GlossaryStats(
        total=len(all_terms),
        pending=len([t for t in all_terms if t.status == "pending"]),
        approved=len([t for t in all_terms if t.status == "approved"]),
        edited=len([t for t in all_terms if t.status == "edited"]),
        rejected=len([t for t in all_terms if t.status == "rejected"]),
    )

    # Filter by status if requested
    if status != "all":
        query = query.filter(models.Term.status == status)

    # Pagination
    doc_terms = query.offset((page - 1) * per_page).limit(per_page).all()

    # Convert DB models to Pydantic models
    terms_list = []
    for t in doc_terms:
        term_dict = {
            "id": t.id,
            "document_id": t.document_id,
            "source_term": t.source_term,
            "target_term": t.target_term,
            "original_proposal": t.original_proposal,
            "source_type": t.source_type,
            "confidence": t.confidence,
            "references": [],  # Database stores as dict, but Pydantic expects list - context extracted separately
            "status": t.status,
            "context": t.references.get("context") if t.references else None,
            "sources": [],
            "created_at": t.created_at,
            "updated_at": t.updated_at,
        }
        terms_list.append(Term(**term_dict))

    return GlossaryResponse(
        total=query.count() if status != "all" else len(all_terms),
        stats=stats,
        terms=terms_list,
    )


@router.put("/{document_id}/{term_id}", response_model=Term)
async def update_term(document_id: str, term_id: str, update: TermUpdate, db: Session = Depends(get_db)):
    """
    Update a term (approve, edit, or reject).

    Args:
        document_id: Document ID
        term_id: Term ID
        update: Term update data
        db: Database session

    Returns:
        Updated term
    """
    # Find term in database
    term = db.query(models.Term).filter(
        models.Term.id == term_id,
        models.Term.document_id == document_id
    ).first()

    if not term:
        raise HTTPException(status_code=404, detail="Term not found")

    # Save original proposal if this is the first edit
    if term.original_proposal is None and update.status == TermStatus.EDITED:
        term.original_proposal = term.target_term

    # Update term
    term.target_term = update.target_term
    term.status = update.status.value
    term.updated_at = datetime.now()

    db.commit()
    db.refresh(term)

    return Term(
        id=term.id,
        document_id=term.document_id,
        source_term=term.source_term,
        target_term=term.target_term,
        original_proposal=term.original_proposal,
        source_type=term.source_type,
        confidence=term.confidence,
        references=[],  # Database stores as dict, but Pydantic expects list - context extracted separately
        status=term.status,
        context=term.references.get("context") if term.references else None,
        sources=[],
        created_at=term.created_at,
        updated_at=term.updated_at,
    )


@router.post("/{document_id}/approve-all")
async def approve_all_pending(document_id: str, db: Session = Depends(get_db)):
    """
    Approve all pending terms for a document.

    Args:
        document_id: Document ID
        db: Database session

    Returns:
        Count of approved terms
    """
    # Get all pending terms for this document
    pending_terms = db.query(models.Term).filter(
        models.Term.document_id == document_id,
        models.Term.status == "pending"
    ).all()

    count = 0
    for term in pending_terms:
        term.status = "approved"
        term.updated_at = datetime.now()
        count += 1

    db.commit()

    return {"message": f"Approved {count} terms", "count": count}
