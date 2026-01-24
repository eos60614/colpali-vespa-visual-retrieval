# ColPali-Vespa Visual Retrieval

Visual document search engine combining ColPali vision-language embeddings with Vespa's distributed search. Supports PDF upload/indexing, multi-modal search (BM25, visual, hybrid), similarity map visualization, and enterprise database ingestion from Procore.

## Project Structure

```text
.
├── main.py                       # FastHTML application entry point (port 7860)
├── backend/
│   ├── vespa_app.py              # VespaQueryClient - query execution, 3 connection modes
│   ├── colpali.py                # SimMapGenerator - ColQwen2.5 model, similarity maps
│   ├── ingest.py                 # PDF ingestion pipeline (validate, extract, embed, index)
│   ├── rerank.py                 # MaxSim reranking with binary/float embeddings
│   ├── cache.py                  # Caching utilities
│   ├── stopwords.py              # Stopword filtering for queries
│   ├── testquery.py              # Query testing utilities
│   ├── models/
│   │   └── config.py             # Model registry (colpali, colqwen3 configs)
│   └── ingestion/                # Procore database ingestion module
│       ├── db_connection.py      # Async PostgreSQL connection pooling
│       ├── schema_discovery.py   # Table/column introspection, relationship mapping
│       ├── record_ingester.py    # Record transformation, relationship extraction
│       ├── file_detector.py      # S3 key pattern matching, URL/JSONB parsing
│       ├── file_downloader.py    # Multi-strategy S3 downloads with retry
│       ├── pdf_processor.py      # PDF extraction from downloaded files
│       ├── change_detector.py    # Timestamp-based change tracking
│       ├── sync_manager.py       # Orchestration, job management, progress
│       ├── checkpoint.py         # Sync state persistence/recovery
│       └── exceptions.py         # Custom exceptions
├── frontend/
│   ├── app.py                    # UI components (SearchBox, Results, Upload, SimMap)
│   └── layout.py                 # Layout framework (grid, theme, header)
├── scripts/
│   ├── feed_data.py              # Index PDFs into Vespa
│   ├── discover_schema.py        # Database schema introspection CLI
│   ├── ingest_database.py        # Full/incremental database ingestion CLI
│   ├── sync_database.py          # Continuous sync daemon CLI
│   ├── ingest_colqwen3_embeddings.py  # Re-embed with ColQwen2.5
│   ├── ingest_sample.py          # Sample data ingestion
│   ├── setup_local.sh            # Automated local Vespa setup
│   ├── sync_cron.sh              # Cron-compatible sync wrapper
│   └── test_connections.py       # DB/Vespa connectivity validation
├── vespa-app/
│   ├── services.xml              # Vespa service configuration
│   ├── hosts.xml                 # Host definitions
│   └── schemas/
│       ├── pdf_page.sd           # PDF pages with ColPali embeddings (main schema)
│       ├── procore_record.sd     # Database records with relationships
│       └── procore_schema_metadata.sd  # Schema metadata for agent navigation
├── tests/
│   ├── conftest.py               # Shared fixtures (mock DB, Vespa, sample data)
│   ├── unit/ingestion/           # Unit tests for ingestion module
│   └── integration/ingestion/    # Integration tests
├── static/
│   ├── img/                      # Static images
│   └── js/highlightjs-theme.js   # Code highlighting theme switcher
├── specs/                        # Feature specifications
│   ├── 001-procore-db-ingestion/
│   └── 002-file-upload-ingest/
├── docker-compose.yml            # Vespa container (vespaengine/vespa:8)
├── requirements.txt              # Production dependencies
├── requirements-local.txt        # Additional local dev deps (pymupdf, reportlab)
├── .env.example                  # Environment variable template
├── globals.css                   # TailwindCSS source
├── output.css                    # Generated CSS
└── tailwind.config.js            # TailwindCSS configuration
```

## Commands

```bash
# Run the application
python main.py                    # Starts on http://localhost:7860

# Local Vespa setup
bash scripts/setup_local.sh       # Start Vespa container + deploy schemas

# Index PDF documents
python scripts/feed_data.py --sample                   # Sample data
python scripts/feed_data.py --pdf-folder /path/to/pdfs # Custom PDFs
python scripts/feed_data.py --pdf-folder /path --workers 4

# Database ingestion
python scripts/discover_schema.py --format markdown --output schema-report.md
python scripts/ingest_database.py --full
python scripts/ingest_database.py --full --tables photos drawings projects
python scripts/ingest_database.py --full --download-files --file-workers 4
python scripts/ingest_database.py --full --dry-run
python scripts/ingest_database.py --incremental
python scripts/sync_database.py --daemon --interval 300
python scripts/sync_database.py --once

# Testing
pytest tests/
pytest tests/unit/ingestion/
pytest tests/integration/ingestion/

# Linting
ruff check .
ruff check --fix .

# CSS (if modifying styles)
./tailwindcss -i globals.css -o output.css --watch
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Vespa connection (at least one required)
VESPA_LOCAL_URL=http://localhost:8080          # Local Vespa
VESPA_DATA_DIR=/mnt/vespa-storage             # Storage path for Docker volume
# VESPA_APP_TOKEN_URL=                        # Vespa Cloud token auth
# VESPA_CLOUD_SECRET_TOKEN=
# USE_MTLS=true                               # Vespa Cloud mTLS auth
# VESPA_APP_MTLS_URL=
# VESPA_CLOUD_MTLS_KEY=
# VESPA_CLOUD_MTLS_CERT=

# Application
GEMINI_API_KEY=                               # Google Gemini for AI chat responses
LOG_LEVEL=INFO                                # DEBUG, INFO, WARNING, ERROR
HOT_RELOAD=False                              # Dev hot reload

# Database ingestion (optional)
PROCORE_DATABASE_URL=postgresql://user:pass@host:5432/procore_int_v2

# AWS S3 for file downloads (optional)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1
S3_BUCKET=procore-integration-files
```

## Architecture

### Search Pipeline

1. **Query** → `main.py` receives search request with query text and ranking mode
2. **Embedding** → `SimMapGenerator.get_query_embeddings_and_token_map()` generates ColQwen2.5 query embeddings
3. **Vespa Search** → `VespaQueryClient.get_result_from_query()` sends embeddings to Vespa
4. **Reranking** → `rerank.py` performs application-level MaxSim reranking (binary → float)
5. **Results** → Top results returned with images and metadata
6. **Sim Maps** → Generated asynchronously in background thread, polled by frontend

### Ranking Profiles (pdf_page schema)

- `bm25` — Traditional keyword search on title + text
- `colpali` — MaxSim visual similarity (binary first pass, float rerank)
- `hybrid` — Combined ColPali + BM25 (text boosted 2x)
- `*_sim` variants — Same as above but return per-token similarity features for visualization

### Vespa Connection Modes

`VespaQueryClient` supports three connection strategies (checked in order):
1. **Local** — `VESPA_LOCAL_URL` env var, no auth
2. **mTLS** — Certificate-based auth to Vespa Cloud
3. **Token** — Secret token auth to Vespa Cloud

### Embedding Models

Configured in `backend/models/config.py`:
- `colpali` — `vidore/colpali-v1.2` (128-dim, 1024 max visual tokens)
- `colqwen3` — `tsystems/colqwen2.5-3b-multilingual-v1.0` (128-dim, 768 max tokens) — **currently active**

### PDF Ingestion Pipeline (`backend/ingest.py`)

1. Validate PDF integrity with PyMuPDF
2. Extract page images at configurable DPI
3. Generate ColPali embeddings per page (patch-level)
4. Encode images as base64 (blur + full quality)
5. Feed to Vespa `pdf_page` schema with all metadata

### Frontend Stack

- **FastHTML** — Python-native HTML components (no JS framework)
- **HTMX** — Dynamic updates, SSE streaming, polling
- **shad4fast** — ShadCN UI components (Button, Input, Badge, etc.)
- **lucide-fasthtml** — Icon library
- **TailwindCSS** — Styling (pre-compiled, no build step needed for dev)
- **Awesomplete** — Search autocomplete
- **OverlayScrollbars** — Custom scrollbar styling

### AI Chat (Gemini Integration)

The sidebar chat uses Google Gemini 2.5 Flash to answer questions about search results:
- Streams responses via SSE (`/get-message` endpoint)
- Sends top 3 result images to Gemini as context
- HTML-formatted responses rendered in the sidebar

## Vespa Schemas

### pdf_page.sd (Primary)

Core document storage for visual retrieval:
- `embedding`: Binary int8 tensor `(patch{}, v[16])` — 128-bit Hamming, HNSW indexed
- `embedding_float`: Float tensor `(patch{}, v[128])` — full precision for reranking
- `blur_image` / `full_image`: Base64 encoded page images
- `text`, `title`, `snippet`: Searchable text fields
- `queries`, `questions`, `tags`: Metadata arrays

### procore_record.sd

Database records with navigation metadata:
- `relationships`: JSON array `{target_doc_id, target_table, direction, cardinality}`
- `file_references`: JSON array `{s3_key, source_column, reference_type, provenance}`
- `incoming_relationships`: Reverse traversal hints
- `content_text`: BM25-searchable content
- Ranking: `default` (BM25), `freshness` (BM25 + recency boost)

### procore_schema_metadata.sd

Schema metadata for agent navigation:
- `metadata_type`: `"full_schema"` or `"table"`
- `columns`, `outgoing_relationships`, `incoming_relationships`
- `timestamp_columns`, `file_reference_columns`

## Code Conventions

- **Python 3.11+** (uses modern type hints, dataclasses, async/await)
- **Async**: Database and Vespa operations use `asyncio` / `asyncpg`
- **Logging**: Use `logging.getLogger("vespa_app")` pattern; level controlled via `LOG_LEVEL` env
- **Error handling**: Custom exceptions in `backend/ingestion/exceptions.py`
- **Testing**: `pytest` with `pytest-asyncio`; fixtures in `tests/conftest.py`
- **Linting**: `ruff` for Python linting and formatting
- **No JS build step**: TailwindCSS is pre-compiled; JavaScript is vanilla (no bundler)

## Docker Setup

```bash
docker-compose up -d              # Start Vespa container
# Ports: 8080 (Query/Feed API), 19071 (Config server)
# Health check: curl http://localhost:19071/state/v1/health
# Deploy schemas: vespa deploy vespa-app -t http://localhost:19071
```

Vespa requires significant startup time (~1-2 minutes on first run) and disk space for indexing.
