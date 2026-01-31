"""
Model registry and configuration.

Provides model definitions loaded from ki55.toml.
"""

from backend.core.models.config import (
    ModelConfig,
    MODELS,
    get_model_config,
    get_available_models,
)

__all__ = [
    "ModelConfig",
    "MODELS",
    "get_model_config",
    "get_available_models",
]
