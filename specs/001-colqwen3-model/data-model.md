# Data Model: Add ColQwen3 Model Support

**Branch**: `001-colqwen3-model` | **Date**: 2026-01-14

## Entities

### ModelConfig

Represents the configuration for a supported embedding model.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `id` | string | Unique model identifier | Required, one of: `colpali`, `colqwen3` |
| `name` | string | Display name for UI | Required |
| `hf_model_id` | string | HuggingFace model ID | Required |
| `embedding_dim` | int | Output embedding dimension | Required, positive integer |
| `max_visual_tokens` | int | Maximum visual tokens per image | Required, positive integer |
| `description` | string | Brief description for UI tooltip | Optional |
| `requires_flash_attention` | bool | Whether FlashAttention 2 is recommended | Default: false |

**Predefined Instances**:

```
COLPALI = ModelConfig(
    id="colpali",
    name="ColPali",
    hf_model_id="vidore/colpali-v1.2",
    embedding_dim=128,
    max_visual_tokens=1024,
    description="Original ColPali model, good general performance",
    requires_flash_attention=False
)

COLQWEN3 = ModelConfig(
    id="colqwen3",
    name="ColQwen3",
    hf_model_id="TomoroAI/tomoro-colqwen3-embed-4b",
    embedding_dim=320,
    max_visual_tokens=1280,
    description="Better multilingual support, improved chart/table understanding",
    requires_flash_attention=True
)
```

---

### ModelState

Represents the runtime state of the model loading system.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `current_model_id` | string | ID of currently loaded model | One of supported model IDs |
| `model` | object | Loaded model instance | Runtime object, not persisted |
| `processor` | object | Loaded processor instance | Runtime object, not persisted |
| `is_loading` | bool | Whether a model is currently being loaded | Default: false |
| `last_error` | string | Most recent error message, if any | Optional |

**State Transitions**:

```
[Initial] --load_default--> [ColPali Loaded]
[ColPali Loaded] --switch_to_colqwen3--> [Loading] --success--> [ColQwen3 Loaded]
[ColPali Loaded] --switch_to_colqwen3--> [Loading] --failure--> [Error State]
[ColQwen3 Loaded] --switch_to_colpali--> [Loading] --success--> [ColPali Loaded]
[Error State] --retry--> [Loading]
```

---

### SearchRequest

Extended search request with model selection.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `query` | string | Search query text | Required, non-empty |
| `ranking` | string | Ranking method | One of: `colpali`, `bm25`, `hybrid` |
| `model` | string | Model to use for embeddings | One of: `colpali`, `colqwen3`. Default: `colpali` |

---

### SearchSession (Frontend State)

Represents the user's current search session state.

| Field | Type | Description | Constraints |
|-------|------|-------------|-------------|
| `query` | string | Current query value | May be empty |
| `ranking` | string | Selected ranking method | Default: `hybrid` |
| `model` | string | Selected model | Default: `colpali` |

**Persistence**: Session state persists within browser session, resets on page refresh.

---

## Relationships

```
SearchRequest
    └── uses → ModelConfig (via model field)

ModelState
    ├── has_loaded → ModelConfig (current_model_id)
    ├── contains → model instance
    └── contains → processor instance

SearchSession
    ├── specifies → ranking method
    └── specifies → model selection
```

---

## Validation Rules

1. **ModelConfig.id**: Must be unique, lowercase alphanumeric
2. **SearchRequest.model**: Must match a defined ModelConfig.id
3. **ModelState transitions**: Cannot switch models while `is_loading` is true
4. **GPU Memory**: Must unload current model before loading new model
