"""
Request and response schemas for the compliance API endpoints.
Based on the OpenAPI specification in contracts/openapi.yaml.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from .enums import SessionStatus, LaneType, RequirementStatus, ComplianceOutcome, CorrectionType
from .bounding_box import BoundingBox, RegionEvidence, RequirementLocation, SubmittalMatch


# ============== REQUEST SCHEMAS ==============

class CreateSessionRequest(BaseModel):
    """Request to create a new review session."""
    submittal_id: str
    project_id: str


class ConfirmSpecSectionRequest(BaseModel):
    """Request to confirm spec section selection."""
    spec_section_id: str
    override: bool = False


class UpdateRequirementRequest(BaseModel):
    """Request to update a requirement."""
    lane: Optional[LaneType] = None
    target_value: Optional[str] = None
    status: Optional[RequirementStatus] = None


class CorrectionRequest(BaseModel):
    """Request to correct a verification result."""
    correction_type: CorrectionType
    corrected_outcome: Optional[ComplianceOutcome] = None
    corrected_value: Optional[str] = None
    reason: Optional[str] = None


# ============== RESPONSE SCHEMAS ==============

class ReviewSessionResponse(BaseModel):
    """Response for a review session."""
    id: str
    submittal_id: str
    spec_section_id: Optional[str] = None
    project_id: str
    status: SessionStatus
    overall_result: Optional[ComplianceOutcome] = None
    created_at: datetime
    updated_at: datetime


class SpecSectionResponse(BaseModel):
    """Response for a spec section."""
    id: str
    section_number: str
    section_title: str
    page_numbers: list[int] = Field(default_factory=list)


class SpecSectionSuggestionResponse(BaseModel):
    """Response for a spec section suggestion."""
    spec_section: SpecSectionResponse
    similarity_score: float = Field(ge=0.0, le=1.0)
    rank: int


class SpecSectionSuggestionsResponse(BaseModel):
    """Response for spec section suggestions list."""
    suggestions: list[SpecSectionSuggestionResponse] = Field(default_factory=list)


class RequirementsSummary(BaseModel):
    """Summary of requirements by lane."""
    total: int
    by_lane: dict[str, int]


class ResultsSummary(BaseModel):
    """Summary of compliance results."""
    total: int
    passed: int = Field(alias="pass", default=0)
    fail: int = 0
    not_found: int = 0
    needs_review: int = 0
    confirmed: int = 0
    unconfirmed: int = 0


class ReviewSessionDetailResponse(ReviewSessionResponse):
    """Detailed response for a review session."""
    spec_section: Optional[SpecSectionResponse] = None
    requirements_summary: Optional[RequirementsSummary] = None
    results_summary: Optional[ResultsSummary] = None


class SessionListResponse(BaseModel):
    """Response for paginated session list."""
    items: list[ReviewSessionResponse] = Field(default_factory=list)
    total: int
    limit: int
    offset: int


class RequirementResponse(BaseModel):
    """Response for a requirement."""
    id: str
    session_id: str
    text: str
    lane: LaneType
    source_page: int
    source_location: Optional[BoundingBox] = None
    attribute_type: Optional[str] = None
    target_value: Optional[str] = None
    status: RequirementStatus


class ComplianceResultResponse(BaseModel):
    """Response for a compliance result."""
    id: str
    requirement_id: str
    outcome: ComplianceOutcome
    value_found: Optional[str] = None
    confidence: float
    submittal_page: Optional[int] = None
    submittal_location: Optional[BoundingBox] = None
    human_confirmed: bool
    created_at: datetime


class RequirementDetailResponse(RequirementResponse):
    """Detailed response for a requirement with compliance result."""
    compliance_result: Optional[ComplianceResultResponse] = None


class RequirementListResponse(BaseModel):
    """Response for requirements grouped by lane."""
    auto_check: list[RequirementResponse] = Field(default_factory=list)
    needs_scoping: list[RequirementResponse] = Field(default_factory=list)
    informational: list[RequirementResponse] = Field(default_factory=list)


class CorrectionResponse(BaseModel):
    """Response for a correction."""
    id: str
    correction_type: CorrectionType
    original_value: dict
    corrected_value: dict
    user_id: str
    reason: Optional[str] = None
    created_at: datetime


class EvidenceResponse(BaseModel):
    """Response for evidence URLs."""
    spec_image_url: str
    submittal_image_url: str


class ComplianceResultDetailResponse(ComplianceResultResponse):
    """Detailed response for a compliance result with evidence."""
    requirement: Optional[RequirementResponse] = None
    reasoning: Optional[str] = None
    evidence: Optional[EvidenceResponse] = None
    corrections: list[CorrectionResponse] = Field(default_factory=list)


class ComplianceResultListResponse(BaseModel):
    """Response for compliance results list."""
    items: list[ComplianceResultResponse] = Field(default_factory=list)
    total: int


class VerificationStatusResponse(BaseModel):
    """Response for verification status."""
    status: str
    total_requirements: int
    verified_count: int
    progress_percent: float
    error: Optional[str] = None


class ReportResultItemResponse(BaseModel):
    """Response for a single result in a report."""
    requirement_text: str
    target_value: Optional[str] = None
    value_found: Optional[str] = None
    outcome: ComplianceOutcome
    source_page: int
    submittal_page: Optional[int] = None
    was_corrected: bool = False


class ReportSummaryResponse(BaseModel):
    """Summary statistics for a compliance report."""
    total_requirements: int
    passed: int
    failed: int
    not_applicable: int
    not_found: int


class ComplianceReportResponse(BaseModel):
    """Response for a compliance report."""
    session_id: str
    submittal_id: str
    spec_section: Optional[SpecSectionResponse] = None
    overall_result: Optional[ComplianceOutcome] = None
    generated_at: datetime
    reviewer_id: Optional[str] = None
    summary: ReportSummaryResponse
    results: list[ReportResultItemResponse] = Field(default_factory=list)
    corrections_made: int = 0


class ErrorResponse(BaseModel):
    """Response for errors."""
    error: str
    message: str
    details: Optional[dict] = None
