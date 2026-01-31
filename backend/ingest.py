"""
Ingestion module for processing PDFs and images with ColPali embeddings.
Extracts core functionality from scripts/feed_data.py for on-demand upload processing.

Enhanced with:
- Smart page size detection and adaptive DPI
- Dual text extraction (layer + OCR)
- Rich metadata extraction for queryable fields
"""

import base64
import hashlib
import io
import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import fitz  # PyMuPDF
import numpy as np
from PIL import Image
from vespa.application import Vespa

from backend.config import get
from backend.logging_config import get_logger
from backend.drawing_regions import (
    detect_and_extract_regions,
    should_detect_regions,
)
from backend.page_sizing import (
    PageSizeCategory,
    analyze_pdf_page,
    categorize_image,
    format_page_dimensions,
    get_adaptive_dpi,
)
from backend.text_extraction import (
    TextExtractionResult,
    extract_text,
    format_text_metadata,
    sanitize_text,
)
from backend.metadata_extraction import (
    CustomMetadata,
    create_processing_metadata,
    extract_document_metadata,
    extract_page_metadata,
    format_document_metadata,
    format_page_metadata,
    merge_metadata,
)

logger = get_logger(__name__)


def validate_pdf(file_bytes: bytes) -> Tuple[bool, str]:
    """
    Validate PDF file for integrity and accessibility.

    Returns:
        Tuple of (is_valid, message)
    """
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        if doc.is_encrypted:
            doc.close()
            return False, "Password-protected PDFs are not supported"
        page_count = len(doc)
        doc.close()
        return True, f"Valid PDF with {page_count} pages"
    except Exception as e:
        return False, f"Invalid PDF: {str(e)}"


def image_to_base64(image: Image.Image, format: str = "JPEG") -> str:
    """Convert PIL Image to base64 string."""
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


def create_blur_image(image: Image.Image, max_size: int = None) -> str:
    """Create a small blurred version of the image for fast loading."""
    if max_size is None:
        max_size = get("image", "blur_max_size")
    img_copy = image.copy()
    img_copy.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    return image_to_base64(img_copy, format="JPEG")


def float_to_binary_embedding(float_embedding: np.ndarray) -> list:
    """Convert float embedding to packed int8 binary embedding."""
    binary = np.packbits(np.where(float_embedding > 0, 1, 0)).astype(np.int8)
    return binary.tolist()


def render_page(page, dpi: int = None) -> Tuple[Image.Image, str]:
    """
    Render a single fitz.Page to a PIL Image and extract its text.

    Note: For full text extraction with OCR support, use extract_text()
    from backend.text_extraction instead.

    Args:
        page: fitz.Page object
        dpi: Rendering DPI

    Returns:
        Tuple of (PIL Image, sanitized layer text)
    """
    if dpi is None:
        dpi = get("image", "dpi")
    pix = page.get_pixmap(dpi=dpi)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    text = sanitize_text(page.get_text("text").strip())
    return img, text


def pdf_to_images(file_bytes: bytes, dpi: int = None) -> Tuple[List[Image.Image], List[str]]:
    """
    Convert PDF bytes to list of PIL Images and extracted text per page.

    Returns:
        Tuple of (images list, texts list)
    """
    if dpi is None:
        dpi = get("image", "dpi")
    images = []
    texts = []

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for page_num in range(len(doc)):
        img, text = render_page(doc[page_num], dpi=dpi)
        images.append(img)
        texts.append(text)
    doc.close()

    return images, texts


def generate_embeddings(model, processor, images: List[Image.Image], device: str, batch_size: int = None) -> List[Tuple[dict, dict]]:
    """
    Generate ColQwen2.5 embeddings for images.

    Returns:
        List of tuples (binary_embedding, float_embedding) in Vespa tensor format
    """
    import torch

    if batch_size is None:
        batch_size = get("ingestion", "batch_size")
    all_embeddings = []

    for i in range(0, len(images), batch_size):
        batch_images = images[i:i + batch_size]

        with torch.no_grad():
            batch_inputs = processor.process_images(batch_images).to(device)
            embeddings = model(**batch_inputs)

        # Convert to both binary and float embeddings in Vespa tensor format
        for emb in embeddings:
            emb_np = emb.cpu().float().numpy()
            # Vespa expects {"blocks": {"0": [...], "1": [...], ...}} format

            # Binary embeddings for HNSW search (compact)
            binary_embs = {
                "blocks": {
                    str(patch_idx): float_to_binary_embedding(patch_emb)
                    for patch_idx, patch_emb in enumerate(emb_np)
                }
            }

            # Float embeddings for precise reranking
            float_embs = {
                "blocks": {
                    str(patch_idx): patch_emb.tolist()
                    for patch_idx, patch_emb in enumerate(emb_np)
                }
            }

            all_embeddings.append((binary_embs, float_embs))

    return all_embeddings


def feed_document(app: Vespa, doc: dict) -> Tuple[str, bool, str]:
    """
    Feed a single document to Vespa.

    Returns:
        Tuple of (doc_id, success, error_message)
    """
    try:
        schema = get("vespa", "schema_name")
        response = app.feed_data_point(
            schema=schema,
            data_id=doc["id"],
            fields=doc["fields"]
        )
        if response.status_code == 200:
            return doc["id"], True, ""
        else:
            return doc["id"], False, str(response.json)
    except Exception as e:
        return doc["id"], False, str(e)


def generate_doc_id(pdf_bytes: bytes, title: str) -> str:
    """
    Generate a document ID based on content hash and title.

    Format: {title_slug}_{content_hash}
    """
    hash_length = get("ingestion", "doc_id_hash_length")
    content_hash = hashlib.md5(pdf_bytes).hexdigest()[:hash_length]
    # Create safe title slug: alphanumeric only, max chars from config
    slug_max_length = get("ingestion", "doc_id_slug_max_length")
    safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)[:slug_max_length].strip('_').lower()
    if not safe_title:
        safe_title = "document"
    return f"{safe_title}_{content_hash}"


def ingest_pdf(
    file_bytes: bytes,
    filename: str,
    vespa_app: Vespa,
    model,
    processor,
    device: str,
    title: Optional[str] = None,
    description: str = "",
    tags: Optional[List[str]] = None,
    batch_size: int = None,
    detect_drawing_regions: bool = False,
    use_vlm_detection: bool = False,
    vlm_api_key: Optional[str] = None,
    detection_method: str = "auto",
    s3_key: Optional[str] = None,
    custom_metadata: Optional[Dict[str, str]] = None,
    enable_ocr: Optional[bool] = None,
) -> Tuple[bool, str, int]:
    """
    Main ingestion function: validates, processes, and feeds a PDF to Vespa.

    Enhanced with:
    - Smart page size detection with adaptive DPI
    - Dual text extraction (layer + OCR)
    - Rich metadata extraction for queryable fields

    For large-format drawings, optionally detects sub-regions (elevations, details,
    tables) and embeds each region separately for better ColPali patch coverage.

    Args:
        file_bytes: Raw PDF bytes
        filename: Original filename
        vespa_app: Vespa application instance
        model: ColPali model
        processor: ColPali processor
        device: Device string (cuda/cpu)
        title: Optional custom title (defaults to filename without extension)
        description: Optional description
        tags: Optional list of tags
        batch_size: Batch size for embedding generation
        detect_drawing_regions: Enable region detection for large drawings
        use_vlm_detection: Use VLM for semantic region labeling
        vlm_api_key: API key for VLM
        detection_method: Region detection strategy
        s3_key: Optional S3 key for file reference
        custom_metadata: Optional dict of custom metadata key-value pairs
        enable_ocr: Override OCR setting (None = use config)

    Returns:
        Tuple of (success, message, pages_indexed)
    """
    start_time = time.time()

    # Default title from filename
    if title is None or title.strip() == "":
        title = Path(filename).stem

    # Default tags to empty list
    if tags is None:
        tags = []

    # Resolve defaults from config
    if batch_size is None:
        batch_size = get("ingestion", "batch_size")
    snippet_ingest_length = get("image", "truncation", "snippet_ingest_length")

    # Check if metadata extraction is enabled
    try:
        extract_metadata = get("ingestion", "metadata", "extract_pdf_metadata")
    except (KeyError, TypeError):
        extract_metadata = True

    # Step 1: Validate PDF
    is_valid, validation_msg = validate_pdf(file_bytes)
    if not is_valid:
        return False, validation_msg, 0

    # Step 2: Generate base document ID
    base_doc_id = generate_doc_id(file_bytes, title)

    # Step 3: Open PDF and process pages
    docs_indexed = 0
    failed_docs = []

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        return False, f"Error opening PDF: {str(e)}", 0

    if len(doc) == 0:
        doc.close()
        return False, "PDF has no pages", 0

    # Extract document-level metadata
    doc_metadata = {}
    if extract_metadata:
        doc_meta = extract_document_metadata(doc)
        doc_metadata = format_document_metadata(doc_meta)

    # Prepare processing metadata
    processing_metadata = create_processing_metadata()

    # Prepare custom metadata
    custom_meta_dict = custom_metadata or {}

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]

            # Analyze page for adaptive processing
            page_analysis = analyze_pdf_page(page)
            render_dpi = page_analysis.recommended_dpi

            # Render page at optimal DPI
            image, _ = render_page(page, dpi=render_dpi)
            page_doc_id = f"{base_doc_id}_page_{page_num + 1}"

            # Extract text with dual method (layer + OCR)
            force_ocr = enable_ocr if enable_ocr is not None else False
            text_result = extract_text(page, image, force_ocr=force_ocr)
            page_text = text_result.merged_text

            # Extract page-level metadata
            page_meta = extract_page_metadata(
                page, page_num + 1, image.width, image.height
            )
            page_metadata = format_page_metadata(page_meta)

            # Add page size category from analysis
            page_metadata["page_size_category"] = page_analysis.category.value
            page_metadata["page_orientation"] = page_analysis.orientation.value

            # Format text extraction metadata
            text_metadata = format_text_metadata(text_result)

            # Determine if this page needs region detection
            needs_regions = detect_drawing_regions and (
                should_detect_regions(image) or
                page_analysis.category in (PageSizeCategory.OVERSIZED, PageSizeCategory.MASSIVE)
            )

            if needs_regions:
                # Pass fitz.Page for vector analysis
                region_results = detect_and_extract_regions(
                    image,
                    use_vlm=use_vlm_detection,
                    vlm_api_key=vlm_api_key,
                    detection_method=detection_method,
                    pdf_page=page,
                )
                logger.info(
                    f"Page {page_num + 1}: detected {len(region_results)} regions "
                    f"(size: {page_analysis.category.value}, {image.size[0]}x{image.size[1]})"
                )

                # Generate embeddings for all region images
                region_images = [r[0] for r in region_results]
                try:
                    region_embeddings = generate_embeddings(
                        model, processor, region_images, device, batch_size
                    )
                except Exception as e:
                    failed_docs.append((page_doc_id, f"Embedding error: {e}"))
                    continue

                # Feed each region as a document
                for region_idx, ((region_img, region_meta), (bin_emb, float_emb)) in enumerate(
                    zip(region_results, region_embeddings)
                ):
                    is_full_page = region_meta.region_type == "full_page"
                    if is_full_page:
                        doc_id = page_doc_id
                    else:
                        doc_id = f"{page_doc_id}_region_{region_idx}"

                    snippet = page_text[:snippet_ingest_length] + "..." if len(page_text) > snippet_ingest_length else page_text
                    if not snippet:
                        snippet = f"Page {page_num + 1} of {filename}"
                    if not is_full_page and region_meta.label:
                        snippet = f"[{region_meta.label}] {snippet}"

                    # Build document fields with all metadata
                    fields = {
                        "id": doc_id,
                        "url": filename,
                        "title": title,
                        "page_number": page_num + 1,
                        "text": page_text if is_full_page else "",
                        "text_layer": text_result.layer_text if is_full_page else "",
                        "text_ocr": text_result.ocr_text if is_full_page else "",
                        "snippet": snippet,
                        "description": description,
                        "tags": tags,
                        "blur_image": create_blur_image(region_img),
                        "full_image": image_to_base64(region_img),
                        "embedding": bin_emb,
                        "embedding_float": float_emb,
                        "questions": [],
                        "queries": [],
                        "is_region": not is_full_page,
                        "parent_doc_id": page_doc_id if not is_full_page else "",
                        "region_label": region_meta.label if not is_full_page else "",
                        "region_type": region_meta.region_type,
                        "region_bbox": json.dumps(region_meta.to_dict()) if not is_full_page else "",
                        "s3_key": s3_key or "",
                    }

                    # Merge in metadata
                    fields.update(doc_metadata)
                    fields.update(page_metadata)
                    fields.update(text_metadata)
                    fields.update(processing_metadata)
                    if custom_meta_dict:
                        fields["custom_metadata"] = custom_meta_dict

                    vespa_doc = {"id": doc_id, "fields": fields}

                    _, success, error = feed_document(vespa_app, vespa_doc)
                    if success:
                        docs_indexed += 1
                    else:
                        failed_docs.append((doc_id, error))
            else:
                # Standard single-page processing (no region detection)
                try:
                    embeddings = generate_embeddings(
                        model, processor, [image], device, batch_size
                    )
                    bin_emb, float_emb = embeddings[0]
                except Exception as e:
                    failed_docs.append((page_doc_id, f"Embedding error: {e}"))
                    continue

                snippet = page_text[:snippet_ingest_length] + "..." if len(page_text) > snippet_ingest_length else page_text
                if not snippet:
                    snippet = f"Page {page_num + 1} of {filename}"

                # Build document fields with all metadata
                fields = {
                    "id": page_doc_id,
                    "url": filename,
                    "title": title,
                    "page_number": page_num + 1,
                    "text": page_text,
                    "text_layer": text_result.layer_text,
                    "text_ocr": text_result.ocr_text,
                    "snippet": snippet,
                    "description": description,
                    "tags": tags,
                    "blur_image": create_blur_image(image),
                    "full_image": image_to_base64(image),
                    "embedding": bin_emb,
                    "embedding_float": float_emb,
                    "questions": [],
                    "queries": [],
                    "is_region": False,
                    "parent_doc_id": "",
                    "region_label": "",
                    "region_type": "full_page",
                    "region_bbox": "",
                    "s3_key": s3_key or "",
                }

                # Merge in metadata
                fields.update(doc_metadata)
                fields.update(page_metadata)
                fields.update(text_metadata)
                fields.update(processing_metadata)
                if custom_meta_dict:
                    fields["custom_metadata"] = custom_meta_dict

                vespa_doc = {"id": page_doc_id, "fields": fields}

                _, success, error = feed_document(vespa_app, vespa_doc)
                if success:
                    docs_indexed += 1
                else:
                    failed_docs.append((page_doc_id, error))
    finally:
        doc.close()

    elapsed = time.time() - start_time
    if docs_indexed == 0:
        return False, f"Failed to index any documents. Errors: {failed_docs}", 0
    elif failed_docs:
        return True, f"Indexed {docs_indexed} documents in {elapsed:.1f}s. {len(failed_docs)} failed.", docs_indexed
    else:
        return True, f"Successfully indexed {docs_indexed} documents in {elapsed:.1f}s.", docs_indexed


# Processable image extensions (ColPali accepts any PIL-compatible image)
PROCESSABLE_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".tiff", ".tif"}
PROCESSABLE_EXTENSIONS = {".pdf"} | PROCESSABLE_IMAGE_EXTENSIONS


def validate_image(file_bytes: bytes) -> Tuple[bool, str]:
    """
    Validate an image file for integrity.

    Returns:
        Tuple of (is_valid, message)
    """
    try:
        img = Image.open(io.BytesIO(file_bytes))
        img.verify()
        return True, f"Valid {img.format} image ({img.size[0]}x{img.size[1]})"
    except Exception as e:
        return False, f"Invalid image: {str(e)}"


def ingest_image(
    file_bytes: bytes,
    filename: str,
    vespa_app: Vespa,
    model,
    processor,
    device: str,
    title: Optional[str] = None,
    description: str = "",
    tags: Optional[List[str]] = None,
    batch_size: int = None,
    s3_key: Optional[str] = None,
    custom_metadata: Optional[Dict[str, str]] = None,
) -> Tuple[bool, str, int]:
    """
    Ingest a single image file (JPG, PNG, GIF, TIFF) with ColPali embeddings.

    Opens the image with PIL, generates multi-vector embeddings via ColQwen2.5,
    and feeds the document to Vespa using the same pdf_page schema.

    Args:
        file_bytes: Raw image bytes
        filename: Original filename
        vespa_app: Vespa application instance
        model: ColPali model
        processor: ColPali processor
        device: Device string (cuda/cpu)
        title: Optional custom title (defaults to filename without extension)
        description: Optional description
        tags: Optional list of tags
        batch_size: Batch size for embedding generation
        s3_key: Optional S3 key for original file reference
        custom_metadata: Optional dict of custom metadata key-value pairs

    Returns:
        Tuple of (success, message, pages_indexed)
    """
    start_time = time.time()

    if title is None or title.strip() == "":
        title = Path(filename).stem
    if tags is None:
        tags = []
    if batch_size is None:
        batch_size = get("ingestion", "batch_size")

    snippet_ingest_length = get("image", "truncation", "snippet_ingest_length")

    # Step 1: Validate image
    is_valid, validation_msg = validate_image(file_bytes)
    if not is_valid:
        return False, validation_msg, 0

    # Step 2: Open image as PIL
    try:
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
    except Exception as e:
        return False, f"Error opening image: {str(e)}", 0

    # Step 3: Generate document ID
    base_doc_id = generate_doc_id(file_bytes, title)
    doc_id = f"{base_doc_id}_page_1"

    # Step 4: Generate embeddings
    try:
        embeddings = generate_embeddings(model, processor, [image], device, batch_size)
        bin_emb, float_emb = embeddings[0]
    except Exception as e:
        return False, f"Embedding generation failed: {str(e)}", 0

    # Step 5: Analyze page size
    size_category = categorize_image(image)

    # Step 6: Build processing metadata
    processing_metadata = create_processing_metadata()

    # Step 7: Build and feed Vespa document
    snippet = filename
    if len(snippet) > snippet_ingest_length:
        snippet = snippet[:snippet_ingest_length] + "..."

    fields = {
        "id": doc_id,
        "url": filename,
        "title": title,
        "page_number": 1,
        "text": "",
        "text_layer": "",
        "text_ocr": "",
        "snippet": snippet,
        "description": description,
        "tags": tags,
        "blur_image": create_blur_image(image),
        "full_image": image_to_base64(image),
        "embedding": bin_emb,
        "embedding_float": float_emb,
        "questions": [],
        "queries": [],
        "is_region": False,
        "parent_doc_id": "",
        "region_label": "",
        "region_type": "full_page",
        "region_bbox": "",
        "s3_key": s3_key or "",
        # Image metadata
        "page_width_px": image.width,
        "page_height_px": image.height,
        "page_size_category": size_category.value,
        "page_orientation": "landscape" if image.width > image.height else "portrait",
        "text_extraction_method": "none",
    }

    # Add processing metadata
    fields.update(processing_metadata)

    # Add custom metadata
    if custom_metadata:
        fields["custom_metadata"] = custom_metadata

    vespa_doc = {"id": doc_id, "fields": fields}

    _, success, error = feed_document(vespa_app, vespa_doc)
    elapsed = time.time() - start_time

    if success:
        return True, f"Successfully indexed image {filename} in {elapsed:.1f}s.", 1
    else:
        return False, f"Failed to feed image to Vespa: {error}", 0
