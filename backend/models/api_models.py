"""
API data models for ECTHR Translator.
"""
from typing import List, Optional
from pydantic import BaseModel, Field


class TermSearchRequest(BaseModel):
    """Request model for single term search."""
    term: str = Field(..., description="Legal term to search for")
    source_lang: str = Field(default="en", description="Source language code")
    target_lang: str = Field(default="pl", description="Target language code")
    sources: Optional[List[str]] = Field(
        default=None,
        description="Databases to search (hudoc, curia, iate). If None, searches all enabled."
    )


class BatchSearchRequest(BaseModel):
    """Request model for batch term search."""
    terms: List[str] = Field(..., description="List of legal terms to search for")
    source_lang: str = Field(default="en", description="Source language code")
    target_lang: str = Field(default="pl", description="Target language code")
    sources: Optional[List[str]] = Field(
        default=None,
        description="Databases to search (hudoc, curia, iate). If None, searches all enabled."
    )


class SourceResult(BaseModel):
    """Result from a single database source."""
    source: str = Field(..., description="Source database name")
    translation: Optional[str] = Field(None, description="Translation found")
    confidence: float = Field(..., description="Confidence score (0.0 - 1.0)")
    references: List[str] = Field(default_factory=list, description="Case references")
    domain: Optional[str] = Field(None, description="Legal domain (for IATE)")


class TermSearchResponse(BaseModel):
    """Response model for single term search."""
    term: str = Field(..., description="The searched term")
    best_translation: Optional[str] = Field(None, description="Best translation found")
    best_confidence: float = Field(..., description="Confidence of best translation")
    best_source: Optional[str] = Field(None, description="Source of best translation")
    all_results: List[SourceResult] = Field(
        default_factory=list,
        description="Results from all searched sources"
    )


class BatchSearchResponse(BaseModel):
    """Response model for batch term search."""
    results: List[TermSearchResponse] = Field(..., description="Search results for all terms")
    summary: dict = Field(..., description="Summary statistics")


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    services: dict
