# Implementation Plan: Three-Domain Architecture

## Phase 1: Core Infrastructure (Low Risk)

### Tasks
1. Create `backend/core/` directory
2. Move `backend/config.py` → `backend/core/config.py`
3. Move `backend/logging_config.py` → `backend/core/logging_config.py`
4. Move `backend/middleware.py` → `backend/core/middleware.py`
5. Move `backend/cache.py` → `backend/core/cache.py`
6. Move `backend/models/` → `backend/core/models/`
7. Create `backend/core/__init__.py` with re-exports
8. Add backward-compatible re-exports in `backend/` root
9. Update all imports across codebase
10. Run tests to verify

### Files Affected
- `main.py`
- All `backend/*.py` files
- All `scripts/*.py` files
- All `tests/*.py` files

---

## Phase 2: Connectors Domain (Medium Risk)

### Tasks
1. Create `backend/connectors/` directory structure
2. Create `backend/connectors/vespa/client.py`:
   - Extract connection logic from `vespa_app.py`
   - Class: `VespaConnection` (connection management only)
3. Create `backend/connectors/vespa/tensors.py`:
   - Extract tensor conversion functions from `vespa_app.py`
4. Move `backend/llm_config.py` → `backend/connectors/llm/config.py`
5. Create `backend/connectors/llm/client.py`:
   - Wrapper for httpx OpenAI-compatible calls
   - Used by `agent.py`, `llm_rerank.py`, `drawing_regions.py`
6. Move `backend/s3.py` → `backend/connectors/storage/s3.py`
7. Extract PostgreSQL connection from `backend/ingestion/db_connection.py` → `backend/connectors/database/postgres.py`
8. Create `backend/connectors/__init__.py` with public API
9. Add backward-compatible re-exports
10. Update imports and run tests

### Dependency Graph for Vespa Split
```
vespa_app.py
├── Connection Management → connectors/vespa/client.py
│   ├── __init__() with connection modes
│   ├── keepalive()
│   └── get_app() → returns Vespa instance
├── Tensor Conversions → connectors/vespa/tensors.py
│   ├── format_binary_embedding()
│   ├── format_float_embedding()
│   └── parse_*_embedding()
└── Query Methods → query/search/dispatcher.py (Phase 4)
    ├── query_vespa_*()
    ├── get_result_from_query()
    └── results_to_search_results()
```

---

## Phase 3: Ingestion Domain (Medium Risk)

### Tasks
1. Create `backend/ingestion/` directory structure
2. Create `backend/ingestion/pdf/`:
   - `processor.py` - Main ingestion pipeline from `ingest.py`
   - `validator.py` - `validate_pdf()` function
   - `renderer.py` - `render_page()`, `create_blur_image()`
3. Create `backend/ingestion/embeddings/`:
   - `generator.py` - Embedding generation from `colpali.py`
   - `packing.py` - Binary packing utilities from `ingest.py`
4. Create `backend/ingestion/regions/`:
   - `detector.py` - Main detection from `drawing_regions.py`
   - `strategies.py` - Heuristic, VLM, tiling strategies
5. Reorganize `backend/ingestion/` database modules:
   - Rename to `backend/ingestion/database/`
   - Keep existing structure, update imports
6. Move `backend/ingest.py` content to new locations
7. Move `backend/drawing_regions.py` content to new locations
8. Delete old files after migration
9. Update imports and run tests

### ColPali Split Strategy
```
colpali.py (current)
├── Model Loading (shared)
│   └── → core/models/colpali.py (singleton loader)
├── Embedding Generation
│   ├── process_images()
│   ├── get_image_embeddings()
│   └── → ingestion/embeddings/generator.py
└── Similarity Maps
    ├── get_sim_maps()
    ├── get_query_embeddings()
    ├── generate_sim_map_image()
    └── → query/similarity/generator.py
```

---

## Phase 4: Query Domain (Medium-High Risk)

### Tasks
1. Create `backend/query/` directory structure
2. Create `backend/query/search/`:
   - `dispatcher.py` - Query execution from `vespa_app.py`
   - `bm25.py` - BM25 query building
   - `colpali.py` - ColPali query building
   - `hybrid.py` - Hybrid ranking logic
3. Create `backend/query/ranking/`:
   - `maxsim.py` - From `rerank.py`
   - `llm.py` - From `llm_rerank.py`
4. Create `backend/query/similarity/`:
   - `generator.py` - SimMap generation from `colpali.py`
   - `cache.py` - SimMap caching logic
5. Create `backend/query/agent/`:
   - `session.py` - AgentSession from `agent.py`
   - `tools.py` - Tool definitions
6. Move `backend/stopwords.py` → `backend/query/text/stopwords.py`
7. Create `backend/query/results.py` - Result transformation
8. Delete old files after migration
9. Update imports and run tests

### VespaQueryClient Split
```
VespaQueryClient (current)
├── Connection (→ connectors/vespa/client.py)
│   ├── __init__() - connection setup
│   ├── keepalive() - health check
│   └── app property - Vespa instance
├── Query Dispatch (→ query/search/dispatcher.py)
│   ├── get_result_from_query()
│   ├── query_vespa_colpali()
│   ├── query_vespa_bm25()
│   └── query_vespa_hybrid()
├── Results (→ query/results.py)
│   └── results_to_search_results()
└── SimMaps (→ query/similarity/)
    ├── get_sim_maps_from_query()
    └── → query/similarity/generator.py
```

---

## Phase 5: Final Integration (Low Risk)

### Tasks
1. Update `main.py` imports to use new structure
2. Update all `scripts/*.py` imports
3. Update all `tests/*.py` imports
4. Remove backward-compatibility re-exports
5. Update `CLAUDE.md` with new architecture
6. Run full test suite
7. Manual testing of all API endpoints

---

## Risk Mitigation

### During Migration
- Run tests after each file move
- Keep backward-compatible imports during transition
- Use feature branch for entire migration
- Review import changes carefully

### Rollback Strategy
- Each phase is independently revertible
- Git history preserved for all moves
- Old import paths work during transition

---

## Estimated Effort

| Phase | Complexity | Files Changed |
|-------|------------|---------------|
| Phase 1: Core | Low | ~15 |
| Phase 2: Connectors | Medium | ~20 |
| Phase 3: Ingestion | Medium | ~15 |
| Phase 4: Query | Medium-High | ~20 |
| Phase 5: Integration | Low | ~25 |

---

## Testing Checklist

### Unit Tests
- [ ] All existing unit tests pass
- [ ] Import paths work correctly
- [ ] No circular import issues

### Integration Tests
- [ ] PDF upload works
- [ ] Search (BM25, ColPali, hybrid) works
- [ ] Similarity maps generate correctly
- [ ] Agent mode functions
- [ ] LLM chat streaming works

### Manual Tests
- [ ] Frontend search flow
- [ ] PDF upload from UI
- [ ] Chat sidebar
- [ ] Similarity map viewer
