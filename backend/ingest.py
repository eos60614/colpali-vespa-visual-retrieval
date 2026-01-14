"""
Ingestion module for processing single PDF files.
Extracts core functionality from scripts/feed_data.py for on-demand upload processing.
"""

import base64
import hashlib
import io
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF
import numpy as np
from PIL import Image
from vespa.application import Vespa


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


def create_blur_image(image: Image.Image, max_size: int = 100) -> str:
    """Create a small blurred version of the image for fast loading."""
    img_copy = image.copy()
    img_copy.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    return image_to_base64(img_copy, format="JPEG")


def float_to_binary_embedding(float_embedding: np.ndarray) -> list:
    """Convert float embedding to packed int8 binary embedding."""
    binary = np.packbits(np.where(float_embedding > 0, 1, 0)).astype(np.int8)
    return binary.tolist()


def pdf_to_images(file_bytes: bytes, dpi: int = 150) -> Tuple[List[Image.Image], List[str]]:
    """
    Convert PDF bytes to list of PIL Images and extracted text per page.

    Returns:
        Tuple of (images list, texts list)
    """
    images = []
    texts = []

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    for page_num in range(len(doc)):
        page = doc[page_num]
        # Render image
        pix = page.get_pixmap(dpi=dpi)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)
        # Extract text
        text = page.get_text("text").strip()
        texts.append(text)
    doc.close()

    return images, texts


def generate_embeddings(model, processor, images: List[Image.Image], device: str, batch_size: int = 4) -> List[dict]:
    """
    Generate ColPali embeddings for images.

    Returns:
        List of embedding dictionaries in Vespa tensor format
    """
    import torch

    all_embeddings = []

    for i in range(0, len(images), batch_size):
        batch_images = images[i:i + batch_size]

        with torch.no_grad():
            batch_inputs = processor.process_images(batch_images).to(device)
            embeddings = model(**batch_inputs)

        # Convert to binary embeddings in Vespa tensor format
        for emb in embeddings:
            emb_np = emb.cpu().float().numpy()
            # Vespa expects {"blocks": {"0": [...], "1": [...], ...}} format
            binary_embs = {
                "blocks": {
                    str(patch_idx): float_to_binary_embedding(patch_emb)
                    for patch_idx, patch_emb in enumerate(emb_np)
                }
            }
            all_embeddings.append(binary_embs)

    return all_embeddings


def feed_document(app: Vespa, doc: dict) -> Tuple[str, bool, str]:
    """
    Feed a single document to Vespa.

    Returns:
        Tuple of (doc_id, success, error_message)
    """
    try:
        response = app.feed_data_point(
            schema="pdf_page",
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
    content_hash = hashlib.md5(pdf_bytes).hexdigest()[:12]
    # Create safe title slug: alphanumeric only, max 30 chars
    safe_title = re.sub(r'[^a-zA-Z0-9]', '_', title)[:30].strip('_').lower()
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
    batch_size: int = 4,
) -> Tuple[bool, str, int]:
    """
    Main ingestion function: validates, processes, and feeds a PDF to Vespa.

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

    Returns:
        Tuple of (success, message, pages_indexed)
    """
    # Default title from filename
    if title is None or title.strip() == "":
        title = Path(filename).stem

    # Default tags to empty list
    if tags is None:
        tags = []

    # Step 1: Validate PDF
    is_valid, validation_msg = validate_pdf(file_bytes)
    if not is_valid:
        return False, validation_msg, 0

    # Step 2: Generate base document ID
    base_doc_id = generate_doc_id(file_bytes, title)

    # Step 3: Convert PDF to images and extract text
    try:
        images, texts = pdf_to_images(file_bytes)
    except Exception as e:
        return False, f"Error rendering PDF: {str(e)}", 0

    if not images:
        return False, "PDF has no pages", 0

    # Step 4: Generate embeddings
    try:
        embeddings = generate_embeddings(model, processor, images, device, batch_size)
    except Exception as e:
        return False, f"Error generating embeddings: {str(e)}", 0

    # Step 5: Create and feed documents
    pages_indexed = 0
    failed_pages = []

    for page_num, (image, embedding) in enumerate(zip(images, embeddings)):
        page_text = texts[page_num] if page_num < len(texts) else ""

        # Create snippet from first 200 chars of text or default
        snippet = page_text[:200] + "..." if len(page_text) > 200 else page_text
        if not snippet:
            snippet = f"Page {page_num + 1} of {filename}"

        doc_id = f"{base_doc_id}_page_{page_num + 1}"

        doc = {
            "id": doc_id,
            "fields": {
                "id": doc_id,
                "url": filename,
                "title": title,
                "page_number": page_num + 1,
                "text": page_text,
                "snippet": snippet,
                "description": description,
                "tags": tags,
                "blur_image": create_blur_image(image),
                "full_image": image_to_base64(image),
                "embedding": embedding,
                "questions": [],
                "queries": [],
            },
        }

        _, success, error = feed_document(vespa_app, doc)
        if success:
            pages_indexed += 1
        else:
            failed_pages.append((page_num + 1, error))

    if pages_indexed == 0:
        return False, f"Failed to index any pages. Errors: {failed_pages}", 0
    elif failed_pages:
        return True, f"Indexed {pages_indexed} pages. {len(failed_pages)} pages failed.", pages_indexed
    else:
        return True, f"Successfully indexed {pages_indexed} pages.", pages_indexed
