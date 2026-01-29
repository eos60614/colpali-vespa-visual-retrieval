# Implementation Plan: File Upload and Ingestion with Metadata

> **Note**: This spec was written for an earlier architecture. The application now uses Starlette (JSON API) + Next.js (frontend). The upload feature implementation is complete and still valid.

**Branch**: `002-file-upload-ingest` | **Date**: 2026-01-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/002-file-upload-ingest/spec.md`

## Summary

Add a file upload interface to the frontend that allows users to upload PDF documents (up to 250MB) with optional metadata (title, description, tags). The uploaded files are processed through the existing ingestion pipeline (PDF rendering, ColPali embedding generation, Vespa indexing) and become searchable via visual and text-based queries.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: Starlette, PyMuPDF (fitz), ColPali, Vespa Python client
**Storage**: Vespa (document store), filesystem (temporary upload storage)
**Testing**: Manual testing (no existing test framework in project)
**Target Platform**: Linux server (local Vespa deployment)
**Project Type**: Web application (Starlette backend + Next.js frontend)
**Performance Goals**: N/A (functional correctness over optimization)
**Constraints**: Max file size 250MB
**Scale/Scope**: Single-user local deployment

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The constitution file is a placeholder template with no concrete project-specific rules defined. No violations to check against.

**Status**: PASS (no defined constraints)

## Project Structure

### Documentation (this feature)

```text
specs/002-file-upload-ingest/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (repository root)

```text
# Existing structure - web application style
backend/
├── __init__.py
├── cache.py
├── colpali.py           # SimMapGenerator - embedding generation
├── stopwords.py
├── vespa_app.py         # VespaQueryClient - Vespa operations
└── models/

web/                     # Next.js frontend
├── src/app/
│   └── upload/page.tsx  # Upload page component
└── ...

main.py                  # Starlette API backend
scripts/
└── feed_data.py         # Existing batch ingestion script

vespa-app/
└── schemas/
    └── pdf_page.sd      # Vespa document schema
```

**Structure Decision**: Extend existing structure. Add upload API endpoint to `main.py` and upload page to Next.js frontend (`web/`).

## Complexity Tracking

No violations to track - constitution has no defined rules.
