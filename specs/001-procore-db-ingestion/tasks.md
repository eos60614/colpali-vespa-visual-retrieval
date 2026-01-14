# Tasks: Procore Database Automatic Ingestion

**Input**: Design documents from `/specs/001-procore-db-ingestion/`
**Prerequisites**: plan.md ✓, spec.md ✓, research.md ✓, data-model.md ✓, contracts/ ✓

**Tests**: Not explicitly requested - test tasks omitted.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Based on plan.md structure:
- **Module code**: `backend/ingestion/`
- **CLI scripts**: `scripts/`
- **Tests**: `tests/unit/ingestion/`, `tests/integration/ingestion/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and module structure

- [X] T001 Create ingestion module directory structure in backend/ingestion/
- [X] T002 [P] Create backend/ingestion/__init__.py with module exports
- [X] T003 [P] Add new dependencies to requirements.txt (asyncpg, boto3, aiosqlite, tqdm)
- [X] T004 [P] Create tests/unit/ingestion/ and tests/integration/ingestion/ directories
- [X] T005 [P] Create tests/conftest.py with shared test fixtures

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Implement exception classes in backend/ingestion/exceptions.py (IngestionError, ConnectionError, SchemaError, TransformError, IndexError, DownloadError)
- [X] T007 Implement ConnectionConfig dataclass in backend/ingestion/db_connection.py with from_url() parser
- [X] T008 Implement DatabaseConnection class in backend/ingestion/db_connection.py (connect, close, execute, stream methods)
- [X] T009 Implement CheckpointStore class in backend/ingestion/checkpoint.py with SQLite persistence
- [X] T010 [P] Create data/ directory for SQLite checkpoint database
- [X] T011 [P] Update .gitignore to exclude data/*.db files

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Database Schema Discovery (Priority: P1) 🎯 MVP

**Goal**: Generate a comprehensive inventory of all tables, columns, relationships, and file reference columns from the Procore database

**Independent Test**: Connect to the database and generate a complete schema report (JSON and Markdown) showing all tables, columns, relationships, and sample data

### Implementation for User Story 1

- [X] T012 [P] [US1] Implement Column dataclass in backend/ingestion/schema_discovery.py
- [X] T013 [P] [US1] Implement FileReferenceType enum and FileReferenceColumn dataclass in backend/ingestion/schema_discovery.py
- [X] T014 [P] [US1] Implement Table dataclass in backend/ingestion/schema_discovery.py
- [X] T015 [P] [US1] Implement ImplicitRelationship dataclass in backend/ingestion/schema_discovery.py
- [X] T016 [US1] Implement SchemaMap dataclass in backend/ingestion/schema_discovery.py
- [X] T017 [US1] Implement SchemaDiscovery.get_tables() method using information_schema in backend/ingestion/schema_discovery.py
- [X] T018 [US1] Implement SchemaDiscovery.get_columns() method in backend/ingestion/schema_discovery.py
- [X] T019 [US1] Implement SchemaDiscovery.get_row_count() method in backend/ingestion/schema_discovery.py
- [X] T020 [US1] Implement SchemaDiscovery.detect_file_columns() method to identify S3/URL columns in backend/ingestion/schema_discovery.py
- [X] T021 [US1] Implement SchemaDiscovery.infer_relationships() method for _id column patterns in backend/ingestion/schema_discovery.py
- [X] T022 [US1] Implement SchemaDiscovery.discover() orchestration method in backend/ingestion/schema_discovery.py
- [X] T023 [US1] Implement SchemaDiscovery.to_json() export method in backend/ingestion/schema_discovery.py
- [X] T024 [US1] Implement SchemaDiscovery.to_markdown() export method in backend/ingestion/schema_discovery.py
- [X] T025 [US1] Create CLI script scripts/discover_schema.py with argparse (--database-url, --output, --format, --include-samples, --include-stats)
- [X] T026 [US1] Add progress reporting and logging to discover_schema.py

**Checkpoint**: User Story 1 complete - can run schema discovery and generate comprehensive database documentation

---

## Phase 4: User Story 2 - Initial Full Data Ingestion (Priority: P2)

**Goal**: Ingest all database records into Vespa with complete metadata preserved and relationships linked

**Independent Test**: Run full ingestion and verify all table records appear in Vespa search with complete metadata

### Implementation for User Story 2

- [X] T027 [P] [US2] Implement IngestedRecord dataclass in backend/ingestion/record_ingester.py
- [X] T028 [P] [US2] Implement IngestionResult dataclass in backend/ingestion/record_ingester.py
- [X] T029 [US2] Implement RecordIngester.transform_record() method with metadata mapping in backend/ingestion/record_ingester.py
- [X] T030 [US2] Implement RecordIngester.extract_relationships() method for _id columns in backend/ingestion/record_ingester.py
- [X] T031 [US2] Implement RecordIngester.generate_content_text() method with table-specific field selection in backend/ingestion/record_ingester.py
- [X] T032 [US2] Implement RecordIngester.index_record() method using existing Vespa client in backend/ingestion/record_ingester.py
- [X] T033 [US2] Implement RecordIngester.index_batch() method for parallel indexing in backend/ingestion/record_ingester.py
- [X] T034 [US2] Implement RecordIngester.ingest_table() async iterator method in backend/ingestion/record_ingester.py
- [X] T035 [P] [US2] Implement IngestionJob dataclass in backend/ingestion/sync_manager.py
- [X] T036 [P] [US2] Implement SyncConfig dataclass in backend/ingestion/sync_manager.py
- [X] T037 [P] [US2] Implement SyncResult dataclass in backend/ingestion/sync_manager.py
- [X] T038 [US2] Implement SyncManager.get_tables_to_sync() method with include/exclude logic in backend/ingestion/sync_manager.py
- [X] T039 [US2] Implement SyncManager.sync_table() method in backend/ingestion/sync_manager.py
- [X] T040 [US2] Implement SyncManager.run_full_sync() orchestration method in backend/ingestion/sync_manager.py
- [X] T041 [US2] Create Vespa schema procore_record in vespa/schemas/procore_record.sd (doc_id, source_table, source_id, project_id, metadata, relationships, file_references, timestamps, content_text)
- [X] T042 [US2] Create CLI script scripts/ingest_database.py with argparse (--full, --tables, --exclude, --batch-size, --workers, --dry-run)
- [X] T043 [US2] Add progress bar (tqdm), status output, and logging to ingest_database.py
- [X] T044 [US2] Add checkpoint saving after each table completion in SyncManager

**Checkpoint**: User Story 2 complete - all database records searchable in Vespa with full metadata

---

## Phase 5: User Story 3 - S3/File Reference Detection and Ingestion (Priority: P3)

**Goal**: Automatically detect S3/file references in database records and download/index those files

**Independent Test**: Identify columns containing S3/file paths, download files, and verify they are indexed and linked to source records

### Implementation for User Story 3

- [X] T045 [P] [US3] Implement DetectedFile dataclass in backend/ingestion/file_detector.py
- [X] T046 [US3] Implement FileDetector.parse_s3_key() method for direct S3 key columns in backend/ingestion/file_detector.py
- [X] T047 [US3] Implement FileDetector.parse_jsonb_attachments() method for JSONB attachment maps in backend/ingestion/file_detector.py
- [X] T048 [US3] Implement FileDetector.parse_url() method for Procore signed URLs in backend/ingestion/file_detector.py
- [X] T049 [US3] Implement FileDetector.detect_in_record() orchestration method in backend/ingestion/file_detector.py
- [X] T050 [US3] Implement FileDetector.extract_filename() and infer_file_type() helpers in backend/ingestion/file_detector.py
- [X] T051 [P] [US3] Implement DownloadResult dataclass in backend/ingestion/file_downloader.py
- [X] T052 [P] [US3] Implement DownloadStrategy enum in backend/ingestion/file_downloader.py
- [X] T053 [US3] Implement FileDownloader.download_from_url() for Procore signed URLs in backend/ingestion/file_downloader.py
- [X] T054 [US3] Implement FileDownloader.download_from_s3() with boto3 in backend/ingestion/file_downloader.py
- [X] T055 [US3] Implement FileDownloader.should_skip() for unsupported types and large files in backend/ingestion/file_downloader.py
- [X] T056 [US3] Implement FileDownloader.download() dispatch method in backend/ingestion/file_downloader.py
- [X] T057 [US3] Implement FileDownloader.download_batch() for parallel downloads in backend/ingestion/file_downloader.py
- [X] T058 [US3] Integrate FileDetector into RecordIngester.extract_file_references() in backend/ingestion/record_ingester.py
- [X] T059 [US3] Add --download-files and --file-workers flags to scripts/ingest_database.py
- [X] T060 [US3] Integrate file download into SyncManager.sync_table() in backend/ingestion/sync_manager.py
- [X] T061 [US3] Add file download progress tracking and error logging

**Checkpoint**: User Story 3 complete - files automatically detected, downloaded, and indexed with parent record links

---

## Phase 6: User Story 4 - Automatic Change Detection and Sync (Priority: P4)

**Goal**: Detect inserts, updates, and deletes in the database and sync changes to Vespa automatically

**Independent Test**: Make database changes (insert, update, delete) and verify the search index reflects those changes within sync interval

### Implementation for User Story 4

- [X] T062 [P] [US4] Implement Change dataclass in backend/ingestion/change_detector.py
- [X] T063 [P] [US4] Implement ChangeSet dataclass in backend/ingestion/change_detector.py
- [X] T064 [US4] Implement ChangeDetector.get_timestamp_column() to select best timestamp field in backend/ingestion/change_detector.py
- [X] T065 [US4] Implement ChangeDetector.get_updated_records() streaming method in backend/ingestion/change_detector.py
- [X] T066 [US4] Implement ChangeDetector.detect_deletes() by comparing known IDs in backend/ingestion/change_detector.py
- [X] T067 [US4] Implement ChangeDetector.detect_changes() orchestration method in backend/ingestion/change_detector.py
- [X] T068 [US4] Implement SyncManager.run_incremental_sync() using ChangeDetector in backend/ingestion/sync_manager.py
- [X] T069 [US4] Add delete handling to SyncManager - remove records from Vespa in backend/ingestion/sync_manager.py
- [X] T070 [US4] Create CLI script scripts/sync_database.py with --daemon, --once, --status, --interval flags
- [X] T071 [US4] Implement daemon loop with configurable interval in sync_database.py
- [X] T072 [US4] Implement --status command showing sync state for all tables in sync_database.py
- [X] T073 [US4] Add signal handling (SIGINT, SIGTERM) for graceful daemon shutdown
- [X] T074 [US4] Add PID file management for daemon mode

**Checkpoint**: User Story 4 complete - database changes automatically reflected in search index

---

## Phase 7: User Story 5 - Agent Navigation Metadata (Priority: P5)

**Goal**: Preserve rich metadata and relationship links for intelligent agent navigation between records

**Independent Test**: Query the search index and traverse from a record to its related records, files, and parent/child entities

### Implementation for User Story 5

- [X] T075 [US5] Enhance relationships field in IngestedRecord to include full navigation context in backend/ingestion/record_ingester.py
- [X] T076 [US5] Add bidirectional relationship tracking (parent → child and child → parent) in backend/ingestion/record_ingester.py
- [X] T077 [US5] Implement relationship link generation from SchemaMap in backend/ingestion/record_ingester.py
- [X] T078 [US5] Add source_column and relationship_type to file_references for complete provenance in backend/ingestion/record_ingester.py
- [X] T079 [US5] Add schema documentation fields to Vespa records (table_description, column_types) in backend/ingestion/record_ingester.py
- [X] T080 [US5] Create schema metadata document type for agent reference in vespa/schemas/
- [X] T081 [US5] Index SchemaMap as navigable metadata document in SyncManager

**Checkpoint**: User Story 5 complete - all records have rich navigable metadata for agent consumption

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T082 [P] Add comprehensive logging throughout all modules
- [X] T083 [P] Add type hints to all public methods
- [X] T084 Run ruff check and fix any linting issues
- [X] T085 Validate all CLI scripts match contracts/cli-interface.md specification
- [X] T086 Run quickstart.md workflow end-to-end validation
- [X] T087 Update CLAUDE.md with new commands if needed

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
- **Polish (Phase 8)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational - No dependencies on other stories
- **User Story 2 (P2)**: Can start after US1 (needs SchemaMap from schema_discovery)
- **User Story 3 (P3)**: Can start after US2 (needs RecordIngester infrastructure)
- **User Story 4 (P4)**: Can start after US2 (needs SyncManager infrastructure)
- **User Story 5 (P5)**: Can start after US2 (enhances existing record structure)

### Within Each User Story

- Dataclasses before methods that use them
- Core methods before orchestration methods
- Module code before CLI scripts
- CLI scripts before integration testing

### Parallel Opportunities

**Phase 1 (Setup)**:
- T002, T003, T004, T005 can all run in parallel

**Phase 2 (Foundational)**:
- T010, T011 can run in parallel
- T007 must complete before T008

**Phase 3 (US1 - Schema Discovery)**:
- T012, T013, T014, T015 (dataclasses) can all run in parallel
- T017-T021 (discovery methods) can run in parallel after dataclasses
- T023, T024 (export methods) can run in parallel

**Phase 4 (US2 - Full Ingestion)**:
- T027, T028 can run in parallel
- T035, T036, T037 can run in parallel

**Phase 5 (US3 - File Detection)**:
- T045, T051, T052 can run in parallel
- T046, T047, T048 can run in parallel

**Phase 6 (US4 - Change Detection)**:
- T062, T063 can run in parallel

**Phase 8 (Polish)**:
- T082, T083 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all dataclasses for User Story 1 together:
Task: "T012 Implement Column dataclass"
Task: "T013 Implement FileReferenceType enum and FileReferenceColumn dataclass"
Task: "T014 Implement Table dataclass"
Task: "T015 Implement ImplicitRelationship dataclass"

# After dataclasses complete, launch discovery methods together:
Task: "T017 Implement SchemaDiscovery.get_tables()"
Task: "T018 Implement SchemaDiscovery.get_columns()"
Task: "T019 Implement SchemaDiscovery.get_row_count()"
Task: "T020 Implement SchemaDiscovery.detect_file_columns()"
Task: "T021 Implement SchemaDiscovery.infer_relationships()"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (Schema Discovery)
4. **STOP and VALIDATE**: Run `python scripts/discover_schema.py` against Procore database
5. Deploy/demo - administrators can now see complete database structure

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. User Story 1 → Schema Discovery works → Demo database map
3. User Story 2 → Full Ingestion works → Demo searchable records
4. User Story 3 → File Ingestion works → Demo document search
5. User Story 4 → Change Sync works → Demo live updates
6. User Story 5 → Agent Navigation works → Demo traversal

### Suggested MVP Scope

**MVP = Phase 1 + Phase 2 + Phase 3 (User Story 1)**
- Delivers: Complete database schema documentation
- Files: 4 new files (db_connection.py, schema_discovery.py, checkpoint.py, discover_schema.py)
- Value: Administrators understand database structure before configuring ingestion

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Total tasks: 87
  - Phase 1 (Setup): 5 tasks
  - Phase 2 (Foundational): 6 tasks
  - Phase 3 (US1): 15 tasks
  - Phase 4 (US2): 18 tasks
  - Phase 5 (US3): 17 tasks
  - Phase 6 (US4): 13 tasks
  - Phase 7 (US5): 7 tasks
  - Phase 8 (Polish): 6 tasks
