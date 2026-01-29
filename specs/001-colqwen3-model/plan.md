# Implementation Plan: Add ColQwen3 Model Support

> **Note**: This spec was written for an earlier architecture. The application now uses Starlette (JSON API) + Next.js (frontend). The model support implementation is complete and still valid.

**Branch**: `001-colqwen3-model` | **Date**: 2026-01-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-colqwen3-model/spec.md`

## Summary

Add TomoroAI/tomoro-colqwen3-embed-4b as an alternative embedding model for visual document retrieval. The implementation enables users to select between ColPali (current) and ColQwen3 (new) models via the search UI. Models are swapped on GPU as needed due to memory constraints. This is for evaluation purposes only - no automatic fallback on failures.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Starlette, transformers, torch, colpali-engine, pyvespa
**Storage**: Vespa (document storage), filesystem (cached images/sim maps)
**Testing**: Manual testing (no existing test framework in codebase)
**Target Platform**: Linux server with CUDA GPU
**Project Type**: Web application (Starlette backend + Next.js frontend)
**Performance Goals**: Model swap < 30 seconds, search latency within 20% of ColPali
**Constraints**: Single GPU, one model loaded at a time, 8GB+ VRAM recommended
**Scale/Scope**: Evaluation use case, single user at a time

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Constitution file contains template placeholders only (no specific rules defined). Gate passes by default.

**Post-Design Re-check**: Pass - implementation follows existing codebase patterns.

## Project Structure

### Documentation (this feature)

```text
specs/001-colqwen3-model/
├── plan.md              # This file
├── research.md          # Phase 0 output - model research & decisions
├── data-model.md        # Phase 1 output - entity definitions
├── quickstart.md        # Phase 1 output - setup & usage guide
├── contracts/           # Phase 1 output - API contracts
│   └── api.md           # HTTP endpoint specifications
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
backend/
├── colpali.py           # MODIFY: Add model abstraction, ColQwen3 loading, GPU swap
├── vespa_app.py         # MODIFY: Pass model parameter through query flow
└── models/              # NEW: Model configuration and registry (optional)
    └── config.py        # NEW: ModelConfig dataclass definitions

frontend/
└── app.py               # MODIFY: Add model selection RadioGroup to SearchBox

main.py                  # MODIFY: Add model endpoints, model state management
```

**Structure Decision**: Follows existing web application structure. Backend handles model loading and search. Frontend handles UI. Main.py orchestrates startup and routing.

## Key Implementation Components

### 1. Model Configuration (backend/models/config.py - optional)

```python
@dataclass
class ModelConfig:
    id: str
    name: str
    hf_model_id: str
    embedding_dim: int
    max_visual_tokens: int
    description: str
    requires_flash_attention: bool = False

MODELS = {
    "colpali": ModelConfig(...),
    "colqwen3": ModelConfig(...)
}
```

### 2. Model Manager (backend/colpali.py)

Extend `SimMapGenerator` to support:
- Model selection on initialization
- `switch_model(model_id)` method with GPU cleanup
- Abstracted embedding generation for both model types

### 3. Frontend Model Selector (frontend/app.py)

Add RadioGroup in `SearchBox()`:
```python
RadioGroup(
    RadioGroupItem(value="colpali", id="colpali-model"),
    RadioGroupItem(value="colqwen3", id="colqwen3-model"),
    name="model",
    default_value="colpali"
)
```

### 4. API Changes (main.py)

- Add `model` query parameter to `/search` and `/fetch_results`
- Add `GET /switch_model?model=X` endpoint
- Add `GET /model_status` endpoint
- Handle model swap before query processing

## Complexity Tracking

No constitution violations - implementation follows existing patterns.

## Related Artifacts

- [research.md](./research.md) - Technical research and decisions
- [data-model.md](./data-model.md) - Entity definitions
- [contracts/api.md](./contracts/api.md) - API specifications
- [quickstart.md](./quickstart.md) - Setup and usage guide
