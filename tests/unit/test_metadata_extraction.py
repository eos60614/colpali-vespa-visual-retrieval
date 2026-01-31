"""Unit tests for backend.metadata_extraction module."""

import pytest

from backend.metadata_extraction import (
    CustomMetadata,
    DocumentMetadata,
    PageMetadata,
    create_processing_metadata,
    format_document_metadata,
    format_page_metadata,
    merge_metadata,
    parse_keywords,
    parse_pdf_date,
)


class TestParsePdfDate:
    """Tests for PDF date string parsing."""

    def test_standard_format(self):
        """Test standard PDF date format."""
        # D:YYYYMMDDHHmmSS format
        result = parse_pdf_date("D:20230615143022")
        assert result is not None
        # Should be a timestamp in milliseconds
        assert result > 0

    def test_without_prefix(self):
        """Test date without D: prefix."""
        result = parse_pdf_date("20230615143022")
        assert result is not None

    def test_date_only(self):
        """Test date without time component."""
        result = parse_pdf_date("D:20230615")
        assert result is not None

    def test_with_timezone(self):
        """Test date with timezone suffix."""
        result = parse_pdf_date("D:20230615143022+05'30'")
        assert result is not None

    def test_with_z_timezone(self):
        """Test date with Z (UTC) timezone."""
        result = parse_pdf_date("D:20230615143022Z")
        assert result is not None

    def test_year_only(self):
        """Test year-only date."""
        result = parse_pdf_date("D:2023")
        assert result is not None

    def test_none_returns_none(self):
        """Test None input returns None."""
        assert parse_pdf_date(None) is None

    def test_empty_returns_none(self):
        """Test empty string returns None."""
        assert parse_pdf_date("") is None

    def test_invalid_returns_none(self):
        """Test invalid format returns None."""
        assert parse_pdf_date("not-a-date") is None


class TestParseKeywords:
    """Tests for keyword string parsing."""

    def test_comma_separated(self):
        """Test comma-separated keywords."""
        result = parse_keywords("python, machine learning, pdf")
        assert result == ["python", "machine learning", "pdf"]

    def test_semicolon_separated(self):
        """Test semicolon-separated keywords."""
        result = parse_keywords("python; machine learning; pdf")
        assert result == ["python", "machine learning", "pdf"]

    def test_space_separated(self):
        """Test space-separated keywords."""
        result = parse_keywords("python machine learning")
        assert "python" in result
        assert "machine" in result

    def test_single_keyword(self):
        """Test single keyword."""
        result = parse_keywords("python")
        assert result == ["python"]

    def test_none_returns_empty(self):
        """Test None returns empty list."""
        assert parse_keywords(None) == []

    def test_empty_returns_empty(self):
        """Test empty string returns empty list."""
        assert parse_keywords("") == []

    def test_whitespace_stripped(self):
        """Test whitespace is stripped from keywords."""
        result = parse_keywords("  python  ,  ml  ")
        assert result == ["python", "ml"]


class TestDocumentMetadata:
    """Tests for DocumentMetadata dataclass."""

    def test_default_values(self):
        """Test default values are set correctly."""
        meta = DocumentMetadata()

        assert meta.title == ""
        assert meta.author == ""
        assert meta.keywords == []
        assert meta.page_count == 0
        assert meta.is_encrypted is False
        assert meta.created_at is None

    def test_custom_values(self):
        """Test setting custom values."""
        meta = DocumentMetadata(
            title="Test Document",
            author="Test Author",
            keywords=["test", "python"],
            page_count=10,
            created_at=1686835822000,
        )

        assert meta.title == "Test Document"
        assert meta.author == "Test Author"
        assert meta.keywords == ["test", "python"]
        assert meta.page_count == 10


class TestPageMetadata:
    """Tests for PageMetadata dataclass."""

    def test_required_fields(self):
        """Test creating with required fields."""
        meta = PageMetadata(
            page_number=1,
            width_px=800,
            height_px=1000,
            width_pt=612.0,
            height_pt=792.0,
        )

        assert meta.page_number == 1
        assert meta.width_px == 800
        assert meta.height_px == 1000

    def test_default_optional_fields(self):
        """Test default values for optional fields."""
        meta = PageMetadata(
            page_number=1,
            width_px=800,
            height_px=1000,
            width_pt=612.0,
            height_pt=792.0,
        )

        assert meta.rotation == 0
        assert meta.has_images is False
        assert meta.has_text is False
        assert meta.parent_doc_id == ""


class TestCustomMetadata:
    """Tests for CustomMetadata class."""

    def test_set_and_get(self):
        """Test setting and getting values."""
        meta = CustomMetadata()
        meta.set("project_id", "12345")
        meta.set("department", "Engineering")

        assert meta.get("project_id") == "12345"
        assert meta.get("department") == "Engineering"

    def test_get_default(self):
        """Test getting with default value."""
        meta = CustomMetadata()
        assert meta.get("nonexistent", "default") == "default"

    def test_converts_to_string(self):
        """Test that values are converted to strings."""
        meta = CustomMetadata()
        meta.set("number", 123)
        meta.set("boolean", True)

        assert meta.get("number") == "123"
        assert meta.get("boolean") == "True"

    def test_none_becomes_empty(self):
        """Test that None becomes empty string."""
        meta = CustomMetadata()
        meta.set("nullable", None)
        assert meta.get("nullable") == ""

    def test_to_dict(self):
        """Test converting to dictionary."""
        meta = CustomMetadata()
        meta.set("key1", "value1")
        meta.set("key2", "value2")

        result = meta.to_dict()
        assert result == {"key1": "value1", "key2": "value2"}


class TestFormatDocumentMetadata:
    """Tests for formatting document metadata."""

    def test_includes_doc_prefix(self):
        """Test that formatted keys have doc_ prefix."""
        meta = DocumentMetadata(
            author="Test Author",
            subject="Test Subject",
            keywords=["test"],
        )

        result = format_document_metadata(meta)

        assert "doc_author" in result
        assert "doc_subject" in result
        assert "doc_keywords" in result
        assert result["doc_author"] == "Test Author"

    def test_includes_all_expected_fields(self):
        """Test that all expected fields are present."""
        meta = DocumentMetadata()
        result = format_document_metadata(meta)

        expected_fields = [
            "doc_author",
            "doc_subject",
            "doc_keywords",
            "doc_creator",
            "doc_producer",
            "doc_created_at",
            "doc_modified_at",
            "doc_page_count",
            "doc_has_toc",
            "doc_has_annotations",
            "doc_has_forms",
        ]

        for field in expected_fields:
            assert field in result


class TestFormatPageMetadata:
    """Tests for formatting page metadata."""

    def test_includes_all_fields(self):
        """Test that all expected fields are present."""
        meta = PageMetadata(
            page_number=1,
            width_px=800,
            height_px=1000,
            width_pt=612.0,
            height_pt=792.0,
            has_images=True,
            has_text=True,
        )

        result = format_page_metadata(meta)

        assert "page_width_px" in result
        assert "page_height_px" in result
        assert "page_has_images" in result
        assert "page_has_text" in result

        assert result["page_width_px"] == 800
        assert result["page_has_images"] is True


class TestCreateProcessingMetadata:
    """Tests for creating processing metadata."""

    def test_includes_timestamp(self):
        """Test that ingested_at timestamp is included."""
        result = create_processing_metadata()
        assert "ingested_at" in result
        assert result["ingested_at"] > 0

    def test_includes_model_name(self):
        """Test that embedding model name is included."""
        result = create_processing_metadata()
        assert "embedding_model" in result


class TestMergeMetadata:
    """Tests for merging metadata dictionaries."""

    def test_merges_multiple_dicts(self):
        """Test merging multiple dictionaries."""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"c": 3, "d": 4}
        dict3 = {"e": 5}

        result = merge_metadata(dict1, dict2, dict3)

        assert result == {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}

    def test_later_overrides_earlier(self):
        """Test that later dictionaries override earlier ones."""
        dict1 = {"a": 1, "b": 2}
        dict2 = {"b": 20, "c": 3}

        result = merge_metadata(dict1, dict2)

        assert result["a"] == 1
        assert result["b"] == 20
        assert result["c"] == 3

    def test_handles_none(self):
        """Test that None dictionaries are handled."""
        dict1 = {"a": 1}
        result = merge_metadata(dict1, None, {"b": 2})

        assert result == {"a": 1, "b": 2}

    def test_empty_returns_empty(self):
        """Test that no arguments returns empty dict."""
        result = merge_metadata()
        assert result == {}
