"""
Unit tests for drawing region detection.

Tests cover PDF vector detection, heuristic fallback, content-aware tiling,
VLM classifier, auto dispatch, and backward compatibility.
"""

from collections import namedtuple
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from PIL import Image

from backend.ingestion.regions.detector import (
    DetectedRegion,
    _cluster_elements_spatially,
    _find_density_minima_splits,
    _rect_spans_page,
    detect_and_extract_regions,
    detect_regions_content_aware_tiling,
    detect_regions_pdf_vector,
    should_detect_regions,
)


# Simple point type for fitz.Point-like objects
Point = namedtuple("Point", ["x", "y"])


# --- Helpers ---

def _make_large_image(w=4000, h=3000, color=255):
    """Create a large white image that qualifies for region detection."""
    return Image.new("RGB", (w, h), (color, color, color))


def _make_small_image(w=800, h=600):
    """Create a small image that does NOT qualify for region detection."""
    return Image.new("RGB", (w, h), (255, 255, 255))


def _make_mock_fitz_page(
    drawings=None,
    text_blocks=None,
    page_width=612,  # letter width in points
    page_height=792,  # letter height in points
    images=None,
):
    """Create a mock fitz.Page with configurable drawings, text, and images."""
    page = MagicMock()

    # page.rect
    rect = MagicMock()
    rect.width = page_width
    rect.height = page_height
    page.rect = rect

    # page.get_drawings()
    page.get_drawings.return_value = drawings or []

    # page.get_text("dict")
    blocks = []
    for tb in (text_blocks or []):
        blocks.append({"type": 0, "bbox": tb})
    page.get_text.return_value = {"blocks": blocks}

    # page.get_images()
    page.get_images.return_value = images or []

    return page


# --- Tests ---

class TestShouldDetectRegions:
    def test_small_image_returns_false(self):
        img = _make_small_image()
        assert not should_detect_regions(img)

    def test_large_image_returns_true(self):
        img = _make_large_image()
        assert should_detect_regions(img)

    def test_force_overrides_size(self):
        img = _make_small_image()
        assert should_detect_regions(img, force=True)


class TestDetectedRegion:
    def test_area(self):
        r = DetectedRegion(x=0, y=0, width=100, height=200)
        assert r.area == 20000

    def test_bbox(self):
        r = DetectedRegion(x=10, y=20, width=100, height=200)
        assert r.bbox == (10, 20, 110, 220)

    def test_to_dict_includes_content_hint(self):
        r = DetectedRegion(
            x=0, y=0, width=100, height=100,
            content_hint="table",
        )
        d = r.to_dict()
        assert d["content_hint"] == "table"

    def test_default_content_hint_is_empty(self):
        r = DetectedRegion(x=0, y=0, width=100, height=100)
        assert r.content_hint == ""


class TestPdfVectorDetection:
    def test_empty_page_returns_empty(self):
        """Page with no vector paths returns empty list."""
        page = _make_mock_fitz_page(drawings=[])
        regions = detect_regions_pdf_vector(page, 1800, 2400)
        assert regions == []

    def test_few_paths_returns_empty(self):
        """Page with fewer than MIN_VECTOR_PATHS returns empty (treated as raster)."""
        # 5 small drawings - below threshold
        drawings = [
            {"items": [("l", Point(x=10, y=10), Point(x=100, y=10))],
             "rect": (10, 10, 100, 100)}
            for _ in range(5)
        ]
        page = _make_mock_fitz_page(drawings=drawings)
        regions = detect_regions_pdf_vector(page, 1800, 2400)
        assert regions == []

    def test_basic_vector_detection(self):
        """Page with two well-separated groups of vector elements produces regions."""
        # Create two clusters of drawings well apart on a large page
        page_w, page_h = 2592, 1728  # 36x24" at 72 DPI

        # Cluster 1: top-left area (many paths)
        cluster1 = [
            {"items": [("l", Point(x=50 + i * 10, y=50), Point(x=50 + i * 10, y=400))],
             "rect": (50, 50, 800, 400)}
            for i in range(8)
        ]
        # Cluster 2: bottom-right area (many paths)
        cluster2 = [
            {"items": [("l", Point(x=1500 + i * 10, y=1000), Point(x=1500 + i * 10, y=1400))],
             "rect": (1500, 1000, 2400, 1400)}
            for i in range(8)
        ]

        drawings = cluster1 + cluster2
        page = _make_mock_fitz_page(
            drawings=drawings, page_width=page_w, page_height=page_h
        )

        # Render at 150 DPI → pixel dimensions
        dpi_scale = 150 / 72
        px_w = int(page_w * dpi_scale)
        px_h = int(page_h * dpi_scale)

        regions = detect_regions_pdf_vector(page, px_w, px_h)
        assert len(regions) >= 2

    def test_border_removal(self):
        """Large rectangle spanning >85% of page is excluded as border."""
        page_w, page_h = 2592, 1728

        # Border rectangle spanning 90% of page
        border = {
            "items": [
                ("l", Point(x=50, y=50), Point(x=2542, y=50)),
                ("l", Point(x=2542, y=50), Point(x=2542, y=1678)),
                ("l", Point(x=2542, y=1678), Point(x=50, y=1678)),
                ("l", Point(x=50, y=1678), Point(x=50, y=50)),
            ],
            "rect": (50, 50, 2542, 1678),
        }

        # Interior content
        content = [
            {"items": [("l", Point(x=200, y=200), Point(x=800, y=200))],
             "rect": (200, 200, 800, 700)}
            for _ in range(10)
        ]

        drawings = [border] + content
        page = _make_mock_fitz_page(
            drawings=drawings, page_width=page_w, page_height=page_h
        )

        dpi_scale = 150 / 72
        px_w = int(page_w * dpi_scale)
        px_h = int(page_h * dpi_scale)

        regions = detect_regions_pdf_vector(page, px_w, px_h)
        # The border itself should NOT appear as a region
        for r in regions:
            # No region should span >85% of the rendered image
            assert r.width / px_w < 0.90 or r.height / px_h < 0.90

    def test_coordinate_mapping(self):
        """Verify point-to-pixel conversion (72 DPI → 150 DPI)."""
        page_w, page_h = 612, 792  # letter size in points

        # Single cluster of content at known point coordinates
        drawings = [
            {"items": [("l", Point(x=100, y=100), Point(x=300, y=100))],
             "rect": (100, 100, 300, 400)}
            for _ in range(12)
        ]
        page = _make_mock_fitz_page(
            drawings=drawings, page_width=page_w, page_height=page_h
        )

        dpi_scale = 150 / 72
        px_w = int(page_w * dpi_scale)
        px_h = int(page_h * dpi_scale)

        regions = detect_regions_pdf_vector(page, px_w, px_h)
        if regions:
            # Check the region coordinates are in pixel space, not point space
            r = regions[0]
            # At 150 DPI, 100pt = ~208px, 300pt = ~625px
            expected_x_min = int(100 * dpi_scale) - 10
            expected_x_max = int(300 * dpi_scale) + 10
            assert r.x >= expected_x_min
            assert r.x + r.width <= expected_x_max + 50  # some tolerance


class TestTableDetection:
    def test_regular_grid_detected_as_table(self):
        """A grid of regularly-spaced horizontal and vertical lines is detected as a table."""
        page_w, page_h = 2592, 1728
        drawings = []

        # Create a grid: 5 horizontal lines, 5 vertical lines
        for i in range(5):
            y_pos = 500 + i * 50
            # Horizontal line
            drawings.append({
                "items": [("l", Point(x=500, y=y_pos), Point(x=1000, y=y_pos))],
                "rect": (500, y_pos, 1000, y_pos + 1),
            })
        for i in range(5):
            x_pos = 500 + i * 125
            # Vertical line
            drawings.append({
                "items": [("l", Point(x=x_pos, y=500), Point(x=x_pos, y=700))],
                "rect": (x_pos, 500, x_pos + 1, 700),
            })

        # Add enough extra drawings to pass the MIN_VECTOR_PATHS check
        # Use diagonal lines (not h/v) so they don't interfere with table detection
        for i in range(5):
            drawings.append({
                "items": [("l", Point(x=1800 + i * 30, y=100 + i * 30), Point(x=1900 + i * 30, y=200 + i * 30))],
                "rect": (1800 + i * 30, 100 + i * 30, 1900 + i * 30, 200 + i * 30),
            })

        page = _make_mock_fitz_page(
            drawings=drawings, page_width=page_w, page_height=page_h
        )

        dpi_scale = 150 / 72
        px_w = int(page_w * dpi_scale)
        px_h = int(page_h * dpi_scale)

        regions = detect_regions_pdf_vector(page, px_w, px_h)
        table_regions = [r for r in regions if r.content_hint == "table"]
        assert len(table_regions) >= 1


class TestRectSpansPage:
    def test_full_span(self):
        assert _rect_spans_page((10, 10, 990, 990), 1000, 1000, threshold=0.85)

    def test_small_rect(self):
        assert not _rect_spans_page((10, 10, 400, 400), 1000, 1000, threshold=0.85)


class TestClusterElements:
    def test_nearby_elements_merged(self):
        bboxes = [
            (0, 0, 100, 100),
            (110, 0, 200, 100),  # 10px gap - within 100px threshold
        ]
        clusters = _cluster_elements_spatially(bboxes, gap_threshold=100)
        assert len(clusters) == 1

    def test_distant_elements_separate(self):
        bboxes = [
            (0, 0, 100, 100),
            (500, 500, 600, 600),  # far apart
        ]
        clusters = _cluster_elements_spatially(bboxes, gap_threshold=50)
        assert len(clusters) == 2

    def test_empty_input(self):
        assert _cluster_elements_spatially([]) == []


class TestContentAwareTiling:
    def test_produces_tiles_for_large_image(self):
        img = _make_large_image()
        tiles = detect_regions_content_aware_tiling(img)
        assert len(tiles) >= 2
        for t in tiles:
            assert t.region_type == "content_tile" or t.region_type == "tile"

    def test_tiles_cover_image(self):
        img = _make_large_image(4000, 3000)
        tiles = detect_regions_content_aware_tiling(img)
        # Tiles should collectively cover a significant portion of the image
        total_tile_area = sum(t.area for t in tiles)
        image_area = 4000 * 3000
        # Allow overlap, so total could exceed image area
        assert total_tile_area >= image_area * 0.5


class TestDensityMinimaSplits:
    def test_finds_split_at_low_density(self):
        # Create density with a clear dip in the middle
        density = np.concatenate([
            np.ones(100) * 0.5,   # high density
            np.ones(50) * 0.01,   # low density gap
            np.ones(100) * 0.5,   # high density
        ])
        splits = _find_density_minima_splits(density, n_splits=1, window=30)
        assert len(splits) == 1
        # Split should be near the middle gap (around position 125)
        assert 90 < splits[0] < 160

    def test_zero_splits(self):
        density = np.ones(100)
        assert _find_density_minima_splits(density, n_splits=0) == []


class TestClassifyRegionsVlm:
    def test_labels_updated_on_success(self):
        """VLM classifier updates region labels from response."""
        import httpx as httpx_module
        from backend.ingestion.regions.detector import classify_regions_vlm

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"1": "floor plan", "2": "notes"}'}}]
        }
        mock_response.raise_for_status = MagicMock()

        regions = [
            DetectedRegion(x=0, y=0, width=500, height=500),
            DetectedRegion(x=600, y=0, width=500, height=500),
        ]
        img = _make_large_image()

        with patch.object(httpx_module, "post", return_value=mock_response):
            with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
                result = classify_regions_vlm(img, regions, api_key="test-key")

        assert result[0].label == "floor plan"
        assert result[1].label == "notes"

    def test_no_regions_returns_empty(self):
        from backend.ingestion.regions.detector import classify_regions_vlm
        img = _make_large_image()
        result = classify_regions_vlm(img, [])
        assert result == []


class TestAutoDispatch:
    def test_auto_prefers_pdf_vector(self):
        """Auto mode tries pdf_vector first when pdf_page is provided."""
        # Create a page with enough vector data
        page_w, page_h = 2592, 1728
        cluster1 = [
            {"items": [("l", Point(x=50 + i * 10, y=50), Point(x=50 + i * 10, y=400))],
             "rect": (50, 50, 800, 400)}
            for i in range(8)
        ]
        cluster2 = [
            {"items": [("l", Point(x=1500 + i * 10, y=1000), Point(x=1500 + i * 10, y=1400))],
             "rect": (1500, 1000, 2400, 1400)}
            for i in range(8)
        ]
        page = _make_mock_fitz_page(
            drawings=cluster1 + cluster2,
            page_width=page_w, page_height=page_h,
        )

        dpi_scale = 150 / 72
        px_w = int(page_w * dpi_scale)
        px_h = int(page_h * dpi_scale)
        img = _make_large_image(px_w, px_h)

        results = detect_and_extract_regions(
            img, detection_method="auto", pdf_page=page, force=True
        )
        # Should have full_page + detected regions
        assert len(results) >= 2
        # First result is always full_page
        assert results[0][1].region_type == "full_page"

    def test_pdf_vector_method_requires_page(self):
        """Requesting pdf_vector without pdf_page raises ValueError."""
        img = _make_large_image()
        with pytest.raises(ValueError, match="pdf_vector detection requires pdf_page"):
            detect_and_extract_regions(
                img, detection_method="pdf_vector", force=True
            )

    def test_unknown_method_raises(self):
        img = _make_large_image()
        with pytest.raises(ValueError, match="Unknown detection_method"):
            detect_and_extract_regions(
                img, detection_method="nonexistent", force=True
            )


class TestBackwardCompat:
    def test_existing_signature_works(self):
        """detect_and_extract_regions works with original arguments (no new params)."""
        img = _make_large_image()
        results = detect_and_extract_regions(img, force=True)
        assert len(results) >= 1
        assert results[0][1].region_type == "full_page"

    def test_small_image_returns_full_page(self):
        """Small image returns single full_page result without detection."""
        img = _make_small_image()
        results = detect_and_extract_regions(img)
        assert len(results) == 1
        assert results[0][1].region_type == "full_page"

    def test_heuristic_method_works(self):
        """Explicit heuristic method produces results."""
        img = _make_large_image()
        results = detect_and_extract_regions(
            img, detection_method="heuristic", force=True
        )
        assert len(results) >= 1
