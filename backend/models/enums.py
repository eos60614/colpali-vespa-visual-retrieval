"""
Enum definitions for the compliance checking system.
"""

from enum import Enum


class SessionStatus(str, Enum):
    """Status states for a compliance review session."""
    MATCHING = "MATCHING"
    EXTRACTING = "EXTRACTING"
    VERIFYING = "VERIFYING"
    REVIEWING = "REVIEWING"
    COMPLETED = "COMPLETED"


class LaneType(str, Enum):
    """Classification lanes for requirements."""
    AUTO_CHECK = "AUTO_CHECK"  # Clear, typed requirement - automatic verification
    NEEDS_SCOPING = "NEEDS_SCOPING"  # References external docs - human must provide value
    INFORMATIONAL = "INFORMATIONAL"  # Workmanship/narrative - display only, not verified


class RequirementStatus(str, Enum):
    """Status of a requirement through the verification workflow."""
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    SCOPED = "SCOPED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class ComplianceOutcome(str, Enum):
    """Possible outcomes of compliance verification."""
    PASS = "PASS"  # Requirement satisfied
    FAIL = "FAIL"  # Requirement not satisfied
    NOT_FOUND = "NOT_FOUND"  # Could not locate relevant info in submittal
    NEEDS_REVIEW = "NEEDS_REVIEW"  # Low confidence, requires human determination


class CorrectionType(str, Enum):
    """Types of human corrections that can be made."""
    VALUE = "value"  # Changed extracted/found value
    STATUS = "status"  # Changed PASS/FAIL/NOT_FOUND outcome
    LANE = "lane"  # Reclassified requirement lane
    NA = "na"  # Marked requirement as Not Applicable
