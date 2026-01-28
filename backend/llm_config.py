"""
Centralized LLM configuration.

LLM_BASE_URL MUST be set in .env. No fallback URL logic.
API keys are also required from .env for remote providers.
"""

from backend.config import get, get_env, require_env


def resolve_llm_config() -> tuple[str, str]:
    """Resolve LLM base URL and API key.

    LLM_BASE_URL is required -- raises RuntimeError if not set.
    API key comes from OPENROUTER_API_KEY or OPENAI_API_KEY.

    Returns:
        (base_url, api_key)
    """
    base_url = require_env("LLM_BASE_URL")
    api_key = get_env("OPENROUTER_API_KEY") or get_env("OPENAI_API_KEY") or ""
    return base_url, api_key


def get_chat_model() -> str:
    """Get the chat model identifier from ki55.toml."""
    return get("llm", "chat_model")


def is_remote_api(base_url: str) -> bool:
    """Check if the base URL points to a remote (non-local) API."""
    return "openrouter.ai" in base_url or "openai.com" in base_url


def build_auth_headers(api_key: str) -> dict:
    """Build HTTP headers including auth if key is present."""
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers
