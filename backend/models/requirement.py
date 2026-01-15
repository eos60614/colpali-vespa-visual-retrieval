"""
Pydantic models for requirement entities.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator

from .enums import LaneType, RequirementStatus
from .bounding_box import BoundingBox


class Requirement(BaseModel):
    """An extracted requirement from a specification section."""
    id: str
    session_id: str
    text: str = Field(max_length=2000)
    lane: LaneType
    source_page: int = Field(gt=0)
    source_location: Optional[BoundingBox] = None
    attribute_type: Optional[str] = None
    target_value: Optional[str] = None
    status: RequirementStatus = RequirementStatus.PENDING
    created_at: datetime

    @field_validator("target_value")
    @classmethod
    def validate_target_value(cls, v: Optional[str], info) -> Optional[str]:
        """Validate that AUTO_CHECK requirements have a target value."""
        lane = info.data.get("lane")
        if lane == LaneType.AUTO_CHECK and not v:
            raise ValueError("Auto-check requirements must have target value")
        return v
