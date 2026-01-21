# Research: Procore Database Investigation

**Feature**: 001-procore-db-ingestion
**Date**: 2026-01-14
**Database**: postgresql://database-3.czsyw64yw006.us-east-2.rds.amazonaws.com:5432/procore_int_v2

## Executive Summary

Complete investigation of the Procore integration database reveals:
- **50 tables** in the `public` schema
- **~40,000+ total records** across all tables
- **No formal foreign keys** defined (implicit relationships via `_id` columns)
- **33 file/S3 reference columns** across 16 tables
- **All tables have timestamp columns** (`updated_at`, `last_synced_at`) for change detection
- Files stored in Procore's storage service with signed URLs and S3 keys

---

## Database Schema Overview

### Table Inventory (50 tables)

| Category | Tables | Total Records |
|----------|--------|---------------|
| Core Project Data | projects, project_users, project_roles, company_users | ~2,334 |
| Documents/Drawings | drawings, drawing_revisions, drawing_sets, drawing_areas, documents, photos | ~13,997 |
| Financial | budget_line_items, budget_views, change_orders, commitment_*, direct_costs, prime_contracts | ~2,838 |
| Submittals/RFIs | submittals, submittal_attachments, rfis | ~808 |
| Field Data | daily_logs, timesheets, inspections, punch_items, observations | ~5,429 |
| Specifications | specification_sections, specification_section_revisions, specification_section_divisions | ~4,598 |
| System/Integration | sync_events, webhook_*, audit_records, api_credentials, _prisma_migrations | ~7,356+ |

### Record Counts (Top 15 Tables)

```
photos                          : 7,631
sync_events                     : 5,973
drawings                        : 5,701
drawing_revisions               : 5,481
timesheets                      : 5,413
requisitions                    : 2,704
specification_sections          : 2,145
specification_section_revisions : 2,145
project_users                   : 1,610
direct_cost_items               : 1,450
audit_records                   : 1,356
company_users                   : 590
budget_line_items               : 518
change_orders                   : 516
submittals                      : 500
```

---

## Key Tables Schema Analysis

### 1. Projects (Core Entity)

```sql
projects (31 rows)
├── id                        : bigint (PK - no formal constraint)
├── name                      : text
├── display_name              : text
├── project_number            : text
├── address, city, state_code, country_code, zip
├── active                    : boolean
├── estimated_start_date      : date
├── estimated_completion_date : date
├── created_at                : timestamp
├── updated_at                : timestamp
└── last_synced_at            : timestamp
```

**Sample Data**:
- ID: `562949953567479`, Name: "537-18-141 Failed AHU-1 and Rem Chiller"
- Construction projects with addresses primarily in IL, US

### 2. Photos (Highest Volume - 7,631 rows)

```sql
photos
├── id                : bigint
├── project_id        : bigint → projects
├── url               : text (Procore signed URL)
├── thumbnail_url     : text (Procore signed URL)
├── s3_key            : text (S3 path pattern)
├── image_category_id : bigint
├── description       : text
├── location          : text
├── taken_at          : timestamp
├── created_at, updated_at, last_synced_at
```

**S3 Key Pattern**: `{company_id}/{project_id}/photos/{photo_id}/{filename}`
**URL Pattern**: `https://storage.procore.com/api/v5/files/...?companyId=X&projectId=Y&sig=Z`

### 3. Drawing Revisions (5,481 rows)

```sql
drawing_revisions
├── id              : bigint
├── project_id      : bigint → projects
├── drawing_id      : bigint → drawings
├── drawing_area_id : bigint → drawing_areas
├── drawing_set_id  : bigint → drawing_sets
├── revision_number : text
├── current         : boolean
├── s3_key          : text (S3 path to PDF)
├── filename        : text
├── file_size       : integer (bytes)
├── created_at, updated_at, last_synced_at
```

**S3 Key Pattern**: `{company_id}/{project_id}/drawings/{revision_id}/{filename}.pdf`
**File Types**: PDF documents (drawing sheets)

### 4. Commitment Contracts (318 rows, 60 columns)

Complex financial entity with multiple attachment references:

```sql
commitment_contracts
├── id, project_id, vendor_id
├── type, number, title, description, status
├── Financial fields (retainage, billing, payment terms)
├── Date fields (contract_date, execution_date, etc.)
├── attachment_ids         : jsonb
├── attachments_s3_keys    : jsonb  ← S3 keys
├── drawing_revision_ids   : jsonb
├── file_version_ids       : jsonb
├── image_ids              : jsonb
└── timestamps
```

---

## File/S3 Reference Analysis

### Columns Containing File References (33 total)

| Table | Column | Type | Content Pattern |
|-------|--------|------|-----------------|
| photos | s3_key | text | Direct S3 path |
| photos | url | text | Procore signed URL |
| photos | thumbnail_url | text | Procore signed URL |
| drawing_revisions | s3_key | text | Direct S3 path (PDFs) |
| drawing_revisions | filename | text | Original filename |
| specification_section_revisions | s3_key | text | Direct S3 path |
| submittal_attachments | s3_key | text | Direct S3 path |
| documents | url | text | Procore URL |
| change_orders | attachment_s3_keys | jsonb | Map of ID→S3 key |
| commitment_contracts | attachments_s3_keys | jsonb | Map of ID→S3 key |
| commitment_change_orders | attachments_s3_keys | jsonb | Map of ID→S3 key |
| direct_costs | attachments_s3_keys | jsonb | Map of ID→S3 key |
| requisitions | attachments_s3_keys | jsonb | Map of ID→S3 key |
| submittals | official_response_attachment_s3_keys | jsonb | Map of ID→S3 key |
| rfis | official_response_attachment_s3_keys | jsonb | Map of ID→S3 key |

### S3 Key Format

All S3 keys follow the pattern:
```
{company_id}/{project_id}/{resource_type}/{resource_id}/{filename}
```

Example: `562949953425831/562949954923622/photos/562950208716653/IMG_1128.jpg`

### JSONB Attachment Format

```json
{
  "562951022152066": "562949953425831/562949954229558/change_orders/562949956208422/EOS_CO11.pdf",
  "562951023918286": "562949953425831/562949954229558/change_orders/562949956208422/another_file.pdf"
}
```

### Estimated File Volume

| Source | Estimated Files |
|--------|-----------------|
| photos (s3_key) | ~7,631 |
| drawing_revisions (s3_key) | ~5,481 |
| specification_section_revisions (s3_key) | ~2,145 |
| submittal_attachments (s3_key) | ~500+ |
| change_orders (jsonb) | ~500-1000+ |
| commitment_contracts (jsonb) | ~300+ |
| **Total Estimated** | **~16,000+ files** |

---

## Relationship Mapping (Implicit Foreign Keys)

No formal foreign key constraints exist. All relationships are implicit via `_id` suffix columns.

### Core Relationship Graph

```
projects (31)
├── photos (7,631) via project_id
├── drawings (5,701) via project_id
│   └── drawing_revisions (5,481) via drawing_id
├── drawing_areas (32) via project_id
├── drawing_sets (153) via project_id
├── specification_sections (2,145) via project_id
│   └── specification_section_revisions (2,145) via specification_section_id
├── commitment_contracts (318) via project_id
│   ├── commitment_contract_items (380) via commitment_contract_id
│   └── commitment_change_orders (137) via contract_id
├── prime_contracts (8) via project_id
│   ├── prime_contract_line_items (62) via prime_contract_id
│   └── prime_contract_change_orders (7) via prime_contract_id
├── change_orders (516) via project_id
├── budget_line_items (518) via project_id
├── direct_costs (252) via project_id
│   └── direct_cost_items (1,450) via direct_cost_id
├── rfis (308) via project_id
├── submittals (500) via project_id
│   └── submittal_attachments (0) via submittal_id
├── requisitions (2,704) via project_id
├── timesheets (5,413) via project_id
├── daily_logs (16) via project_id
├── project_users (1,610) via project_id
└── project_roles (103) via project_id

vendors (346)
├── commitment_contracts via vendor_id
├── direct_costs via vendor_id
├── company_users via vendor_id
└── vendor_insurances via vendor_id

company_users (590)
└── project_users via employee_id
```

### Key Relationship Columns (164 identified)

Most common relationship patterns:
- `project_id` - Links to projects (appears in 40+ tables)
- `vendor_id` - Links to vendors
- `commitment_contract_id` / `contract_id` - Links to contracts
- `drawing_id`, `drawing_area_id`, `drawing_set_id` - Drawing hierarchy

---

## Change Detection Strategy

### Available Timestamp Columns

All 50 tables have at least one of:
- `updated_at` - Last modification timestamp (present in all tables)
- `last_synced_at` - Last sync from Procore (present in 47 tables)
- `created_at` - Creation timestamp (present in all tables)

### Recommended Approach

**Primary**: Use `updated_at` for change detection
- Most reliable indicator of data modification
- Present in all tables
- Updated on any field change

**Supplementary**: Use `last_synced_at` to detect sync events
- Indicates when data was pulled from Procore
- Useful for understanding data freshness

### Change Detection Query Pattern

```sql
SELECT * FROM {table}
WHERE updated_at > '{last_sync_checkpoint}'
ORDER BY updated_at ASC
LIMIT {batch_size};
```

---

## Technical Decisions

### Decision 1: Database Connection Library

**Decision**: Use `asyncpg` for PostgreSQL access
**Rationale**:
- High-performance async driver
- Native support for JSONB
- Connection pooling built-in
- Matches async patterns in existing codebase (FastHTML, aiohttp)

**Alternatives Considered**:
- psycopg2: Synchronous only, would require threading
- SQLAlchemy async: Additional abstraction layer not needed for read-only access

### Decision 2: Schema Introspection Approach

**Decision**: Use PostgreSQL `information_schema` views directly
**Rationale**:
- No additional dependencies
- Complete schema information available
- Can generate both human-readable and machine-readable output

**Implementation**:
```sql
-- Tables and columns
SELECT * FROM information_schema.columns WHERE table_schema = 'public';

-- Implied relationships (no formal FKs exist)
SELECT column_name FROM information_schema.columns WHERE column_name LIKE '%_id';
```

### Decision 3: S3 File Access Strategy

**Decision**: Use Procore signed URLs from database, not direct S3 access
**Rationale**:
- URLs in database are pre-signed by Procore
- No separate S3 credentials needed initially
- URLs include signature for authorization
- Can fall back to direct S3 if URLs expire

**Concern**: URL signatures may expire. Monitor for 403 errors and implement:
1. Retry with fresh URL from Procore API (future enhancement)
2. Direct S3 access with separate credentials (if provided)

### Decision 4: Record Identification Strategy

**Decision**: Use `id` column as primary identifier despite no formal PK constraints
**Rationale**:
- All tables have `id` column with `bigint` type
- IDs are unique within each table (Procore-generated)
- Pattern consistent: `{company_id * 2^50 + sequence}`

### Decision 5: JSONB S3 Key Extraction

**Decision**: Parse JSONB attachment columns to extract all S3 keys
**Rationale**:
- Many attachments stored as `{"file_id": "s3_key"}` maps
- Need to extract all values from the map
- Can link back to source record for metadata

**Implementation**:
```sql
SELECT id, jsonb_each_text(attachment_s3_keys)
FROM change_orders
WHERE attachment_s3_keys IS NOT NULL;
```

### Decision 6: Batch Processing Size

**Decision**: 10,000 records per batch for initial ingestion
**Rationale**:
- Largest table (photos) has ~7,600 rows - fits in single batch
- Balance between memory usage and network roundtrips
- Allows for checkpoint/resume at batch boundaries

### Decision 7: Vespa Document Schema

**Decision**: Create single document type for database records with dynamic fields
**Rationale**:
- Different tables have different schemas
- Need to preserve all metadata for agent navigation
- Can use Vespa's flexible field mapping

**Schema Approach**:
```
source_table: string (required)
source_id: string (required)
project_id: long (indexed for filtering)
metadata: map<string, string> (all column values)
relationships: array<string> (linked record IDs)
file_references: array<string> (S3 keys for this record)
updated_at: timestamp (for sync tracking)
```

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Signed URL expiration | Files become inaccessible | Cache downloaded files, implement refresh mechanism |
| No formal FKs | Relationships may be incomplete | Validate `_id` patterns, document assumptions |
| Large tables (photos) | Memory/performance issues | Batch processing with checkpoints |
| Schema changes | Ingestion breaks | Periodic schema re-discovery, graceful handling of new columns |
| Read-only access | Can't track sync state in source | Use local SQLite for checkpoints |

---

## Next Steps (Phase 1)

1. **Data Model**: Define Vespa schema and ingestion record format
2. **Contracts**: Define CLI interfaces for schema discovery, ingestion, sync
3. **Quickstart**: Document setup and usage workflow
