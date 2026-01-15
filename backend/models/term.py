"""Term models."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List
from enum import Enum


class TermSource(str, Enum):
    """Source of the term translation."""

    TM_EXACT = "tm_exact"
    TM_FUZZY = "tm_fuzzy"
    HUDOC = "hudoc"
    CURIA = "curia"
    PROPOSED = "proposed"


class TermStatus(str, Enum):
    """Term validation status."""

    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    REJECTED = "rejected"


class TermReference(BaseModel):
    """Reference to source of term translation."""

    source: str
    case_name: Optional[str] = None
    url: Optional[str] = None
    confidence: Optional[float] = None


class TermCreate(BaseModel):
    """Term creation request."""

    document_id: str
    source_term: str
    target_term: Optional[str] = None
    source_type: TermSource
    confidence: float
    references: Optional[List[TermReference]] = None


class Term(BaseModel):
    """Term response model."""

    id: str
    document_id: str
    source_term: str
    target_term: Optional[str] = None
    source_type: TermSource
    confidence: float
    status: TermStatus
    original_proposal: Optional[str] = None
    references: Optional[List[TermReference]] = None
    occurrences: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TermUpdate(BaseModel):
    """Term update request."""

    target_term: str
    status: TermStatus


class GlossaryStats(BaseModel):
    """Statistics about terms in a glossary."""

    total: int
    pending: int
    approved: int
    edited: int
    rejected: int


class GlossaryResponse(BaseModel):
    """Response with list of terms and statistics."""

    total: int
    stats: GlossaryStats
    terms: List[Term]
