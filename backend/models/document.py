"""Document models."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from enum import Enum


class DocumentStatus(str, Enum):
    """Document processing status."""

    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    TRANSLATING = "translating"
    VALIDATING = "validating"
    COMPLETED = "completed"
    ERROR = "error"


class DocumentCreate(BaseModel):
    """Document creation request."""

    filename: str
    original_path: str


class Document(BaseModel):
    """Document response model."""

    id: str
    filename: str
    original_path: str
    translated_path: Optional[str] = None
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    """Response after uploading a document."""

    id: str
    filename: str
    status: DocumentStatus
    created_at: datetime
