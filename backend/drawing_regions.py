"""
Drawing region detection for large-format architectural/construction drawings.

Large drawings (e.g., 40"x32") compress poorly into ColPali's fixed patch grid (~1024 patches),
losing fine detail. This module detects meaningful sub-regions (elevations, details, tables,
schedules) and produces crops that each get full patch coverage when embedded separately.

Two detection strategies:
1. Heuristic: Uses image analysis to find content boundaries via whitespace/border detection
2. VLM-assisted: Uses a vision-language model to identify and label semantic regions
"""

import io
import json
import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)

# Minimum region dimension in pixels to be worth embedding separately
MIN_REGION_SIZE = 200
# Minimum pixel area for a region to be considered meaningful
MIN_REGION_AREA = 100_000
# Page size threshold (pixels) above which region detection activates
# At 150 DPI:
#   - Letter (8.5x11): 1275x1650 = 2.1M pixels (excluded)
#   - Tabloid (11x17): 1650x2550 = 4.2M pixels (included)
#   - ARCH D (24x36): 3600x5400 = 19.4M pixels (included)
#   - Large format (40x32): 6000x4800 = 28.8M pixels (included)
LARGE_PAGE_THRESHOLD = 1400 * 2000  # ~2.8M pixels - includes 11x17 and above
# Overlap in pixels between adjacent tiles in the grid fallback
TILE_OVERLAP = 100
# Maximum regions to extract from a single page
MAX_REGIONS = 12


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
    content_mask = gray < 240

    # Find horizontal whitespace bands (rows with very little content)
    row_density = content_mask.mean(axis=1)  # fraction of content pixels per row
    h_splits = _find_splits(row_density, min_gap=50, threshold=0.02)

    # Find vertical whitespace bands (columns with very little content)
    col_density = content_mask.mean(axis=0)  # fraction of content pixels per column
    v_splits = _find_splits(col_density, min_gap=50, threshold=0.02)

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
            if region_content.mean() < 0.005:  # Less than 0.5% content = empty
                continue

            regions.append(DetectedRegion(
                x=x1, y=y1, width=rw, height=rh,
                region_type="detected",
                confidence=min(1.0, region_content.mean() * 10),  # Scale content density
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
    target_tile = 1800
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


def detect_regions_vlm(
    image: Image.Image,
    api_key: Optional[str] = None,
    model: str = "claude-sonnet-4-20250514",
) -> List[DetectedRegion]:
    """
    Use a vision-language model to identify semantic regions in a drawing.

    Sends the image to Claude and asks it to identify distinct drawing regions
    with bounding boxes and labels.

    Args:
        image: PIL Image (full drawing page)
        api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        model: Model to use for detection

    Returns:
        List of DetectedRegion objects with semantic labels
    """
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package not installed, falling back to heuristic detection")
        return detect_regions_heuristic(image)

    api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.warning("No ANTHROPIC_API_KEY set, falling back to heuristic detection")
        return detect_regions_heuristic(image)

    w, h = image.size

    # Downscale for the API call (we just need region locations, not full detail)
    max_api_dim = 1500
    scale = min(max_api_dim / w, max_api_dim / h, 1.0)
    if scale < 1.0:
        api_image = image.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
    else:
        api_image = image

    # Convert to base64
    buffer = io.BytesIO()
    api_image.save(buffer, format="JPEG", quality=80)
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
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model,
            max_tokens=2000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": prompt},
                ],
            }],
        )

        # Parse the JSON response
        response_text = response.content[0].text.strip()
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
    padding: int = 20,
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
) -> List[Tuple[Image.Image, DetectedRegion]]:
    """
    Main entry point: detect regions in a drawing and extract cropped images.

    If the image is small enough that ColPali can handle it well natively,
    returns a single region covering the full page (unless force=True).

    Args:
        image: Full drawing page as PIL Image
        use_vlm: Whether to use VLM for semantic region detection
        vlm_api_key: API key for VLM (defaults to env var)
        force: Force region detection even on small images
        min_region_size: Minimum dimension for a region
        min_region_area: Minimum pixel area for a region
        max_regions: Maximum number of regions

    Returns:
        List of (cropped_image, region_metadata) tuples.
        If no region detection is needed, returns [(original_image, full_page_region)].
    """
    w, h = image.size

    if not should_detect_regions(image, force=force):
        # Image is small enough for ColPali to handle natively
        full_region = DetectedRegion(
            x=0, y=0, width=w, height=h,
            label="full_page", region_type="full_page",
        )
        return [(image, full_region)]

    logger.info(f"Image {w}x{h} qualifies for region detection (area={w*h:,} > threshold={LARGE_PAGE_THRESHOLD:,})")

    # Detect regions
    if use_vlm:
        regions = detect_regions_vlm(image, api_key=vlm_api_key)
        logger.info(f"VLM detected {len(regions)} regions")
    else:
        regions = detect_regions_heuristic(
            image,
            min_region_size=min_region_size,
            min_region_area=min_region_area,
            max_regions=max_regions,
        )
        logger.info(f"Heuristic detected {len(regions)} regions")

    # Extract region images
    extracted = extract_region_images(image, regions)

    # Always include the full page as well (lower priority for search, but provides context)
    full_region = DetectedRegion(
        x=0, y=0, width=w, height=h,
        label="full_page", region_type="full_page",
    )
    extracted.insert(0, (image, full_region))

    return extracted
