"""
Ranking module.

Provides reranking functionality:
- MaxSim reranking (maxsim.py) - Fast embedding-based reranking
- LLM reranking (llm.py) - Semantic cross-encoder reranking via LLM
"""

from backend.query.ranking.maxsim import (
    rerank_results,
    compute_max_sim,
    parse_float_embedding,
    unpack_binary_embedding,
)
from backend.query.ranking.llm import (
    llm_rerank_results,
    is_llm_rerank_enabled,
    get_llm_rerank_candidates,
)

__all__ = [
    "rerank_results",
    "compute_max_sim",
    "parse_float_embedding",
    "unpack_binary_embedding",
    "llm_rerank_results",
    "is_llm_rerank_enabled",
    "get_llm_rerank_candidates",
]
