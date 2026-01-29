# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Visual document retrieval system combining ColPali (vision-language model) embeddings with Vespa search. Users upload PDFs or search existing documents using text queries matched against visual page embeddings. An AI chat sidebar provides natural language answers grounded in search results. A multi-step agent can iteratively search and reason over documents.

**Tech stack:** Python 3.12, Starlette (JSON API backend), Next.js 16/React 19 (frontend), ColQwen2.5 (colpali-engine), Vespa 8, PyMuPDF, TypeScript.

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
ruff format .                                     # Format code

# Database ingestion (Procore PostgreSQL)
python scripts/ingest_database.py --full          # Full ingestion
python scripts/ingest_database.py --incremental   # Incremental sync
python scripts/sync_database.py --daemon          # Continuous sync daemon
```

### Slash Commands

Development slash commands are defined in `.claude/commands/`. Key ones:

- **`/check`** — Run full code quality checks (lint + tests), fail-fast, logs to `logs/check.log`
- **`/lint`** — Run ruff linter with full context, logs to `logs/lint.log`
- **`/lint-fix`** — Auto-fix linting issues with `ruff check --fix` + `ruff format`, logs to `logs/lint-fix.log`
- **`/test`** — Run pytest with `-v -x --tb=short`, supports `-k` pattern matching, logs to `logs/test.log`
- **`/server`** — Start backend dev server in background (port 7860), pre-flight checks for Vespa/port availability, logs to `logs/server.log`
- **`/debug`** — Search git branches for existing fixes to similar issues

All slash commands detect and activate the virtual environment (`venv/`, `.venv/`, or `env/`), log output to `logs/`, and use the Read tool to check results (preserving context window).

SpecKit workflow commands (`/speckit.*`) are also available for feature specification and planning. Feature specs live in the `specs/` directory.

## Architecture

### Request Flow

```
Browser → Next.js (web/) → JSON API routes → Starlette (main.py)
  ├── SimMapGenerator (colpali.py) → ColQwen2.5 model → query embeddings
  ├── VespaQueryClient (vespa_app.py) → Vespa (HNSW + BM25)
  ├── rerank.py → application-level MaxSim reranking (NumPy)
  ├── LLM chat → streaming SSE via OpenAI-compatible API
  └── AgentSession (agent.py) → multi-step function-calling reasoning loop
```

### Key Modules

**`main.py`** — Starlette ASGI app entry point. Pure JSON API backend — all routes return `JSONResponse` or `StreamingResponse` (SSE). Initializes singletons on startup: `VespaQueryClient`, `SimMapGenerator` (loaded in background thread), `ThreadPoolExecutor`. Contains `message_generator()` for SSE chat streaming via httpx. Key API routes: `/api/search`, `/api/visual-search`, `/api/upload`, `/api/sim-map`, `/api/synthesize`, `/get-message`.

**`backend/config.py`** — Centralized configuration loader. Reads non-sensitive config from `ki55.toml` at import time. Provides `get(*keys)` for nested TOML traversal (e.g., `get("llm", "chat_model")`), `require_env()` for mandatory env vars, and `get_env()` for optional ones. All config access across the codebase goes through this module.

**`backend/llm_config.py`** — LLM provider configuration. `resolve_llm_config()` returns `(base_url, api_key)` — `LLM_BASE_URL` is required (no fallback). Also provides `get_chat_model()`, `is_remote_api()`, and `build_auth_headers()`. Used by `main.py`, `backend/agent.py`, and `backend/drawing_regions.py`.

**`backend/vespa_app.py`** — `VespaQueryClient` class. Three connection modes (local, mTLS, token). Query dispatching for bm25, colpali, and hybrid ranking. Handles tensor format conversions between Python/NumPy and Vespa's block format. Key methods: `get_result_from_query()`, `query_vespa_colpali()`, `query_vespa_bm25()`, `get_sim_maps_from_query()`.

**`backend/colpali.py`** — `SimMapGenerator` class. Loads the ColQwen2.5 model (`tsystems/colqwen2.5-3b-multilingual-v1.0`) with bfloat16. Query embeddings cached via `@lru_cache(maxsize=128)`. Generates similarity map heatmaps by blending viridis colormaps onto page images. CPU-bound inference runs in ThreadPoolExecutor.

**`backend/ingest.py`** — PDF ingestion pipeline. Validates → renders pages at 150 DPI (PyMuPDF) → extracts text → generates embeddings (binary int8 + float f32) → creates blur previews → feeds to Vespa. Supports region detection for large-format drawings (>2.8M pixels).

**`backend/drawing_regions.py`** — Region detection for large architectural/construction drawings. Two strategies: heuristic (whitespace-based grid segmentation) and VLM-assisted (sends image to LLM for semantic bounding boxes). Falls back to tiling if heuristic finds <2 regions. Each region becomes a separate Vespa document linked to its parent page.

**`backend/rerank.py`** — Application-level MaxSim reranking using float embeddings fetched from Vespa. Prefers float precision, falls back to unpacking binary embeddings.

**`backend/llm_rerank.py`** — Optional LLM-based semantic reranking. Uses the configured LLM as a cross-encoder to jointly read query and document content and score relevance. Runs after MaxSim reranking when enabled via `llm.llm_rerank_enabled` in `ki55.toml` (default: disabled).

**`backend/agent.py`** — `AgentSession` for multi-step document reasoning via OpenAI-compatible function calling. Three tools: `search_documents`, `get_page_text`, `provide_answer`. Loops up to 5 steps. Streams reasoning steps as SSE events.

**`backend/models/config.py`** — Model registry. Loads model definitions from `ki55.toml` `[colpali.models.*]` sections. Two models: `colpali` (vidore/colpali-v1.2) and `colqwen3` (tsystems/colqwen2.5-3b-multilingual-v1.0, active default). Both use 128-dim embeddings.

**`backend/ingestion/`** — Procore PostgreSQL ingestion subsystem. Auto-discovers schema, transforms rows to Vespa documents with relationship/navigation metadata, detects and downloads S3/URL file references, supports incremental sync via SQLite-backed change tracking.

**`web/`** — Next.js 16/React 19 frontend (TypeScript). Primary UI for the application. Runs on port 3000 (`npm run dev`). Consumes JSON APIs from `main.py`. Key features: visual search with multi-select synthesis, similarity map viewer, document upload, streaming AI chat. See `web/CLAUDE.md` for detailed frontend documentation.

### Embedding & Ranking Pipeline

Two embedding representations stored in Vespa:
- **Binary:** `tensor<int8>(patch{}, v[16])` — 128 bits packed via `np.packbits`, HNSW-indexed (Hamming distance)
- **Float:** `tensor<float>(patch{}, v[128])` — full precision, attribute-only (no index)

Ranking phases:
1. **Retrieval:** HNSW nearest neighbor on binary embeddings
2. **First-phase:** MaxSim with binary embeddings (all candidates)
3. **Second-phase:** MaxSim with float embeddings (top 10)
4. **Optional app-level rerank:** Full MaxSim in Python/NumPy (`backend/rerank.py`)
5. **Optional LLM rerank:** Semantic cross-encoder scoring via LLM (`backend/llm_rerank.py`, disabled by default)

Ranking profiles in `vespa-app/schemas/pdf_page.sd`: `unranked`, `bm25`, `colpali`, `hybrid`, and `*_sim` variants (same logic + similarity map tensors).

### Configuration Architecture

Non-sensitive config lives in **`ki55.toml`** (required at startup). All sections: `[app]`, `[llm]`, `[vespa]`, `[colpali]`, `[search]`, `[image]`, `[agent]`, `[drawing_regions]`, `[ingestion]`, `[autocomplete]`. Sensitive values (API keys, database URLs) stay in `.env`. Access both via `backend/config.py`.

### LLM Provider Configuration

All LLM/AI calls go through a single OpenAI-compatible API abstraction (`resolve_llm_config()` in `backend/llm_config.py`):

- **`LLM_BASE_URL`** — Required in `.env`. No fallback URLs. Set to `https://openrouter.ai/api/v1`, `https://api.openai.com/v1`, `http://localhost:11434/v1` (Ollama), etc.
- **API key** — `OPENROUTER_API_KEY` or `OPENAI_API_KEY` from `.env` (optional for local providers).
- **Chat model** — Set via `llm.chat_model` in `ki55.toml` (default: `google/gemini-2.5-flash`).
- **VLM model** — Set via `llm.vlm_model` in `ki55.toml` (used for drawing region classification).

### Vespa Schemas

- **`pdf_page.sd`** — Main document schema: embeddings (binary + float), text fields (title, text, snippet, tags with BM25), images (blur + full as base64). Region documents link back via `parent_doc_id`.
- **`procore_record.sd`** — Database records with relationship navigation metadata, file references, schema context for agents.
- **`procore_schema_metadata.sd`** — Schema metadata for agent-assisted navigation.

## Code Conventions

- Async for I/O-bound work (Vespa queries, HTTP, asyncpg). Sync for CPU-bound work (model inference via `ThreadPoolExecutor`).
- Dependencies pinned via `uv pip compile` → `requirements.txt`. Local dev deps in `requirements-local.txt`.
- Logging via stdlib `logging` (not loguru). Non-sensitive config in `ki55.toml` via `backend/config.py`; secrets in `.env` via `python-dotenv`.
- No ORM — raw asyncpg with parameterized queries for Procore DB.
- Vespa documents fed via pyvespa client library.
- Git LFS for large binaries (model weights, demo images) — see `.gitattributes`.
- Backend helpers are snake_case; frontend components are PascalCase.
- Starlette routes defined via `Route()` list — all return JSON or SSE streams.
- Ruff uses default config — no `pyproject.toml` or `ruff.toml` customization.
- No CI/CD pipelines — testing and linting run via slash commands or manually.

### Testing Conventions

- pytest with pytest-asyncio for async tests.
- Preferred flags: `pytest -v -x --tb=short` (verbose, fail on first error, short tracebacks).
- `tests/conftest.py` provides shared fixtures: `mock_vespa_client`, `mock_db_connection`, `sample_record`, `sample_table_columns`, `sample_jsonb_attachments`, `test_data_dir`, `database_url`, `vespa_url`.
- Integration tests require running Vespa and/or database services.

## Environment Variables

Copy `.env.example` to `.env`. Only sensitive/secret values go here; everything else is in `ki55.toml`.

- **Required:** `LLM_BASE_URL` (OpenAI-compatible endpoint), plus `OPENROUTER_API_KEY` or `OPENAI_API_KEY` (for remote providers)
- **Vespa:** `VESPA_LOCAL_URL` (default `http://localhost:8080`), or cloud auth via `VESPA_CLOUD_SECRET_TOKEN` / mTLS certs
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
python main.py                                    # Backend API: http://localhost:7860

# Frontend (separate terminal)
cd web && npm install && npm run dev              # Next.js: http://localhost:3000
```

Docker ports: 8080 (query/feed API), 19071 (config server).

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
