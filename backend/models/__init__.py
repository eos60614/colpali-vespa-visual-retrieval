# Backend models package

from .database import init_db, get_connection, get_db_path
from .enums import (
    SessionStatus,
    LaneType,
    RequirementStatus,
    ComplianceOutcome,
    CorrectionType,
)
from .compliance import (
    ReviewSession,
    ComplianceResult,
    SpecSection,
    SpecMatchSuggestion,
)
from .requirement import Requirement
from .correction import Correction
from .bounding_box import (
    BoundingBox,
    RegionEvidence,
    RequirementLocation,
    SubmittalMatch,
)

__all__ = [
    # Database
    "init_db",
    "get_connection",
    "get_db_path",
    # Enums
    "SessionStatus",
    "LaneType",
    "RequirementStatus",
    "ComplianceOutcome",
    "CorrectionType",
    # Models
    "ReviewSession",
    "ComplianceResult",
    "SpecSection",
    "SpecMatchSuggestion",
    "Requirement",
    "Correction",
    # Bounding Box
    "BoundingBox",
    "RegionEvidence",
    "RequirementLocation",
    "SubmittalMatch",
]
