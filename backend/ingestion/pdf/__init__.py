"""
PDF ingestion module.

Provides PDF processing, validation, rendering, and Vespa document generation.
"""

from backend.ingestion.pdf.processor import (
    validate_pdf,
    validate_image,
    ingest_pdf,
    ingest_image,
    pdf_to_images,
    render_page,
    generate_embeddings,
    feed_document,
    generate_doc_id,
    create_blur_image,
    image_to_base64,
    float_to_binary_embedding,
    sanitize_text,
    PROCESSABLE_EXTENSIONS,
    PROCESSABLE_IMAGE_EXTENSIONS,
)

__all__ = [
    "validate_pdf",
    "validate_image",
    "ingest_pdf",
    "ingest_image",
    "pdf_to_images",
    "render_page",
    "generate_embeddings",
    "feed_document",
    "generate_doc_id",
    "create_blur_image",
    "image_to_base64",
    "float_to_binary_embedding",
    "sanitize_text",
    "PROCESSABLE_EXTENSIONS",
    "PROCESSABLE_IMAGE_EXTENSIONS",
]
