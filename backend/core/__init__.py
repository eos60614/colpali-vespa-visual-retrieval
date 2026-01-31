"""
Core infrastructure shared across all backend domains.

This module provides:
- Configuration loading (config.py)
- Centralized logging (logging_config.py)
- ASGI middleware (middleware.py)
- Caching utilities (cache.py)
- Model registry (models/)
"""

from backend.core.config import get, get_env, require_env
from backend.core.logging_config import (
    configure_logging,
    get_logger,
    get_correlation_id,
    set_correlation_id,
    generate_correlation_id,
    is_production,
    is_development,
    CORRELATION_HEADER,
)
from backend.core.middleware import CorrelationIdMiddleware, ErrorBoundaryMiddleware
from backend.core.cache import LRUCache

__all__ = [
    # config
    "get",
    "get_env",
    "require_env",
    # logging
    "configure_logging",
    "get_logger",
    "get_correlation_id",
    "set_correlation_id",
    "generate_correlation_id",
    "is_production",
    "is_development",
    "CORRELATION_HEADER",
    # middleware
    "CorrelationIdMiddleware",
    "ErrorBoundaryMiddleware",
    # cache
    "LRUCache",
]
