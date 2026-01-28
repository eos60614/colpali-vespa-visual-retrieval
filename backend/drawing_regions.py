"""
Drawing region detection for large-format architectural/construction drawings.

Large drawings (e.g., 40"x32") compress poorly into ColPali's fixed patch grid (~1024 patches),
losing fine detail. This module detects meaningful sub-regions (elevations, details, tables,
schedules) and produces crops that each get full patch coverage when embedded separately.

Detection hierarchy (auto mode tries in order, uses first that finds 2+ regions):
1. PDF Vector Analysis (PyMuPDF) — extracts structure from vector PDF paths/text
2. Whitespace Heuristic — lightweight gutter detection
3. Content-Aware Tiling — density-based tile placement (always succeeds)

Optional overlay: VLM-as-Classifier — labels pre-detected regions semantically
"""

import io
import json
from dataclasses import dataclass
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image

from backend.config import get
from backend.logging_config import get_logger

logger = get_logger(__name__)

# Region detection constants from ki55.toml
MIN_REGION_SIZE = get("drawing_regions", "min_region_size")
MIN_REGION_AREA = get("drawing_regions", "min_region_area")
LARGE_PAGE_THRESHOLD = get("drawing_regions", "large_page_threshold")
TILE_OVERLAP = get("drawing_regions", "tile_overlap")
MAX_REGIONS = get("drawing_regions", "max_regions")

# PDF vector detection parameters from ki55.toml
BORDER_SPAN_PCT = get("drawing_regions", "pdf_vector", "border_span_pct")
ELEMENT_PROXIMITY_PX = get("drawing_regions", "pdf_vector", "element_proximity_px")
TABLE_MIN_LINES = get("drawing_regions", "pdf_vector", "table_min_lines")
TABLE_SPACING_VARIANCE = get("drawing_regions", "pdf_vector", "table_spacing_variance")
MIN_VECTOR_PATHS = get("drawing_regions", "pdf_vector", "min_vector_paths")
LINE_Y_THRESHOLD = get("drawing_regions", "pdf_vector", "line_y_threshold")
MIN_LINE_LENGTH = get("drawing_regions", "pdf_vector", "min_line_length")
BOUNDARY_TOLERANCE = get("drawing_regions", "pdf_vector", "boundary_tolerance")
BORDER_TOLERANCE = get("drawing_regions", "pdf_vector", "border_tolerance")
CONTAINED_TOLERANCE = get("drawing_regions", "pdf_vector", "contained_tolerance")
TINY_PATH_THRESHOLD = get("drawing_regions", "pdf_vector", "tiny_path_threshold")

# Confidence scores from ki55.toml
TABLE_REGION_CONFIDENCE = get("drawing_regions", "confidence", "table_region")
FRAMED_REGION_CONFIDENCE = get("drawing_regions", "confidence", "framed_region")
CLUSTER_REGION_CONFIDENCE = get("drawing_regions", "confidence", "cluster_region")
CONTAINMENT_RATIO = get("drawing_regions", "confidence", "containment_ratio")

# Heuristic detection parameters from ki55.toml
DENSITY_SCALING_FACTOR = get("drawing_regions", "density_scaling_factor")
NEIGHBORHOOD_DIVISOR = get("drawing_regions", "neighborhood_divisor")


@dataclass
class DetectedRegion:
    """A detected sub-region of a drawing page."""
    x: int  # Left coordinate
    y: int  # Top coordinate
    width: int
    height: int
    label: str = ""  # Semantic label (e.g., "floor plan", "detail section A")
    confidence: float = 1.0
    region_type: str = "detected"  # "detected", "tile", "full_page"
    content_hint: str = ""  # "drawing_view", "table", "notes", "detail", "content_tile"

    @property
    def area(self) -> int:
        return self.width * self.height

    @property
    def bbox(self) -> Tuple[int, int, int, int]:
        """Returns (left, top, right, bottom) for PIL crop."""
        return (self.x, self.y, self.x + self.width, self.y + self.height)

    def to_dict(self) -> dict:
        return {
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "label": self.label,
            "confidence": self.confidence,
            "region_type": self.region_type,
            "content_hint": self.content_hint,
        }


def should_detect_regions(image: Image.Image, force: bool = False) -> bool:
    """
    Determine if an image is large enough to benefit from region detection.

    Args:
        image: PIL Image to evaluate
        force: If True, always detect regions regardless of size

    Returns:
        True if the image should have region detection applied
    """
    if force:
        return True
    w, h = image.size
    return (w * h) > LARGE_PAGE_THRESHOLD


def _is_vector_pdf(page) -> bool:
    """Check if a fitz.Page has enough vector data to be analyzed structurally."""
    drawings = page.get_drawings()
    if len(drawings) < MIN_VECTOR_PATHS:
        return False
    # Also check for a single large raster image covering the page
    images = page.get_images(full=True)
    if len(images) == 1 and len(drawings) < MIN_VECTOR_PATHS * 2:
        # Likely a scanned page with minimal vector overlay
        return False
    return True


def _rect_spans_page(rect_bbox, page_width, page_height, threshold=BORDER_SPAN_PCT):
    """Check if a rectangle spans most of the page (likely a border frame)."""
    x0, y0, x1, y1 = rect_bbox
    rect_w = x1 - x0
    rect_h = y1 - y0
    return (rect_w / page_width > threshold) and (rect_h / page_height > threshold)


def _find_border_rects(drawings, page_width, page_height):
    """Find rectangles that span >85% of the page (border/frame elements)."""
    border_rects = []
    for d in drawings:
        items = d.get("items", [])
        # Check if this drawing is a rectangle (4 line segments forming a closed shape)
        if len(items) < 3:
            continue
        # Get the bounding rect of this drawing
        rect = d.get("rect")
        if rect is None:
            continue
        x0, y0, x1, y1 = rect
        if _rect_spans_page((x0, y0, x1, y1), page_width, page_height):
            border_rects.append((x0, y0, x1, y1))
    return border_rects


def _detect_tables_from_lines(drawings, page_width, page_height, dpi_scale):
    """
    Detect table regions from clusters of regularly-spaced horizontal and vertical lines.

    Returns list of DetectedRegion for detected tables.
    """
    h_lines = []  # (y, x_start, x_end)
    v_lines = []  # (x, y_start, y_end)

    for d in drawings:
        items = d.get("items", [])
        for item in items:
            if item[0] == "l":  # line segment
                p1, p2 = item[1], item[2]
                x1, y1 = p1.x, p1.y
                x2, y2 = p2.x, p2.y
                # Horizontal line (y values close)
                if abs(y2 - y1) < LINE_Y_THRESHOLD and abs(x2 - x1) > MIN_LINE_LENGTH:
                    h_lines.append((min(y1, y2), min(x1, x2), max(x1, x2)))
                # Vertical line (x values close)
                elif abs(x2 - x1) < LINE_Y_THRESHOLD and abs(y2 - y1) > MIN_LINE_LENGTH:
                    v_lines.append((min(x1, x2), min(y1, y2), max(y1, y2)))

    if len(h_lines) < TABLE_MIN_LINES or len(v_lines) < TABLE_MIN_LINES:
        return []

    # Sort lines
    h_lines.sort(key=lambda ln: ln[0])
    v_lines.sort(key=lambda ln: ln[0])

    # Find clusters of lines that form tables
    # Group h_lines by proximity into potential table regions
    tables = []
    h_clusters = _cluster_lines_by_position(h_lines, axis=0, gap_threshold=page_height * 0.3)

    for h_cluster in h_clusters:
        if len(h_cluster) < TABLE_MIN_LINES:
            continue
        # Check spacing regularity
        h_positions = sorted(set(ln[0] for ln in h_cluster))
        if len(h_positions) < TABLE_MIN_LINES:
            continue
        spacings = [h_positions[i + 1] - h_positions[i] for i in range(len(h_positions) - 1)]
        mean_spacing = np.mean(spacings)
        if mean_spacing <= 0:
            continue
        variance = np.std(spacings) / mean_spacing
        if variance > TABLE_SPACING_VARIANCE:
            continue

        # Find the bounding box of this h_cluster
        h_min = min(ln[0] for ln in h_cluster)
        h_max = max(ln[0] for ln in h_cluster)
        x_min = min(ln[1] for ln in h_cluster)
        x_max = max(ln[2] for ln in h_cluster)

        # Check if there are vertical lines overlapping this region
        matching_v = [v for v in v_lines
                      if v[1] <= h_max and v[2] >= h_min
                      and v[0] >= x_min - BOUNDARY_TOLERANCE and v[0] <= x_max + BOUNDARY_TOLERANCE]
        if len(matching_v) < TABLE_MIN_LINES:
            continue

        # Convert to pixel coordinates
        px_x = int(x_min * dpi_scale)
        px_y = int(h_min * dpi_scale)
        px_w = int((x_max - x_min) * dpi_scale)
        px_h = int((h_max - h_min) * dpi_scale)

        if px_w > MIN_REGION_SIZE and px_h > MIN_REGION_SIZE:
            tables.append(DetectedRegion(
                x=px_x, y=px_y, width=px_w, height=px_h,
                label="table", region_type="detected",
                content_hint="table", confidence=TABLE_REGION_CONFIDENCE,
            ))

    return tables


def _cluster_lines_by_position(lines, axis, gap_threshold):
    """Cluster lines by their position on the given axis, grouping nearby lines."""
    if not lines:
        return []
    sorted_lines = sorted(lines, key=lambda ln: ln[axis])
    clusters = [[sorted_lines[0]]]
    for line in sorted_lines[1:]:
        if line[axis] - clusters[-1][-1][axis] < gap_threshold:
            clusters[-1].append(line)
        else:
            clusters.append([line])
    return clusters


def _cluster_elements_spatially(bboxes, gap_threshold=ELEMENT_PROXIMITY_PX):
    """
    Cluster bounding boxes by spatial proximity.

    Iteratively merges bboxes that overlap or are within gap_threshold pixels.
    Each bbox is (x0, y0, x1, y1).

    Returns list of merged bounding boxes.
    """
    if not bboxes:
        return []

    # Start each bbox as its own cluster
    clusters = [list(bb) for bb in bboxes]  # mutable copies

    changed = True
    while changed:
        changed = False
        merged = []
        used = [False] * len(clusters)

        for i in range(len(clusters)):
            if used[i]:
                continue
            cx0, cy0, cx1, cy1 = clusters[i]

            for j in range(i + 1, len(clusters)):
                if used[j]:
                    continue
                ox0, oy0, ox1, oy1 = clusters[j]

                # Check if within gap_threshold (expand one box by gap and check overlap)
                if (cx0 - gap_threshold <= ox1 and cx1 + gap_threshold >= ox0 and
                        cy0 - gap_threshold <= oy1 and cy1 + gap_threshold >= oy0):
                    # Merge
                    cx0 = min(cx0, ox0)
                    cy0 = min(cy0, oy0)
                    cx1 = max(cx1, ox1)
                    cy1 = max(cy1, oy1)
                    used[j] = True
                    changed = True

            merged.append([cx0, cy0, cx1, cy1])
            used[i] = True

        clusters = merged

    return [tuple(c) for c in clusters]


def _classify_cluster(cluster_bbox, drawing_bboxes, text_bboxes):
    """Classify a cluster by its content density (drawing paths vs text blocks)."""
    cx0, cy0, cx1, cy1 = cluster_bbox
    drawing_count = 0
    text_count = 0

    for dx0, dy0, dx1, dy1 in drawing_bboxes:
        # Check overlap
        if dx0 < cx1 and dx1 > cx0 and dy0 < cy1 and dy1 > cy0:
            drawing_count += 1

    for tx0, ty0, tx1, ty1 in text_bboxes:
        if tx0 < cx1 and tx1 > cx0 and ty0 < cy1 and ty1 > cy0:
            text_count += 1

    total = drawing_count + text_count
    if total == 0:
        return "detail"

    text_ratio = text_count / total
    if text_ratio > 0.7:
        return "notes"
    elif text_ratio < 0.3:
        return "drawing_view"
    else:
        return "detail"


def _find_framing_rects(drawings, page_width, page_height, border_rects, min_area_pct=None):
    """
    Find internal framing rectangles that define content regions.

    On architectural drawings, distinct regions (detail callouts, schedule tables,
    notes sections, title blocks) are typically enclosed by rectangular outlines.
    These are smaller than page borders but large enough to be meaningful.

    Args:
        drawings: List of drawing dicts from page.get_drawings()
        page_width: Page width in points
        page_height: Page height in points
        border_rects: Already-detected border rectangles to exclude
        min_area_pct: Minimum area as fraction of page area

    Returns:
        List of (x0, y0, x1, y1) tuples in point coordinates
    """
    if min_area_pct is None:
        min_area_pct = get("drawing_regions", "pdf_vector", "framing_rect_min_area_pct")
    page_area = page_width * page_height
    min_area = page_area * min_area_pct
    framing_rects = []

    for d in drawings:
        items = d.get("items", [])
        rect = d.get("rect")
        if rect is None:
            continue
        x0, y0, x1, y1 = rect
        w = x1 - x0
        h = y1 - y0

        # Skip if too small
        if w * h < min_area:
            continue

        # Skip if it's a page border
        is_border = False
        for bx0, by0, bx1, by1 in border_rects:
            if (abs(x0 - bx0) < BORDER_TOLERANCE and abs(y0 - by0) < BORDER_TOLERANCE and
                    abs(x1 - bx1) < BORDER_TOLERANCE and abs(y1 - by1) < BORDER_TOLERANCE):
                is_border = True
                break
        if is_border:
            continue
        if _rect_spans_page((x0, y0, x1, y1), page_width, page_height):
            continue

        # Check if this is a rectangular path (closed shape with ~4 segments)
        # Rectangular drawings have items that trace a closed box
        is_rect_shape = False
        if len(items) >= 3:
            # Check if items form a rectangle: all line segments, bounding box
            # matches the rect closely
            line_count = sum(1 for it in items if it[0] == "l")
            if line_count >= 3:
                is_rect_shape = True
        # Also accept single "re" (rectangle) items
        for it in items:
            if it[0] == "re":
                is_rect_shape = True
                break

        if is_rect_shape:
            # Deduplicate: don't add if we already have a very similar rect
            is_dup = False
            for fx0, fy0, fx1, fy1 in framing_rects:
                if (abs(x0 - fx0) < BOUNDARY_TOLERANCE and abs(y0 - fy0) < BOUNDARY_TOLERANCE and
                        abs(x1 - fx1) < BOUNDARY_TOLERANCE and abs(y1 - fy1) < BOUNDARY_TOLERANCE):
                    is_dup = True
                    break
            if not is_dup:
                framing_rects.append((x0, y0, x1, y1))

    # Sort by area descending
    framing_rects.sort(key=lambda r: (r[2] - r[0]) * (r[3] - r[1]), reverse=True)
    return framing_rects


def _remove_contained_rects(rects):
    """Remove rectangles that are fully contained within larger ones."""
    if len(rects) <= 1:
        return rects
    result = []
    for i, (x0, y0, x1, y1) in enumerate(rects):
        contained = False
        for j, (ox0, oy0, ox1, oy1) in enumerate(rects):
            if i == j:
                continue
            # Check if rect i is fully inside rect j (with tolerance)
            if (x0 >= ox0 - CONTAINED_TOLERANCE and y0 >= oy0 - CONTAINED_TOLERANCE and
                    x1 <= ox1 + CONTAINED_TOLERANCE and y1 <= oy1 + CONTAINED_TOLERANCE):
                # Only remove if the outer rect is strictly larger
                outer_area = (ox1 - ox0) * (oy1 - oy0)
                inner_area = (x1 - x0) * (y1 - y0)
                if inner_area < outer_area * CONTAINMENT_RATIO:
                    contained = True
                    break
        if not contained:
            result.append((x0, y0, x1, y1))
    return result


def detect_regions_pdf_vector(
    page,
    page_width_px: int,
    page_height_px: int,
    min_region_size: int = MIN_REGION_SIZE,
    min_region_area: int = MIN_REGION_AREA,
    max_regions: int = MAX_REGIONS,
) -> List[DetectedRegion]:
    """
    Detect content regions by analyzing vector paths and text blocks in a PDF page.

    Uses PyMuPDF's page.get_drawings() and page.get_text("dict") to extract
    structural information directly from vector PDFs (e.g., CAD exports).

    Detection strategy:
    1. Find and remove page border frames
    2. Find internal framing rectangles (detail boxes, schedule outlines, etc.)
       → these directly define regions
    3. Detect table grids from regular line patterns
    4. Cluster remaining elements by spatial proximity
    5. Classify each region by content density

    Args:
        page: fitz.Page object
        page_width_px: Rendered pixel width (for coordinate mapping)
        page_height_px: Rendered pixel height
        min_region_size: Minimum width or height for a region
        min_region_area: Minimum pixel area for a region
        max_regions: Maximum number of regions to return

    Returns:
        List of DetectedRegion objects. Empty list if page is not vector-based.
    """
    if not _is_vector_pdf(page):
        return []

    page_rect = page.rect
    page_w_pts = page_rect.width
    page_h_pts = page_rect.height

    if page_w_pts <= 0 or page_h_pts <= 0:
        return []

    # DPI scale: PyMuPDF uses points (72 DPI), rendered at 150 DPI
    dpi_scale = page_width_px / page_w_pts

    # Step 1: Get all vector drawings
    drawings = page.get_drawings()

    # Step 2: Find and exclude border frames
    border_rects = _find_border_rects(drawings, page_w_pts, page_h_pts)

    # Step 3: Find internal framing rectangles that define regions
    framing_rects = _find_framing_rects(
        drawings, page_w_pts, page_h_pts, border_rects
    )
    framing_rects = _remove_contained_rects(framing_rects)

    # Step 4: Collect all drawing bounding boxes (excluding borders)
    drawing_bboxes = []  # in point coordinates
    for d in drawings:
        rect = d.get("rect")
        if rect is None:
            continue
        x0, y0, x1, y1 = rect
        # Skip border rectangles
        is_border = False
        for bx0, by0, bx1, by1 in border_rects:
            if (abs(x0 - bx0) < BORDER_TOLERANCE and abs(y0 - by0) < BORDER_TOLERANCE and
                    abs(x1 - bx1) < BORDER_TOLERANCE and abs(y1 - by1) < BORDER_TOLERANCE):
                is_border = True
                break
        if is_border:
            continue
        # Skip tiny paths
        if (x1 - x0) < TINY_PATH_THRESHOLD and (y1 - y0) < TINY_PATH_THRESHOLD:
            continue
        drawing_bboxes.append((x0, y0, x1, y1))

    # Step 5: Get text blocks with positions
    text_bboxes = []
    try:
        text_dict = page.get_text("dict")
        for block in text_dict.get("blocks", []):
            if block.get("type") == 0:  # text block
                bbox = block.get("bbox")
                if bbox:
                    text_bboxes.append(tuple(bbox))
    except Exception:
        pass

    # Step 6: Convert framing rects to regions (these are high-confidence)
    framed_regions = []
    framed_areas_pts = []  # track areas to exclude from further clustering
    for fx0, fy0, fx1, fy1 in framing_rects:
        px_x = int(fx0 * dpi_scale)
        px_y = int(fy0 * dpi_scale)
        px_w = int((fx1 - fx0) * dpi_scale)
        px_h = int((fy1 - fy0) * dpi_scale)

        if px_w < min_region_size or px_h < min_region_size:
            continue
        if px_w * px_h < min_region_area:
            continue

        # Clamp to image bounds
        px_x = max(0, min(px_x, page_width_px))
        px_y = max(0, min(px_y, page_height_px))
        px_w = min(px_w, page_width_px - px_x)
        px_h = min(px_h, page_height_px - px_y)

        content_hint = _classify_cluster(
            (fx0, fy0, fx1, fy1), drawing_bboxes, text_bboxes
        )

        framed_regions.append(DetectedRegion(
            x=px_x, y=px_y, width=px_w, height=px_h,
            region_type="detected", content_hint=content_hint,
            confidence=FRAMED_REGION_CONFIDENCE,
        ))
        framed_areas_pts.append((fx0, fy0, fx1, fy1))

    # Step 7: Detect tables
    table_regions = _detect_tables_from_lines(drawings, page_w_pts, page_h_pts, dpi_scale)

    # Build set of already-claimed areas (framed + table) for exclusion
    claimed_areas_pts = list(framed_areas_pts)
    for tr in table_regions:
        t_x0 = tr.x / dpi_scale
        t_y0 = tr.y / dpi_scale
        t_x1 = (tr.x + tr.width) / dpi_scale
        t_y1 = (tr.y + tr.height) / dpi_scale
        claimed_areas_pts.append((t_x0, t_y0, t_x1, t_y1))

    # Step 8: Cluster remaining elements not inside framed/table areas
    unclaimed_bboxes = []
    for bbox in drawing_bboxes + text_bboxes:
        bx0, by0, bx1, by1 = bbox
        in_claimed = False
        for cx0, cy0, cx1, cy1 in claimed_areas_pts:
            if bx0 >= cx0 - CONTAINED_TOLERANCE and by0 >= cy0 - CONTAINED_TOLERANCE and bx1 <= cx1 + CONTAINED_TOLERANCE and by1 <= cy1 + CONTAINED_TOLERANCE:
                in_claimed = True
                break
        if not in_claimed:
            unclaimed_bboxes.append(bbox)

    # Cluster using proximity threshold (in points, convert from pixels)
    proximity_pts = ELEMENT_PROXIMITY_PX / dpi_scale
    clusters = _cluster_elements_spatially(unclaimed_bboxes, gap_threshold=proximity_pts)

    # Step 9: Convert clusters to regions and classify
    cluster_regions = []
    for cx0, cy0, cx1, cy1 in clusters:
        px_x = int(cx0 * dpi_scale)
        px_y = int(cy0 * dpi_scale)
        px_w = int((cx1 - cx0) * dpi_scale)
        px_h = int((cy1 - cy0) * dpi_scale)

        if px_w < min_region_size or px_h < min_region_size:
            continue
        if px_w * px_h < min_region_area:
            continue

        # Clamp to image bounds
        px_x = max(0, min(px_x, page_width_px))
        px_y = max(0, min(px_y, page_height_px))
        px_w = min(px_w, page_width_px - px_x)
        px_h = min(px_h, page_height_px - px_y)

        content_hint = _classify_cluster(
            (cx0, cy0, cx1, cy1), drawing_bboxes, text_bboxes
        )

        cluster_regions.append(DetectedRegion(
            x=px_x, y=px_y, width=px_w, height=px_h,
            region_type="detected", content_hint=content_hint,
            confidence=CLUSTER_REGION_CONFIDENCE,
        ))

    # Combine all region types
    all_regions = framed_regions + table_regions + cluster_regions
    all_regions.sort(key=lambda r: r.area, reverse=True)

    logger.info(
        f"PDF vector analysis detected {len(all_regions)} regions "
        f"({len(framed_regions)} framed, {len(table_regions)} tables, "
        f"{len(cluster_regions)} clusters) from {len(drawings)} vector paths"
    )

    return all_regions[:max_regions]


def detect_regions_heuristic(
    image: Image.Image,
    min_region_size: int = MIN_REGION_SIZE,
    min_region_area: int = MIN_REGION_AREA,
    max_regions: int = MAX_REGIONS,
) -> List[DetectedRegion]:
    """
    Detect content regions in a drawing using image analysis heuristics.

    Strategy:
    1. Convert to grayscale and detect content vs whitespace
    2. Find horizontal and vertical whitespace bands (gutters between drawing views)
    3. Use those bands to segment the image into rectangular regions
    4. Filter out regions that are too small to be meaningful

    Args:
        image: PIL Image (full drawing page)
        min_region_size: Minimum width or height for a region
        min_region_area: Minimum pixel area for a region
        max_regions: Maximum number of regions to return

    Returns:
        List of DetectedRegion objects
    """
    w, h = image.size

    # Convert to grayscale for analysis
    gray = np.array(image.convert("L"))

    # Threshold: pixels below 240 are "content" (drawings are mostly black on white)
    content_thresh = get("drawing_regions", "content_threshold")
    content_mask = gray < content_thresh

    # Find horizontal whitespace bands (rows with very little content)
    row_density = content_mask.mean(axis=1)  # fraction of content pixels per row
    min_gap = get("drawing_regions", "min_gap")
    ws_threshold = get("drawing_regions", "whitespace_threshold")
    h_splits = _find_splits(row_density, min_gap=min_gap, threshold=ws_threshold)

    # Find vertical whitespace bands (columns with very little content)
    col_density = content_mask.mean(axis=0)  # fraction of content pixels per column
    v_splits = _find_splits(col_density, min_gap=min_gap, threshold=ws_threshold)

    # Add image boundaries
    h_boundaries = [0] + h_splits + [h]
    v_boundaries = [0] + v_splits + [w]

    # Generate candidate regions from the grid
    regions = []
    for i in range(len(h_boundaries) - 1):
        for j in range(len(v_boundaries) - 1):
            y1 = h_boundaries[i]
            y2 = h_boundaries[i + 1]
            x1 = v_boundaries[j]
            x2 = v_boundaries[j + 1]

            rw = x2 - x1
            rh = y2 - y1

            if rw < min_region_size or rh < min_region_size:
                continue
            if rw * rh < min_region_area:
                continue

            # Check if region actually has meaningful content
            region_content = content_mask[y1:y2, x1:x2]
            content_density_threshold = get("drawing_regions", "content_density_threshold")
            if region_content.mean() < content_density_threshold:
                continue

            regions.append(DetectedRegion(
                x=x1, y=y1, width=rw, height=rh,
                region_type="detected",
                confidence=min(1.0, region_content.mean() * DENSITY_SCALING_FACTOR),
            ))

    # If heuristic detection found too few or too many regions, fall back to tiling
    if len(regions) < 2:
        regions = _generate_tiles(w, h, min_region_size, min_region_area)

    # Sort by area (largest first) and limit
    regions.sort(key=lambda r: r.area, reverse=True)
    return regions[:max_regions]


def _find_splits(density: np.ndarray, min_gap: int = 50, threshold: float = 0.02) -> List[int]:
    """
    Find split points in a 1D density array.

    A split occurs where there's a continuous band of low-density rows/columns,
    indicating whitespace between drawing elements.

    Args:
        density: 1D array of content density per row or column
        min_gap: Minimum gap width in pixels to count as a split
        threshold: Density below this counts as "whitespace"

    Returns:
        List of split positions (midpoints of whitespace gaps)
    """
    is_gap = density < threshold
    splits = []
    gap_start = None

    for i, is_g in enumerate(is_gap):
        if is_g and gap_start is None:
            gap_start = i
        elif not is_g and gap_start is not None:
            gap_len = i - gap_start
            if gap_len >= min_gap:
                splits.append(gap_start + gap_len // 2)
            gap_start = None

    # Handle gap at the end (but don't add - it's the image boundary)
    return splits


def _generate_tiles(
    width: int,
    height: int,
    min_region_size: int = MIN_REGION_SIZE,
    min_region_area: int = MIN_REGION_AREA,
) -> List[DetectedRegion]:
    """
    Generate overlapping tile regions as a fallback when heuristic detection
    doesn't find natural boundaries.

    Tiles are sized so each one gets good patch coverage from ColPali.
    Target: tiles around 1500-2000px per side for good detail at 1024 patches.

    Args:
        width: Image width
        height: Image height
        min_region_size: Minimum tile dimension
        min_region_area: Minimum tile area

    Returns:
        List of tile regions
    """
    # Target tile size: aim for tiles that give ColPali good coverage
    # ColPali input is typically resized to ~768-1024px, so tiles of ~1500-2000px
    # give 2:1 compression ratio instead of the original 6:1+
    target_tile = get("drawing_regions", "target_tile_size")
    overlap = TILE_OVERLAP

    tiles = []

    # Calculate grid
    n_cols = max(1, int(np.ceil((width - overlap) / (target_tile - overlap))))
    n_rows = max(1, int(np.ceil((height - overlap) / (target_tile - overlap))))

    # Recalculate actual tile sizes to cover the image evenly
    if n_cols > 1:
        step_x = (width - target_tile) / (n_cols - 1)
    else:
        step_x = 0

    if n_rows > 1:
        step_y = (height - target_tile) / (n_rows - 1)
    else:
        step_y = 0

    for row in range(n_rows):
        for col in range(n_cols):
            x = int(col * step_x) if n_cols > 1 else 0
            y = int(row * step_y) if n_rows > 1 else 0

            tile_w = min(target_tile, width - x)
            tile_h = min(target_tile, height - y)

            if tile_w < min_region_size or tile_h < min_region_size:
                continue
            if tile_w * tile_h < min_region_area:
                continue

            tiles.append(DetectedRegion(
                x=x, y=y, width=tile_w, height=tile_h,
                region_type="tile",
                label=f"tile_r{row}_c{col}",
            ))

    return tiles


def detect_regions_content_aware_tiling(
    image: Image.Image,
    min_region_size: int = MIN_REGION_SIZE,
    min_region_area: int = MIN_REGION_AREA,
    max_regions: int = MAX_REGIONS,
) -> List[DetectedRegion]:
    """
    Generate tiles whose boundaries respect content density.

    Instead of a blind grid, computes a coarse density heatmap and shifts
    tile boundaries toward local density minima to avoid splitting content.

    Args:
        image: PIL Image (full drawing page)
        min_region_size: Minimum dimension for a region
        min_region_area: Minimum pixel area for a region
        max_regions: Maximum number of regions to return

    Returns:
        List of DetectedRegion objects with region_type="content_tile"
    """
    w, h = image.size
    gray = np.array(image.convert("L"))

    # Content mask (pixels below threshold are content)
    content_thresh = get("drawing_regions", "content_threshold")
    content_mask = (gray < content_thresh).astype(np.float32)

    # Compute coarse density on a grid
    grid_size = get("drawing_regions", "grid_size")
    rows_per_cell = max(1, h // grid_size)
    cols_per_cell = max(1, w // grid_size)

    # Row and column density profiles
    row_density = content_mask.mean(axis=1)
    col_density = content_mask.mean(axis=0)

    # Target tile size
    target_tile = get("drawing_regions", "target_tile_size")
    overlap = TILE_OVERLAP

    # Calculate how many tiles we need
    n_cols = max(1, int(np.ceil((w - overlap) / (target_tile - overlap))))
    n_rows = max(1, int(np.ceil((h - overlap) / (target_tile - overlap))))

    # Find optimal split points at density minima
    h_splits = _find_density_minima_splits(row_density, n_rows, window=rows_per_cell)
    v_splits = _find_density_minima_splits(col_density, n_cols, window=cols_per_cell)

    h_boundaries = [0] + h_splits + [h]
    v_boundaries = [0] + v_splits + [w]

    tiles = []
    for i in range(len(h_boundaries) - 1):
        for j in range(len(v_boundaries) - 1):
            y1 = h_boundaries[i]
            y2 = h_boundaries[i + 1]
            x1 = v_boundaries[j]
            x2 = v_boundaries[j + 1]

            rw = x2 - x1
            rh = y2 - y1

            if rw < min_region_size or rh < min_region_size:
                continue
            if rw * rh < min_region_area:
                continue

            tiles.append(DetectedRegion(
                x=x1, y=y1, width=rw, height=rh,
                region_type="content_tile",
                content_hint="content_tile",
                label=f"tile_r{i}_c{j}",
            ))

    # If content-aware didn't produce enough tiles, fall back to blind grid
    if len(tiles) < 2:
        tiles = _generate_tiles(w, h, min_region_size, min_region_area)

    tiles.sort(key=lambda r: r.area, reverse=True)
    return tiles[:max_regions]


def _find_density_minima_splits(density, n_splits, window=50):
    """
    Find split points at local density minima.

    Divides the density array into n_splits+1 roughly equal segments,
    then within a window around each ideal split point, picks the position
    with the lowest average density.
    """
    if n_splits <= 0:
        return []

    length = len(density)
    splits = []

    for i in range(1, n_splits + 1):
        # Ideal split position
        ideal = int(length * i / (n_splits + 1))
        # Search window
        start = max(0, ideal - window)
        end = min(length, ideal + window)

        if start >= end:
            splits.append(ideal)
            continue

        # Find the position with minimum average density in a small neighborhood
        best_pos = ideal
        best_score = float("inf")
        neighborhood = max(1, window // NEIGHBORHOOD_DIVISOR)

        for pos in range(start, end):
            region_start = max(0, pos - neighborhood)
            region_end = min(length, pos + neighborhood)
            score = density[region_start:region_end].mean()
            if score < best_score:
                best_score = score
                best_pos = pos

        splits.append(best_pos)

    return sorted(splits)


def classify_regions_vlm(
    image: Image.Image,
    regions: List[DetectedRegion],
    api_key: Optional[str] = None,
    model: str = None,
    base_url: Optional[str] = None,
) -> List[DetectedRegion]:
    """
    Use a VLM to label pre-detected regions (classifier, not detector).

    Draws numbered colored rectangles on a copy of the image and asks the VLM
    to provide descriptive labels for each numbered region.

    Args:
        image: Full drawing page as PIL Image
        regions: Pre-detected regions to label
        api_key: API key for VLM
        model: Model identifier
        base_url: API base URL

    Returns:
        Regions with updated labels
    """
    if not regions:
        return regions

    try:
        import httpx
    except ImportError:
        logger.warning("httpx not installed, skipping VLM classification")
        return regions

    from backend.llm_config import resolve_llm_config, is_remote_api, build_auth_headers

    if model is None:
        model = get("llm", "vlm_model")
    if not base_url or not api_key:
        resolved_url, resolved_key = resolve_llm_config()
        if not base_url:
            base_url = resolved_url
        if not api_key:
            api_key = resolved_key

    if is_remote_api(base_url) and not api_key:
        logger.warning("No API key for VLM classification, returning unlabeled regions")
        return regions

    from PIL import ImageDraw

    # Draw numbered rectangles on a copy of the image
    annotated = image.copy()
    draw = ImageDraw.Draw(annotated)
    colors = ["red", "blue", "green", "orange", "purple", "cyan", "magenta", "yellow"]

    for i, region in enumerate(regions):
        color = colors[i % len(colors)]
        bbox = region.bbox
        draw.rectangle(bbox, outline=color, width=4)
        draw.text((bbox[0] + 5, bbox[1] + 5), str(i + 1), fill=color)

    # Downscale for API
    w, h = annotated.size
    max_api_dim = get("image", "max_api_dimension")
    scale = min(max_api_dim / w, max_api_dim / h, 1.0)
    if scale < 1.0:
        annotated = annotated.resize(
            (int(w * scale), int(h * scale)), Image.Resampling.LANCZOS
        )

    vlm_jpeg_quality = get("image", "vlm_jpeg_quality")
    buffer = io.BytesIO()
    annotated.save(buffer, format="JPEG", quality=vlm_jpeg_quality)
    import base64
    image_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    prompt = f"""This architectural/construction drawing has {len(regions)} numbered regions outlined in colored rectangles.

For each numbered region (1 through {len(regions)}), provide a short descriptive label.

Respond with ONLY a JSON object mapping region numbers to labels:
{{"1": "floor plan", "2": "door schedule", "3": "general notes", ...}}"""

    try:
        headers = build_auth_headers(api_key)
        vlm_classifier_max_tokens = get("llm", "vlm_classifier_max_tokens")
        vlm_timeout = get("llm", "vlm_timeout_seconds")

        response = httpx.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "max_tokens": vlm_classifier_max_tokens,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }],
            },
            timeout=vlm_timeout,
        )
        response.raise_for_status()
        result = response.json()

        response_text = result["choices"][0]["message"]["content"].strip()
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        labels = json.loads(response_text)

        for i, region in enumerate(regions):
            label = labels.get(str(i + 1), "")
            if label:
                region.label = label

        logger.info(f"VLM classified {len(labels)} region labels")

    except Exception as e:
        logger.warning(f"VLM classification failed: {e}, returning unlabeled regions")

    return regions


def detect_regions_vlm_legacy(
    image: Image.Image,
    api_key: Optional[str] = None,
    model: str = None,
    base_url: Optional[str] = None,
) -> List[DetectedRegion]:
    """
    Use a vision-language model to identify semantic regions in a drawing.

    Sends the image to a VLM through an OpenAI-compatible API (OpenRouter,
    OpenAI, or local Ollama) and asks it to identify distinct drawing regions
    with bounding boxes and labels.

    Args:
        image: PIL Image (full drawing page)
        api_key: API key (checks OPENROUTER_API_KEY then OPENAI_API_KEY; not needed for Ollama)
        model: Model identifier to use for detection
        base_url: API base URL (defaults to LLM_BASE_URL env var)

    Returns:
        List of DetectedRegion objects with semantic labels
    """
    try:
        import httpx
    except ImportError:
        logger.warning("httpx package not installed, falling back to heuristic detection")
        return detect_regions_heuristic(image)

    from backend.llm_config import resolve_llm_config, is_remote_api, build_auth_headers

    if model is None:
        model = get("llm", "vlm_model")
    if not base_url or not api_key:
        resolved_url, resolved_key = resolve_llm_config()
        if not base_url:
            base_url = resolved_url
        if not api_key:
            api_key = resolved_key

    if is_remote_api(base_url) and not api_key:
        logger.warning("No API key set, falling back to heuristic detection")
        return detect_regions_heuristic(image)

    w, h = image.size

    # Downscale for the API call (we just need region locations, not full detail)
    max_api_dim = get("image", "max_api_dimension")
    scale = min(max_api_dim / w, max_api_dim / h, 1.0)
    if scale < 1.0:
        api_image = image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    else:
        api_image = image

    # Convert to base64
    vlm_jpeg_quality = get("image", "vlm_jpeg_quality")
    buffer = io.BytesIO()
    api_image.save(buffer, format="JPEG", quality=vlm_jpeg_quality)
    import base64
    image_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

    prompt = f"""Analyze this architectural/construction drawing and identify distinct visual regions.

The full image is {w}x{h} pixels. I need you to identify separate drawing views, detail sections,
tables/schedules, title blocks, notes sections, and other distinct areas.

For each region, provide:
- Bounding box coordinates (x, y, width, height) in pixels relative to the FULL {w}x{h} image
- A short descriptive label (e.g., "floor plan", "section A-A", "door schedule", "general notes")
- Confidence score (0.0 to 1.0)

Respond with ONLY a JSON array, no other text:
[
  {{"x": 0, "y": 0, "width": 3000, "height": 2400, "label": "floor plan", "confidence": 0.95}},
  ...
]

Rules:
- Minimum region size: {MIN_REGION_SIZE}x{MIN_REGION_SIZE} pixels
- Don't include the title block as a search-worthy region (it's metadata)
- Focus on regions that contain meaningful drawing content
- Regions can overlap slightly if views share borders
- Maximum {MAX_REGIONS} regions"""

    try:
        headers = build_auth_headers(api_key)
        vlm_max_tokens = get("llm", "vlm_max_tokens")
        vlm_timeout = get("llm", "vlm_timeout_seconds")

        response = httpx.post(
            f"{base_url}/chat/completions",
            headers=headers,
            json={
                "model": model,
                "max_tokens": vlm_max_tokens,
                "messages": [{
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}",
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }],
            },
            timeout=vlm_timeout,
        )
        response.raise_for_status()
        result = response.json()

        # Parse the JSON response (OpenAI-compatible format)
        response_text = result["choices"][0]["message"]["content"].strip()
        # Handle potential markdown code fences
        if response_text.startswith("```"):
            response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        region_data = json.loads(response_text)
        regions = []
        for r in region_data:
            rx = max(0, int(r["x"]))
            ry = max(0, int(r["y"]))
            rw = min(int(r["width"]), w - rx)
            rh = min(int(r["height"]), h - ry)

            if rw < MIN_REGION_SIZE or rh < MIN_REGION_SIZE:
                continue

            regions.append(DetectedRegion(
                x=rx, y=ry, width=rw, height=rh,
                label=r.get("label", ""),
                confidence=float(r.get("confidence", 0.8)),
                region_type="vlm_detected",
            ))

        if not regions:
            logger.warning("VLM returned no valid regions, falling back to heuristic")
            return detect_regions_heuristic(image)

        return regions[:MAX_REGIONS]

    except Exception as e:
        logger.warning(f"VLM detection failed: {e}, falling back to heuristic")
        return detect_regions_heuristic(image)


def extract_region_images(
    image: Image.Image,
    regions: List[DetectedRegion],
    padding: int = None,
) -> List[Tuple[Image.Image, DetectedRegion]]:
    """
    Crop region images from the full drawing.

    Args:
        image: Full drawing image
        regions: List of detected regions
        padding: Extra pixels to add around each region for context

    Returns:
        List of (cropped_image, region) tuples
    """
    if padding is None:
        padding = get("drawing_regions", "region_extract_padding")
    w, h = image.size
    results = []

    for region in regions:
        # Add padding but stay within bounds
        x1 = max(0, region.x - padding)
        y1 = max(0, region.y - padding)
        x2 = min(w, region.x + region.width + padding)
        y2 = min(h, region.y + region.height + padding)

        crop = image.crop((x1, y1, x2, y2))
        results.append((crop, region))

    return results


def detect_and_extract_regions(
    image: Image.Image,
    use_vlm: bool = False,
    vlm_api_key: Optional[str] = None,
    force: bool = False,
    min_region_size: int = MIN_REGION_SIZE,
    min_region_area: int = MIN_REGION_AREA,
    max_regions: int = MAX_REGIONS,
    detection_method: str = "auto",
    pdf_page=None,
) -> List[Tuple[Image.Image, DetectedRegion]]:
    """
    Main entry point: detect regions in a drawing and extract cropped images.

    If the image is small enough that ColPali can handle it well natively,
    returns a single region covering the full page (unless force=True).

    Detection methods:
        "auto" — tries pdf_vector (if pdf_page given) → heuristic → content-aware tiling
        "pdf_vector" — PDF vector analysis only (requires pdf_page)
        "heuristic" — whitespace gutter detection only
        "vlm_legacy" — VLM-based bounding box detection (original behavior)

    Args:
        image: Full drawing page as PIL Image
        use_vlm: Whether to use VLM to label detected regions (classifier overlay)
        vlm_api_key: API key for VLM (defaults to env var)
        force: Force region detection even on small images
        min_region_size: Minimum dimension for a region
        min_region_area: Minimum pixel area for a region
        max_regions: Maximum number of regions
        detection_method: Detection strategy ("auto", "pdf_vector", "heuristic", "vlm_legacy")
        pdf_page: fitz.Page object for PDF vector analysis

    Returns:
        List of (cropped_image, region_metadata) tuples.
        If no region detection is needed, returns [(original_image, full_page_region)].
    """
    w, h = image.size

    if not should_detect_regions(image, force=force):
        full_region = DetectedRegion(
            x=0, y=0, width=w, height=h,
            label="full_page", region_type="full_page",
        )
        return [(image, full_region)]

    logger.info(f"Image {w}x{h} qualifies for region detection (area={w*h:,} > threshold={LARGE_PAGE_THRESHOLD:,})")

    det_kwargs = dict(
        min_region_size=min_region_size,
        min_region_area=min_region_area,
        max_regions=max_regions,
    )

    regions = []

    if detection_method == "auto":
        # 1. Try PDF vector analysis if page provided
        if pdf_page is not None:
            regions = detect_regions_pdf_vector(
                pdf_page, w, h, **det_kwargs
            )
            if len(regions) >= 2:
                logger.info(f"PDF vector analysis found {len(regions)} regions")

        # 2. Try whitespace heuristic
        if len(regions) < 2:
            regions = detect_regions_heuristic(image, **det_kwargs)
            if len(regions) >= 2:
                logger.info(f"Heuristic found {len(regions)} regions")

        # 3. Content-aware tiling (always succeeds)
        if len(regions) < 2:
            regions = detect_regions_content_aware_tiling(image, **det_kwargs)
            logger.info(f"Content-aware tiling produced {len(regions)} tiles")

    elif detection_method == "pdf_vector":
        if pdf_page is None:
            raise ValueError("pdf_vector detection requires pdf_page argument")
        regions = detect_regions_pdf_vector(pdf_page, w, h, **det_kwargs)

    elif detection_method == "heuristic":
        regions = detect_regions_heuristic(image, **det_kwargs)

    elif detection_method == "vlm_legacy":
        regions = detect_regions_vlm_legacy(image, api_key=vlm_api_key)

    else:
        raise ValueError(f"Unknown detection_method: {detection_method!r}")

    # Optional VLM classifier overlay to label regions
    if use_vlm and regions and detection_method != "vlm_legacy":
        regions = classify_regions_vlm(image, regions, api_key=vlm_api_key)

    # Extract region images
    extracted = extract_region_images(image, regions)

    # Always include the full page as well (lower priority for search, but provides context)
    full_region = DetectedRegion(
        x=0, y=0, width=w, height=h,
        label="full_page", region_type="full_page",
    )
    extracted.insert(0, (image, full_region))

    return extracted
