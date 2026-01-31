"""
LLM provider connector.

Provides configuration and client utilities for OpenAI-compatible LLM APIs.
"""

from backend.connectors.llm.config import (
    resolve_llm_config,
    get_chat_model,
    is_remote_api,
    build_auth_headers,
)

__all__ = [
    "resolve_llm_config",
    "get_chat_model",
    "is_remote_api",
    "build_auth_headers",
]
