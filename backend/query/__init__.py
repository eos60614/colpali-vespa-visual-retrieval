"""
Query domain module.

Provides search, ranking, and agent capabilities:
- ranking/ - MaxSim and LLM reranking
- agent/ - Multi-step reasoning agent
- text/ - Text processing utilities
- similarity/ - Similarity map generation (uses backend/colpali.py)
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
from backend.query.agent.session import AgentSession
from backend.query.text.stopwords import filter as filter_stopwords

__all__ = [
    # Ranking
    "rerank_results",
    "compute_max_sim",
    "parse_float_embedding",
    "unpack_binary_embedding",
    "llm_rerank_results",
    "is_llm_rerank_enabled",
    "get_llm_rerank_candidates",
    # Agent
    "AgentSession",
    # Text
    "filter_stopwords",
]
