"""SQLAlchemy ORM models."""

from sqlalchemy import Column, String, Text, Float, Integer, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func
from db.database import Base


class Document(Base):
    """Document model."""

    __tablename__ = "documents"

    id = Column(String(50), primary_key=True)
    filename = Column(String(255), nullable=False)
    original_path = Column(String(500), nullable=False)
    translated_path = Column(String(500), nullable=True)
    status = Column(String(50), default="uploaded")  # uploaded, analyzing, translating, validating, completed, error
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Segment(Base):
    """Segment model."""

    __tablename__ = "segments"

    id = Column(String(50), primary_key=True)
    document_id = Column(String(50), ForeignKey("documents.id"), nullable=False)
    index = Column(Integer, nullable=False)
    source_text = Column(Text, nullable=False)
    target_text = Column(Text, nullable=True)
    section_type = Column(String(50), nullable=True)  # procedure, facts, law, operative, other
    format_metadata = Column(JSON, nullable=True)
    status = Column(String(50), default="pending")  # pending, translated, reviewed
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Term(Base):
    """Term model."""

    __tablename__ = "terms"

    id = Column(String(50), primary_key=True)
    document_id = Column(String(50), ForeignKey("documents.id"), nullable=False)
    source_term = Column(String(500), nullable=False)
    target_term = Column(String(500), nullable=True)
    source_type = Column(String(50), nullable=False)  # tm_exact, tm_fuzzy, hudoc, curia, proposed
    confidence = Column(Float, nullable=False)
    status = Column(String(50), default="pending")  # pending, approved, edited, rejected
    original_proposal = Column(String(500), nullable=True)
    references = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TranslationJob(Base):
    """Translation job model."""

    __tablename__ = "translation_jobs"

    id = Column(String(50), primary_key=True)
    document_id = Column(String(50), ForeignKey("documents.id"), nullable=False)
    phase = Column(String(50), nullable=False)  # analysis, translation, validation, implementation, completed
    status = Column(String(50), default="pending")  # pending, in_progress, awaiting_validation, completed, error
    progress = Column(Float, default=0.0)
    current_step = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
