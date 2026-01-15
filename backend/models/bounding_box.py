"""
Bounding box model for visual region highlighting.
"""

from typing import Optional
from pydantic import BaseModel, Field


class BoundingBox(BaseModel):
    """
    Bounding box coordinates for highlighting regions in documents.

    Coordinates are normalized (0-1) relative to page dimensions,
    making them resolution-independent.
    """
    x: float = Field(ge=0.0, le=1.0, description="Left edge (0-1)")
    y: float = Field(ge=0.0, le=1.0, description="Top edge (0-1)")
    width: float = Field(ge=0.0, le=1.0, description="Width (0-1)")
    height: float = Field(ge=0.0, le=1.0, description="Height (0-1)")
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Detection confidence")
    label: Optional[str] = Field(default=None, description="Optional label for the region")

    def to_pixels(self, page_width: int, page_height: int) -> dict:
        """Convert normalized coordinates to pixel values."""
        return {
            "x": int(self.x * page_width),
            "y": int(self.y * page_height),
            "width": int(self.width * page_width),
            "height": int(self.height * page_height),
        }

    def to_css(self) -> dict:
        """Convert to CSS positioning values (percentages)."""
        return {
            "left": f"{self.x * 100}%",
            "top": f"{self.y * 100}%",
            "width": f"{self.width * 100}%",
            "height": f"{self.height * 100}%",
        }


class RegionEvidence(BaseModel):
    """
    Evidence region with bounding box and metadata.
    Used for displaying highlighted regions in the UI.
    """
    page_number: int = Field(ge=1, description="Page number (1-indexed)")
    bounding_box: BoundingBox
    text_snippet: Optional[str] = Field(default=None, description="Extracted text from region")
    image_url: Optional[str] = Field(default=None, description="URL to cropped region image")


class RequirementLocation(BaseModel):
    """Location of a requirement in the spec document."""
    page_number: int = Field(ge=1)
    bounding_box: BoundingBox
    context_text: Optional[str] = Field(default=None, description="Surrounding context text")


class SubmittalMatch(BaseModel):
    """Location where requirement evidence was found in submittal."""
    page_number: int = Field(ge=1)
    bounding_box: BoundingBox
    extracted_value: Optional[str] = Field(default=None, description="Value extracted from this region")
    similarity_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
