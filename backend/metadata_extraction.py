"""
PDF and document metadata extraction for enhanced querying.

Extracts document-level metadata (author, dates, keywords) and page-level
properties for storage in Vespa.
"""

import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.config import get
from backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class DocumentMetadata:
    """Document-level metadata extracted from PDF properties."""

    # Standard PDF metadata
    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: List[str] = field(default_factory=list)
    creator: str = ""  # Application that created the original
    producer: str = ""  # PDF producer application

    # Dates (as Unix timestamps in milliseconds)
    created_at: Optional[int] = None
    modified_at: Optional[int] = None

    # Document structure
    page_count: int = 0
    has_toc: bool = False
    has_annotations: bool = False
    has_forms: bool = False

    # Security
    is_encrypted: bool = False
    permissions: Dict[str, bool] = field(default_factory=dict)


@dataclass
class PageMetadata:
    """Page-level metadata."""

    page_number: int
    width_px: int
    height_px: int
    width_pt: float
    height_pt: float
    rotation: int = 0

    # Content indicators
    has_images: bool = False
    has_text: bool = False
    has_drawings: bool = False
    has_annotations: bool = False

    # Link to document
    parent_doc_id: str = ""


@dataclass
class CustomMetadata:
    """User-defined custom metadata fields."""

    fields: Dict[str, str] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        """Set a custom field (converts to string)."""
        self.fields[key] = str(value) if value is not None else ""

    def get(self, key: str, default: str = "") -> str:
        """Get a custom field value."""
        return self.fields.get(key, default)

    def to_dict(self) -> Dict[str, str]:
        """Convert to dictionary for Vespa."""
        return dict(self.fields)


def parse_pdf_date(date_str: Optional[str]) -> Optional[int]:
    """
    Parse PDF date string to Unix timestamp in milliseconds.

    PDF dates have format: D:YYYYMMDDHHmmSSOHH'mm'
    Where O is timezone offset direction (+/-/Z)
    """
    if not date_str:
        return None

    try:
        # Remove D: prefix if present
        if date_str.startswith("D:"):
            date_str = date_str[2:]

        # Try various formats
        formats = [
            "%Y%m%d%H%M%S",
            "%Y%m%d%H%M",
            "%Y%m%d",
            "%Y",
        ]

        # Clean up timezone suffix
        date_clean = re.sub(r"[+-]\d{2}'\d{2}'$", "", date_str)
        date_clean = re.sub(r"Z$", "", date_clean)

        for fmt in formats:
            try:
                dt = datetime.strptime(date_clean[: len(fmt.replace("%", ""))], fmt)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue

        logger.debug(f"Could not parse PDF date: {date_str}")
        return None

    except Exception as e:
        logger.debug(f"Error parsing PDF date '{date_str}': {e}")
        return None


def parse_keywords(keywords_str: Optional[str]) -> List[str]:
    """
    Parse PDF keywords string into list.

    Keywords may be comma, semicolon, or space separated.
    """
    if not keywords_str:
        return []

    # Try comma first, then semicolon, then space
    for separator in [",", ";", " "]:
        if separator in keywords_str:
            keywords = [k.strip() for k in keywords_str.split(separator)]
            keywords = [k for k in keywords if k]  # Remove empty
            if len(keywords) > 1:
                return keywords

    # Single keyword
    return [keywords_str.strip()] if keywords_str.strip() else []


def extract_document_metadata(doc) -> DocumentMetadata:
    """
    Extract metadata from a PyMuPDF Document.

    Args:
        doc: fitz.Document object

    Returns:
        DocumentMetadata with extracted fields
    """
    try:
        metadata = doc.metadata or {}

        # Extract dates
        created_at = parse_pdf_date(metadata.get("creationDate"))
        modified_at = parse_pdf_date(metadata.get("modDate"))

        # Extract keywords
        keywords = parse_keywords(metadata.get("keywords"))

        # Check document features
        has_toc = len(doc.get_toc()) > 0 if hasattr(doc, "get_toc") else False

        has_annotations = False
        has_forms = False
        for page_num in range(min(len(doc), 5)):  # Check first 5 pages
            page = doc[page_num]
            if page.annots():
                has_annotations = True
            if page.widgets():
                has_forms = True
            if has_annotations and has_forms:
                break

        # Check permissions
        permissions = {}
        try:
            permissions = {
                "print": doc.permissions & 4 > 0,
                "modify": doc.permissions & 8 > 0,
                "copy": doc.permissions & 16 > 0,
                "annotate": doc.permissions & 32 > 0,
            }
        except Exception:
            pass

        return DocumentMetadata(
            title=metadata.get("title", ""),
            author=metadata.get("author", ""),
            subject=metadata.get("subject", ""),
            keywords=keywords,
            creator=metadata.get("creator", ""),
            producer=metadata.get("producer", ""),
            created_at=created_at,
            modified_at=modified_at,
            page_count=len(doc),
            has_toc=has_toc,
            has_annotations=has_annotations,
            has_forms=has_forms,
            is_encrypted=doc.is_encrypted,
            permissions=permissions,
        )

    except Exception as e:
        logger.warning(f"Error extracting document metadata: {e}")
        return DocumentMetadata()


def extract_page_metadata(page, page_number: int, rendered_width: int, rendered_height: int) -> PageMetadata:
    """
    Extract metadata from a PyMuPDF Page.

    Args:
        page: fitz.Page object
        page_number: 1-indexed page number
        rendered_width: Width of rendered image
        rendered_height: Height of rendered image

    Returns:
        PageMetadata with extracted fields
    """
    try:
        rect = page.rect

        # Check content types
        has_images = len(page.get_images()) > 0
        has_text = len(page.get_text("text").strip()) > 0

        has_drawings = False
        try:
            drawings = page.get_drawings()
            has_drawings = len(drawings) > 10
        except Exception:
            pass

        has_annotations = bool(page.annots())

        return PageMetadata(
            page_number=page_number,
            width_px=rendered_width,
            height_px=rendered_height,
            width_pt=rect.width,
            height_pt=rect.height,
            rotation=page.rotation,
            has_images=has_images,
            has_text=has_text,
            has_drawings=has_drawings,
            has_annotations=has_annotations,
        )

    except Exception as e:
        logger.warning(f"Error extracting page metadata: {e}")
        return PageMetadata(
            page_number=page_number,
            width_px=rendered_width,
            height_px=rendered_height,
            width_pt=0.0,
            height_pt=0.0,
        )


def format_document_metadata(meta: DocumentMetadata) -> Dict[str, Any]:
    """
    Format DocumentMetadata for Vespa document fields.

    Returns fields prefixed with 'doc_' for document-level metadata.
    """
    return {
        "doc_author": meta.author,
        "doc_subject": meta.subject,
        "doc_keywords": meta.keywords,
        "doc_creator": meta.creator,
        "doc_producer": meta.producer,
        "doc_created_at": meta.created_at,
        "doc_modified_at": meta.modified_at,
        "doc_page_count": meta.page_count,
        "doc_has_toc": meta.has_toc,
        "doc_has_annotations": meta.has_annotations,
        "doc_has_forms": meta.has_forms,
    }


def format_page_metadata(meta: PageMetadata) -> Dict[str, Any]:
    """
    Format PageMetadata for Vespa document fields.
    """
    return {
        "page_width_px": meta.width_px,
        "page_height_px": meta.height_px,
        "page_width_pt": int(meta.width_pt),
        "page_height_pt": int(meta.height_pt),
        "page_rotation": meta.rotation,
        "page_has_images": meta.has_images,
        "page_has_text": meta.has_text,
        "page_has_drawings": meta.has_drawings,
    }


def create_processing_metadata() -> Dict[str, Any]:
    """
    Create metadata about the ingestion process.
    """
    try:
        embedding_model = get("colpali", "model_name")
    except (KeyError, TypeError):
        embedding_model = "unknown"

    return {
        "ingested_at": int(time.time() * 1000),
        "embedding_model": embedding_model,
    }


def merge_metadata(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge multiple metadata dictionaries.

    Later dictionaries override earlier ones for duplicate keys.
    """
    result = {}
    for d in dicts:
        if d:
            result.update(d)
    return result
