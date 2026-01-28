"""
Ingestion module for processing single PDF files.
Extracts core functionality from scripts/feed_data.py for on-demand upload processing.
"""

import base64
import hashlib
import io
import json
import logging
import re
from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF
import numpy as np
from PIL import Image
from vespa.application import Vespa

from backend.config import get
from backend.drawing_regions import (
    detect_and_extract_regions,
    should_detect_regions,
)

logger = logging.getLogger(__name__)


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


def sanitize_text(text: str) -> str:
    """Remove illegal control characters from extracted PDF text.

    Vespa rejects text containing certain control characters like null (0x0).
    This removes all ASCII control characters except common whitespace.
    """
    if not text:
        return text
    # Remove ASCII control chars (0x00-0x1F and 0x7F) except tab, newline, carriage return
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)


def render_page(page, dpi: int = None) -> Tuple[Image.Image, str]:
    """
    Render a single fitz.Page to a PIL Image and extract its text.

    Args:
        page: fitz.Page object
        dpi: Rendering DPI

    Returns:
        Tuple of (PIL Image, sanitized text)
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
) -> Tuple[bool, str, int]:
    """
    Main ingestion function: validates, processes, and feeds a PDF to Vespa.

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
        use_vlm_detection: Use VLM for semantic region labeling (via OpenRouter/OpenAI/Ollama)
        vlm_api_key: API key for VLM (defaults to OPENROUTER_API_KEY or OPENAI_API_KEY env var)
        detection_method: Region detection strategy ("auto", "pdf_vector", "heuristic", "vlm_legacy")

    Returns:
        Tuple of (success, message, pages_indexed)
    """
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
    render_dpi = get("image", "dpi")

    # Step 1: Validate PDF
    is_valid, validation_msg = validate_pdf(file_bytes)
    if not is_valid:
        return False, validation_msg, 0

    # Step 2: Generate base document ID
    base_doc_id = generate_doc_id(file_bytes, title)

    # Step 3: Open PDF and process pages (keep doc open for vector analysis)
    docs_indexed = 0
    failed_docs = []

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
    except Exception as e:
        return False, f"Error opening PDF: {str(e)}", 0

    if len(doc) == 0:
        doc.close()
        return False, "PDF has no pages", 0

    try:
        for page_num in range(len(doc)):
            page = doc[page_num]
            image, page_text = render_page(page, dpi=render_dpi)
            page_doc_id = f"{base_doc_id}_page_{page_num + 1}"

            # Determine if this page needs region detection
            if detect_drawing_regions and should_detect_regions(image):
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
                    f"(image size: {image.size[0]}x{image.size[1]})"
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

                    vespa_doc = {
                        "id": doc_id,
                        "fields": {
                            "id": doc_id,
                            "url": filename,
                            "title": title,
                            "page_number": page_num + 1,
                            "text": page_text if is_full_page else "",
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
                        },
                    }

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

                vespa_doc = {
                    "id": page_doc_id,
                    "fields": {
                        "id": page_doc_id,
                        "url": filename,
                        "title": title,
                        "page_number": page_num + 1,
                        "text": page_text,
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
                    },
                }

                _, success, error = feed_document(vespa_app, vespa_doc)
                if success:
                    docs_indexed += 1
                else:
                    failed_docs.append((page_doc_id, error))
    finally:
        doc.close()

    if docs_indexed == 0:
        return False, f"Failed to index any documents. Errors: {failed_docs}", 0
    elif failed_docs:
        return True, f"Indexed {docs_indexed} documents. {len(failed_docs)} failed.", docs_indexed
    else:
        return True, f"Successfully indexed {docs_indexed} documents.", docs_indexed
