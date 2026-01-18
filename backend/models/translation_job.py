"""Translation job models."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class TranslationPhase(str, Enum):
    """Phase of translation process."""

    ANALYSIS = "analysis"
    TERM_EXTRACTION = "term_extraction"
    RESEARCH = "research"
    TRANSLATING = "translating"
    VALIDATION = "validation"
    IMPLEMENTING = "implementing"
    QA = "qa"
    COMPLETED = "completed"


class TranslationJobStatus(str, Enum):
    """Overall job status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    AWAITING_VALIDATION = "awaiting_validation"
    FINALIZING = "finalizing"
    COMPLETED = "completed"
    ERROR = "error"


class TranslationWorkflowMode(str, Enum):
    """Translation workflow mode."""

    FULL = "full"  # Full workflow with term extraction and validation
    QUICK = "quick"  # Quick translation using only TM, HUDOC, CURIA - no validation


class TranslationConfig(BaseModel):
    """Configuration for translation job."""

    language_pair: str = "EN-PL"
    workflow_mode: TranslationWorkflowMode = TranslationWorkflowMode.FULL
    use_hudoc: bool = True
    use_curia: bool = True
    fuzzy_threshold: float = 0.75


class TranslationJobCreate(BaseModel):
    """Translation job creation request."""

    document_id: str
    config: Optional[TranslationConfig] = TranslationConfig()


class TranslationStats(BaseModel):
    """Statistics about translation progress."""

    segments_total: int = 0
    segments_translated: int = 0
    terms_extracted: int = 0


class TranslationJob(BaseModel):
    """Translation job response model."""

    id: str
    document_id: str
    phase: TranslationPhase
    status: TranslationJobStatus
    progress: float
    current_step: Optional[str] = None
    stats: Optional[TranslationStats] = None
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TranslationJobStartResponse(BaseModel):
    """Response after starting translation."""

    job_id: str
    document_id: str
    status: TranslationJobStatus
    phase: TranslationPhase


class WebSocketMessage(BaseModel):
    """WebSocket message format."""

    type: str
    data: Dict[str, Any]
