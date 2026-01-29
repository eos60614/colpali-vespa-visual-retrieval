"""
LLM-based reranking for search results.

Uses the configured LLM (via OpenAI-compatible API) to semantically rerank
search results based on query relevance. Runs as an optional stage after the
existing MaxSim embedding reranking.

The MaxSim reranker is fast and uses embedding similarity. This LLM reranker
adds a slower but more semantically rich cross-encoder-style scoring pass,
where the LLM jointly reads the query and document content to judge relevance.

Enable via llm.llm_rerank_enabled in ki55.toml (default: disabled).
"""

import json
from typing import Any

import httpx

from backend.config import get
from backend.logging_config import get_logger
from backend.llm_config import (
    build_auth_headers,
    get_chat_model,
    is_remote_api,
    resolve_llm_config,
)

logger = get_logger(__name__)

LLM_RERANK_SYSTEM_PROMPT = """You are a document relevance scorer. Given a user query and a list of document results (with title, page number, snippet, and text), score each document's relevance to the query on a scale of 0 to 10.

Return a JSON array of objects with "index" (the original result index) and "score" (relevance score 0-10).

Example output:
[{"index": 0, "score": 9}, {"index": 1, "score": 3}, {"index": 2, "score": 7}]

Scoring guidelines:
- 10: Perfect match, directly answers the query
- 7-9: Highly relevant, contains substantial related information
- 4-6: Somewhat relevant, tangentially related
- 1-3: Low relevance, barely related
- 0: Completely irrelevant

Only output the JSON array, nothing else."""


def is_llm_rerank_enabled() -> bool:
    """Check if LLM reranking is enabled via ki55.toml config."""
    return get("llm", "llm_rerank_enabled")


def get_llm_rerank_candidates() -> int:
    """Get number of candidates to send to LLM for reranking."""
    return get("llm", "llm_rerank_candidates")


async def llm_rerank_results(
    query: str,
    results: list[dict[str, Any]],
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """
    Rerank search results using an LLM for semantic relevance scoring.

    Sends the query and result metadata (title, snippet, text) to the LLM,
    which scores each result on a 0-10 relevance scale. Results are re-sorted
    by LLM score.

    Falls back to original ordering if the LLM call fails or response
    cannot be parsed.

    Args:
        query: The user's search query.
        results: List of Vespa result dicts (each with a "fields" key).
        top_k: If set, return only the top K results after reranking.

    Returns:
        Reranked list of results with 'llm_rerank_score' added to fields.
    """
    if not results:
        return results

    base_url, api_key = resolve_llm_config()
    chat_model = get_chat_model()

    if is_remote_api(base_url) and not api_key:
        logger.warning("LLM reranking skipped: no API key configured")
        return results

    # Build document summaries for the LLM
    snippet_length = get("image", "truncation", "snippet_length")
    text_length = get("image", "truncation", "text_length")

    doc_summaries = []
    for i, result in enumerate(results):
        fields = result.get("fields", {})
        doc_summaries.append(
            {
                "index": i,
                "title": fields.get("title", "Unknown"),
                "page_number": (fields.get("page_number") or 0) + 1,
                "snippet": (fields.get("snippet", "") or "")[:snippet_length],
                "text": (fields.get("text", "") or "")[:text_length],
            }
        )

    user_message = (
        f"Query: {query}\n\nDocuments:\n{json.dumps(doc_summaries, indent=2)}"
    )

    headers = build_auth_headers(api_key)

    try:
        async with httpx.AsyncClient(timeout=get("llm", "http_timeout_seconds")) as client:
            resp = await client.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json={
                    "model": chat_model,
                    "messages": [
                        {"role": "system", "content": LLM_RERANK_SYSTEM_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    "temperature": 0.0,
                },
            )
            resp.raise_for_status()
            response_data = resp.json()

        content = response_data["choices"][0]["message"].get("content", "")
        scores = _parse_scores(content, len(results))

        if scores is None:
            logger.warning(
                "LLM reranking: failed to parse scores, keeping original order"
            )
            return results

        # Apply LLM scores and re-sort
        scored_results = []
        for i, result in enumerate(results):
            result_copy = result.copy()
            result_copy["fields"] = result["fields"].copy()
            llm_score = scores.get(i, 0.0)
            result_copy["fields"]["llm_rerank_score"] = llm_score
            result_copy["fields"]["maxsim_relevance"] = result.get("relevance", 0.0)
            scored_results.append((llm_score, i, result_copy))

        # Sort by LLM score descending, break ties by original position
        scored_results.sort(key=lambda x: (-x[0], x[1]))
        reranked = [r for _, _, r in scored_results]

        if top_k is not None:
            reranked = reranked[:top_k]

        logger.info(
            f"LLM reranking complete: reordered {len(reranked)} results "
            f"(scores: {[s[0] for s in scored_results[:len(reranked)]]})"
        )
        return reranked

    except httpx.HTTPStatusError as e:
        logger.error(
            f"LLM reranking HTTP error: {e.response.status_code} - "
            f"{e.response.text[:200]}"
        )
        return results
    except Exception as e:
        logger.error(f"LLM reranking failed: {e}")
        return results


def _parse_scores(content: str, num_results: int) -> dict[int, float] | None:
    """Parse LLM response into a mapping of result index to score.

    Handles both clean JSON and JSON wrapped in markdown code blocks.
    """
    content = content.strip()
    if content.startswith("```"):
        lines = content.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        content = "\n".join(lines).strip()

    try:
        parsed = json.loads(content)
        if not isinstance(parsed, list):
            return None

        scores = {}
        for item in parsed:
            idx = int(item.get("index", -1))
            score = float(item.get("score", 0))
            if 0 <= idx < num_results:
                scores[idx] = score
        return scores
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
