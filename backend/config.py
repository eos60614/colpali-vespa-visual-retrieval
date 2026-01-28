"""
Centralized configuration loader.

Loads non-sensitive config from ki55.toml (required, no fallback defaults).
Sensitive values come from .env via os.environ (also no fallback defaults).
"""

import os
import tomllib
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_CONFIG_PATH = Path(
    os.environ.get("KI55_CONFIG_PATH", Path(__file__).parent.parent / "ki55.toml")
)

if not _CONFIG_PATH.exists():
    raise RuntimeError(f"Configuration file not found: {_CONFIG_PATH}")

with open(_CONFIG_PATH, "rb") as _f:
    _CONFIG = tomllib.load(_f)


def get(*keys: str) -> Any:
    """Traverse nested TOML config by dotted keys.

    Example: get("vespa", "schema_name") -> "pdf_page"
    Raises RuntimeError if any key is missing.
    """
    current = _CONFIG
    path = ".".join(keys)
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            raise RuntimeError(
                f"Missing required config key '{path}' in ki55.toml"
            )
        current = current[key]
    return current


def require_env(name: str) -> str:
    """Get a required environment variable. Raises RuntimeError if missing or empty."""
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"Required environment variable '{name}' is not set. "
            f"Add it to your .env file."
        )
    return value


def get_env(name: str) -> str | None:
    """Get an optional environment variable (returns None if not set)."""
    return os.environ.get(name)
