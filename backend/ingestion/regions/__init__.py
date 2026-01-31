"""
Region detection for large-format drawings.

Provides detection of meaningful sub-regions in architectural/construction drawings.
"""

from backend.ingestion.regions.detector import (
    DetectedRegion,
    should_detect_regions,
    detect_and_extract_regions,
)

__all__ = [
    "DetectedRegion",
    "should_detect_regions",
    "detect_and_extract_regions",
]
