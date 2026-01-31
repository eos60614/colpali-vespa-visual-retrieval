"""Unit tests for backend.page_sizing module."""

import pytest
from PIL import Image

from backend.page_sizing import (
    PageOrientation,
    PageSizeCategory,
    SplitStrategy,
    analyze_page,
    categorize_page_size,
    categorize_image,
    determine_orientation,
    determine_split_strategy,
    format_page_dimensions,
    get_category_dpi,
)


class TestPageSizeCategory:
    """Tests for page size categorization."""

    def test_standard_size(self):
        """Standard pages (< 1M pixels) should be categorized as STANDARD."""
        # 800x1000 = 800,000 pixels
        assert categorize_page_size(800, 1000) == PageSizeCategory.STANDARD

        # A4 at 150 DPI: ~1240x1754 = ~2.2M - actually large
        # Letter at 100 DPI: ~850x1100 = 935,000 - standard
        assert categorize_page_size(850, 1100) == PageSizeCategory.STANDARD

    def test_large_size(self):
        """Large pages (1M - 3M pixels) should be categorized as LARGE."""
        # 1500x1500 = 2.25M pixels
        assert categorize_page_size(1500, 1500) == PageSizeCategory.LARGE

        # Tabloid at 150 DPI: ~1700x2550 = ~4.3M - actually oversized
        # A3 at 100 DPI: ~1169x1654 = ~1.9M - large
        assert categorize_page_size(1169, 1654) == PageSizeCategory.LARGE

    def test_oversized(self):
        """Oversized pages (3M - 10M pixels) should be categorized as OVERSIZED."""
        # 2000x2000 = 4M pixels
        assert categorize_page_size(2000, 2000) == PageSizeCategory.OVERSIZED

        # Architectural drawing: 3000x2000 = 6M pixels
        assert categorize_page_size(3000, 2000) == PageSizeCategory.OVERSIZED

    def test_massive(self):
        """Massive pages (> 10M pixels) should be categorized as MASSIVE."""
        # 4000x3000 = 12M pixels
        assert categorize_page_size(4000, 3000) == PageSizeCategory.MASSIVE

        # Large format: 5000x4000 = 20M pixels
        assert categorize_page_size(5000, 4000) == PageSizeCategory.MASSIVE

    def test_categorize_image(self):
        """Test categorizing PIL Image objects."""
        # Create a small test image
        img = Image.new("RGB", (800, 1000))
        assert categorize_image(img) == PageSizeCategory.STANDARD

        img = Image.new("RGB", (2000, 2000))
        assert categorize_image(img) == PageSizeCategory.OVERSIZED


class TestPageOrientation:
    """Tests for page orientation detection."""

    def test_portrait(self):
        """Taller-than-wide pages should be PORTRAIT."""
        assert determine_orientation(800, 1200) == PageOrientation.PORTRAIT
        assert determine_orientation(100, 150) == PageOrientation.PORTRAIT

    def test_landscape(self):
        """Wider-than-tall pages should be LANDSCAPE."""
        assert determine_orientation(1200, 800) == PageOrientation.LANDSCAPE
        assert determine_orientation(150, 100) == PageOrientation.LANDSCAPE

    def test_square(self):
        """Similar dimensions should be SQUARE (within tolerance)."""
        # Exact square
        assert determine_orientation(1000, 1000) == PageOrientation.SQUARE

        # Within 10% tolerance
        assert determine_orientation(1000, 1050) == PageOrientation.SQUARE
        assert determine_orientation(1050, 1000) == PageOrientation.SQUARE

    def test_near_square_boundary(self):
        """Test orientation at boundary of square tolerance."""
        # 11% difference should not be square
        assert determine_orientation(1000, 1110) != PageOrientation.SQUARE


class TestSplitStrategy:
    """Tests for split strategy determination."""

    def test_standard_no_split(self):
        """Standard pages should not be split."""
        strategy = determine_split_strategy(PageSizeCategory.STANDARD)
        assert strategy == SplitStrategy.NONE

    def test_massive_always_split(self):
        """Massive pages should always be split."""
        strategy = determine_split_strategy(PageSizeCategory.MASSIVE)
        assert strategy in (SplitStrategy.PDF_VECTOR, SplitStrategy.MANDATORY_TILE)

    def test_vector_preference(self):
        """Pages with vector paths should prefer PDF_VECTOR strategy."""
        strategy = determine_split_strategy(
            PageSizeCategory.OVERSIZED, has_vector_paths=True
        )
        assert strategy == SplitStrategy.PDF_VECTOR

    def test_heuristic_fallback(self):
        """Oversized pages without vectors should use HEURISTIC."""
        strategy = determine_split_strategy(
            PageSizeCategory.OVERSIZED, has_vector_paths=False
        )
        assert strategy == SplitStrategy.HEURISTIC

    def test_large_with_low_text(self):
        """Large pages with low text coverage should use HEURISTIC."""
        strategy = determine_split_strategy(
            PageSizeCategory.LARGE, has_vector_paths=False, text_coverage=0.1
        )
        assert strategy == SplitStrategy.HEURISTIC


class TestAnalyzePage:
    """Tests for complete page analysis."""

    def test_standard_page_analysis(self):
        """Analyze a standard-sized page."""
        analysis = analyze_page(800, 1000)

        assert analysis.width_px == 800
        assert analysis.height_px == 1000
        assert analysis.pixel_count == 800000
        assert analysis.category == PageSizeCategory.STANDARD
        assert analysis.orientation == PageOrientation.PORTRAIT
        assert analysis.split_strategy == SplitStrategy.NONE
        assert analysis.needs_region_detection is False

    def test_oversized_page_analysis(self):
        """Analyze an oversized page."""
        analysis = analyze_page(
            3000, 2000, has_vector_paths=True, estimated_text_coverage=0.1
        )

        assert analysis.category == PageSizeCategory.OVERSIZED
        assert analysis.orientation == PageOrientation.LANDSCAPE
        assert analysis.split_strategy == SplitStrategy.PDF_VECTOR
        assert analysis.needs_region_detection is True
        assert analysis.has_vector_paths is True

    def test_dpi_recommendation(self):
        """Verify DPI recommendations by category."""
        standard = analyze_page(800, 1000)
        oversized = analyze_page(3000, 2000)

        # Standard should have higher DPI than oversized
        assert standard.recommended_dpi >= oversized.recommended_dpi


class TestFormatPageDimensions:
    """Tests for formatting page analysis as metadata."""

    def test_format_includes_all_fields(self):
        """Ensure all expected metadata fields are present."""
        analysis = analyze_page(1500, 2000, has_vector_paths=True)
        metadata = format_page_dimensions(analysis)

        assert "page_width_px" in metadata
        assert "page_height_px" in metadata
        assert "page_size_category" in metadata
        assert "page_orientation" in metadata
        assert "render_dpi" in metadata
        assert "has_vector_paths" in metadata

        assert metadata["page_width_px"] == 1500
        assert metadata["page_height_px"] == 2000
        assert metadata["page_size_category"] == "large"
        assert metadata["page_orientation"] == "portrait"


class TestGetCategoryDpi:
    """Tests for DPI retrieval by category."""

    def test_default_dpi_values(self):
        """Test that each category returns a reasonable DPI."""
        standard_dpi = get_category_dpi(PageSizeCategory.STANDARD)
        large_dpi = get_category_dpi(PageSizeCategory.LARGE)
        oversized_dpi = get_category_dpi(PageSizeCategory.OVERSIZED)
        massive_dpi = get_category_dpi(PageSizeCategory.MASSIVE)

        # DPI should decrease as page size increases
        assert standard_dpi >= large_dpi >= oversized_dpi >= massive_dpi

        # All should be positive
        assert all(dpi > 0 for dpi in [standard_dpi, large_dpi, oversized_dpi, massive_dpi])
