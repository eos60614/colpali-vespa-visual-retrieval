# Codebase Reorganization: Three-Domain Architecture

## Overview

This spec proposes reorganizing the backend codebase into three distinct domains:

1. **Ingestion** - Document processing, embedding generation, Vespa feeding
2. **Query** - Search, ranking, retrieval, similarity maps
3. **Connectors** - External service integrations (LLM, Vespa, PostgreSQL, S3)

## Current State Analysis

### Existing Structure
```
backend/
├── config.py              # Shared: config loading
├── llm_config.py          # Connector: LLM provider config
├── logging_config.py      # Shared: logging setup
├── middleware.py          # Shared: ASGI middleware
├── cache.py               # Shared: LRU cache
├── stopwords.py           # Query: text processing
├── colpali.py             # Mixed: model inference (used by both ingestion & query)
├── vespa_app.py           # Connector: Vespa client
├── ingest.py              # Ingestion: PDF processing pipeline
├── rerank.py              # Query: MaxSim reranking
├── llm_rerank.py          # Query: LLM-based reranking
├── drawing_regions.py     # Ingestion: region detection
├── agent.py               # Query: multi-step reasoning
├── s3.py                  # Connector: S3 operations
├── testquery.py           # Query: testing tool
├── ingestion/             # Ingestion: database ingestion subsystem
│   ├── db_connection.py
│   ├── schema_discovery.py
│   ├── change_detector.py
│   ├── checkpoint.py
│   ├── file_detector.py
│   ├── file_downloader.py
│   ├── pdf_processor.py
│   ├── record_ingester.py
│   ├── sync_manager.py
│   └── exceptions.py
└── models/                # Shared: model registry
    └── config.py
```

### Key Dependencies

| Module | Depends On |
|--------|------------|
| `main.py` | colpali, vespa_app, ingest, s3, llm_rerank, config, llm_config |
| `ingest.py` | colpali, drawing_regions, config |
| `vespa_app.py` | colpali, stopwords, config |
| `agent.py` | llm_config, config |
| `rerank.py` | config |
| `drawing_regions.py` | llm_config, config |
| `colpali.py` | config |

### Coupling Issues

1. **`colpali.py`** is used by both ingestion (for generating embeddings) and query (for similarity maps). This is the most complex cross-cutting module.

2. **`vespa_app.py`** mixes connector logic (connection management) with query logic (search dispatching, result transformation).

3. **`main.py`** orchestrates everything - it's the main coupling point.

## Proposed Architecture

### Directory Structure

```
backend/
├── __init__.py
├── core/                      # Shared infrastructure
│   ├── __init__.py
│   ├── config.py              # Configuration loading
│   ├── logging_config.py      # Centralized logging
│   ├── middleware.py          # ASGI middleware
│   ├── cache.py               # LRU cache utilities
│   └── models/                # Model registry
│       ├── __init__.py
│       └── config.py
│
├── ingestion/                 # Domain: Document Ingestion
│   ├── __init__.py
│   ├── pdf/                   # PDF processing
│   │   ├── __init__.py
│   │   ├── processor.py       # Core PDF pipeline (from ingest.py)
│   │   ├── validator.py       # PDF validation
│   │   └── renderer.py        # Page rendering
│   ├── embeddings/            # Embedding generation
│   │   ├── __init__.py
│   │   ├── generator.py       # ColPali embedding generation
│   │   └── packing.py         # Binary packing utilities
│   ├── regions/               # Region detection
│   │   ├── __init__.py
│   │   ├── detector.py        # Main region detection (from drawing_regions.py)
│   │   └── strategies.py      # Detection strategies (heuristic, VLM)
│   ├── database/              # Database ingestion (existing ingestion/ subdir)
│   │   ├── __init__.py
│   │   ├── connection.py      # db_connection.py
│   │   ├── schema.py          # schema_discovery.py
│   │   ├── changes.py         # change_detector.py + checkpoint.py
│   │   ├── files.py           # file_detector.py + file_downloader.py
│   │   ├── records.py         # record_ingester.py
│   │   └── sync.py            # sync_manager.py
│   └── exceptions.py          # Ingestion-specific exceptions
│
├── query/                     # Domain: Query & Search
│   ├── __init__.py
│   ├── search/                # Search execution
│   │   ├── __init__.py
│   │   ├── dispatcher.py      # Query dispatching (from vespa_app.py)
│   │   ├── bm25.py            # BM25 search
│   │   ├── colpali.py         # ColPali vector search
│   │   └── hybrid.py          # Hybrid ranking
│   ├── ranking/               # Reranking
│   │   ├── __init__.py
│   │   ├── maxsim.py          # MaxSim reranking (from rerank.py)
│   │   └── llm.py             # LLM reranking (from llm_rerank.py)
│   ├── similarity/            # Similarity maps
│   │   ├── __init__.py
│   │   ├── generator.py       # SimMap generation (from colpali.py)
│   │   └── cache.py           # SimMap caching
│   ├── agent/                 # Agent-based reasoning
│   │   ├── __init__.py
│   │   ├── session.py         # AgentSession (from agent.py)
│   │   └── tools.py           # Agent tool definitions
│   ├── text/                  # Text processing
│   │   ├── __init__.py
│   │   └── stopwords.py       # Stopword utilities
│   └── results.py             # Result transformation
│
├── connectors/                # Domain: External Connectors
│   ├── __init__.py
│   ├── vespa/                 # Vespa connector
│   │   ├── __init__.py
│   │   ├── client.py          # Connection management
│   │   ├── tensors.py         # Tensor format conversions
│   │   └── schemas.py         # Schema definitions/types
│   ├── llm/                   # LLM provider connector
│   │   ├── __init__.py
│   │   ├── client.py          # OpenAI-compatible client
│   │   ├── config.py          # Provider configuration
│   │   └── streaming.py       # SSE streaming utilities
│   ├── storage/               # Storage connectors
│   │   ├── __init__.py
│   │   ├── s3.py              # S3 operations
│   │   └── filesystem.py      # Local filesystem operations
│   └── database/              # Database connectors
│       ├── __init__.py
│       └── postgres.py        # PostgreSQL async connection
│
└── api/                       # API layer (optional future)
    ├── __init__.py
    ├── routes/                # Route handlers
    │   ├── search.py
    │   ├── upload.py
    │   └── chat.py
    └── middleware.py          # API-specific middleware
```

### Module Mapping

| Current Location | New Location | Domain |
|------------------|--------------|--------|
| `config.py` | `core/config.py` | Shared |
| `logging_config.py` | `core/logging_config.py` | Shared |
| `middleware.py` | `core/middleware.py` | Shared |
| `cache.py` | `core/cache.py` | Shared |
| `models/config.py` | `core/models/config.py` | Shared |
| `ingest.py` | `ingestion/pdf/processor.py` | Ingestion |
| `drawing_regions.py` | `ingestion/regions/detector.py` | Ingestion |
| `ingestion/*.py` | `ingestion/database/*.py` | Ingestion |
| `colpali.py` (embedding) | `ingestion/embeddings/generator.py` | Ingestion |
| `colpali.py` (simmap) | `query/similarity/generator.py` | Query |
| `vespa_app.py` (connection) | `connectors/vespa/client.py` | Connectors |
| `vespa_app.py` (query) | `query/search/dispatcher.py` | Query |
| `rerank.py` | `query/ranking/maxsim.py` | Query |
| `llm_rerank.py` | `query/ranking/llm.py` | Query |
| `agent.py` | `query/agent/session.py` | Query |
| `stopwords.py` | `query/text/stopwords.py` | Query |
| `llm_config.py` | `connectors/llm/config.py` | Connectors |
| `s3.py` | `connectors/storage/s3.py` | Connectors |

### Key Refactoring Decisions

#### 1. Split `colpali.py`

The current `colpali.py` contains two distinct responsibilities:
- **Embedding generation** (for ingestion) - `get_image_embeddings()`
- **Similarity map generation** (for query) - `get_sim_maps()`

**Proposal:** Split into two modules with shared model loading:
- `ingestion/embeddings/generator.py` - Embedding generation
- `query/similarity/generator.py` - Similarity maps

Both import a shared model instance from `core/models/`.

#### 2. Split `vespa_app.py`

Currently mixes connection management with query logic:
- **Connection management** - connection modes, keepalive
- **Query execution** - BM25, ColPali, hybrid dispatching
- **Tensor conversions** - format transformations

**Proposal:**
- `connectors/vespa/client.py` - Connection management
- `connectors/vespa/tensors.py` - Tensor format utilities
- `query/search/dispatcher.py` - Query logic using the connector

#### 3. Consolidate Database Ingestion

The `ingestion/` subdirectory is already well-organized. Rename to `database/` within the new `ingestion/` domain for clarity.

### Dependency Flow

```
                    ┌─────────────────────────────────────┐
                    │              core/                  │
                    │  config, logging, cache, models     │
                    └─────────────────────────────────────┘
                                     ▲
                                     │ (all domains import)
        ┌────────────────────────────┼────────────────────────────┐
        │                            │                            │
        ▼                            ▼                            ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│  ingestion/   │          │    query/     │          │ connectors/   │
│               │          │               │          │               │
│ pdf/          │◄────────►│ search/       │◄────────►│ vespa/        │
│ embeddings/   │          │ ranking/      │          │ llm/          │
│ regions/      │          │ similarity/   │          │ storage/      │
│ database/     │          │ agent/        │          │ database/     │
└───────────────┘          └───────────────┘          └───────────────┘
        │                            │                            │
        └────────────────────────────┼────────────────────────────┘
                                     │
                                     ▼
                            ┌───────────────┐
                            │   main.py     │
                            │  (API layer)  │
                            └───────────────┘
```

## Implementation Phases

### Phase 1: Create Core Infrastructure
1. Create `core/` directory with shared utilities
2. Move `config.py`, `logging_config.py`, `middleware.py`, `cache.py`
3. Update all imports across codebase

### Phase 2: Create Connectors Domain
1. Create `connectors/` directory structure
2. Extract Vespa connection logic from `vespa_app.py`
3. Move `llm_config.py` to `connectors/llm/config.py`
4. Move `s3.py` to `connectors/storage/s3.py`
5. Update imports

### Phase 3: Create Ingestion Domain
1. Create `ingestion/` directory structure
2. Move PDF processing from `ingest.py`
3. Split `colpali.py` - embedding generation to `ingestion/embeddings/`
4. Move `drawing_regions.py` to `ingestion/regions/`
5. Reorganize existing `ingestion/` database modules
6. Update imports

### Phase 4: Create Query Domain
1. Create `query/` directory structure
2. Extract query logic from `vespa_app.py` to `query/search/`
3. Split `colpali.py` - similarity maps to `query/similarity/`
4. Move `rerank.py` to `query/ranking/maxsim.py`
5. Move `llm_rerank.py` to `query/ranking/llm.py`
6. Move `agent.py` to `query/agent/session.py`
7. Update imports

### Phase 5: Update main.py and Tests
1. Update all imports in `main.py`
2. Update test imports in `tests/`
3. Update script imports in `scripts/`
4. Verify all functionality works

## Trade-offs and Considerations

### Benefits
1. **Clear domain boundaries** - Each domain has a specific responsibility
2. **Easier testing** - Domains can be tested in isolation
3. **Scalability** - Domains can evolve independently
4. **Onboarding** - New developers can understand the structure quickly

### Costs
1. **Migration effort** - Significant refactoring required
2. **Import path changes** - All existing code needs import updates
3. **Potential for bugs** - Risk of breaking changes during migration
4. **Deeper nesting** - More directories to navigate

### Alternatives Considered

#### Alternative A: Keep Flat Structure
Keep current flat structure but add clear prefixes:
- `ingest_*.py`, `query_*.py`, `conn_*.py`

**Rejected:** Doesn't provide true separation or namespace benefits.

#### Alternative B: Two Domains Only
Split into just `processing/` and `retrieval/`:
- `processing/` - Everything related to getting documents in
- `retrieval/` - Everything related to getting documents out

**Rejected:** Connectors are distinct and warrant their own domain.

#### Alternative C: Monorepo with Packages
Create separate Python packages for each domain that are installed independently.

**Rejected:** Overkill for current project size. Could be future evolution.

## Migration Strategy

### Step-by-Step Migration
1. Create new directory structure (empty)
2. Add `__init__.py` files with backward-compatible exports
3. Move files one at a time, updating imports
4. Run tests after each file move
5. Remove backward-compatibility exports once complete

### Backward Compatibility
During migration, old import paths should continue to work:
```python
# backend/__init__.py (during migration)
from backend.core.config import get  # New location
from backend.config import get  # Old location (deprecated)
```

## Success Criteria

1. All existing tests pass
2. All API routes function correctly
3. No performance regression
4. Clear documentation of new structure
5. Updated CLAUDE.md with new architecture

## Open Questions

1. Should `testquery.py` move to `scripts/` instead of `query/`?
2. Should we introduce a `backend/api/` directory for route handlers extracted from `main.py`?
3. Should model weights caching be a concern of `core/` or `connectors/`?
