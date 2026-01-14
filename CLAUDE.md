# colpali-procore Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-01-14

## Active Technologies

- Python 3.11+ (matching existing codebase) + asyncpg, boto3, pyvespa (existing), sqlalchemy (metadata reflection) (001-procore-db-ingestion)

## Project Structure

```text
backend/
├── __init__.py
├── vespa_app.py          # Existing Vespa client
├── colpali.py            # Existing ColPali integration
└── ingestion/            # Database ingestion module
    ├── __init__.py
    ├── db_connection.py      # PostgreSQL connection
    ├── schema_discovery.py   # Schema introspection
    ├── record_ingester.py    # Record transformation
    ├── file_detector.py      # S3/file reference detection
    ├── file_downloader.py    # File download
    ├── change_detector.py    # Change detection
    ├── sync_manager.py       # Sync orchestration
    ├── checkpoint.py         # Sync checkpoints
    └── exceptions.py         # Custom exceptions

scripts/
├── feed_data.py          # Existing PDF feeder
├── discover_schema.py    # Schema discovery CLI
├── ingest_database.py    # Full ingestion CLI
└── sync_database.py      # Sync daemon CLI

tests/
├── unit/ingestion/       # Unit tests
├── integration/ingestion/ # Integration tests
└── conftest.py           # Shared fixtures
```

## Commands

```bash
# Schema Discovery
python scripts/discover_schema.py --format markdown --output schema-report.md
python scripts/discover_schema.py --format json --output schema-map.json

# Full Database Ingestion
python scripts/ingest_database.py --full
python scripts/ingest_database.py --full --tables photos drawings projects
python scripts/ingest_database.py --full --exclude _prisma_migrations sync_events
python scripts/ingest_database.py --full --download-files --file-workers 4
python scripts/ingest_database.py --full --dry-run

# Incremental Sync
python scripts/ingest_database.py --incremental

# Sync Daemon
python scripts/sync_database.py --daemon
python scripts/sync_database.py --daemon --interval 300
python scripts/sync_database.py --once
python scripts/sync_database.py --status

# Testing
pytest tests/
ruff check .
```

## Environment Variables

```bash
# Required
PROCORE_DATABASE_URL=postgresql://user:pass@host:5432/procore_int_v2

# Optional
VESPA_LOCAL_URL=http://localhost:8080
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
LOG_LEVEL=INFO
```

## Code Style

Python 3.11+ (matching existing codebase): Follow standard conventions

## Vespa Schemas

```text
vespa-app/schemas/
├── pdf_page.sd                # Existing PDF page schema with ColPali embeddings
├── procore_record.sd          # Database records with navigation metadata
└── procore_schema_metadata.sd # Schema metadata for agent reference
```

### procore_record Fields (Agent Navigation)
- `relationships`: JSON array with target_doc_id, target_table, direction, cardinality
- `file_references`: JSON array with s3_key, source_column, reference_type, provenance
- `incoming_relationships`: JSON array of potential reverse traversal hints
- `table_description`: Human-readable table context for agents
- `column_types`: Type information for field interpretation

### procore_schema_metadata
Navigable schema metadata for agents to understand database structure:
- `metadata_type`: "full_schema" or "table"
- `columns`: Column definitions with types
- `outgoing_relationships`: Links from this table
- `incoming_relationships`: Links to this table

## Recent Changes

- 001-procore-db-ingestion: Added Python 3.11+ (matching existing codebase) + asyncpg, boto3, pyvespa (existing), sqlalchemy (metadata reflection)
- 001-procore-db-ingestion: Implemented User Story 5 - Agent Navigation Metadata with bidirectional relationships, file provenance, and schema metadata indexing

<!-- MANUAL ADDITIONS START -->
<!-- MANUAL ADDITIONS END -->
