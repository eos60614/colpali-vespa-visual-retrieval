"""
Pydantic models for correction/override entities.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from .enums import CorrectionType


class Correction(BaseModel):
    """A human override of a system-generated verification result."""
    id: str
    result_id: str
    correction_type: CorrectionType
    original_value: str  # JSON string of original system output
    corrected_value: str  # JSON string of human correction
    user_id: str
    reason: Optional[str] = None
    created_at: datetime
