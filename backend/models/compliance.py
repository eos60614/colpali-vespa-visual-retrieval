"""
Pydantic models for compliance-related entities.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from .enums import SessionStatus, ComplianceOutcome
from .bounding_box import BoundingBox


class ReviewSession(BaseModel):
    """A compliance review session tracking the full workflow."""
    id: str
    submittal_id: str
    spec_section_id: Optional[str] = None
    project_id: str
    status: SessionStatus = SessionStatus.MATCHING
    reviewer_id: Optional[str] = None
    overall_result: Optional[ComplianceOutcome] = None
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None


class ComplianceResult(BaseModel):
    """Result of verifying a single requirement against a submittal."""
    id: str
    requirement_id: str
    outcome: ComplianceOutcome
    value_found: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    submittal_page: Optional[int] = None
    submittal_location: Optional[BoundingBox] = None
    evidence_path: Optional[str] = None
    reasoning: Optional[str] = None
    human_confirmed: bool = False
    created_at: datetime


class SpecSection(BaseModel):
    """A specification section stored in Vespa."""
    id: str
    project_id: str
    section_number: str
    section_title: str
    source_doc_id: str
    page_numbers: list[int] = Field(default_factory=list)
    text: Optional[str] = None


class SpecMatchSuggestion(BaseModel):
    """A suggested spec section match with similarity score."""
    id: str
    session_id: str
    spec_section_id: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    rank: int
    selected: bool = False
