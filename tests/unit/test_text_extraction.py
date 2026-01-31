"""Unit tests for backend.text_extraction module."""

import pytest

from backend.text_extraction import (
    OCREngine,
    TextExtractionMethod,
    TextExtractionResult,
    deduplicate_merge,
    format_text_metadata,
    merge_text_sources,
    normalize_whitespace,
    sanitize_text,
)


class TestSanitizeText:
    """Tests for text sanitization."""

    def test_removes_null_bytes(self):
        """Null bytes should be removed."""
        text = "Hello\x00World"
        assert sanitize_text(text) == "HelloWorld"

    def test_removes_control_characters(self):
        """Control characters except whitespace should be removed."""
        text = "Hello\x01\x02\x03World"
        assert sanitize_text(text) == "HelloWorld"

    def test_preserves_whitespace(self):
        """Tab, newline, and carriage return should be preserved."""
        text = "Hello\tWorld\nNew\rLine"
        assert sanitize_text(text) == text

    def test_empty_string(self):
        """Empty string should return empty string."""
        assert sanitize_text("") == ""

    def test_none_returns_empty(self):
        """None should return empty string."""
        assert sanitize_text(None) == ""

    def test_normal_text_unchanged(self):
        """Normal text should pass through unchanged."""
        text = "This is normal text with numbers 123 and symbols !@#"
        assert sanitize_text(text) == text


class TestNormalizeWhitespace:
    """Tests for whitespace normalization."""

    def test_multiple_spaces_collapsed(self):
        """Multiple spaces should become single space."""
        text = "Hello     World"
        assert normalize_whitespace(text) == "Hello World"

    def test_multiple_newlines_collapsed(self):
        """Three or more newlines should become two."""
        text = "Hello\n\n\n\n\nWorld"
        result = normalize_whitespace(text)
        assert result.count("\n") == 2

    def test_tabs_collapsed(self):
        """Multiple tabs should become single space."""
        text = "Hello\t\t\tWorld"
        assert normalize_whitespace(text) == "Hello World"

    def test_strips_edges(self):
        """Leading and trailing whitespace should be stripped."""
        text = "   Hello World   "
        assert normalize_whitespace(text) == "Hello World"

    def test_empty_returns_empty(self):
        """Empty string should return empty string."""
        assert normalize_whitespace("") == ""


class TestMergeTextSources:
    """Tests for merging layer and OCR text."""

    def test_empty_layer_uses_ocr(self):
        """When layer is empty, OCR text should be used."""
        merged, method = merge_text_sources("", "OCR text here")
        assert merged == "OCR text here"
        assert method == TextExtractionMethod.OCR

    def test_empty_ocr_uses_layer(self):
        """When OCR is empty, layer text should be used."""
        merged, method = merge_text_sources("Layer text here", "")
        assert merged == "Layer text here"
        assert method == TextExtractionMethod.LAYER

    def test_both_empty_returns_none(self):
        """When both are empty, return empty with NONE method."""
        merged, method = merge_text_sources("", "")
        assert merged == ""
        assert method == TextExtractionMethod.NONE

    def test_similar_length_prefers_layer(self):
        """When texts are similar length, prefer layer (better positioning)."""
        layer = "This is layer text with some content."
        ocr = "This is OCR text with some content."
        merged, method = merge_text_sources(layer, ocr)
        assert merged == layer
        assert method == TextExtractionMethod.LAYER

    def test_ocr_much_longer_uses_ocr(self):
        """When OCR is much longer (1.5x+), prefer OCR (likely scanned)."""
        layer = "Short layer."
        ocr = "This is much longer OCR text that was extracted from a scanned document."
        merged, method = merge_text_sources(layer, ocr)
        assert merged == ocr
        assert method == TextExtractionMethod.OCR

    def test_layer_much_longer_uses_layer(self):
        """When layer is much longer, prefer layer."""
        layer = "This is much longer layer text that was extracted from a native PDF."
        ocr = "Short OCR."
        merged, method = merge_text_sources(layer, ocr)
        assert merged == layer
        assert method == TextExtractionMethod.LAYER


class TestDeduplicateMerge:
    """Tests for deduplicating merged text."""

    def test_identical_returns_one(self):
        """Identical texts should return just one copy."""
        text = "Hello World"
        result = deduplicate_merge(text, text)
        # Should not contain duplicated content
        assert result.count("Hello") == 1

    def test_unique_sentences_added(self):
        """Unique sentences from shorter text should be added."""
        text1 = "First sentence. Second sentence."
        text2 = "First sentence. Third sentence."
        result = deduplicate_merge(text1, text2)
        # Should contain both unique sentences
        assert "Second sentence" in result
        assert "Third sentence" in result

    def test_longer_used_as_base(self):
        """Longer text should be used as base."""
        short = "Short."
        long = "This is a much longer text with more content."
        result = deduplicate_merge(short, long)
        assert long in result


class TestTextExtractionResult:
    """Tests for TextExtractionResult dataclass."""

    def test_creation(self):
        """Test creating a TextExtractionResult."""
        result = TextExtractionResult(
            layer_text="Layer text",
            ocr_text="OCR text",
            merged_text="Layer text",
            extraction_method=TextExtractionMethod.LAYER,
            ocr_confidence=0.85,
            layer_coverage=0.6,
            layer_char_count=10,
            ocr_char_count=8,
            ocr_engine_used="pymupdf",
        )

        assert result.layer_text == "Layer text"
        assert result.ocr_confidence == 0.85
        assert result.extraction_method == TextExtractionMethod.LAYER


class TestFormatTextMetadata:
    """Tests for formatting text extraction results as metadata."""

    def test_format_includes_all_fields(self):
        """Ensure all expected metadata fields are present."""
        result = TextExtractionResult(
            layer_text="Layer text",
            ocr_text="OCR text",
            merged_text="Layer text",
            extraction_method=TextExtractionMethod.LAYER,
            ocr_confidence=0.85,
            layer_coverage=0.6,
            layer_char_count=10,
            ocr_char_count=8,
            ocr_engine_used="pymupdf",
        )

        metadata = format_text_metadata(result)

        assert "text_extraction_method" in metadata
        assert "ocr_confidence" in metadata
        assert "layer_text_coverage" in metadata
        assert "layer_char_count" in metadata
        assert "ocr_char_count" in metadata
        assert "ocr_engine" in metadata

        assert metadata["text_extraction_method"] == "layer"
        assert metadata["ocr_confidence"] == 0.85

    def test_negative_confidence_is_none(self):
        """Negative OCR confidence should format as None."""
        result = TextExtractionResult(
            layer_text="Layer",
            ocr_text="",
            merged_text="Layer",
            extraction_method=TextExtractionMethod.LAYER,
            ocr_confidence=-1.0,  # OCR not run
            layer_coverage=0.5,
            layer_char_count=5,
            ocr_char_count=0,
        )

        metadata = format_text_metadata(result)
        assert metadata["ocr_confidence"] is None


class TestOCREngine:
    """Tests for OCR engine enum."""

    def test_engine_values(self):
        """Test OCR engine enum values."""
        assert OCREngine.PYMUPDF.value == "pymupdf"
        assert OCREngine.TESSERACT.value == "tesseract"
        assert OCREngine.NONE.value == "none"


class TestTextExtractionMethod:
    """Tests for text extraction method enum."""

    def test_method_values(self):
        """Test extraction method enum values."""
        assert TextExtractionMethod.LAYER.value == "layer"
        assert TextExtractionMethod.OCR.value == "ocr"
        assert TextExtractionMethod.MERGED.value == "merged"
        assert TextExtractionMethod.NONE.value == "none"
