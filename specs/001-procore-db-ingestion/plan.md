# Implementation Plan: Procore Database Automatic Ingestion

**Branch**: `001-procore-db-ingestion` | **Date**: 2026-01-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/001-procore-db-ingestion/spec.md`

## Summary

Implement automatic data ingestion from a Procore PostgreSQL database into the existing Vespa visual retrieval system. The feature provides comprehensive schema discovery, full data ingestion with rich metadata, S3/file reference detection and download, change detection for automatic sync, and agent-navigable relationship links. Primary technical approach: Python-based ingestion pipeline using asyncpg for PostgreSQL access, boto3 for S3, and the existing pyvespa client for indexing.

## Technical Context

**Language/Version**: Python 3.11+ (matching existing codebase)
**Primary Dependencies**: asyncpg, boto3, pyvespa (existing), sqlalchemy (metadata reflection)
**Storage**: PostgreSQL (source - read-only), Vespa (target - existing), SQLite (sync checkpoints)
**Testing**: pytest with pytest-asyncio
**Target Platform**: Linux server (existing deployment)
**Project Type**: Single backend service extension
**Performance Goals**: Process 10,000 records per batch, sync latency within configured interval (default 5 minutes)
**Constraints**: Read-only database access, graceful degradation on S3 failures, resumable operations
**Scale/Scope**: All tables in procore_int_v2 database, potentially millions of records

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution is in template form (not yet customized). Applying general best practices:

| Principle | Status | Notes |
|-----------|--------|-------|
| Library-First | PASS | Ingestion module will be standalone, independently testable |
| CLI Interface | PASS | Will expose CLI commands for schema discovery, ingestion, sync |
| Test-First | PASS | Integration tests for DB connection, unit tests for transformations |
| Observability | PASS | Structured logging, progress reporting, error tracking |
| Simplicity | PASS | Single responsibility modules, no premature abstractions |

## Project Structure

### Documentation (this feature)

```text
specs/001-procore-db-ingestion/
├── plan.md              # This file
├── research.md          # Phase 0 output - database investigation findings
├── data-model.md        # Phase 1 output - entity definitions
├── quickstart.md        # Phase 1 output - getting started guide
├── contracts/           # Phase 1 output - API/CLI interface definitions
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── __init__.py          # Existing
├── vespa_app.py         # Existing Vespa client
├── colpali.py           # Existing ColPali integration
├── ingestion/           # NEW - Database ingestion module
│   ├── __init__.py
│   ├── db_connection.py     # PostgreSQL connection management
│   ├── schema_discovery.py  # Schema introspection and documentation
│   ├── record_ingester.py   # Record extraction and transformation
│   ├── file_detector.py     # S3/file reference detection
│   ├── file_downloader.py   # S3 file download and processing
│   ├── change_detector.py   # Change detection logic
│   ├── sync_manager.py      # Orchestrates sync operations
│   └── checkpoint.py        # Sync checkpoint persistence

scripts/
├── feed_data.py         # Existing PDF feeder
├── discover_schema.py   # NEW - Schema discovery CLI
├── ingest_database.py   # NEW - Full ingestion CLI
└── sync_database.py     # NEW - Change sync daemon CLI

tests/
├── unit/
│   └── ingestion/
│       ├── test_schema_discovery.py
│       ├── test_file_detector.py
│       └── test_change_detector.py
├── integration/
│   └── ingestion/
│       ├── test_db_connection.py
│       └── test_vespa_indexing.py
└── conftest.py
```

**Structure Decision**: Extends existing backend/ directory with new ingestion/ submodule. Scripts follow existing pattern (scripts/feed_data.py). New tests/ directory for organized testing.

## Complexity Tracking

No constitution violations identified. Design follows existing patterns in the codebase.
