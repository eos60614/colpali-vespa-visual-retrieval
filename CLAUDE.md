# ColPali-Vespa Visual Retrieval — Developer Guide

A visual document retrieval system combining ColPali/ColQwen embeddings with Vespa search. Supports PDF upload and search via a FastHTML web UI, plus Procore database ingestion for structured record retrieval.

## Quick Reference

```bash
# Run the web application
python main.py                        # Starts on http://localhost:7860

# Start local Vespa
docker-compose up -d                  # Vespa on :8080 (query) and :19071 (config)

# Deploy Vespa schemas
vespa deploy vespa-app -t http://localhost:19071

# Index sample data
python scripts/feed_data.py --sample

# Lint
ruff check .
ruff check --fix .

# Tests
pytest tests/

# Full automated local setup
./scripts/setup_local.sh
```

## Architecture Overview

```
Browser (:7860)
    │
    ▼
FastHTML App (main.py)
    ├── ColPali/ColQwen Embeddings (backend/colpali.py)
    ├── Vespa Client (backend/vespa_app.py)
    ├── Reranking (backend/rerank.py)
    ├── PDF Ingestion (backend/ingest.py)
    └── Gemini AI Chat (optional, google.generativeai)
    │
    ▼
Vespa (Docker, :8080)
    ├── pdf_page schema — PDF pages with ColPali embeddings + HNSW index
    ├── procore_record schema — Database records with navigation metadata
    └── procore_schema_metadata schema — Schema metadata for agent navigation
```

The app uses **HTMX** for dynamic UI updates and **Tailwind CSS** for styling.

## Project Structure

```
├── main.py                          # FastHTML web app entry point (uvicorn, port 7860)
├── docker-compose.yml               # Local Vespa 8 container
├── requirements.txt                 # Python deps (compiled via uv pip compile)
├── requirements-local.txt           # Optional local dev deps
├── .env.example                     # Environment variable template
├── icons.py                         # SVG icon definitions for UI
├── tailwind.config.js               # Tailwind CSS config
├── globals.css / output.css         # Tailwind source / compiled CSS
│
├── backend/
│   ├── vespa_app.py                 # VespaQueryClient — connection, query, ranking
│   ├── colpali.py                   # SimMapGenerator — ColQwen2.5 model, similarity maps
│   ├── ingest.py                    # PDF validation, page conversion, embedding, Vespa feed
│   ├── rerank.py                    # Application-level MaxSim reranking
│   ├── cache.py                     # LRU cache (OrderedDict, max_size=20)
│   ├── stopwords.py                 # spaCy-based English stopword filtering
│   ├── testquery.py                 # Query testing utilities
│   ├── models/
│   │   └── config.py                # Model registry (colpali, colqwen3)
│   └── ingestion/                   # Procore database ingestion module
│       ├── db_connection.py         # Async PostgreSQL via asyncpg
│       ├── schema_discovery.py      # Database schema introspection
│       ├── record_ingester.py       # Record → Vespa document transform
│       ├── file_detector.py         # S3/URL reference extraction from records
│       ├── file_downloader.py       # Async S3/URL file download with retries
│       ├── pdf_processor.py         # ColPali processing for downloaded PDFs
│       ├── change_detector.py       # Incremental sync via timestamp detection
│       ├── checkpoint.py            # SQLite-based sync state persistence
│       ├── sync_manager.py          # Full/incremental sync orchestration
│       └── exceptions.py            # Custom exception hierarchy
│
├── frontend/
│   ├── app.py                       # UI components: Search, Upload, Results, ChatResult
│   └── layout.py                    # Layout, scrollbars, dark mode toggle
│
├── tests/
│   ├── conftest.py                  # Pytest fixtures (mocks, sample data, event loop)
│   ├── unit/ingestion/              # Unit test directory
│   └── integration/ingestion/       # Integration test directory
│
├── scripts/
│   ├── feed_data.py                 # Batch PDF indexing (--pdf-folder, --sample)
│   ├── discover_schema.py           # Procore DB schema export (json/markdown)
│   ├── ingest_database.py           # Full/incremental DB ingestion CLI
│   ├── sync_database.py             # Continuous sync daemon
│   ├── ingest_sample.py             # Demo data loader
│   ├── ingest_colqwen3_embeddings.py  # Re-embed docs with ColQwen3
│   ├── reingest_single_file_colqwen3.py # Single file re-processing
│   ├── setup_local.sh               # Automated local dev setup
│   ├── sync_cron.sh                 # Cron wrapper for sync daemon
│   ├── test_connections.py          # DB + Vespa connectivity check
│   ├── test_ingestion.py            # Ingestion pipeline test
│   ├── test_real_ingestion.py       # Real DB integration test
│   └── test_e2e_file_ingestion.py   # End-to-end file ingestion test
│
├── vespa-app/
│   ├── services.xml                 # Vespa cluster config (search, content, doc-api)
│   ├── hosts.xml                    # Host mapping (localhost)
│   ├── validation-overrides.xml     # Schema change validation overrides
│   └── schemas/
│       ├── pdf_page.sd              # PDF pages: text + ColPali embeddings + HNSW
│       ├── procore_record.sd        # DB records with relationships + file refs
│       └── procore_schema_metadata.sd # Schema metadata for agent navigation
│
├── specs/                           # Feature specifications
│   ├── 001-colqwen3-model/          # ColQwen3 embedding model migration
│   ├── 001-procore-db-ingestion/    # Procore DB integration
│   └── 002-file-upload-ingest/      # PDF file upload feature
│
├── .claude/commands/                # Claude Code custom commands
│   ├── server.md, debug.md          # Dev workflow commands
│   ├── lint.md, lint-fix.md         # Code quality
│   ├── check.md, test.md            # Validation commands
│   └── speckit.*.md                 # Specification framework commands
│
├── .specify/                        # Project specification framework
│   ├── memory/constitution.md       # Project standards and rules
│   ├── scripts/bash/                # Feature creation, setup scripts
│   └── templates/                   # Spec, plan, checklist templates
│
└── static/
    ├── js/highlightjs-theme.js      # Syntax highlighting theme loader
    └── img/                         # Logos, architecture diagrams, social icons
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# --- Vespa Connection (pick one) ---
VESPA_LOCAL_URL=http://localhost:8080              # Local development (no auth)
# VESPA_APP_TOKEN_URL=https://...                  # Vespa Cloud token auth
# VESPA_CLOUD_SECRET_TOKEN=...
# USE_MTLS=true                                    # Vespa Cloud mTLS auth
# VESPA_APP_MTLS_URL=https://...
# VESPA_CLOUD_MTLS_KEY=...
# VESPA_CLOUD_MTLS_CERT=...

# --- Application ---
LOG_LEVEL=INFO                                     # DEBUG, INFO, WARNING, ERROR
HOT_RELOAD=False                                   # Dev hot reload
GEMINI_API_KEY=...                                 # Optional: Google Gemini for chat
VESPA_DATA_DIR=/mnt/vespa-storage                  # Vespa data mount (500GB+)

# --- Procore Database (read-only) ---
PROCORE_DATABASE_URL=postgresql://user:pass@host:5432/procore_int_v2

# --- AWS S3 (optional, for file downloads) ---
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
S3_BUCKET=procore-integration-files
```

## Key Technical Concepts

### Embedding Pipeline

The system uses **ColQwen2.5** (`tsystems/colqwen2.5-3b-multilingual-v1.0`) for visual document embeddings:

1. PDF pages are rendered as images
2. ColQwen2.5 generates multi-vector embeddings: one 128-dim vector per visual patch
3. Embeddings are stored in Vespa as:
   - `embedding`: Binary int8 packed format (`tensor<int8>(patch{}, v[16])`) — used for HNSW approximate nearest neighbor retrieval
   - `embedding_float`: Full precision (`tensor<float>(patch{}, v[128])`) — used for reranking
4. Queries are encoded the same way, producing per-token 128-dim vectors

### Ranking Profiles

Vespa supports three ranking strategies (defined in `pdf_page.sd`):

| Profile | First Phase | Second Phase | Use Case |
|---------|-------------|--------------|----------|
| `bm25` | BM25(title + text) | — | Text-only search |
| `colpali` | MaxSim (binary, Hamming) | MaxSim (float, unpacked) | Visual similarity |
| `hybrid` | MaxSim (binary) | MaxSim + 2×BM25(text+title+tags) | Combined search |

Each profile has a `_sim` variant that also returns similarity maps for visualization.

### Application-Level Reranking

After Vespa returns candidates, `backend/rerank.py` performs MaxSim reranking using full-precision float embeddings for improved accuracy. The flow:
1. Fetch 20 candidates from Vespa
2. Compute MaxSim using `embedding_float` fields
3. Return top 3 results

### Vespa Query Flow

`VespaQueryClient` (`backend/vespa_app.py`) handles all Vespa communication:
- Supports 3 auth modes: local (no auth), mTLS, token
- Query embeddings are converted to both float and binary int8 formats
- Binary embeddings create nearest-neighbor query strings (`rq0`–`rq63`, max 64 query terms)
- Stopwords are filtered before querying to improve visual relevance

## Commands Reference

### Web Application
```bash
python main.py                                    # Start on :7860
```

### PDF Ingestion
```bash
python scripts/feed_data.py --sample              # Index demo PDFs
python scripts/feed_data.py --pdf-folder /path    # Index custom PDFs
```

### Database Ingestion (Procore)
```bash
# Schema discovery
python scripts/discover_schema.py --format markdown --output schema-report.md
python scripts/discover_schema.py --format json --output schema-map.json

# Full ingestion
python scripts/ingest_database.py --full
python scripts/ingest_database.py --full --tables photos drawings projects
python scripts/ingest_database.py --full --exclude _prisma_migrations sync_events
python scripts/ingest_database.py --full --download-files --file-workers 4
python scripts/ingest_database.py --full --dry-run

# Incremental sync
python scripts/ingest_database.py --incremental

# Sync daemon
python scripts/sync_database.py --daemon                # Run continuously (default 300s interval)
python scripts/sync_database.py --daemon --interval 300
python scripts/sync_database.py --once                  # Single sync cycle
python scripts/sync_database.py --status                # Check sync status
```

### Re-embedding
```bash
python scripts/ingest_colqwen3_embeddings.py            # Re-embed all docs with ColQwen3
python scripts/reingest_single_file_colqwen3.py         # Re-process single file
```

### Development
```bash
# Linting
ruff check .
ruff check --fix .

# Tests
pytest tests/
pytest tests/unit/
pytest tests/integration/

# Connectivity checks
python scripts/test_connections.py
python scripts/test_e2e_file_ingestion.py

# Vespa management
docker-compose up -d                               # Start Vespa
docker-compose down                                # Stop (keeps data)
docker-compose down -v                             # Stop + remove data
vespa deploy vespa-app -t http://localhost:19071    # Deploy schemas
```

## Vespa Schemas

### pdf_page
Primary document type for PDF content. Key fields:
- `id`, `title`, `url`, `page_number`, `year` — identifiers and metadata
- `text`, `snippet` — extracted text (BM25-indexed)
- `blur_image`, `full_image` — base64-encoded images
- `embedding` — binary int8 ColPali embeddings with HNSW index (Hamming distance)
- `embedding_float` — full-precision float embeddings for reranking
- `questions`, `queries`, `description`, `tags` — searchable generated metadata
- Fieldset `default`: title + text

### procore_record
Database records with agent navigation metadata:
- `doc_id`, `source_table`, `source_id`, `project_id` — record identifiers
- `content_text` — full-text searchable content
- `metadata` — key-value pairs from database columns
- `relationships` — JSON array: `{target_doc_id, target_table, direction, cardinality}`
- `file_references` — JSON array: `{s3_key, source_column, reference_type, provenance}`
- `incoming_relationships` — reverse traversal hints
- `table_description`, `column_types` — agent reference metadata
- Rank profiles: `default`, `bm25`, `freshness` (BM25 + recency)

### procore_schema_metadata
Schema metadata for agents to understand database structure:
- `metadata_type`: `"full_schema"` or `"table"`
- `columns`, `timestamp_columns`, `file_reference_columns` — column metadata
- `outgoing_relationships`, `incoming_relationships` — navigation graph
- `schema_summary` — for full_schema documents

## Code Style

- **Python 3.11+** — use standard conventions
- **Linting**: `ruff check .` (no pre-commit hooks configured)
- **Testing**: `pytest` with async support (session-scoped event loop in conftest)
- **Logging**: Use `logging.getLogger()`, configurable via `LOG_LEVEL` env var
- **Async**: asyncpg for database, Vespa async sessions for queries
- **Type hints**: Used throughout backend modules

## Model Registry

Defined in `backend/models/config.py`:

| ID | Model | HF ID | Dims | Max Tokens |
|----|-------|--------|------|------------|
| `colpali` | ColPali v1.2 | `vidore/colpali-v1.2` | 128 | 1024 |
| `colqwen3` | ColQwen2.5 | `tsystems/colqwen2.5-3b-multilingual-v1.0` | 128 | 768 |

The active model is ColQwen2.5 (loaded in `backend/colpali.py` `SimMapGenerator`).

## Local Development Setup

1. Start Vespa: `docker-compose up -d`
2. Wait for health: `curl http://localhost:19071/state/v1/health`
3. Deploy schemas: `vespa deploy vespa-app -t http://localhost:19071`
4. Install deps: `pip install -r requirements.txt && python -m spacy download en_core_web_sm`
5. Configure env: `cp .env.example .env`
6. Index data: `python scripts/feed_data.py --sample`
7. Run app: `python main.py`

Or use the automated script: `./scripts/setup_local.sh`

**Requirements**: Docker (8GB+ RAM), Python 3.10+, CUDA GPU recommended for embeddings.
