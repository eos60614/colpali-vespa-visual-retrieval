"""
Application-level MaxSim reranking for multivector embeddings.

This module provides reranking functionality using full-precision MaxSim computation
after retrieving candidate documents from Vespa.
"""

import numpy as np
import torch
from typing import List, Dict, Any, Tuple

from backend.core.config import get

EMBEDDING_DIM = get("colpali", "embedding_dim")


def parse_float_embedding(float_cells: Dict) -> np.ndarray:
    """
    Parse Vespa's float embedding format to numpy array.

    Vespa stores float embeddings as tensor<float>(patch{}, v[128]) where each patch
    has 128 float values.

    Args:
        float_cells: Vespa embedding format with "blocks" containing
                    patch-indexed float arrays, e.g.:
                    {"blocks": {"0": [0.1, -0.2, ...], "1": [...], ...}}

    Returns:
        np.ndarray: Embeddings of shape (num_patches, 128)
    """
    blocks = float_cells.get("blocks", {})
    if not blocks:
        return np.array([])

    # Sort patches by index
    patch_indices = sorted([int(k) for k in blocks.keys()])
    num_patches = len(patch_indices)

    # Parse each patch's float embedding
    embeddings = np.zeros((num_patches, EMBEDDING_DIM), dtype=np.float32)

    for i, patch_idx in enumerate(patch_indices):
        embeddings[i] = np.array(blocks[str(patch_idx)], dtype=np.float32)

    return embeddings


def unpack_binary_embedding(binary_cells: Dict) -> np.ndarray:
    """
    Unpack Vespa's binary embedding format back to float values.

    Fallback for documents without float embeddings.

    Vespa stores embeddings as tensor<int8>(patch{}, v[16]) where each patch
    has 16 int8 values representing 128 binary bits (16 * 8 = 128).

    Args:
        binary_cells: Vespa embedding format with "blocks" containing
                     patch-indexed int8 arrays, e.g.:
                     {"blocks": {"0": [-1, 2, ...], "1": [...], ...}}

    Returns:
        np.ndarray: Unpacked embeddings of shape (num_patches, 128) with values -1 or +1
    """
    blocks = binary_cells.get("blocks", {})
    if not blocks:
        return np.array([])

    # Sort patches by index
    patch_indices = sorted([int(k) for k in blocks.keys()])
    num_patches = len(patch_indices)

    # Unpack each patch's binary embedding
    unpacked = np.zeros((num_patches, EMBEDDING_DIM), dtype=np.float32)

    for i, patch_idx in enumerate(patch_indices):
        binary_int8 = np.array(blocks[str(patch_idx)], dtype=np.int8)
        # Convert int8 to uint8 for unpackbits
        binary_uint8 = binary_int8.view(np.uint8)
        # Unpack bits: each int8 becomes 8 bits
        bits = np.unpackbits(binary_uint8)
        # Convert 0/1 to -1/+1 for proper similarity computation
        unpacked[i] = bits.astype(np.float32) * 2 - 1

    return unpacked


def compute_max_sim(
    query_embs: torch.Tensor,
    doc_emb: np.ndarray,
) -> float:
    """
    Compute MaxSim score between query embeddings and document embeddings.

    MaxSim = sum over query tokens of: max over patches of: dot_product(q_token, patch)

    Args:
        query_embs: Query token embeddings, shape (num_query_tokens, 128)
        doc_emb: Document patch embeddings, shape (num_patches, 128)

    Returns:
        float: MaxSim score
    """
    if doc_emb.size == 0:
        return 0.0

    # Convert query embeddings to numpy if needed
    if isinstance(query_embs, torch.Tensor):
        q_emb = query_embs.cpu().numpy().astype(np.float32)
    else:
        q_emb = query_embs.astype(np.float32)

    # Compute similarity matrix: (num_query_tokens, num_patches)
    # Each entry is the dot product between a query token and a document patch
    similarities = np.matmul(q_emb, doc_emb.T)

    # MaxSim: for each query token, take max over patches, then sum over query tokens
    max_per_token = np.max(similarities, axis=1)
    max_sim_score = np.sum(max_per_token)

    return float(max_sim_score)


def rerank_results(
    query_embs: torch.Tensor,
    results: List[Dict[str, Any]],
    float_embedding_field: str = "embedding_float",
    binary_embedding_field: str = "embedding",
) -> List[Dict[str, Any]]:
    """
    Rerank search results using application-level MaxSim computation.

    Prefers float embeddings for maximum precision, falls back to binary
    embeddings if float embeddings are not available.

    Args:
        query_embs: Query token embeddings from ColPali processor
        results: List of Vespa result dictionaries, each containing 'fields'
                with embedding fields
        float_embedding_field: Name of the float embedding field (preferred)
        binary_embedding_field: Name of the binary embedding field (fallback)

    Returns:
        List of results sorted by MaxSim score (highest first), with
        'rerank_score' added to each result's fields
    """
    if not results:
        return results

    scored_results = []

    for result in results:
        fields = result.get("fields", {})

        # Prefer float embeddings for maximum precision
        float_embedding = fields.get(float_embedding_field)
        binary_embedding = fields.get(binary_embedding_field)

        if float_embedding is not None:
            # Use full-precision float embeddings
            doc_emb = parse_float_embedding(float_embedding)
            score = compute_max_sim(query_embs, doc_emb)
        elif binary_embedding is not None:
            # Fallback to unpacked binary embeddings
            doc_emb = unpack_binary_embedding(binary_embedding)
            score = compute_max_sim(query_embs, doc_emb)
        else:
            # No embedding data, keep original relevance score
            score = result.get("relevance", 0.0)

        # Store the rerank score
        result_copy = result.copy()
        result_copy["fields"] = fields.copy()
        result_copy["fields"]["rerank_score"] = score
        result_copy["original_relevance"] = result.get("relevance", 0.0)
        result_copy["relevance"] = score

        scored_results.append((score, result_copy))

    # Sort by score descending
    scored_results.sort(key=lambda x: x[0], reverse=True)

    return [r for _, r in scored_results]


def rerank_with_processor(
    processor,
    query: str,
    results: List[Dict[str, Any]],
    embedding_field: str = "embedding",
) -> Tuple[List[Dict[str, Any]], torch.Tensor]:
    """
    Convenience function to rerank results using just the processor.

    This generates query embeddings using the processor and then reranks.

    Args:
        processor: ColPali processor instance
        query: Query string
        results: List of Vespa result dictionaries
        embedding_field: Name of the embedding field in results

    Returns:
        Tuple of (reranked results, query embeddings)
    """
    # The processor output contains input_ids which can be used for tokenization
    # but we need the model to generate actual embeddings
    # This function assumes embeddings are passed separately
    raise NotImplementedError(
        "rerank_with_processor requires model inference. "
        "Use rerank_results() with pre-computed query embeddings instead."
    )
