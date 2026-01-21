# Research: Add ColQwen3 Model Support

**Branch**: `001-colqwen3-model` | **Date**: 2026-01-14

## Research Summary

This document consolidates research findings for integrating the TomoroAI/tomoro-colqwen3-embed-4b model into the ColPali-Vespa visual retrieval system.

---

## 1. ColQwen3 Model Architecture & Requirements

### Decision: Use transformers AutoModel/AutoProcessor for ColQwen3

**Rationale**: ColQwen3 uses a different architecture than ColPali and requires the generic `transformers` API rather than the `colpali-engine` library.

**Key Differences from ColPali**:

| Aspect | ColPali (vidore/colpali-v1.2) | ColQwen3 (TomoroAI/tomoro-colqwen3-embed-4b) |
|--------|------------------------------|---------------------------------------------|
| Library | `colpali_engine.models` | `transformers.AutoModel/AutoProcessor` |
| Embedding Dim | 128 | 320 |
| Model Class | `ColPali`, `ColPaliProcessor` | `AutoModel`, `AutoProcessor` with `trust_remote_code=True` |
| Attention | Standard | FlashAttention 2 recommended |
| Precision | bfloat16 | bfloat16 |
| Max Visual Tokens | 1024 | 1280 (images), 5120 (video) |
| Query Processing | `processor.process_queries()` | `processor.process_texts()` |
| Image Processing | `processor.process_images()` | `processor.process_images()` |
| Scoring | MaxSim via colpali_engine | `processor.score_multi_vector()` |

**Alternatives Considered**:
- Using colpali-engine for both: Not possible, ColQwen3 requires custom model code from HuggingFace

### ColQwen3 Loading Code Pattern

```python
from transformers import AutoModel, AutoProcessor
import torch

MODEL_ID = "TomoroAI/tomoro-colqwen3-embed-4b"
processor = AutoProcessor.from_pretrained(
    MODEL_ID,
    trust_remote_code=True,
    max_num_visual_tokens=1280
)
model = AutoModel.from_pretrained(
    MODEL_ID,
    torch_dtype=torch.bfloat16,
    attn_implementation="flash_attention_2",
    trust_remote_code=True,
    device_map="cuda"
).eval()
```

---

## 2. GPU Memory Management Strategy

### Decision: Implement model swapping with explicit GPU memory cleanup

**Rationale**: Single GPU constraint requires loading only one model at a time. Model swap must explicitly free CUDA memory.

**Implementation Pattern**:
```python
def unload_current_model(self):
    if self.model is not None:
        del self.model
        del self.processor
        self.model = None
        self.processor = None
        torch.cuda.empty_cache()
        gc.collect()
```

**Alternatives Considered**:
- Running both models simultaneously: Rejected due to GPU memory constraints
- CPU fallback: Rejected due to performance impact on search latency

---

## 3. Embedding Compatibility with Vespa

### Decision: ColQwen3's 320-dim embeddings require Vespa schema consideration

**Rationale**: The current Vespa schema is configured for ColPali's 128-dim embeddings. ColQwen3 produces 320-dim embeddings.

**Current Schema** (`vespa-app/schemas/pdf_page.sd`):
- Binary embedding: `tensor<int8>(patch{}, v[16])` (128 bits = 16 bytes)
- Float embedding for query: dimension 128

**Impact Analysis**:
- For **query-side only** (this feature scope): The query embeddings dimension change affects the `input.query(qt)` tensor passed to Vespa
- Binary quantization: 320 dims → 40 bytes (vs 16 bytes for ColPali)
- MaxSim calculations remain compatible since they use dot product

**Recommendation**:
- Focus on query-side integration first
- Document that full ColQwen3 support (including indexing) would require schema updates and re-indexing

---

## 4. API Integration Points

### Decision: Extend SimMapGenerator with model selection

**Current Code Structure** (`backend/colpali.py`):
```python
class SimMapGenerator:
    def __init__(self, logger, model_name="vidore/colpali-v1.2", n_patch=32):
        self.model, self.processor = self.load_model()

    def load_model(self):
        model = ColPali.from_pretrained(...)
        processor = ColPaliProcessor.from_pretrained(...)
        return model, processor
```

**Required Changes**:
1. Add model selection parameter to `__init__`
2. Add `load_colqwen3_model()` method
3. Add `switch_model()` method for GPU swap
4. Abstract embedding generation to handle both model types

---

## 5. Frontend Integration

### Decision: Add model selector as separate UI element from ranking

**Current UI** (`frontend/app.py`):
- RadioGroup for ranking: colpali, bm25, hybrid
- No model selection

**Recommended UI Addition**:
- Add a new RadioGroup or Select for model: "ColPali", "ColQwen3"
- Place above or alongside ranking selection
- Add tooltip with model descriptions

**Form Parameter Flow**:
```
SearchBox → /search?query=X&ranking=Y&model=Z → /fetch_results
```

---

## 6. Backend API Changes

### Decision: Add model parameter to search endpoints

**Current Endpoints**:
- `GET /search?query=X&ranking=Y`
- `GET /fetch_results?query=X&ranking=Y`

**Updated Endpoints**:
- `GET /search?query=X&ranking=Y&model=colpali|colqwen3`
- `GET /fetch_results?query=X&ranking=Y&model=colpali|colqwen3`

**Startup Behavior**:
- Load default model (ColPali) on startup
- Switch model on-demand when different model requested

---

## 7. Error Handling

### Decision: Display user-facing error on model load failure

**Rationale**: Per spec, this is for evaluation purposes only - no automatic fallback required.

**Error Scenarios**:
1. Model download failure → Display "Failed to load ColQwen3 model: [error]"
2. GPU OOM during swap → Display "Insufficient GPU memory to load model"
3. FlashAttention not available → Display warning, attempt without FA2

---

## 8. Dependencies

### Decision: Minimal dependency changes

**Current** (`requirements.txt`):
- `transformers==4.45.0` - Already present, sufficient for AutoModel
- `torch==2.8.0` - Already present
- `flash-attn` - May need to add for optimal ColQwen3 performance

**Potential Addition**:
```
flash-attn>=2.0.0  # Optional, for ColQwen3 performance
```

**Note**: flash-attn requires CUDA and specific torch version compatibility

---

## Summary of Decisions

| Topic | Decision | Impact |
|-------|----------|--------|
| Model Loading | Use transformers AutoModel/AutoProcessor | New load method needed |
| GPU Management | Swap models with explicit memory cleanup | Add unload/load cycle |
| Vespa Integration | Query-side only for this feature | No schema changes |
| Frontend | Add model selector RadioGroup | New UI element |
| Backend | Add model parameter to endpoints | API change |
| Error Handling | User-facing error messages | No fallback |
| Dependencies | Minimal (flash-attn optional) | Low risk |
