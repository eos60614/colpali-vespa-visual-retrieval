"""
Dual text extraction module: PDF layer text + OCR.

Extracts text from both the PDF text layer and via OCR, then intelligently
merges the results for optimal search coverage.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from PIL import Image

from backend.config import get
from backend.logging_config import get_logger

logger = get_logger(__name__)


class TextExtractionMethod(Enum):
    """Method used for primary text extraction."""

    LAYER = "layer"  # PDF text layer only
    OCR = "ocr"  # OCR only (scanned document)
    MERGED = "merged"  # Combined layer + OCR
    NONE = "none"  # No text extracted


class OCREngine(Enum):
    """Available OCR engines."""

    PYMUPDF = "pymupdf"  # PyMuPDF built-in OCR (requires tesseract)
    TESSERACT = "tesseract"  # Direct pytesseract
    NONE = "none"  # OCR disabled


@dataclass
class TextExtractionResult:
    """Result of dual text extraction."""

    # Extracted text
    layer_text: str  # From PDF text layer
    ocr_text: str  # From OCR
    merged_text: str  # Combined/primary text

    # Metadata
    extraction_method: TextExtractionMethod
    ocr_confidence: float  # 0-1, or -1 if OCR not run
    layer_coverage: float  # Estimated text coverage from layer

    # Diagnostic info
    layer_char_count: int
    ocr_char_count: int
    ocr_engine_used: Optional[str] = None


def sanitize_text(text: str) -> str:
    """
    Remove illegal control characters from extracted text.

    Vespa rejects text containing certain control characters like null (0x0).
    This removes all ASCII control characters except common whitespace.
    """
    if not text:
        return ""
    # Remove ASCII control chars (0x00-0x1F and 0x7F) except tab, newline, carriage return
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)


def normalize_whitespace(text: str) -> str:
    """Normalize excessive whitespace while preserving structure."""
    if not text:
        return ""
    # Replace multiple spaces with single space
    text = re.sub(r"[ \t]+", " ", text)
    # Replace 3+ newlines with 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_layer_text(page) -> Tuple[str, float]:
    """
    Extract text from PDF text layer.

    Args:
        page: fitz.Page object

    Returns:
        Tuple of (extracted text, estimated coverage ratio)
    """
    try:
        text = page.get_text("text")
        text = sanitize_text(text)
        text = normalize_whitespace(text)

        # Estimate coverage
        try:
            text_dict = page.get_text("dict")
            text_blocks = text_dict.get("blocks", [])
            text_area = sum(
                (b["bbox"][2] - b["bbox"][0]) * (b["bbox"][3] - b["bbox"][1])
                for b in text_blocks
                if b.get("type") == 0
            )
            rect = page.rect
            page_area = rect.width * rect.height
            coverage = text_area / page_area if page_area > 0 else 0
        except Exception:
            # Fallback: estimate from text length
            coverage = min(len(text) / 5000, 1.0) if text else 0

        return text, coverage

    except Exception as e:
        logger.warning(f"Layer text extraction failed: {e}")
        return "", 0.0


def extract_ocr_text_pymupdf(page) -> Tuple[str, float]:
    """
    Extract text using PyMuPDF's built-in OCR.

    Requires: pip install pymupdf[ocr] and Tesseract installed.

    Args:
        page: fitz.Page object

    Returns:
        Tuple of (OCR text, confidence score)
    """
    try:
        # Get OCR'd text page
        tp = page.get_textpage_ocr(language="eng", dpi=150)
        text = page.get_text("text", textpage=tp)
        text = sanitize_text(text)
        text = normalize_whitespace(text)

        # PyMuPDF doesn't provide confidence directly, estimate from structure
        confidence = 0.8 if len(text) > 50 else 0.5

        return text, confidence

    except Exception as e:
        logger.warning(f"PyMuPDF OCR failed: {e}")
        return "", 0.0


def extract_ocr_text_tesseract(image: Image.Image) -> Tuple[str, float]:
    """
    Extract text using pytesseract directly.

    Requires: pip install pytesseract and Tesseract installed.

    Args:
        image: PIL Image

    Returns:
        Tuple of (OCR text, confidence score)
    """
    try:
        import pytesseract

        # Get detailed data including confidence
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)

        # Extract text and calculate average confidence
        texts = []
        confidences = []

        for i, conf in enumerate(data["conf"]):
            if conf > 0:  # -1 means no confidence data
                text = data["text"][i].strip()
                if text:
                    texts.append(text)
                    confidences.append(conf)

        text = " ".join(texts)
        text = sanitize_text(text)
        text = normalize_whitespace(text)

        avg_confidence = sum(confidences) / len(confidences) / 100 if confidences else 0

        return text, avg_confidence

    except ImportError:
        logger.warning("pytesseract not installed, OCR unavailable")
        return "", 0.0
    except Exception as e:
        logger.warning(f"Tesseract OCR failed: {e}")
        return "", 0.0


def get_ocr_engine() -> OCREngine:
    """Get configured OCR engine from config."""
    try:
        engine = get("ingestion", "text_extraction", "ocr_engine")
        return OCREngine(engine)
    except (KeyError, TypeError, ValueError):
        return OCREngine.PYMUPDF  # Default


def is_ocr_enabled() -> bool:
    """Check if OCR is enabled in config."""
    try:
        return get("ingestion", "text_extraction", "enable_ocr")
    except (KeyError, TypeError):
        return True  # Default to enabled


def should_run_ocr(
    layer_text: str,
    layer_coverage: float,
    force_ocr: bool = False,
) -> bool:
    """
    Determine if OCR should be run based on layer text results.

    Args:
        layer_text: Text from PDF layer
        layer_coverage: Coverage ratio from layer extraction
        force_ocr: Always run OCR regardless of layer results

    Returns:
        True if OCR should be run
    """
    if not is_ocr_enabled():
        return False

    if force_ocr:
        return True

    try:
        always_ocr = get("ingestion", "text_extraction", "always_run_ocr")
        if always_ocr:
            return True
    except (KeyError, TypeError):
        pass

    # Get thresholds from config
    try:
        min_coverage = get("ingestion", "text_extraction", "layer_text_min_coverage")
    except (KeyError, TypeError):
        min_coverage = 0.1

    # Run OCR if layer text is insufficient
    if len(layer_text.strip()) < 50:
        return True

    if layer_coverage < min_coverage:
        return True

    return False


def merge_text_sources(layer_text: str, ocr_text: str) -> Tuple[str, TextExtractionMethod]:
    """
    Intelligently merge layer and OCR text.

    Args:
        layer_text: Text from PDF layer
        ocr_text: Text from OCR

    Returns:
        Tuple of (merged text, extraction method used)
    """
    layer_clean = layer_text.strip()
    ocr_clean = ocr_text.strip()

    # If one is empty, use the other
    if not layer_clean and not ocr_clean:
        return "", TextExtractionMethod.NONE

    if not layer_clean:
        return ocr_clean, TextExtractionMethod.OCR

    if not ocr_clean:
        return layer_clean, TextExtractionMethod.LAYER

    # Both have content - decide which to prefer
    layer_len = len(layer_clean)
    ocr_len = len(ocr_clean)

    # If similar length (within 20%), prefer layer (better positioning)
    if abs(layer_len - ocr_len) / max(layer_len, ocr_len) < 0.2:
        return layer_clean, TextExtractionMethod.LAYER

    # If OCR found significantly more text, likely scanned
    if ocr_len > layer_len * 1.5:
        return ocr_clean, TextExtractionMethod.OCR

    # If layer has more, use layer
    if layer_len > ocr_len * 1.5:
        return layer_clean, TextExtractionMethod.LAYER

    # Similar amounts but different - merge unique content
    merged = deduplicate_merge(layer_clean, ocr_clean)
    return merged, TextExtractionMethod.MERGED


def deduplicate_merge(text1: str, text2: str) -> str:
    """
    Merge two text sources, removing duplicates.

    Uses sentence-level deduplication to combine content.
    """
    # Simple approach: use the longer one as base, add unique sentences from shorter
    if len(text1) >= len(text2):
        base, other = text1, text2
    else:
        base, other = text2, text1

    # Split into sentences/chunks
    base_sentences = set(s.strip().lower() for s in re.split(r"[.!?\n]", base) if s.strip())

    # Find sentences in other that aren't in base
    other_chunks = re.split(r"[.!?\n]", other)
    unique_sentences = []

    for chunk in other_chunks:
        chunk_clean = chunk.strip()
        if chunk_clean and chunk_clean.lower() not in base_sentences:
            # Check if it's not a substring of any base sentence
            is_substring = any(chunk_clean.lower() in s for s in base_sentences)
            if not is_substring:
                unique_sentences.append(chunk_clean)

    if unique_sentences:
        return base + "\n\n" + " ".join(unique_sentences)

    return base


def extract_text(
    page,
    image: Optional[Image.Image] = None,
    force_ocr: bool = False,
) -> TextExtractionResult:
    """
    Extract text using both layer and OCR methods.

    Args:
        page: fitz.Page object
        image: Optional PIL Image (for Tesseract OCR)
        force_ocr: Force OCR even if layer text is sufficient

    Returns:
        TextExtractionResult with all extraction data
    """
    # Step 1: Extract layer text
    layer_text, layer_coverage = extract_layer_text(page)

    # Step 2: Determine if OCR is needed
    run_ocr = should_run_ocr(layer_text, layer_coverage, force_ocr)

    ocr_text = ""
    ocr_confidence = -1.0
    ocr_engine_used = None

    # Step 3: Run OCR if needed
    if run_ocr:
        engine = get_ocr_engine()

        if engine == OCREngine.PYMUPDF:
            ocr_text, ocr_confidence = extract_ocr_text_pymupdf(page)
            ocr_engine_used = "pymupdf"

        elif engine == OCREngine.TESSERACT and image is not None:
            ocr_text, ocr_confidence = extract_ocr_text_tesseract(image)
            ocr_engine_used = "tesseract"

    # Step 4: Merge results
    merged_text, method = merge_text_sources(layer_text, ocr_text)

    return TextExtractionResult(
        layer_text=layer_text,
        ocr_text=ocr_text,
        merged_text=merged_text,
        extraction_method=method,
        ocr_confidence=ocr_confidence,
        layer_coverage=layer_coverage,
        layer_char_count=len(layer_text),
        ocr_char_count=len(ocr_text),
        ocr_engine_used=ocr_engine_used,
    )


def format_text_metadata(result: TextExtractionResult) -> dict:
    """
    Format text extraction result as metadata dictionary for Vespa.

    Args:
        result: TextExtractionResult

    Returns:
        Dictionary of metadata fields
    """
    return {
        "text_extraction_method": result.extraction_method.value,
        "ocr_confidence": result.ocr_confidence if result.ocr_confidence >= 0 else None,
        "layer_text_coverage": result.layer_coverage,
        "layer_char_count": result.layer_char_count,
        "ocr_char_count": result.ocr_char_count,
        "ocr_engine": result.ocr_engine_used,
    }
