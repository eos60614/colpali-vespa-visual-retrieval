from dataclasses import dataclass
from typing import Dict


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


# Model registry with predefined configurations
MODELS: Dict[str, ModelConfig] = {
    "colpali": ModelConfig(
        id="colpali",
        name="ColPali",
        hf_model_id="vidore/colpali-v1.2",
        embedding_dim=128,
        max_visual_tokens=1024,
        description="Original ColPali model, good general performance",
        requires_flash_attention=False,
    ),
    "colqwen3": ModelConfig(
        id="colqwen3",
        name="ColQwen2.5",
        hf_model_id="tsystems/colqwen2.5-3b-multilingual-v1.0",
        embedding_dim=128,
        max_visual_tokens=768,
        description="Better multilingual support, improved chart/table understanding",
        requires_flash_attention=False,
    ),
}


def get_model_config(model_id: str) -> ModelConfig:
    """Get model configuration by ID."""
    if model_id not in MODELS:
        raise ValueError(f"Unknown model: {model_id}. Available models: {list(MODELS.keys())}")
    return MODELS[model_id]


def get_available_models() -> Dict[str, ModelConfig]:
    """Get all available model configurations."""
    return MODELS
