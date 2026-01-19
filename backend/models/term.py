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

    # Source breakdown
    from_hudoc: int = 0
    from_curia: int = 0
    from_tm_exact: int = 0
    from_tm_fuzzy: int = 0
    from_proposed: int = 0


class GlossaryResponse(BaseModel):
    """Response with list of terms and statistics."""

    total: int
    stats: GlossaryStats
    terms: List[Term]


class SourceReportItem(BaseModel):
    """Single term with source information for reporting."""

    source_term: str
    target_term: Optional[str] = None
    source_type: TermSource
    case_name: Optional[str] = None
    case_url: Optional[str] = None
    context: Optional[str] = None
    status: TermStatus


class SourceReport(BaseModel):
    """Detailed report of term sources."""

    hudoc_terms: List[SourceReportItem] = []
    curia_terms: List[SourceReportItem] = []
    tm_exact_terms: List[SourceReportItem] = []
    tm_fuzzy_terms: List[SourceReportItem] = []
    proposed_terms: List[SourceReportItem] = []
