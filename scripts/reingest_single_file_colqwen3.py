#!/usr/bin/env python3
"""
Reingest a single file's pages for ColQwen3 embeddings with detailed timing statistics.
"""

import argparse
import base64
import os
import sys
import time
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

from backend.core.config import get

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

    raise ValueError("No Vespa connection configured")


def fetch_document_ids_by_title(vespa: Vespa, title_filter: str) -> List[str]:
    """Fetch document IDs matching the title filter."""
    print(f"Fetching documents matching title: '{title_filter}'...")

    with vespa.syncio() as session:
        response = session.query(
            body={
                "yql": f'select id, title, page_number from pdf_page where title contains "{title_filter}"',
                "hits": 400,
                "ranking": "unranked",
            }
        )

        if not response.is_successful():
            raise Exception(f"Failed to fetch documents: {response.json}")

        children = response.json.get("root", {}).get("children", [])
        doc_ids = []
        for child in children:
            fields = child["fields"]
            doc_ids.append(fields["id"])
            print(f"  Found: {fields.get('title', 'N/A')} - page {fields.get('page_number', 'N/A')}")

    return doc_ids


def fetch_single_document(vespa: Vespa, doc_id: str) -> Tuple[str, Optional[str]]:
    """Fetch a single document with its full image."""
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


def generate_batch_embeddings(
    model, processor, images: List[Image.Image], device: str = "cuda"
) -> List[Dict[str, List[int]]]:
    """Generate ColQwen3 embeddings for a batch of images."""
    inputs = processor.process_images(images).to(device)

    with torch.no_grad():
        output = model(**inputs)
        all_embeddings = output.embeddings.float().to("cpu")

    results = []
    for batch_idx in range(all_embeddings.shape[0]):
        embeddings = all_embeddings[batch_idx]
        embeddings_np = embeddings.numpy()

        binary_embeddings = {}
        for patch_idx in range(embeddings_np.shape[0]):
            vector = embeddings_np[patch_idx]
            binary_vector = np.packbits(np.where(vector > 0, 1, 0)).astype(np.int8).tolist()
            binary_embeddings[str(patch_idx)] = binary_vector

        results.append(binary_embeddings)

    return results


def update_single_document(vespa: Vespa, doc_id: str, embedding: Dict[str, List[int]]) -> Tuple[str, bool]:
    """Update a single document with ColQwen3 embedding."""
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


def main():
    parser = argparse.ArgumentParser(description="Reingest a single file for ColQwen3")
    parser.add_argument("--title", type=str, required=True, help="Title/filename filter")
    parser.add_argument("--batch-size", type=int, default=8, help="Batch size for GPU")
    parser.add_argument("--workers", type=int, default=10, help="Parallel workers for I/O")
    parser.add_argument("--device", type=str, default="cuda", help="Device (cuda/cpu)")
    args = parser.parse_args()

    total_start_time = time.time()
    timing_stats = {
        "model_load": 0,
        "fetch_ids": 0,
        "fetch_images": 0,
        "generate_embeddings": 0,
        "update_vespa": 0,
    }

    # Load model
    model_start = time.time()
    vespa = get_vespa_client()
    model, processor = load_colqwen3_model(args.device)
    timing_stats["model_load"] = time.time() - model_start

    # Fetch document IDs
    fetch_ids_start = time.time()
    doc_ids = fetch_document_ids_by_title(vespa, args.title)
    timing_stats["fetch_ids"] = time.time() - fetch_ids_start

    if not doc_ids:
        print(f"No documents found matching '{args.title}'")
        return

    num_pages = len(doc_ids)
    print(f"\nFound {num_pages} pages to process")

    # Fetch images
    fetch_images_start = time.time()
    print(f"\nFetching {num_pages} document images...")
    doc_images = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(fetch_single_document, vespa, doc_id): doc_id for doc_id in doc_ids}
        for future in tqdm(as_completed(futures), total=len(futures), desc="Fetching"):
            doc_id, image_b64 = future.result()
            if image_b64:
                doc_images[doc_id] = image_b64
    timing_stats["fetch_images"] = time.time() - fetch_images_start

    if not doc_images:
        print("No images found!")
        return

    # Generate embeddings
    generate_start = time.time()
    doc_id_list = list(doc_images.keys())
    all_updates = []

    print("\nGenerating ColQwen3 embeddings...")
    for batch_start in tqdm(range(0, len(doc_id_list), args.batch_size), desc="GPU batches"):
        batch_end = min(batch_start + args.batch_size, len(doc_id_list))
        batch_doc_ids = doc_id_list[batch_start:batch_end]

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
                print(f"Error decoding {doc_id}: {e}")

        if batch_images:
            embeddings = generate_batch_embeddings(model, processor, batch_images, args.device)
            for doc_id, embedding in zip(valid_doc_ids, embeddings):
                all_updates.append((doc_id, embedding))

    timing_stats["generate_embeddings"] = time.time() - generate_start

    # Update Vespa
    update_start = time.time()
    print(f"\nUpdating {len(all_updates)} documents in Vespa...")
    success_count = 0
    error_count = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(update_single_document, vespa, doc_id, embedding): doc_id
            for doc_id, embedding in all_updates
        }
        for future in tqdm(as_completed(futures), total=len(futures), desc="Updating"):
            doc_id, success = future.result()
            if success:
                success_count += 1
            else:
                error_count += 1

    timing_stats["update_vespa"] = time.time() - update_start

    total_time = time.time() - total_start_time

    # Print statistics
    print("\n" + "=" * 60)
    print("REINGEST STATISTICS")
    print("=" * 60)
    print(f"\nFile filter:         '{args.title}'")
    print(f"Total pages:         {num_pages}")
    print(f"Successfully updated: {success_count}")
    print(f"Errors:              {error_count}")
    print("\n--- TIMING BREAKDOWN ---")
    print(f"Model loading:       {timing_stats['model_load']:.2f}s")
    print(f"Fetch document IDs:  {timing_stats['fetch_ids']:.2f}s")
    print(f"Fetch images:        {timing_stats['fetch_images']:.2f}s")
    print(f"Generate embeddings: {timing_stats['generate_embeddings']:.2f}s")
    print(f"Update Vespa:        {timing_stats['update_vespa']:.2f}s")
    print("\n--- SUMMARY ---")
    print(f"Total time:          {total_time:.2f}s")
    processing_time = timing_stats['generate_embeddings'] + timing_stats['update_vespa']
    print(f"Processing time:     {processing_time:.2f}s (embedding + update)")
    if num_pages > 0:
        print(f"Time per page:       {total_time / num_pages:.2f}s (total)")
        print(f"Time per page:       {processing_time / num_pages:.2f}s (processing only)")
        print(f"Pages per second:    {num_pages / total_time:.2f} (total)")
        print(f"Pages per second:    {num_pages / processing_time:.2f} (processing only)")
    print("=" * 60)


if __name__ == "__main__":
    main()
