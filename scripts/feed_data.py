#!/usr/bin/env python3
"""
Script to index PDF documents into local Vespa for ColPali visual retrieval.

Usage:
    python scripts/feed_data.py --pdf-folder /path/to/pdfs
    python scripts/feed_data.py --sample  # Download and use sample data
    python scripts/feed_data.py --pdf-folder /path/to/pdfs --workers 20

Requirements:
    - Local Vespa running (docker-compose up -d)
    - Vespa application deployed
    - ColPali model will be downloaded on first run
"""

import argparse
import base64
import io
import os
import sys
from pathlib import Path
from typing import Generator, List, Tuple
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import multiprocessing as mp

import numpy as np
from PIL import Image
from tqdm import tqdm
from dotenv import load_dotenv
from vespa.application import Vespa

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_colpali_model():
    """Load ColQwen2.5 model for generating embeddings."""
    import torch
    from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor

    model_name = "tsystems/colqwen2.5-3b-multilingual-v1.0"
    device = "cuda" if torch.cuda.is_available() else "cpu"

    processor = ColQwen2_5_Processor.from_pretrained(model_name)

    model = ColQwen2_5.from_pretrained(
        model_name,
        torch_dtype=torch.bfloat16 if device == "cuda" else torch.float32,
        device_map=device,
    ).eval()

    return model, processor, device


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


def generate_embeddings(model, processor, images: list, device: str, batch_size: int = 4):
    """Generate ColQwen2.5 embeddings for images.

    Returns:
        List of tuples (binary_embedding, float_embedding) in Vespa tensor format
    """
    import torch

    all_embeddings = []

    for i in range(0, len(images), batch_size):
        batch_images = images[i : i + batch_size]

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


def pdf_to_images_worker(pdf_path: str) -> Tuple[str, List[Image.Image], List[str]]:
    """Worker function to convert PDF pages to PIL Images and extract text (runs in separate process)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        return pdf_path, [], []

    images = []
    texts = []
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            # Render image
            pix = page.get_pixmap(dpi=150)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            images.append(img)
            # Extract text
            text = page.get_text("text").strip()
            texts.append(text)
        doc.close()
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")

    return pdf_path, images, texts


def pdf_to_images(pdf_path: Path) -> list:
    """Convert PDF pages to PIL Images."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("Please install PyMuPDF: pip install pymupdf")
        sys.exit(1)

    images = []
    doc = fitz.open(pdf_path)

    for page_num in range(len(doc)):
        page = doc[page_num]
        pix = page.get_pixmap(dpi=150)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        images.append(img)

    doc.close()
    return images


def process_single_pdf(pdf_path: Path, model, processor, device: str) -> List[dict]:
    """Process a single PDF and return list of documents."""
    images = pdf_to_images(pdf_path)

    if not images:
        return []

    # Generate embeddings for all pages
    embeddings = generate_embeddings(model, processor, images, device)

    docs = []
    for page_num, (image, (binary_embedding, float_embedding)) in enumerate(zip(images, embeddings)):
        doc_id = f"{pdf_path.stem}_page_{page_num + 1}"

        docs.append({
            "id": doc_id,
            "fields": {
                "id": doc_id,
                "url": str(pdf_path),
                "title": pdf_path.stem,
                "page_number": page_num + 1,
                "text": "",
                "snippet": f"Page {page_num + 1} of {pdf_path.name}",
                "blur_image": create_blur_image(image),
                "full_image": image_to_base64(image),
                "embedding": binary_embedding,
                "embedding_float": float_embedding,
                "questions": [],
                "queries": [],
            },
        })

    return docs


def feed_document(app: Vespa, doc: dict) -> Tuple[str, bool, str]:
    """Feed a single document to Vespa. Returns (doc_id, success, error_msg)."""
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


def main():
    parser = argparse.ArgumentParser(description="Feed PDF data to Vespa")
    parser.add_argument("--pdf-folder", type=Path, help="Folder containing PDF files")
    parser.add_argument("--sample", action="store_true", help="Use sample data for testing")
    parser.add_argument(
        "--vespa-url",
        default=os.environ.get("VESPA_LOCAL_URL", "http://localhost:8080"),
        help="Vespa endpoint URL",
    )
    parser.add_argument("--deploy", action="store_true", help="Deploy application before feeding")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel workers for PDF processing")
    parser.add_argument("--feed-workers", type=int, default=10, help="Number of parallel workers for Vespa feeding")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size for embedding generation")
    parser.add_argument(
        "--detect-regions", action="store_true",
        help="Enable AI region detection for large-format drawings. "
             "Splits large pages into sub-regions for better ColPali patch coverage."
    )
    parser.add_argument(
        "--use-vlm", action="store_true",
        help="Use VLM for semantic region labeling via OpenRouter/OpenAI/Ollama. "
             "Requires OPENROUTER_API_KEY or OPENAI_API_KEY (not needed for Ollama). "
             "Falls back to heuristic detection if unavailable."
    )
    parser.add_argument(
        "--detection-method", default="auto",
        choices=["auto", "pdf_vector", "heuristic", "vlm_legacy"],
        help="Region detection strategy. 'auto' tries pdf_vector then heuristic then tiling. "
             "'pdf_vector' uses PDF structure directly (best for CAD exports). "
             "'heuristic' uses whitespace gutters. 'vlm_legacy' uses VLM bounding boxes."
    )

    args = parser.parse_args()
    load_dotenv()

    # Determine PDF folder
    if args.sample:
        pdf_folder = Path("sample_data")
        if not pdf_folder.exists():
            print("Sample data folder not found")
            sys.exit(1)
    elif args.pdf_folder:
        pdf_folder = args.pdf_folder
    else:
        print("Please specify --pdf-folder or --sample")
        sys.exit(1)

    if not pdf_folder.exists():
        print(f"Folder not found: {pdf_folder}")
        sys.exit(1)

    # Connect to Vespa
    print(f"Connecting to Vespa at {args.vespa_url}")
    app = Vespa(url=args.vespa_url)

    try:
        app.wait_for_application_up()
    except Exception as e:
        print(f"Could not connect to Vespa: {e}")
        print("Make sure Vespa is running: docker compose up -d")
        sys.exit(1)

    # Load ColQwen model
    print("Loading ColQwen model...")
    model, processor, device = get_colpali_model()
    print(f"Model loaded on {device}")

    # Find PDF files
    pdf_files = list(pdf_folder.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {pdf_folder}")
        sys.exit(1)

    print(f"Found {len(pdf_files)} PDF files")
    print(f"Using {args.workers} workers for PDF processing, {args.feed_workers} workers for feeding")

    # Phase 1: Parallel PDF rendering using multiprocessing
    print("\n[Phase 1] Rendering PDFs to images + extracting text (parallel)...")
    pdf_data = {}  # {pdf_path: (images, texts)}

    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(pdf_to_images_worker, str(pdf_path)): pdf_path for pdf_path in pdf_files}

        for future in tqdm(as_completed(futures), total=len(futures), desc="Rendering PDFs"):
            pdf_path_str, images, texts = future.result()
            if images:
                pdf_data[pdf_path_str] = (images, texts)

    print(f"Rendered {sum(len(data[0]) for data in pdf_data.values())} pages from {len(pdf_data)} PDFs")

    # Phase 2: Generate embeddings (GPU-bound, sequential per PDF but batched)
    print("\n[Phase 2] Generating ColPali embeddings...")
    if args.detect_regions:
        from backend.drawing_regions import detect_and_extract_regions, should_detect_regions
        import fitz as fitz_module
        import json
        print(f"  Region detection ENABLED (method={args.detection_method})")
        if args.use_vlm:
            print("  VLM-based semantic labeling ENABLED")

    all_docs = []

    for pdf_path_str, (images, texts) in tqdm(pdf_data.items(), desc="Generating embeddings"):
        pdf_path = Path(pdf_path_str)

        if not images:
            continue

        # Re-open PDF for vector analysis when region detection is active
        fitz_doc = None
        if args.detect_regions and args.detection_method in ("auto", "pdf_vector"):
            try:
                fitz_doc = fitz_module.open(pdf_path_str)
            except Exception as e:
                print(f"Warning: Could not re-open {pdf_path_str} for vector analysis: {e}")

        try:
            for page_num, image in enumerate(images):
                page_text = texts[page_num] if page_num < len(texts) else ""
                page_doc_id = f"{pdf_path.stem}_page_{page_num + 1}"

                if args.detect_regions and should_detect_regions(image):
                    # Get fitz page if available
                    pdf_page = None
                    if fitz_doc is not None and page_num < len(fitz_doc):
                        pdf_page = fitz_doc[page_num]

                    # Detect regions for this large drawing
                    region_results = detect_and_extract_regions(
                        image,
                        use_vlm=args.use_vlm,
                        detection_method=args.detection_method,
                        pdf_page=pdf_page,
                    )
                    region_images = [r[0] for r in region_results]
                    embeddings = generate_embeddings(
                        model, processor, region_images, device, batch_size=args.batch_size
                    )

                    for region_idx, ((region_img, region_meta), (bin_emb, float_emb)) in enumerate(
                        zip(region_results, embeddings)
                    ):
                        is_full_page = region_meta.region_type == "full_page"
                        doc_id = page_doc_id if is_full_page else f"{page_doc_id}_region_{region_idx}"

                        snippet = page_text[:200] + "..." if len(page_text) > 200 else page_text
                        if not snippet:
                            snippet = f"Page {page_num + 1} of {pdf_path.name}"
                        if not is_full_page and region_meta.label:
                            snippet = f"[{region_meta.label}] {snippet}"

                        all_docs.append({
                            "id": doc_id,
                            "fields": {
                                "id": doc_id,
                                "url": str(pdf_path),
                                "title": pdf_path.stem,
                                "page_number": page_num + 1,
                                "text": page_text if is_full_page else "",
                                "snippet": snippet,
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
                        })
                else:
                    # Standard single-page embedding
                    embeddings = generate_embeddings(
                        model, processor, [image], device, batch_size=args.batch_size
                    )
                    bin_emb, float_emb = embeddings[0]

                    snippet = page_text[:200] + "..." if len(page_text) > 200 else page_text
                    if not snippet:
                        snippet = f"Page {page_num + 1} of {pdf_path.name}"

                    all_docs.append({
                        "id": page_doc_id,
                        "fields": {
                            "id": page_doc_id,
                            "url": str(pdf_path),
                            "title": pdf_path.stem,
                            "page_number": page_num + 1,
                            "text": page_text,
                            "snippet": snippet,
                            "blur_image": create_blur_image(image),
                            "full_image": image_to_base64(image),
                            "embedding": bin_emb,
                            "embedding_float": float_emb,
                            "questions": [],
                            "queries": [],
                        },
                    })
        finally:
            if fitz_doc is not None:
                fitz_doc.close()

    print(f"Generated embeddings for {len(all_docs)} pages")

    # Phase 3: Parallel feeding to Vespa
    print("\n[Phase 3] Feeding documents to Vespa (parallel)...")
    total_success = 0
    total_failed = 0

    with ThreadPoolExecutor(max_workers=args.feed_workers) as executor:
        futures = {executor.submit(feed_document, app, doc): doc["id"] for doc in all_docs}

        for future in tqdm(as_completed(futures), total=len(futures), desc="Feeding to Vespa"):
            doc_id, success, error = future.result()
            if success:
                total_success += 1
            else:
                total_failed += 1
                if error:
                    print(f"Error feeding {doc_id}: {error}")

    print(f"\n{'='*50}")
    print(f"Successfully indexed: {total_success} documents")
    if total_failed > 0:
        print(f"Failed: {total_failed} documents")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
