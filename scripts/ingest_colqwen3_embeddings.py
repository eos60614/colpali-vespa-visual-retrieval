#!/usr/bin/env python3
"""
Script to add ColQwen3 embeddings to existing documents in Vespa.

This script:
1. Loads the ColQwen3 model
2. Fetches documents from Vespa (with full_image field) in parallel
3. Generates ColQwen3 embeddings in batches on GPU
4. Updates documents with the new embedding_colqwen3 field in parallel

Usage:
    python scripts/ingest_colqwen3_embeddings.py --batch-size 8 --workers 20
"""

import argparse
import base64
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path
from typing import List, Dict, Tuple, Optional

import numpy as np
import torch
from PIL import Image
from dotenv import load_dotenv
from tqdm import tqdm
from vespa.application import Vespa
from transformers import AutoModel, AutoProcessor

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import get

load_dotenv()


def load_colqwen3_model(device: str = "cuda"):
    """Load ColQwen2.5 model and processor."""
    model_id = get("colpali", "model_name")
    print(f"Loading ColQwen2.5 model: {model_id}")

    # Use SDPA (PyTorch's Scaled Dot-Product Attention) - equivalent to FlashAttention 2
    attn_implementation = "sdpa"
    print("Using PyTorch SDPA (Scaled Dot-Product Attention)")

    processor = AutoProcessor.from_pretrained(
        model_id,
        trust_remote_code=True,
        max_num_visual_tokens=768,
    )

    model_kwargs = {
        "torch_dtype": torch.bfloat16,
        "trust_remote_code": True,
        "device_map": device,
        "attn_implementation": attn_implementation,
    }

    model = AutoModel.from_pretrained(model_id, **model_kwargs).eval()

    return model, processor


def get_vespa_client() -> Vespa:
    """Create Vespa client from environment variables."""
    local_url = os.environ.get("VESPA_LOCAL_URL")
    if local_url:
        print(f"Connecting to local Vespa at {local_url}")
        return Vespa(url=local_url)

    token_url = os.environ.get("VESPA_APP_TOKEN_URL")
    token = os.environ.get("VESPA_CLOUD_SECRET_TOKEN")
    if token_url and token:
        print("Connecting to Vespa Cloud")
        return Vespa(url=token_url, vespa_cloud_secret_token=token)

    raise ValueError("No Vespa connection configured. Set VESPA_LOCAL_URL or VESPA_APP_TOKEN_URL")


def fetch_document_ids(vespa: Vespa, limit: int = None) -> List[str]:
    """Fetch all document IDs from Vespa."""
    print("Fetching document IDs...")

    # First get total count
    with vespa.syncio() as session:
        response = session.query(
            body={
                "yql": "select id from pdf_page where true",
                "hits": 0,
                "ranking": "unranked",
            }
        )
        total_count = response.json.get("root", {}).get("fields", {}).get("totalCount", 0)
        print(f"Total documents in Vespa: {total_count}")

    # Fetch all documents using match all with a high hit count
    # Vespa's offset pagination doesn't work well, so we use a different approach
    all_doc_ids = []

    with vespa.syncio() as session:
        # Use userQuery with match all
        response = session.query(
            body={
                "yql": "select id from pdf_page where true",
                "hits": min(limit or 10000, 400),  # Vespa limit is 400
                "ranking": "unranked",
            }
        )

        if not response.is_successful():
            raise Exception(f"Failed to fetch documents: {response.json}")

        children = response.json.get("root", {}).get("children", [])
        all_doc_ids = [child["fields"]["id"] for child in children]

    # If we need more than 400, we need to use a workaround
    # Query by ID ranges or use visit API
    if total_count > len(all_doc_ids) and (limit is None or limit > len(all_doc_ids)):
        print(f"Warning: Only fetched {len(all_doc_ids)} of {total_count} documents due to Vespa hit limit")
        print("Running multiple queries to fetch remaining documents...")

        # Get existing IDs to exclude
        existing_ids = set(all_doc_ids)

        # Try to get more by using different queries
        for title_prefix in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
            if limit and len(all_doc_ids) >= limit:
                break

            response = session.query(
                body={
                    "yql": f'select id from pdf_page where title contains "{title_prefix}"',
                    "hits": 400,
                    "ranking": "unranked",
                }
            )

            if response.is_successful():
                for child in response.json.get("root", {}).get("children", []):
                    doc_id = child["fields"]["id"]
                    if doc_id not in existing_ids:
                        all_doc_ids.append(doc_id)
                        existing_ids.add(doc_id)

    if limit:
        all_doc_ids = all_doc_ids[:limit]

    print(f"Found {len(all_doc_ids)} documents")
    return all_doc_ids


def fetch_single_document(vespa: Vespa, doc_id: str) -> Tuple[str, Optional[str]]:
    """Fetch a single document with its full image. Returns (doc_id, image_b64 or None)."""
    try:
        with vespa.syncio() as session:
            response = session.query(
                body={
                    "yql": f'select id, full_image from pdf_page where id contains "{doc_id}"',
                    "hits": 1,
                    "ranking": "unranked",
                }
            )

        if not response.is_successful():
            return doc_id, None

        children = response.json.get("root", {}).get("children", [])
        if not children:
            return doc_id, None

        return doc_id, children[0]["fields"].get("full_image")
    except Exception as e:
        print(f"Error fetching {doc_id}: {e}")
        return doc_id, None


def fetch_documents_parallel(vespa: Vespa, doc_ids: List[str], workers: int = 20) -> Dict[str, str]:
    """Fetch multiple documents in parallel. Returns dict of doc_id -> image_b64."""
    print(f"Fetching {len(doc_ids)} documents with {workers} workers...")
    results = {}

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(fetch_single_document, vespa, doc_id): doc_id for doc_id in doc_ids}

        for future in tqdm(as_completed(futures), total=len(futures), desc="Fetching"):
            doc_id, image_b64 = future.result()
            if image_b64:
                results[doc_id] = image_b64

    return results


def generate_batch_embeddings(
    model, processor, images: List[Image.Image], device: str = "cuda"
) -> List[Dict[str, List[int]]]:
    """Generate ColQwen3 embeddings for a batch of images."""
    # Process all images in batch
    inputs = processor.process_images(images).to(device)

    with torch.no_grad():
        output = model(**inputs)
        # Convert to float32 for numpy compatibility, then to CPU
        all_embeddings = output.embeddings.float().to("cpu")  # Shape: (batch, num_patches, 320)

    results = []
    for batch_idx in range(all_embeddings.shape[0]):
        embeddings = all_embeddings[batch_idx]  # Shape: (num_patches, 320)
        embeddings_np = embeddings.numpy()

        binary_embeddings = {}
        for patch_idx in range(embeddings_np.shape[0]):
            vector = embeddings_np[patch_idx]
            binary_vector = np.packbits(np.where(vector > 0, 1, 0)).astype(np.int8).tolist()
            binary_embeddings[str(patch_idx)] = binary_vector

        results.append(binary_embeddings)

    return results


def update_single_document(vespa: Vespa, doc_id: str, embedding: Dict[str, List[int]]) -> Tuple[str, bool]:
    """Update a single document with ColQwen3 embedding. Returns (doc_id, success)."""
    try:
        cells = []
        for patch_id, values in embedding.items():
            for v_idx, value in enumerate(values):
                cells.append({"address": {"patch": patch_id, "v": str(v_idx)}, "value": value})

        with vespa.syncio() as session:
            response = session.update_data(
                schema=get("vespa", "schema_name"),
                data_id=doc_id,
                fields={"embedding_colqwen3": {"cells": cells}},
            )

        return doc_id, response.is_successful()
    except Exception as e:
        print(f"Error updating {doc_id}: {e}")
        return doc_id, False


def update_documents_parallel(
    vespa: Vespa, updates: List[Tuple[str, Dict[str, List[int]]]], workers: int = 20
) -> Tuple[int, int]:
    """Update multiple documents in parallel. Returns (success_count, error_count)."""
    print(f"Updating {len(updates)} documents with {workers} workers...")
    success_count = 0
    error_count = 0

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(update_single_document, vespa, doc_id, embedding): doc_id
            for doc_id, embedding in updates
        }

        for future in tqdm(as_completed(futures), total=len(futures), desc="Updating"):
            doc_id, success = future.result()
            if success:
                success_count += 1
            else:
                error_count += 1

    return success_count, error_count


def main():
    parser = argparse.ArgumentParser(description="Add ColQwen3 embeddings to Vespa documents")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size for GPU processing")
    parser.add_argument("--workers", type=int, default=20, help="Number of parallel workers for I/O")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of documents to process")
    parser.add_argument("--device", type=str, default="cuda", help="Device to use (cuda/cpu)")
    args = parser.parse_args()

    # Initialize
    vespa = get_vespa_client()
    model, processor = load_colqwen3_model(args.device)

    # Fetch document IDs
    doc_ids = fetch_document_ids(vespa, args.limit)

    # Process in chunks to manage memory
    chunk_size = args.batch_size * 10  # Fetch 10 batches worth at a time
    total_success = 0
    total_errors = 0

    for chunk_start in range(0, len(doc_ids), chunk_size):
        chunk_end = min(chunk_start + chunk_size, len(doc_ids))
        chunk_doc_ids = doc_ids[chunk_start:chunk_end]

        print(f"\nProcessing chunk {chunk_start}-{chunk_end} of {len(doc_ids)}")

        # Fetch documents in parallel
        doc_images = fetch_documents_parallel(vespa, chunk_doc_ids, workers=args.workers)

        if not doc_images:
            print("No images found in this chunk")
            continue

        # Prepare batches for GPU processing
        doc_id_list = list(doc_images.keys())
        all_updates = []

        for batch_start in tqdm(range(0, len(doc_id_list), args.batch_size), desc="GPU batches"):
            batch_end = min(batch_start + args.batch_size, len(doc_id_list))
            batch_doc_ids = doc_id_list[batch_start:batch_end]

            # Decode images
            batch_images = []
            valid_doc_ids = []
            for doc_id in batch_doc_ids:
                try:
                    image_b64 = doc_images[doc_id]
                    image_data = base64.b64decode(image_b64)
                    image = Image.open(BytesIO(image_data)).convert("RGB")
                    batch_images.append(image)
                    valid_doc_ids.append(doc_id)
                except Exception as e:
                    print(f"Error decoding image for {doc_id}: {e}")

            if not batch_images:
                continue

            # Generate embeddings for batch
            try:
                embeddings = generate_batch_embeddings(model, processor, batch_images, args.device)
                for doc_id, embedding in zip(valid_doc_ids, embeddings):
                    all_updates.append((doc_id, embedding))
            except Exception as e:
                print(f"Error generating embeddings for batch: {e}")

        # Update documents in parallel
        if all_updates:
            success, errors = update_documents_parallel(vespa, all_updates, workers=args.workers)
            total_success += success
            total_errors += errors

    print(f"\n{'='*50}")
    print(f"Completed: {total_success} success, {total_errors} errors")


if __name__ == "__main__":
    main()
