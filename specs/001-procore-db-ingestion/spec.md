# Feature Specification: Procore Database Automatic Ingestion

**Feature Branch**: `001-procore-db-ingestion`
**Created**: 2026-01-14
**Status**: Draft
**Input**: User description: "Ingest data from Procore database automatically when data is added/modified/deleted. Keep metadata rich with all info in the database. Support S3/file ingestion and linking for intelligent agent navigation. Step 1 should be detailed database investigation."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Database Schema Discovery (Priority: P1)

As a system administrator, I want to perform a comprehensive investigation of the Procore database schema so that I understand all available tables, columns, relationships, and data types before configuring ingestion.

**Why this priority**: Understanding the complete database structure is a prerequisite for all subsequent ingestion work. Without this, we cannot design proper metadata preservation or determine which tables contain S3/file references.

**Independent Test**: Can be fully tested by connecting to the database and generating a complete schema report showing all tables, columns, relationships, and sample data - delivering a comprehensive database map.

**Acceptance Scenarios**:

1. **Given** valid database credentials, **When** the schema discovery runs, **Then** the system generates a complete inventory of all tables with their column names, data types, nullable flags, and primary/foreign key relationships.
2. **Given** a database with multiple schemas, **When** discovery completes, **Then** all schemas are documented with their respective tables.
3. **Given** foreign key relationships exist between tables, **When** discovery completes, **Then** all relationships are mapped showing parent-child table connections.
4. **Given** tables contain sample data, **When** discovery completes, **Then** row counts and sample records (first 5 rows) are captured for each table.

---

### User Story 2 - Initial Full Data Ingestion (Priority: P2)

As a data engineer, I want to perform a full ingestion of all data from the Procore database into the visual retrieval system so that all existing records are searchable with their complete metadata.

**Why this priority**: Once the schema is understood, bulk ingestion of existing data must occur before change detection can be meaningful. This establishes the baseline dataset.

**Independent Test**: Can be fully tested by running a full ingestion and verifying all table records appear in the search system with complete metadata - delivering a fully searchable dataset.

**Acceptance Scenarios**:

1. **Given** the database contains records across multiple tables, **When** full ingestion runs, **Then** all records are indexed with all column values preserved as metadata.
2. **Given** tables have relationships (foreign keys), **When** records are ingested, **Then** related data is linked and navigable in the ingested format.
3. **Given** a record has NULL values in optional columns, **When** ingested, **Then** NULL fields are represented appropriately without breaking the record structure.
4. **Given** ingestion is in progress, **When** a user checks status, **Then** progress information shows tables processed, records ingested, and estimated time remaining.

---

### User Story 3 - S3/File Reference Detection and Ingestion (Priority: P3)

As a data analyst, I want the system to automatically detect S3 URLs or file references stored in the database and ingest those files so that documents are searchable alongside their metadata.

**Why this priority**: Many construction management systems store document references in the database. Ingesting these files enables visual retrieval of actual documents, which is the core value proposition of this application.

**Independent Test**: Can be fully tested by identifying columns containing S3/file paths and successfully downloading and indexing those files - delivering searchable document content linked to database metadata.

**Acceptance Scenarios**:

1. **Given** a database column contains S3 URLs (s3://bucket/path format), **When** ingestion runs, **Then** the system downloads the file and indexes its content linked to the parent record.
2. **Given** a column contains file paths or URLs, **When** the system scans the schema, **Then** potential file reference columns are identified by pattern matching (URLs, paths, common naming like 'file_url', 'document_path', 'attachment').
3. **Given** an S3 file is successfully downloaded, **When** indexed, **Then** the metadata includes the source table, record ID, column name, and all related record fields.
4. **Given** an S3 file cannot be accessed (permissions, not found), **When** ingestion attempts it, **Then** the error is logged with file details but ingestion continues for other records.

---

### User Story 4 - Automatic Change Detection and Sync (Priority: P4)

As a system operator, I want the system to automatically detect when data is added, modified, or deleted in the Procore database and sync those changes to the search index so that the search results stay current.

**Why this priority**: After initial ingestion, maintaining data freshness through change detection ensures long-term value. This requires the baseline (P2) to exist first.

**Independent Test**: Can be fully tested by making database changes (insert, update, delete) and verifying the search index reflects those changes within the configured sync interval - delivering an automatically updated search index.

**Acceptance Scenarios**:

1. **Given** a new record is inserted into a monitored table, **When** the sync process runs, **Then** the new record appears in the search index with complete metadata.
2. **Given** an existing record is updated in the database, **When** the sync process runs, **Then** the search index reflects the updated values.
3. **Given** a record is deleted from the database, **When** the sync process runs, **Then** the corresponding entry is removed from the search index.
4. **Given** a table has a timestamp column (created_at, updated_at, modified_at), **When** change detection runs, **Then** it uses timestamps to identify changed records since last sync.
5. **Given** a table lacks timestamp columns, **When** change detection runs, **Then** it falls back to comparing record hashes or full table scans to detect changes.

---

### User Story 5 - Agent Navigation Metadata (Priority: P5)

As a future AI agent, I want rich metadata and relationship links preserved in the ingested data so that I can intelligently navigate between related records, files, and entities.

**Why this priority**: While not immediately utilized, structuring data for agent consumption now prevents costly re-ingestion later. This is forward-looking infrastructure.

**Independent Test**: Can be fully tested by querying the search index and traversing from a record to its related records, files, and parent/child entities - delivering a navigable knowledge graph structure.

**Acceptance Scenarios**:

1. **Given** a record has foreign key relationships, **When** queried, **Then** the response includes links/references to related records that an agent can follow.
2. **Given** a record has associated S3 files, **When** queried, **Then** the response includes references to the file records that can be retrieved.
3. **Given** multiple tables describe the same conceptual entity (e.g., project details across tables), **When** queried, **Then** the metadata enables joining these perspectives.
4. **Given** the schema documentation from P1, **When** an agent queries metadata, **Then** it can understand table purposes, column meanings, and relationship semantics.

---

### Edge Cases

- What happens when database credentials are invalid or the database is unreachable? System logs error and retries with exponential backoff, alerting after configurable failure threshold.
- How does the system handle tables with no primary key? Records are identified by composite of all non-NULL columns, with warning logged about potential duplicates.
- What happens when an S3 bucket requires different credentials than configured? File ingestion fails gracefully for that file, error logged with details, record metadata is still ingested.
- How does the system handle very large tables (millions of rows)? Ingestion proceeds in batches with configurable batch size, with checkpoint/resume capability.
- What happens if a file type is not supported for visual retrieval? Metadata is still ingested; file content marked as "unsupported format" in index.
- How does change detection handle schema changes (new columns, dropped tables)? Schema discovery re-runs periodically; new columns are automatically included; dropped tables trigger alerts.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST connect to a PostgreSQL database using provided connection credentials (connection string format).
- **FR-002**: System MUST enumerate all schemas, tables, columns, data types, constraints, and relationships in the target database.
- **FR-003**: System MUST generate a human-readable and machine-readable schema documentation report.
- **FR-004**: System MUST ingest all records from all tables (or configured subset) with all column values preserved as searchable metadata.
- **FR-005**: System MUST maintain referential links between related records based on foreign key relationships.
- **FR-006**: System MUST identify columns likely containing S3 URLs or file paths through pattern detection.
- **FR-007**: System MUST download and ingest files from detected S3/URL references, linking them to their source records.
- **FR-008**: System MUST detect data changes (inserts, updates, deletes) in the source database.
- **FR-009**: System MUST synchronize detected changes to the search index automatically.
- **FR-010**: System MUST preserve rich metadata including source table, column names, data types, and relationship context for agent navigation.
- **FR-011**: System MUST log all ingestion activities, errors, and statistics for monitoring.
- **FR-012**: System MUST support configurable sync intervals for change detection.
- **FR-013**: System MUST handle ingestion failures gracefully without losing already-processed data.
- **FR-014**: System MUST support resumable ingestion for large datasets (checkpoint/restart capability).

### Key Entities

- **DatabaseConnection**: Represents the connection to the Procore PostgreSQL database including credentials and connection parameters.
- **SchemaMap**: The complete documentation of database structure including schemas, tables, columns, types, constraints, and relationships.
- **IngestedRecord**: A database record that has been processed and indexed, with all original column values as metadata plus ingestion timestamp and source location.
- **FileReference**: A detected S3 URL or file path in the database, its download status, and link to the parent record.
- **SyncCheckpoint**: Tracks the last sync time per table, enabling incremental change detection.
- **RelationshipLink**: Represents a foreign key relationship between tables, enabling agent navigation between related records.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Schema discovery completes and documents 100% of tables, columns, and relationships in the target database.
- **SC-002**: Initial full ingestion processes all records from all configured tables with zero data loss.
- **SC-003**: All detected S3/file references are attempted for download, with successful files indexed and failures logged.
- **SC-004**: Data changes in the source database are reflected in the search index within the configured sync interval.
- **SC-005**: Search queries return results with complete original metadata (all column values from source record).
- **SC-006**: Related records are discoverable through relationship links, enabling navigation from any record to its related entities.
- **SC-007**: Ingestion can be paused and resumed without re-processing already-ingested records.
- **SC-008**: System provides clear status reporting showing ingestion progress, sync status, and any errors requiring attention.

## Assumptions

- The PostgreSQL database follows standard conventions with defined primary keys and foreign keys for most tables.
- S3 credentials will be provided separately if S3 file access is required.
- The database is read-only from this system's perspective (connection is read-only as indicated by the credentials).
- Tables likely to contain file references will use recognizable column naming patterns or URL/path formats.
- The Vespa search infrastructure is already operational (as indicated by existing codebase).
- Change detection via timestamps is preferred but hash-based detection is an acceptable fallback.
