"""Document statistics and analysis."""

from pydantic import BaseModel
from typing import Optional


class DocumentStats(BaseModel):
    """Document statistics."""

    total_segments: int
    total_words: int
    total_characters: int
    estimated_translation_time_minutes: Optional[int] = None

    class Config:
        from_attributes = True
