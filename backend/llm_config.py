"""
LLM provider configuration for OpenAI-compatible APIs.

Resolves provider (OpenRouter, OpenAI, or local Ollama) from environment
variables and provides helpers used by both the chat endpoint and agent.
"""

import os


def resolve_llm_config() -> tuple[str, str]:
    """Resolve LLM base URL and API key from environment variables.

    Priority:
        1. Explicit LLM_BASE_URL with available API key
        2. OpenAI direct (when OPENAI_API_KEY set without OPENROUTER_API_KEY)
        3. OpenRouter (default)
        4. Local Ollama (set LLM_BASE_URL=http://localhost:11434/v1)
    """
    explicit_base = os.getenv("LLM_BASE_URL")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openai_key = os.getenv("OPENAI_API_KEY")

    if explicit_base:
        base_url = explicit_base
    elif openai_key and not openrouter_key:
        base_url = "https://api.openai.com/v1"
    else:
        base_url = "https://openrouter.ai/api/v1"

    api_key = openrouter_key or openai_key or ""
    return base_url, api_key


def get_chat_model() -> str:
    """Return the configured chat model name."""
    return os.getenv("CHAT_MODEL", "google/gemini-2.5-flash")


def is_remote_api(base_url: str) -> bool:
    """Check whether the base URL points to a remote (non-local) API."""
    return "openrouter.ai" in base_url or "openai.com" in base_url


def build_auth_headers(api_key: str) -> dict[str, str]:
    """Build HTTP headers for an OpenAI-compatible API request."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers
