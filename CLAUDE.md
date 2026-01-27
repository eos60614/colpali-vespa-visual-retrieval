# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Visual document retrieval system combining ColPali (vision-language model) embeddings with Vespa search. Users upload PDFs or search existing documents using text queries matched against visual page embeddings. An AI chat sidebar provides natural language answers grounded in search results. A multi-step agent can iteratively search and reason over documents.

**Tech stack:** Python 3.12, FastHTML, HTMX, ColQwen2.5 (colpali-engine), Vespa 8, PyMuPDF, Tailwind CSS.

## Commands

```bash
# Run the app
python main.py                                    # http://localhost:7860

# Vespa
docker-compose up -d                              # Start Vespa container
vespa deploy vespa-app -t http://localhost:19071   # Deploy schemas
./scripts/setup_local.sh                          # Or: automated Docker + deploy

# Index data
python scripts/feed_data.py --sample              # Sample PDFs
python scripts/feed_data.py --pdf-folder /path    # Custom PDFs

# Testing
pytest tests/                                     # All tests
pytest tests/unit/                                # Unit tests only
pytest tests/integration/                         # Integration tests (require running services)
pytest -v -x --tb=short tests/                    # Verbose, fail-fast (project convention)
pytest -k "test_ingest" tests/                    # Run tests matching pattern

# Linting
ruff check .                                      # Lint
ruff check --fix .                                # Auto-fix

# Database ingestion (Procore PostgreSQL)
python scripts/ingest_database.py --full          # Full ingestion
python scripts/ingest_database.py --incremental   # Incremental sync
python scripts/sync_database.py --daemon          # Continuous sync daemon
```

## Architecture

### Request Flow

```
Browser → HTMX requests → FastHTML (main.py)
  ├── SimMapGenerator (colpali.py) → ColQwen2.5 model → query embeddings
  ├── VespaQueryClient (vespa_app.py) → Vespa (HNSW + BM25)
  ├── rerank.py → application-level MaxSim reranking (NumPy)
  ├── LLM chat → streaming SSE via OpenAI-compatible API
  └── AgentSession (agent.py) → multi-step function-calling reasoning loop
```

### Key Modules

**`main.py`** — FastHTML app entry point. All routes defined here. Initializes singletons on startup: `VespaQueryClient`, `SimMapGenerator` (loaded in background thread), `ThreadPoolExecutor`. Contains `_resolve_llm_config()` for LLM provider selection and `message_generator()` for SSE chat streaming via httpx.

**`backend/vespa_app.py`** — `VespaQueryClient` class. Three connection modes (local, mTLS, token). Query dispatching for bm25, colpali, and hybrid ranking. Handles tensor format conversions between Python/NumPy and Vespa's block format. Key methods: `get_result_from_query()`, `query_vespa_colpali()`, `query_vespa_bm25()`, `get_sim_maps_from_query()`.

**`backend/colpali.py`** — `SimMapGenerator` class. Loads the ColQwen2.5 model (`tsystems/colqwen2.5-3b-multilingual-v1.0`) with bfloat16. Query embeddings cached via `@lru_cache(maxsize=128)`. Generates similarity map heatmaps by blending viridis colormaps onto page images. CPU-bound inference runs in ThreadPoolExecutor.

**`backend/ingest.py`** — PDF ingestion pipeline. Validates → renders pages at 150 DPI (PyMuPDF) → extracts text → generates embeddings (binary int8 + float f32) → creates blur previews → feeds to Vespa. Supports region detection for large-format drawings (>2.8M pixels).

**`backend/drawing_regions.py`** — Region detection for large architectural/construction drawings. Two strategies: heuristic (whitespace-based grid segmentation) and VLM-assisted (sends image to LLM for semantic bounding boxes). Falls back to tiling if heuristic finds <2 regions. Each region becomes a separate Vespa document linked to its parent page.

**`backend/rerank.py`** — Application-level MaxSim reranking using float embeddings fetched from Vespa. Prefers float precision, falls back to unpacking binary embeddings.

**`backend/agent.py`** — `AgentSession` for multi-step document reasoning via OpenAI-compatible function calling. Three tools: `search_documents`, `get_page_text`, `provide_answer`. Loops up to 5 steps. Streams reasoning steps as SSE events. **Note:** imports from `backend.llm_config` which does not yet exist — this module needs to be created to extract LLM config functions from main.py.

**`backend/ingestion/`** — Procore PostgreSQL ingestion subsystem. Auto-discovers schema, transforms rows to Vespa documents with relationship/navigation metadata, detects and downloads S3/URL file references, supports incremental sync via SQLite-backed change tracking.

**`frontend/app.py`** — All UI components as PascalCase functions returning FastHTML elements. Key components: `Home`, `Search`, `SearchResult`, `ChatResult`, `UploadPage`, `SimMapButtonPoll`/`SimMapButtonReady`.

**`frontend/layout.py`** — Page layout template, responsive grid JS (1-col mobile, 2-col desktop at 45fr/15fr), scrollbar initialization, theme toggle.

### Embedding & Ranking Pipeline

Two embedding representations stored in Vespa:
- **Binary:** `tensor<int8>(patch{}, v[16])` — 128 bits packed via `np.packbits`, HNSW-indexed (Hamming distance)
- **Float:** `tensor<float>(patch{}, v[128])` — full precision, attribute-only (no index)

Ranking phases:
1. **Retrieval:** HNSW nearest neighbor on binary embeddings
2. **First-phase:** MaxSim with binary embeddings (all candidates)
3. **Second-phase:** MaxSim with float embeddings (top 10)
4. **Optional app-level rerank:** Full MaxSim in Python/NumPy (`backend/rerank.py`)

Ranking profiles in `vespa-app/schemas/pdf_page.sd`: `unranked`, `bm25`, `colpali`, `hybrid`, and `*_sim` variants (same logic + similarity map tensors).

### LLM Provider Configuration

All LLM/AI calls go through a single OpenAI-compatible API abstraction (`_resolve_llm_config()` in main.py):

| Priority | Provider | Base URL | API Key Env Var |
|----------|----------|----------|-----------------|
| 1 | Explicit | `LLM_BASE_URL` | `OPENROUTER_API_KEY` or `OPENAI_API_KEY` |
| 2 | OpenAI direct | `https://api.openai.com/v1` | `OPENAI_API_KEY` (when no OPENROUTER key) |
| 3 | OpenRouter (default) | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` |
| 4 | Local Ollama | `LLM_BASE_URL=http://localhost:11434/v1` | none |

Chat model set via `CHAT_MODEL` env var (default: `google/gemini-2.5-flash`).

### Vespa Schemas

- **`pdf_page.sd`** — Main document schema: embeddings (binary + float), text fields (title, text, snippet, tags with BM25), images (blur + full as base64). Region documents link back via `parent_doc_id`.
- **`procore_record.sd`** — Database records with relationship navigation metadata, file references, schema context for agents.
- **`procore_schema_metadata.sd`** — Schema metadata for agent-assisted navigation.

## Code Conventions

- Async for I/O-bound work (Vespa queries, HTTP, asyncpg). Sync for CPU-bound work (model inference via `ThreadPoolExecutor`).
- Dependencies pinned via `uv pip compile` → `requirements.txt`. Local dev deps in `requirements-local.txt`.
- Logging via stdlib `logging` (not loguru). Environment config via `python-dotenv`.
- No ORM — raw asyncpg with parameterized queries for Procore DB.
- Vespa documents fed via pyvespa client library.
- Git LFS for large binaries — see `.gitattributes`.
- Frontend components are PascalCase functions; backend helpers are snake_case.
- FastHTML routes use `@rt()` decorator for GET/POST, `@app.get()` for explicit GET.

## Environment Variables

Copy `.env.example` to `.env`. Key groups:

- **Vespa:** `VESPA_LOCAL_URL` (default `http://localhost:8080`), or cloud auth via `VESPA_CLOUD_SECRET_TOKEN` / mTLS certs
- **LLM:** `LLM_BASE_URL`, `OPENROUTER_API_KEY` or `OPENAI_API_KEY`, `CHAT_MODEL`
- **App:** `LOG_LEVEL`, `HOT_RELOAD`
- **Procore DB (optional):** `PROCORE_DATABASE_URL`
- **AWS S3 (optional):** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET`

## Local Development Setup

```bash
docker-compose up -d                              # Start Vespa (~8GB RAM needed)
vespa deploy vespa-app -t http://localhost:19071   # Deploy schemas
pip install -r requirements.txt
pip install -r requirements-local.txt              # ruff, pymupdf, reportlab
python -m spacy download en_core_web_sm
cp .env.example .env                              # Configure LLM provider
python scripts/feed_data.py --sample              # Index sample data
python main.py                                    # http://localhost:7860
```

Docker ports: 8080 (query/feed API), 19071 (config server).

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
