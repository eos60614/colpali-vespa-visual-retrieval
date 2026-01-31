# Research: Current Codebase Analysis

## Module Inventory

### Current Backend Structure

| Module | Lines | Primary Responsibility | Domain |
|--------|-------|------------------------|--------|
| `main.py` | 863 | API routes, orchestration | API |
| `vespa_app.py` | 533 | Vespa queries + connection | Mixed |
| `ingest.py` | 540 | PDF processing pipeline | Ingestion |
| `colpali.py` | 287 | Model inference, embeddings, simmaps | Mixed |
| `drawing_regions.py` | 1341 | Region detection for large drawings | Ingestion |
| `agent.py` | 448 | Multi-step reasoning agent | Query |
| `rerank.py` | 213 | MaxSim reranking | Query |
| `llm_rerank.py` | 198 | LLM-based reranking | Query |
| `config.py` | 58 | Configuration loading | Shared |
| `llm_config.py` | 40 | LLM provider config | Connector |
| `logging_config.py` | 307 | Centralized logging | Shared |
| `middleware.py` | 113 | ASGI middleware | Shared |
| `cache.py` | 26 | LRU cache | Shared |
| `s3.py` | 61 | S3 presigned URLs | Connector |
| `stopwords.py` | ~50 | Text processing | Query |
| `testquery.py` | 3013 | Query testing tool | Dev |

### Ingestion Subsystem (backend/ingestion/)

| Module | Purpose |
|--------|---------|
| `db_connection.py` | PostgreSQL async connection |
| `schema_discovery.py` | Auto-discover DB schema |
| `change_detector.py` | Track changes for incremental sync |
| `checkpoint.py` | Checkpoint management |
| `file_detector.py` | Identify file references in records |
| `file_downloader.py` | Download files from S3/URLs |
| `pdf_processor.py` | Process PDFs with ColPali |
| `record_ingester.py` | Transform DB rows → Vespa docs |
| `sync_manager.py` | Orchestrate full/incremental sync |
| `exceptions.py` | Custom exception types |

## Import Graph Analysis

### High Coupling Modules

**`main.py`** imports from:
- `backend.config`
- `backend.logging_config`
- `backend.middleware`
- `backend.llm_config`
- `backend.colpali`
- `backend.vespa_app`
- `backend.ingest`
- `backend.s3`
- `backend.llm_rerank`

**`vespa_app.py`** imports from:
- `backend.colpali` (SimMapGenerator)
- `backend.stopwords`
- `backend.config`
- `backend.logging_config`

**`ingest.py`** imports from:
- `backend.config`
- `backend.logging_config`
- `backend.drawing_regions`

**`colpali.py`** imports from:
- `backend.config`
- `backend.logging_config`
- External: `colpali_engine`, `vidore_benchmark`

### Circular Dependency Risks

No circular dependencies currently exist. The dependency graph is:
```
config, logging_config (leaf nodes - no backend imports)
         ↑
   All other modules
```

## Function Analysis

### `colpali.py::SimMapGenerator`

Methods to split:

**Ingestion-related (→ `ingestion/embeddings/`):**
- `process_images(images)` - Generate embeddings for images
- `get_image_embeddings(images)` - Batch embedding generation

**Query-related (→ `query/similarity/`):**
- `get_query_embeddings(query)` - Cached query embeddings
- `get_sim_maps(query, images, vespa_maps)` - Generate similarity maps
- `generate_sim_map_image(sim_map, image)` - Render heatmap overlay

**Shared:**
- `__init__()` - Model loading (should be in `core/models/`)
- `model`, `processor` - Model instances

### `vespa_app.py::VespaQueryClient`

Methods to split:

**Connector-related (→ `connectors/vespa/`):**
- `__init__()` - Connection setup (3 modes)
- `keepalive()` - Health check
- `app` property - Vespa instance access

**Query-related (→ `query/search/`):**
- `get_result_from_query()` - Main query dispatcher
- `query_vespa_colpali()` - ColPali vector search
- `query_vespa_bm25()` - BM25 text search
- `query_vespa_hybrid()` - Hybrid ranking
- `get_sim_maps_from_query()` - Fetch sim map tensors

**Results (→ `query/results.py`):**
- `results_to_search_results()` - Transform Vespa response

**Tensors (→ `connectors/vespa/tensors.py`):**
- `format_binary_embedding()` - Python → Vespa format
- `format_float_embedding()` - Python → Vespa format
- Various tensor parsing utilities

## External Dependencies

### Embedding Model
- `colpali_engine.models.ColQwen2_5`
- `colpali_engine.models.ColQwen2_5_Processor`
- Model: `tsystems/colqwen2.5-3b-multilingual-v1.0`

### Vespa
- `vespa.application.Vespa`
- `vespa.io.VespaQueryResponse`
- `pyvespa` client library

### LLM
- `httpx` for OpenAI-compatible API calls
- No SDK dependencies - raw HTTP

### Storage
- `boto3` for S3 (via `backend/s3.py`)
- `asyncpg` for PostgreSQL

### PDF Processing
- `fitz` (PyMuPDF) for PDF rendering
- `PIL` for image processing

## API Surface

### Public Functions (used by main.py)

From `colpali.py`:
- `SimMapGenerator` class

From `vespa_app.py`:
- `VespaQueryClient` class

From `ingest.py`:
- `ingest_pdf()`
- `validate_pdf()`

From `rerank.py`:
- `maxsim_rerank()`

From `llm_rerank.py`:
- `llm_rerank_results()`
- `is_llm_rerank_enabled()`
- `get_llm_rerank_candidates()`

From `agent.py`:
- `AgentSession` class

From `s3.py`:
- `generate_presigned_url()`

From `llm_config.py`:
- `resolve_llm_config()`
- `get_chat_model()`
- `is_remote_api()`
- `build_auth_headers()`

## Configuration Dependencies

### `ki55.toml` Sections Used

| Section | Used By |
|---------|---------|
| `[app]` | main.py, config.py |
| `[llm]` | llm_config.py, main.py, agent.py |
| `[vespa]` | vespa_app.py |
| `[colpali]` | colpali.py, models/config.py |
| `[search]` | main.py |
| `[image]` | ingest.py, main.py |
| `[agent]` | agent.py |
| `[drawing_regions]` | drawing_regions.py |
| `[ingestion]` | ingestion/*.py |

### Environment Variables

| Variable | Used By |
|----------|---------|
| `LLM_BASE_URL` | llm_config.py |
| `OPENROUTER_API_KEY` | llm_config.py |
| `OPENAI_API_KEY` | llm_config.py |
| `VESPA_LOCAL_URL` | vespa_app.py |
| `VESPA_*` (cloud auth) | vespa_app.py |
| `AWS_*` | s3.py |
| `PROCORE_DATABASE_URL` | ingestion/db_connection.py |
