"""
Model registry configuration.

Loads model definitions from ki55.toml [colpali.models.*] sections.
"""

from dataclasses import dataclass
from typing import Dict

from backend.core.config import get


@dataclass
class ModelConfig:
    """Configuration for a supported embedding model."""

    id: str
    name: str
    hf_model_id: str
    embedding_dim: int
    max_visual_tokens: int
    description: str
    requires_flash_attention: bool = False


def _load_models_from_config() -> Dict[str, ModelConfig]:
    """Load model registry from ki55.toml [colpali.models.*] sections."""
    models = {}
    models_config = get("colpali", "models")
    for model_key, model_data in models_config.items():
        models[model_key] = ModelConfig(
            id=model_data["id"],
            name=model_data["name"],
            hf_model_id=model_data["hf_model_id"],
            embedding_dim=model_data["embedding_dim"],
            max_visual_tokens=model_data["max_visual_tokens"],
            description=model_data["description"],
            requires_flash_attention=model_data.get("requires_flash_attention", False),
        )
    return models


MODELS: Dict[str, ModelConfig] = _load_models_from_config()


def get_model_config(model_id: str) -> ModelConfig:
    """Get model configuration by ID."""
    if model_id not in MODELS:
        raise ValueError(f"Unknown model: {model_id}. Available models: {list(MODELS.keys())}")
    return MODELS[model_id]


def get_available_models() -> Dict[str, ModelConfig]:
    """Get all available model configurations."""
    return MODELS
