"""Segment models."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class SectionType(str, Enum):
    """Type of section in ECTHR judgment."""

    PROCEDURE = "procedure"
    FACTS = "facts"
    LAW = "law"
    OPERATIVE = "operative"
    OTHER = "other"


class SegmentStatus(str, Enum):
    """Segment translation status."""

    PENDING = "pending"
    TRANSLATED = "translated"
    REVIEWED = "reviewed"


class TermPosition(BaseModel):
    """Position of a term in segment text."""

    term_id: str
    start: int
    end: int


class SegmentCreate(BaseModel):
    """Segment creation request."""

    document_id: str
    index: int
    source_text: str
    section_type: SectionType
    format_metadata: Optional[Dict[str, Any]] = None


class Segment(BaseModel):
    """Segment response model."""

    id: str
    document_id: str
    index: int
    source_text: str
    target_text: Optional[str] = None
    section_type: SectionType
    format_metadata: Optional[Dict[str, Any]] = None
    status: SegmentStatus
    terms_used: Optional[List[TermPosition]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PreviewSegment(BaseModel):
    """Segment for translation preview."""

    id: str
    section_type: SectionType
    source_text: str
    target_text: str
    terms_used: List[TermPosition]


class PreviewResponse(BaseModel):
    """Response with translation preview."""

    segments: List[PreviewSegment]
