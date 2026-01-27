# ColPali-Vespa Visual Retrieval

Development guidelines for AI assistants working on this codebase.

## Overview

Visual document retrieval system combining ColPali (vision-language model) embeddings with Vespa search. Users upload PDFs or search existing documents using text queries that match against visual page embeddings. An AI chat sidebar (Google Gemini) provides natural language answers grounded in search results.

**Tech stack:** Python 3.12, FastHTML, HTMX, ColQwen2.5 (colpali-engine), Vespa 8, PyMuPDF, Google Gemini, Tailwind CSS.

## Project Structure

```
colpali-vespa-visual-retrieval/
├── main.py                        # FastHTML app entry point, all routes
├── icons.py                       # SVG icon definitions
├── globals.css / output.css       # Tailwind CSS
├── tailwind.config.js             # Tailwind configuration
├── docker-compose.yml             # Vespa container setup
├── requirements.txt               # Pinned deps (uv pip compile output)
├── requirements-local.txt         # Local dev deps (ruff, pymupdf, reportlab)
├── .env.example                   # Environment variable template
├── SETUP_LOCAL.md                 # Local Vespa setup guide with troubleshooting
├── .gitattributes                 # Git LFS config for large files
│
├── backend/
│   ├── vespa_app.py               # VespaQueryClient: query execution, ranking, connection
│   ├── colpali.py                 # SimMapGenerator: embeddings, similarity map heatmaps
│   ├── ingest.py                  # PDF ingestion pipeline (validate, render, embed, feed)
│   ├── rerank.py                  # Application-level MaxSim reranking
│   ├── cache.py                   # Simple LRU cache
│   ├── stopwords.py               # spaCy-based stopword filtering
│   ├── testquery.py               # Test query utility
│   ├── models/
│   │   └── config.py              # ModelConfig dataclass and model registry
│   └── ingestion/                 # Procore database ingestion subsystem
│       ├── db_connection.py       # Async PostgreSQL connection pooling (asyncpg)
│       ├── schema_discovery.py    # Auto-discover DB schema, relationships, file refs
│       ├── record_ingester.py     # Transform DB records to Vespa documents
│       ├── file_detector.py       # Detect S3/URL file references in columns
│       ├── file_downloader.py     # Async S3/URL file downloads
│       ├── change_detector.py     # Row-level change tracking for incremental sync
│       ├── sync_manager.py        # Sync orchestration and scheduling
│       ├── checkpoint.py          # Persist sync state for resumable ingestion (SQLite)
│       ├── pdf_processor.py       # PDF processing with lazy-loaded ColPali model
│       └── exceptions.py          # Custom exception hierarchy
│
├── frontend/
│   ├── app.py                     # All UI components (Home, Search, Upload, Chat, etc.)
│   └── layout.py                  # Layout templates and JS helpers
│
├── scripts/
│   ├── feed_data.py               # Batch PDF indexing (--sample or --pdf-folder)
│   ├── discover_schema.py         # DB schema discovery CLI
│   ├── ingest_database.py         # Full/incremental DB ingestion CLI
│   ├── sync_database.py           # Continuous sync daemon CLI
│   ├── ingest_colqwen3_embeddings.py  # ColQwen3 embedding generation
│   ├── reingest_single_file_colqwen3.py # Re-ingest single file
│   ├── ingest_sample.py           # Sample data generation
│   ├── test_connections.py        # Validate DB and Vespa connectivity
│   ├── test_ingestion.py          # Ingestion integration tests
│   ├── test_e2e_file_ingestion.py # End-to-end file tests
│   ├── test_real_ingestion.py     # Real database integration tests
│   ├── setup_local.sh             # Automated Docker + Vespa deployment
│   └── sync_cron.sh               # Cron wrapper for incremental sync with PDF processing
│
├── tests/
│   ├── conftest.py                # Shared pytest fixtures
│   ├── unit/ingestion/            # Unit tests
│   └── integration/ingestion/     # Integration tests
│
├── vespa-app/                     # Vespa application package
│   ├── schemas/
│   │   ├── pdf_page.sd            # PDF page schema (embeddings, BM25, HNSW)
│   │   ├── procore_record.sd      # Database record schema
│   │   └── procore_schema_metadata.sd  # Schema metadata for agent navigation
│   ├── services.xml               # Vespa services config
│   ├── hosts.xml                  # Vespa cluster config
│   └── validation-overrides.xml   # Schema validation overrides
│
├── static/
│   ├── js/                        # Client-side JavaScript (highlightjs-theme.js)
│   ├── img/                       # Static images (logos, architecture diagrams)
│   ├── full_images/               # (Generated) cached full-res page images (LFS)
│   └── sim_maps/                  # (Generated) similarity map overlays
│
├── specs/                         # Feature specification documents
│   ├── 001-colqwen3-model/
│   ├── 001-procore-db-ingestion/
│   └── 002-file-upload-ingest/
│
├── .claude/                       # Claude IDE slash commands
│   └── commands/
│       ├── check.md               # Full code quality check (lint + tests)
│       ├── debug.md               # Debugging assistance
│       ├── lint.md                # Run ruff linter
│       ├── lint-fix.md            # Auto-fix lint issues
│       ├── server.md              # Start FastHTML dev server
│       ├── test.md                # Run pytest suite
│       └── speckit.*.md           # Speckit feature workflow commands
│
└── .specify/                      # Speckit specification tooling
    ├── memory/constitution.md     # Project constitution template
    ├── scripts/bash/              # Setup and feature automation scripts
    └── templates/                 # Spec, plan, checklist, tasks templates
```

## Commands

### Run the application

```bash
python main.py                     # Starts on http://localhost:7860
```

### Vespa

```bash
docker-compose up -d               # Start Vespa container
vespa deploy vespa-app -t http://localhost:19071  # Deploy schemas
```

Or use the automated setup script:
```bash
./scripts/setup_local.sh           # Docker + schema deployment in one step
```

### Index data

```bash
python scripts/feed_data.py --sample                    # Index sample PDFs
python scripts/feed_data.py --pdf-folder /path/to/pdfs  # Index custom PDFs
python scripts/feed_data.py --pdf-folder /path --workers 20  # Parallel
```

### Database ingestion

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
python scripts/sync_database.py --daemon
python scripts/sync_database.py --daemon --interval 300
python scripts/sync_database.py --once
python scripts/sync_database.py --status

# Cron-based sync (with PDF processing and file downloads)
./scripts/sync_cron.sh             # Single run with lock file, logging, and PDF processing
```

### Testing and linting

```bash
pytest tests/                      # All tests
pytest tests/unit/                 # Unit tests only
pytest tests/integration/          # Integration tests only
ruff check .                       # Lint
ruff check --fix .                 # Auto-fix lint issues
```

### Claude IDE slash commands

These are defined in `.claude/commands/` and can be invoked in Claude Code:

| Command | Purpose |
|---------|---------|
| `/check` | Full code quality check (lint + tests), fail-fast |
| `/test` | Run pytest with verbose output, optional path/filter args |
| `/lint` | Run ruff linter with full output |
| `/lint-fix` | Auto-fix lint issues with ruff |
| `/server` | Start FastHTML dev server (background, with logging) |
| `/debug` | Debugging assistance |
| `/speckit.*` | Feature specification workflow (analyze, specify, plan, tasks, implement, checklist, etc.) |

## Environment Variables

Copy `.env.example` to `.env`. Key variables:

```bash
# Vespa (local dev - no auth needed)
VESPA_LOCAL_URL=http://localhost:8080
VESPA_DATA_DIR=/mnt/vespa-storage

# Vespa Cloud (production - pick one auth method)
# VESPA_APP_TOKEN_URL=https://your-app.vespa-cloud.com
# VESPA_CLOUD_SECRET_TOKEN=your-token
# USE_MTLS=true
# VESPA_APP_MTLS_URL=https://...
# VESPA_CLOUD_MTLS_KEY=...
# VESPA_CLOUD_MTLS_CERT=...

# AI chat (optional)
GEMINI_API_KEY=your-gemini-api-key

# App settings
LOG_LEVEL=INFO                     # DEBUG|INFO|WARNING|ERROR
HOT_RELOAD=False

# Procore database (optional)
PROCORE_DATABASE_URL=postgresql://user:pass@host:5432/procore_int_v2

# AWS S3 (optional, for direct file access)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
S3_BUCKET=procore-integration-files
```

## Architecture

### Request flow

```
Browser (localhost:7860)
    ↓ HTMX requests
FastHTML App (main.py)
    ├── SimMapGenerator (colpali.py) → ColQwen2.5 model → query embeddings
    ├── VespaQueryClient (vespa_app.py) → Vespa search (HNSW + BM25)
    ├── rerank.py → application-level MaxSim reranking
    └── Gemini API → streaming AI chat responses (SSE)
```

### Key routes (main.py)

| Route | Method | Purpose |
|-------|--------|---------|
| `/` | GET | Home page |
| `/search` | GET | Search interface with query + ranking |
| `/fetch_results` | GET | HTMX endpoint for search results |
| `/upload` | GET | PDF upload page |
| `/upload` | POST | Handle PDF file upload and ingestion (250MB max) |
| `/get_sim_map` | GET | Poll for similarity map readiness |
| `/full_image` | GET | Full-res image (cached to disk) |
| `/suggestions` | GET | Autocomplete suggestions |
| `/get-message` | GET | SSE streaming Gemini chat response |
| `/about-this-demo` | GET | Demo information |
| `/app` | GET | Vespa connection status page |
| `/static/{filepath}` | GET | Static file serving |

### Embedding model

Active model: **ColQwen2.5** (`tsystems/colqwen2.5-3b-multilingual-v1.0`)
- Embedding dimension: 128 per patch
- Max visual tokens: 768
- Binary quantization: 128 bits packed into 16 int8 values for HNSW

Model registry is in `backend/models/config.py`. Two models defined: `colpali` (vidore/colpali-v1.2) and `colqwen3` (tsystems/colqwen2.5-3b-multilingual-v1.0). Use `get_model_config(id)` to retrieve and `get_available_models()` to list.

### Ranking pipeline (Vespa)

1. **Retrieval**: HNSW nearest neighbor on binary embeddings (Hamming distance)
2. **First-phase**: MaxSim with binary embeddings (all candidates)
3. **Second-phase**: MaxSim with float embeddings (top 10 reranked)

Available ranking profiles in `pdf_page.sd`:
- `unranked` - no ranking
- `bm25` - text only (`bm25(title) + bm25(text)`)
- `colpali` - visual only (binary first-phase, float second-phase)
- `hybrid` - combined (`max_sim + 2 * (bm25(text) + bm25(title) + bm25(tags))`)
- `*_sim` variants - same logic plus similarity map tensors in summary features

Application-level reranking (`backend/rerank.py`) uses full float embeddings fetched from Vespa to compute MaxSim scores in Python/NumPy.

### Vespa schemas

**`pdf_page.sd`** - Main document schema:
- `embedding`: `tensor<int8>(patch{}, v[16])` - binary, HNSW indexed
- `embedding_float`: `tensor<float>(patch{}, v[128])` - full precision, attribute only
- Text fields: `title`, `text`, `snippet`, `tags` (BM25 indexed)
- Images: `blur_image`, `full_image` (raw base64)

**`procore_record.sd`** - Database records with navigation metadata:
- `relationships`: JSON array of outgoing relationship links
- `file_references`: JSON array with S3 keys, source columns, provenance
- `incoming_relationships`: reverse navigation hints
- `table_description`, `column_types`: schema context for agents
- Ranking: `bm25` on `content_text`, `freshness` variant

**`procore_schema_metadata.sd`** - Schema metadata for agent reference:
- `metadata_type`: "full_schema" or "table"
- `columns`, `outgoing_relationships`, `incoming_relationships`
- `file_reference_columns`, `timestamp_columns`
- Ranking: BM25 on `content_text` + `table_description`

### PDF ingestion flow (backend/ingest.py)

1. Validate PDF (encrypted? page count?)
2. Render pages to PIL images at 150 DPI via PyMuPDF
3. Extract and sanitize text per page
4. Generate ColPali embeddings (binary int8 + float f32)
5. Create blur preview images
6. Feed documents to Vespa `pdf_page` schema

### Database ingestion subsystem (backend/ingestion/)

For Procore PostgreSQL integration:
1. `schema_discovery.py` - auto-discovers tables, columns, relationships, file references
2. `record_ingester.py` - transforms rows into Vespa documents with navigation metadata
3. `file_detector.py` / `file_downloader.py` - detects and downloads S3/URL file references
4. `change_detector.py` / `checkpoint.py` - enables incremental sync (SQLite-backed)
5. `sync_manager.py` - orchestrates full and incremental ingestion cycles
6. `pdf_processor.py` - processes downloaded PDFs with lazy-loaded ColPali model
7. `exceptions.py` - custom exception hierarchy (ConnectionError, SchemaError, TransformError, IndexError, DownloadError)

### Frontend

- **Framework**: FastHTML with HTMX for dynamic updates (no SPA, no JS framework)
- **Styling**: Tailwind CSS with Shad4Fast (shadcn port)
- **Components** (`frontend/app.py`): `Home`, `Hero`, `SampleQueries`, `Search`, `SearchBox`, `SearchInfo`, `SearchResult`, `ShareButtons`, `UploadPage`, `UploadForm`, `UploadSidebar`, `UploadSuccess`, `UploadError`, `ChatResult`, `SimMapButtonPoll`, `SimMapButtonReady`, `LoadingMessage`, `LoadingSkeleton`, `LinkResource`, `AboutThisDemo`
- **Layout** (`frontend/layout.py`): page template, JS for responsive grid, scrollbars, image swapping, input validation
- **Libraries**: OverlayScrollbars, Awesomplete (autocomplete), HighlightJS, htmx-ext-sse

## Code Conventions

- Python 3.11+ (3.12 for main app)
- Async where I/O-bound (asyncpg, aiohttp, Vespa queries)
- Sync for CPU-bound work (model inference via ThreadPoolExecutor)
- Dependencies pinned via `uv pip compile` output in `requirements.txt`
- Logging via stdlib `logging` module (not loguru in main app)
- Environment config via `python-dotenv`
- No ORM for Procore DB - raw asyncpg with parameterized queries
- Vespa documents fed via pyvespa client library
- Git LFS for large binary files (models, images, archives) - see `.gitattributes`

## Testing

### Structure

```
tests/
├── conftest.py                   # Shared pytest fixtures
├── unit/ingestion/               # Unit tests for ingestion modules
└── integration/ingestion/        # Integration tests (require running services)
```

### Available fixtures (conftest.py)

- `event_loop` - session-scoped asyncio event loop
- `test_data_dir` - temporary directory for test data
- `mock_db_connection` - mock async PostgreSQL connection
- `mock_vespa_client` - mock Vespa client (feed, delete, query)
- `sample_table_columns` - sample column metadata for schema discovery tests
- `sample_record` - sample database record for transformation tests
- `sample_jsonb_attachments` - sample JSONB data for file detection tests
- `database_url` / `vespa_url` - connection URLs from env or defaults

## Tooling

### Speckit (.specify/)

Feature specification tooling for structured feature development. Contains:
- `memory/constitution.md` - project constitution template
- `scripts/bash/` - automation scripts (prerequisites, new feature setup, plan creation)
- `templates/` - templates for specs, plans, checklists, tasks, and agent files

Used via the `speckit.*` Claude IDE commands for feature workflows:
`/speckit.analyze` → `/speckit.specify` → `/speckit.plan` → `/speckit.tasks` → `/speckit.implement`

### Feature specs (specs/)

Each feature has a directory under `specs/` containing:
- `spec.md` - feature specification
- `plan.md` - implementation plan
- `tasks.md` - task breakdown
- `research.md` - research findings
- `data-model.md` - data model design
- `quickstart.md` - getting started guide
- `checklists/requirements.md` - requirements checklist
- `contracts/*.md` - API and interface contracts

## Local Development Setup

```bash
docker-compose up -d                              # Start Vespa
vespa deploy vespa-app -t http://localhost:19071   # Deploy schemas
pip install -r requirements.txt
pip install -r requirements-local.txt
python -m spacy download en_core_web_sm
cp .env.example .env                              # Edit as needed
python scripts/feed_data.py --sample              # Index sample data
python main.py                                    # http://localhost:7860
```

Or use the automated setup script for Docker + Vespa:
```bash
./scripts/setup_local.sh                          # Handles Docker, wait, deploy
```

Vespa needs ~8GB RAM minimum. Docker ports: 8080 (query/feed API), 19071 (config server).

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
