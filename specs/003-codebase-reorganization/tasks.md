# Tasks: Codebase Reorganization

## Phase 1: Core Infrastructure

- [ ] Create `backend/core/` directory
- [ ] Create `backend/core/__init__.py`
- [ ] Move `backend/config.py` → `backend/core/config.py`
- [ ] Move `backend/logging_config.py` → `backend/core/logging_config.py`
- [ ] Move `backend/middleware.py` → `backend/core/middleware.py`
- [ ] Move `backend/cache.py` → `backend/core/cache.py`
- [ ] Move `backend/models/` → `backend/core/models/`
- [ ] Update imports in `main.py`
- [ ] Update imports in `backend/*.py`
- [ ] Update imports in `scripts/*.py`
- [ ] Update imports in `tests/*.py`
- [ ] Add backward-compatible exports in `backend/__init__.py`
- [ ] Run `pytest -v -x tests/`
- [ ] Run `/lint`

## Phase 2: Connectors Domain

### Vespa Connector
- [ ] Create `backend/connectors/` directory structure
- [ ] Create `backend/connectors/__init__.py`
- [ ] Create `backend/connectors/vespa/__init__.py`
- [ ] Create `backend/connectors/vespa/client.py` with `VespaConnection` class
  - [ ] Extract connection initialization logic
  - [ ] Extract `keepalive()` method
  - [ ] Expose `app` property for Vespa instance
- [ ] Create `backend/connectors/vespa/tensors.py`
  - [ ] Move `format_binary_embedding()`
  - [ ] Move `format_float_embedding()`
  - [ ] Move tensor parsing utilities

### LLM Connector
- [ ] Create `backend/connectors/llm/__init__.py`
- [ ] Move `backend/llm_config.py` → `backend/connectors/llm/config.py`
- [ ] Create `backend/connectors/llm/client.py`
  - [ ] Create `LLMClient` class wrapping httpx
  - [ ] Add streaming support

### Storage Connector
- [ ] Create `backend/connectors/storage/__init__.py`
- [ ] Move `backend/s3.py` → `backend/connectors/storage/s3.py`

### Database Connector
- [ ] Create `backend/connectors/database/__init__.py`
- [ ] Extract `get_connection()` from `ingestion/db_connection.py` → `backend/connectors/database/postgres.py`

### Integration
- [ ] Update all imports across codebase
- [ ] Add backward-compatible exports
- [ ] Run `pytest -v -x tests/`
- [ ] Run `/lint`

## Phase 3: Ingestion Domain

### PDF Processing
- [ ] Create `backend/ingestion/pdf/__init__.py`
- [ ] Create `backend/ingestion/pdf/validator.py`
  - [ ] Move `validate_pdf()` from `ingest.py`
- [ ] Create `backend/ingestion/pdf/renderer.py`
  - [ ] Move `render_page()` from `ingest.py`
  - [ ] Move `create_blur_image()` from `ingest.py`
- [ ] Create `backend/ingestion/pdf/processor.py`
  - [ ] Move `ingest_pdf()` from `ingest.py`
  - [ ] Move page processing logic

### Embeddings
- [ ] Create `backend/ingestion/embeddings/__init__.py`
- [ ] Create `backend/ingestion/embeddings/generator.py`
  - [ ] Extract `process_images()` from `colpali.py`
  - [ ] Extract `get_image_embeddings()` from `colpali.py`
- [ ] Create `backend/ingestion/embeddings/packing.py`
  - [ ] Move `float_to_binary_embedding()` from `ingest.py`

### Region Detection
- [ ] Create `backend/ingestion/regions/__init__.py`
- [ ] Create `backend/ingestion/regions/detector.py`
  - [ ] Move main detection logic from `drawing_regions.py`
- [ ] Create `backend/ingestion/regions/strategies.py`
  - [ ] Move heuristic detection
  - [ ] Move VLM-assisted detection
  - [ ] Move tiling fallback

### Database Ingestion
- [ ] Rename `backend/ingestion/` → `backend/ingestion/database/`
- [ ] Update internal imports within database modules
- [ ] Update external imports

### Cleanup
- [ ] Delete `backend/ingest.py`
- [ ] Delete `backend/drawing_regions.py`
- [ ] Run `pytest -v -x tests/`
- [ ] Run `/lint`

## Phase 4: Query Domain

### Search
- [ ] Create `backend/query/__init__.py`
- [ ] Create `backend/query/search/__init__.py`
- [ ] Create `backend/query/search/dispatcher.py`
  - [ ] Move `get_result_from_query()` from `vespa_app.py`
  - [ ] Move query dispatch logic
- [ ] Create `backend/query/search/bm25.py`
  - [ ] Move `query_vespa_bm25()` from `vespa_app.py`
- [ ] Create `backend/query/search/colpali.py`
  - [ ] Move `query_vespa_colpali()` from `vespa_app.py`
- [ ] Create `backend/query/search/hybrid.py`
  - [ ] Move hybrid ranking logic

### Ranking
- [ ] Create `backend/query/ranking/__init__.py`
- [ ] Move `backend/rerank.py` → `backend/query/ranking/maxsim.py`
- [ ] Move `backend/llm_rerank.py` → `backend/query/ranking/llm.py`

### Similarity Maps
- [ ] Create `backend/query/similarity/__init__.py`
- [ ] Create `backend/query/similarity/generator.py`
  - [ ] Extract `get_sim_maps()` from `colpali.py`
  - [ ] Extract `get_query_embeddings()` from `colpali.py`
  - [ ] Extract `generate_sim_map_image()` from `colpali.py`
- [ ] Create `backend/query/similarity/cache.py`
  - [ ] Move simmap caching logic from `main.py`

### Agent
- [ ] Create `backend/query/agent/__init__.py`
- [ ] Create `backend/query/agent/session.py`
  - [ ] Move `AgentSession` from `agent.py`
- [ ] Create `backend/query/agent/tools.py`
  - [ ] Move tool definitions from `agent.py`

### Text Processing
- [ ] Create `backend/query/text/__init__.py`
- [ ] Move `backend/stopwords.py` → `backend/query/text/stopwords.py`

### Results
- [ ] Create `backend/query/results.py`
  - [ ] Move `results_to_search_results()` from `vespa_app.py`

### Cleanup
- [ ] Delete `backend/vespa_app.py`
- [ ] Delete `backend/colpali.py`
- [ ] Delete `backend/agent.py`
- [ ] Delete `backend/rerank.py`
- [ ] Delete `backend/llm_rerank.py`
- [ ] Delete `backend/stopwords.py`
- [ ] Run `pytest -v -x tests/`
- [ ] Run `/lint`

## Phase 5: Final Integration

### Import Updates
- [ ] Update all imports in `main.py`
- [ ] Update all imports in `scripts/feed_data.py`
- [ ] Update all imports in `scripts/ingest_database.py`
- [ ] Update all imports in `scripts/sync_database.py`
- [ ] Update all imports in remaining `scripts/*.py`
- [ ] Update all imports in `tests/unit/*.py`
- [ ] Update all imports in `tests/integration/*.py`
- [ ] Update all imports in `tests/conftest.py`

### Cleanup
- [ ] Remove backward-compatible re-exports from `backend/__init__.py`
- [ ] Remove any deprecated modules
- [ ] Verify no unused imports

### Documentation
- [ ] Update `CLAUDE.md` Architecture section
- [ ] Update `CLAUDE.md` Key Modules section
- [ ] Add module docstrings to new `__init__.py` files

### Testing
- [ ] Run full test suite: `pytest -v tests/`
- [ ] Run linting: `ruff check .`
- [ ] Manual test: PDF upload
- [ ] Manual test: Search (all ranking modes)
- [ ] Manual test: Chat sidebar
- [ ] Manual test: Similarity map viewer
- [ ] Manual test: Agent mode

## Post-Migration

- [ ] Review and optimize new module structure
- [ ] Consider adding type hints to new interfaces
- [ ] Consider adding integration tests for domain boundaries
