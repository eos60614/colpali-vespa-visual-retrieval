"""
Page size detection and adaptive processing for the ingestion pipeline.

Classifies pages into size categories and determines optimal processing strategies
including DPI, splitting, and text extraction approaches.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from PIL import Image

from backend.config import get
from backend.logging_config import get_logger

logger = get_logger(__name__)


class PageSizeCategory(Enum):
    """Page size categories for adaptive processing."""

    STANDARD = "standard"  # A4/Letter: < 1M pixels (typical documents)
    LARGE = "large"  # Tabloid/A3: 1M - 3M pixels
    OVERSIZED = "oversized"  # Architectural: 3M - 10M pixels
    MASSIVE = "massive"  # Large format drawings: > 10M pixels


class PageOrientation(Enum):
    """Page orientation based on aspect ratio."""

    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"
    SQUARE = "square"


class SplitStrategy(Enum):
    """Strategies for splitting large pages into regions."""

    NONE = "none"  # No splitting needed
    AUTO = "auto"  # Decide based on content analysis
    PDF_VECTOR = "pdf_vector"  # Use PDF vector path analysis
    HEURISTIC = "heuristic"  # Whitespace-based detection
    CONTENT_TILE = "content_tile"  # Content-aware tiling
    MANDATORY_TILE = "mandatory_tile"  # Always tile (for massive pages)


@dataclass
class PageSizeConfig:
    """Configuration for a page size category."""

    category: PageSizeCategory
    render_dpi: int
    max_dimension: int
    split_strategy: SplitStrategy
    needs_ocr_fallback: bool


@dataclass
class PageAnalysis:
    """Complete analysis of a page's size and recommended processing."""

    # Dimensions
    width_px: int
    height_px: int
    width_pt: float
    height_pt: float
    pixel_count: int

    # Classification
    category: PageSizeCategory
    orientation: PageOrientation

    # Processing recommendations
    recommended_dpi: int
    split_strategy: SplitStrategy
    needs_region_detection: bool

    # Content indicators
    has_vector_paths: bool = False
    estimated_text_coverage: float = 0.0


# Default thresholds (can be overridden via ki55.toml)
DEFAULT_THRESHOLDS = {
    "standard_max_pixels": 1_000_000,
    "large_max_pixels": 3_000_000,
    "oversized_max_pixels": 10_000_000,
}

DEFAULT_DPI = {
    PageSizeCategory.STANDARD: 150,
    PageSizeCategory.LARGE: 120,
    PageSizeCategory.OVERSIZED: 100,
    PageSizeCategory.MASSIVE: 72,
}


def get_size_thresholds() -> dict:
    """Get page size thresholds from config or defaults."""
    try:
        return {
            "standard_max_pixels": get("ingestion", "page_sizing", "standard_max_pixels"),
            "large_max_pixels": get("ingestion", "page_sizing", "large_max_pixels"),
            "oversized_max_pixels": get("ingestion", "page_sizing", "oversized_max_pixels"),
        }
    except (KeyError, TypeError):
        return DEFAULT_THRESHOLDS


def get_category_dpi(category: PageSizeCategory) -> int:
    """Get recommended DPI for a page size category."""
    try:
        adaptive = get("ingestion", "page_sizing", "adaptive_dpi")
        if not adaptive:
            return get("image", "dpi")

        dpi_map = {
            PageSizeCategory.STANDARD: get("ingestion", "page_sizing", "standard_dpi"),
            PageSizeCategory.LARGE: get("ingestion", "page_sizing", "large_dpi"),
            PageSizeCategory.OVERSIZED: get("ingestion", "page_sizing", "oversized_dpi"),
            PageSizeCategory.MASSIVE: get("ingestion", "page_sizing", "massive_dpi"),
        }
        return dpi_map.get(category, DEFAULT_DPI[category])
    except (KeyError, TypeError):
        return DEFAULT_DPI.get(category, 150)


def categorize_page_size(width: int, height: int) -> PageSizeCategory:
    """
    Categorize a page based on its pixel dimensions.

    Args:
        width: Page width in pixels
        height: Page height in pixels

    Returns:
        PageSizeCategory enum value
    """
    pixel_count = width * height
    thresholds = get_size_thresholds()

    if pixel_count <= thresholds["standard_max_pixels"]:
        return PageSizeCategory.STANDARD
    elif pixel_count <= thresholds["large_max_pixels"]:
        return PageSizeCategory.LARGE
    elif pixel_count <= thresholds["oversized_max_pixels"]:
        return PageSizeCategory.OVERSIZED
    else:
        return PageSizeCategory.MASSIVE


def categorize_image(image: Image.Image) -> PageSizeCategory:
    """Categorize a PIL Image by size."""
    return categorize_page_size(image.width, image.height)


def determine_orientation(width: float, height: float, tolerance: float = 0.1) -> PageOrientation:
    """
    Determine page orientation from dimensions.

    Args:
        width: Page width
        height: Page height
        tolerance: Ratio tolerance for "square" classification

    Returns:
        PageOrientation enum value
    """
    if abs(width - height) / max(width, height) <= tolerance:
        return PageOrientation.SQUARE
    elif width > height:
        return PageOrientation.LANDSCAPE
    else:
        return PageOrientation.PORTRAIT


def determine_split_strategy(
    category: PageSizeCategory,
    has_vector_paths: bool = False,
    text_coverage: float = 0.0,
) -> SplitStrategy:
    """
    Determine the optimal splitting strategy for a page.

    Args:
        category: Page size category
        has_vector_paths: Whether the PDF page has vector drawing paths
        text_coverage: Estimated percentage of page covered by text

    Returns:
        SplitStrategy enum value
    """
    if category == PageSizeCategory.STANDARD:
        return SplitStrategy.NONE

    if category == PageSizeCategory.MASSIVE:
        # Massive pages always need splitting
        if has_vector_paths:
            return SplitStrategy.PDF_VECTOR
        return SplitStrategy.MANDATORY_TILE

    if category == PageSizeCategory.OVERSIZED:
        # Oversized: prefer vector analysis if available
        if has_vector_paths:
            return SplitStrategy.PDF_VECTOR
        return SplitStrategy.HEURISTIC

    # Large pages: split only if they have complex content
    if has_vector_paths:
        return SplitStrategy.PDF_VECTOR
    if text_coverage < 0.3:
        # Low text coverage suggests drawings/diagrams
        return SplitStrategy.HEURISTIC

    return SplitStrategy.AUTO


def analyze_page(
    width_px: int,
    height_px: int,
    width_pt: float = 0.0,
    height_pt: float = 0.0,
    has_vector_paths: bool = False,
    estimated_text_coverage: float = 0.0,
) -> PageAnalysis:
    """
    Perform complete analysis of a page for processing decisions.

    Args:
        width_px: Rendered width in pixels
        height_px: Rendered height in pixels
        width_pt: Original width in PDF points (optional)
        height_pt: Original height in PDF points (optional)
        has_vector_paths: Whether the PDF has vector drawing elements
        estimated_text_coverage: Estimated text coverage (0-1)

    Returns:
        PageAnalysis with all processing recommendations
    """
    category = categorize_page_size(width_px, height_px)
    orientation = determine_orientation(width_px, height_px)
    split_strategy = determine_split_strategy(
        category, has_vector_paths, estimated_text_coverage
    )

    # Determine if region detection is needed
    needs_region_detection = split_strategy not in (SplitStrategy.NONE, SplitStrategy.AUTO)

    return PageAnalysis(
        width_px=width_px,
        height_px=height_px,
        width_pt=width_pt or float(width_px),
        height_pt=height_pt or float(height_px),
        pixel_count=width_px * height_px,
        category=category,
        orientation=orientation,
        recommended_dpi=get_category_dpi(category),
        split_strategy=split_strategy,
        needs_region_detection=needs_region_detection,
        has_vector_paths=has_vector_paths,
        estimated_text_coverage=estimated_text_coverage,
    )


def analyze_pdf_page(page, dpi: int = 150) -> PageAnalysis:
    """
    Analyze a PyMuPDF page object.

    Args:
        page: fitz.Page object
        dpi: DPI used for initial rendering estimate

    Returns:
        PageAnalysis with recommendations
    """
    rect = page.rect

    # Estimate rendered size at given DPI
    scale = dpi / 72.0
    width_px = int(rect.width * scale)
    height_px = int(rect.height * scale)

    # Check for vector paths (drawings)
    try:
        paths = page.get_drawings()
        has_vector_paths = len(paths) > 10  # Threshold from config
    except Exception:
        has_vector_paths = False

    # Estimate text coverage
    try:
        text_dict = page.get_text("dict")
        text_blocks = text_dict.get("blocks", [])
        text_area = sum(
            (b["bbox"][2] - b["bbox"][0]) * (b["bbox"][3] - b["bbox"][1])
            for b in text_blocks
            if b.get("type") == 0  # Text blocks only
        )
        page_area = rect.width * rect.height
        text_coverage = text_area / page_area if page_area > 0 else 0
    except Exception:
        text_coverage = 0.0

    return analyze_page(
        width_px=width_px,
        height_px=height_px,
        width_pt=rect.width,
        height_pt=rect.height,
        has_vector_paths=has_vector_paths,
        estimated_text_coverage=text_coverage,
    )


def get_adaptive_dpi(page, base_dpi: int = 150) -> Tuple[int, PageAnalysis]:
    """
    Get the optimal DPI for rendering a page based on its size.

    Args:
        page: fitz.Page object
        base_dpi: Starting DPI for size estimation

    Returns:
        Tuple of (recommended DPI, PageAnalysis)
    """
    # First analyze at base DPI to get category
    analysis = analyze_pdf_page(page, base_dpi)

    # Return the category-appropriate DPI
    return analysis.recommended_dpi, analysis


def should_use_ocr(
    layer_text: str,
    page_analysis: PageAnalysis,
    min_text_length: int = 50,
    min_coverage: float = 0.1,
) -> bool:
    """
    Determine if OCR should be used for a page.

    Args:
        layer_text: Text extracted from PDF text layer
        page_analysis: PageAnalysis result
        min_text_length: Minimum text length to consider layer sufficient
        min_coverage: Minimum text coverage to consider layer sufficient

    Returns:
        True if OCR should be run
    """
    # Always try OCR for large/oversized pages with little text
    if page_analysis.category in (PageSizeCategory.OVERSIZED, PageSizeCategory.MASSIVE):
        if len(layer_text.strip()) < min_text_length:
            return True

    # Low text coverage suggests scanned document
    if page_analysis.estimated_text_coverage < min_coverage:
        return True

    # Very little layer text
    if len(layer_text.strip()) < min_text_length:
        return True

    return False


def format_page_dimensions(analysis: PageAnalysis) -> dict:
    """
    Format page analysis as metadata dictionary for Vespa.

    Args:
        analysis: PageAnalysis result

    Returns:
        Dictionary of metadata fields
    """
    return {
        "page_width_px": analysis.width_px,
        "page_height_px": analysis.height_px,
        "page_width_pt": int(analysis.width_pt),
        "page_height_pt": int(analysis.height_pt),
        "page_size_category": analysis.category.value,
        "page_orientation": analysis.orientation.value,
        "page_pixel_count": analysis.pixel_count,
        "render_dpi": analysis.recommended_dpi,
        "has_vector_paths": analysis.has_vector_paths,
    }
