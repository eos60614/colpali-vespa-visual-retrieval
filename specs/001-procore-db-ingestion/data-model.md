# Data Model: Procore Database Ingestion

**Feature**: 001-procore-db-ingestion
**Date**: 2026-01-14

## Overview

This document defines the data model for ingesting Procore database records into the Vespa visual retrieval system. The model supports:
- Rich metadata preservation from all database columns
- Relationship traversal for agent navigation
- File reference linking for document retrieval
- Change detection for incremental sync

---

## Core Entities

### 1. SchemaMap

Represents the complete database schema discovered during introspection.

```
SchemaMap
├── discovery_timestamp: datetime
├── database_name: string
├── schemas: Schema[]
└── relationships: ImplicitRelationship[]

Schema
├── name: string (e.g., "public")
└── tables: Table[]

Table
├── name: string
├── row_count: integer
├── columns: Column[]
├── primary_key: string[] (inferred from 'id' column)
├── timestamp_columns: string[] (updated_at, last_synced_at, created_at)
└── file_reference_columns: FileReferenceColumn[]

Column
├── name: string
├── data_type: string (PostgreSQL type)
├── is_nullable: boolean
├── default_value: string | null
└── max_length: integer | null

FileReferenceColumn
├── column_name: string
├── reference_type: enum (S3_KEY, URL, JSONB_S3_MAP)
└── pattern: string (regex for validation)

ImplicitRelationship
├── source_table: string
├── source_column: string
├── target_table: string (inferred from column name)
├── target_column: string (always "id")
└── cardinality: enum (MANY_TO_ONE, ONE_TO_MANY)
```

**Storage**: JSON file at `specs/001-procore-db-ingestion/schema-map.json`

---

### 2. IngestedRecord

A database record indexed in Vespa with full metadata and relationship context.

```
IngestedRecord (Vespa Document Schema: procore_record)
├── doc_id: string              # "{table}:{id}" - unique identifier
├── source_table: string        # Table name (e.g., "photos", "projects")
├── source_id: string           # Original bigint ID as string
├── project_id: long            # For filtering/grouping (nullable)
│
├── metadata: map<string, string>  # All column values as key-value pairs
│   ├── "{column_name}": "{value}"
│   └── ... (dynamic, preserves all columns)
│
├── relationships: Relationship[]  # Links to related records
│   ├── type: string              # e.g., "project", "vendor", "drawing"
│   ├── target_table: string      # e.g., "projects", "vendors"
│   └── target_id: string         # ID of related record
│
├── file_references: FileRef[]    # S3 keys for attached files
│   ├── s3_key: string
│   ├── source_column: string    # Which column contained this reference
│   ├── filename: string | null
│   └── file_size: integer | null
│
├── created_at: timestamp         # Record creation time
├── updated_at: timestamp         # Last modification in source DB
├── ingested_at: timestamp        # When ingested into Vespa
└── content_text: string          # Searchable text (concatenated relevant fields)
```

**Vespa Schema Definition**:
```
schema procore_record {
    document procore_record {
        field doc_id type string {
            indexing: summary | attribute
            attribute: fast-search
        }
        field source_table type string {
            indexing: summary | attribute
            attribute: fast-search
        }
        field source_id type string {
            indexing: summary | attribute
        }
        field project_id type long {
            indexing: summary | attribute
            attribute: fast-search
        }
        field metadata type map<string, string> {
            indexing: summary
        }
        field relationships type array<string> {
            indexing: summary | attribute
        }
        field file_references type array<string> {
            indexing: summary | attribute
        }
        field created_at type long {
            indexing: summary | attribute
        }
        field updated_at type long {
            indexing: summary | attribute
            attribute: fast-search
        }
        field ingested_at type long {
            indexing: summary | attribute
        }
        field content_text type string {
            indexing: summary | index
            index: enable-bm25
        }
    }

    fieldset default {
        fields: content_text
    }

    rank-profile bm25 inherits default {
        first-phase {
            expression: bm25(content_text)
        }
    }
}
```

---

### 3. IngestedFile

A file downloaded from S3 and indexed for visual retrieval.

```
IngestedFile (Vespa Document Schema: procore_file)
├── doc_id: string               # "file:{s3_key_hash}"
├── s3_key: string               # Full S3 key path
├── source_record_id: string     # IngestedRecord.doc_id that references this file
├── source_table: string         # Table containing the reference
├── source_column: string        # Column containing the reference
│
├── file_metadata:
│   ├── filename: string
│   ├── file_type: string        # Extension (pdf, jpg, png, etc.)
│   ├── file_size: integer       # Bytes
│   ├── mime_type: string
│   └── download_url: string     # Original URL (may expire)
│
├── project_id: long             # For filtering
├── company_id: long             # For filtering
│
├── content:
│   ├── extracted_text: string   # OCR/text extraction result
│   ├── page_count: integer      # For PDFs
│   └── image_data: binary       # For visual retrieval (ColPali)
│
├── download_status: enum (PENDING, SUCCESS, FAILED, SKIPPED)
├── download_error: string | null
├── downloaded_at: timestamp
├── ingested_at: timestamp
└── embedding: tensor            # ColPali embedding for visual search
```

**Vespa Schema extends existing pdf_page**:
The IngestedFile schema reuses the existing `pdf_page` schema structure for compatibility with ColPali visual retrieval.

---

### 4. SyncCheckpoint

Tracks synchronization state per table for incremental updates.

```
SyncCheckpoint
├── table_name: string           # Primary key
├── last_sync_timestamp: datetime
├── last_record_id: string       # Last processed record ID
├── records_processed: integer
├── records_failed: integer
├── sync_status: enum (IDLE, RUNNING, COMPLETED, FAILED)
├── error_message: string | null
└── updated_at: datetime
```

**Storage**: SQLite database at `data/sync_checkpoints.db`

```sql
CREATE TABLE sync_checkpoints (
    table_name TEXT PRIMARY KEY,
    last_sync_timestamp TEXT,
    last_record_id TEXT,
    records_processed INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    sync_status TEXT DEFAULT 'IDLE',
    error_message TEXT,
    updated_at TEXT
);
```

---

### 5. IngestionJob

Tracks the status of a full or incremental ingestion job.

```
IngestionJob
├── job_id: string (UUID)
├── job_type: enum (FULL, INCREMENTAL, SCHEMA_DISCOVERY)
├── status: enum (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
├── started_at: datetime
├── completed_at: datetime | null
│
├── tables_config:
│   ├── include: string[]        # Tables to include (empty = all)
│   └── exclude: string[]        # Tables to exclude
│
├── progress:
│   ├── tables_total: integer
│   ├── tables_completed: integer
│   ├── records_total: integer
│   ├── records_processed: integer
│   ├── records_failed: integer
│   ├── files_total: integer
│   ├── files_downloaded: integer
│   └── files_failed: integer
│
├── error_log: IngestionError[]
└── updated_at: datetime

IngestionError
├── timestamp: datetime
├── table_name: string
├── record_id: string | null
├── error_type: string
└── error_message: string
```

**Storage**: SQLite database at `data/ingestion_jobs.db`

---

## Relationship Model

### Procore Entity Hierarchy

```
                    ┌─────────────────┐
                    │    projects     │
                    │  (31 records)   │
                    └────────┬────────┘
                             │ project_id
        ┌────────────────────┼────────────────────┐
        │                    │                    │
        ▼                    ▼                    ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│    photos     │   │   drawings    │   │  contracts    │
│   (7,631)     │   │   (5,701)     │   │    (326)      │
└───────────────┘   └───────┬───────┘   └───────┬───────┘
                            │                   │
                            ▼                   ▼
                    ┌───────────────┐   ┌───────────────┐
                    │   revisions   │   │  line items   │
                    │   (5,481)     │   │    (442)      │
                    └───────────────┘   └───────────────┘
```

### Relationship Types

| Source Table | Column | Target Table | Type |
|--------------|--------|--------------|------|
| photos | project_id | projects | MANY_TO_ONE |
| drawings | project_id | projects | MANY_TO_ONE |
| drawing_revisions | drawing_id | drawings | MANY_TO_ONE |
| drawing_revisions | project_id | projects | MANY_TO_ONE |
| commitment_contracts | project_id | projects | MANY_TO_ONE |
| commitment_contracts | vendor_id | vendors | MANY_TO_ONE |
| commitment_contract_items | commitment_contract_id | commitment_contracts | MANY_TO_ONE |
| change_orders | project_id | projects | MANY_TO_ONE |
| rfis | project_id | projects | MANY_TO_ONE |
| submittals | project_id | projects | MANY_TO_ONE |
| project_users | project_id | projects | MANY_TO_ONE |
| project_users | company_id | companies | MANY_TO_ONE |

---

## Data Transformation Rules

### Metadata Field Mapping

All database columns are preserved in the `metadata` map with these transformations:

| PostgreSQL Type | Transformation | Example |
|-----------------|----------------|---------|
| bigint | String conversion | `562949953567479` → `"562949953567479"` |
| text | Direct copy | `"Project Name"` |
| boolean | Lowercase string | `true` → `"true"` |
| timestamp | ISO 8601 string | `"2021-04-02T15:35:33"` |
| date | ISO 8601 date | `"2021-04-02"` |
| numeric | String with precision | `0.05` → `"0.05"` |
| jsonb | JSON string | `{"key": "value"}` → `"{\"key\": \"value\"}"` |
| array | JSON array string | `[1, 2, 3]` → `"[1, 2, 3]"` |
| NULL | Omitted from map | (not included) |

### Content Text Generation

For BM25 search, the `content_text` field is populated by concatenating:

```python
content_fields = {
    'projects': ['name', 'display_name', 'address', 'city'],
    'photos': ['description', 'location'],
    'drawings': ['drawing_number', 'title', 'discipline'],
    'rfis': ['number', 'subject', 'question'],
    'submittals': ['number', 'title', 'description'],
    'change_orders': ['number', 'title', 'description'],
    'commitment_contracts': ['number', 'title', 'description'],
    # ... more tables
}
```

### File Reference Extraction

From JSONB columns:
```python
# Input: {"562951022152066": "company/project/change_orders/id/file.pdf"}
# Output: [FileRef(s3_key="company/project/change_orders/id/file.pdf", ...)]

def extract_file_refs(jsonb_value: dict) -> list[FileRef]:
    return [FileRef(s3_key=v) for v in jsonb_value.values()]
```

From text columns:
```python
# Direct s3_key column
# Input: "562949953425831/562949954923622/photos/562950208716653/IMG_1128.jpg"
# Output: FileRef(s3_key="562949953425831/562949954923622/photos/562950208716653/IMG_1128.jpg")
```

---

## State Transitions

### Ingestion Job State Machine

```
                          ┌──────────┐
                          │ PENDING  │
                          └────┬─────┘
                               │ start()
                               ▼
                          ┌──────────┐
           cancel()  ←────│ RUNNING  │────► error()
              │           └────┬─────┘          │
              ▼                │ complete()     ▼
        ┌───────────┐          │          ┌──────────┐
        │ CANCELLED │          ▼          │  FAILED  │
        └───────────┘     ┌──────────┐    └──────────┘
                          │COMPLETED │
                          └──────────┘
```

### File Download State Machine

```
        ┌─────────┐
        │ PENDING │
        └────┬────┘
             │
     ┌───────┴───────┐
     │               │
     ▼               ▼
┌─────────┐    ┌──────────┐
│ SUCCESS │    │ SKIPPED  │ (unsupported type, too large)
└─────────┘    └──────────┘
     │
     └──► ┌──────────┐
          │  FAILED  │ (network error, 403, 404)
          └──────────┘
```

---

## Validation Rules

### Record Validation

1. **doc_id**: Required, unique, format `{table}:{id}`
2. **source_table**: Required, must exist in SchemaMap
3. **source_id**: Required, must be valid bigint string
4. **project_id**: Optional, but required for project-scoped tables
5. **updated_at**: Required, must be valid timestamp

### File Reference Validation

1. **s3_key**: Must match pattern `^\d+/\d+/\w+/\d+/.+$`
2. **filename**: Extracted from s3_key path
3. **file_type**: Validated against supported types (pdf, jpg, png, jpeg, gif, tiff)

### Relationship Validation

1. Target table must exist in SchemaMap
2. Target ID should be non-null (warn if null, don't fail)

---

## Example Data

### IngestedRecord Example (Photo)

```json
{
  "doc_id": "photos:562950208716653",
  "source_table": "photos",
  "source_id": "562950208716653",
  "project_id": 562949954923622,
  "metadata": {
    "id": "562950208716653",
    "project_id": "562949954923622",
    "url": "https://storage.procore.com/api/v5/files/...",
    "thumbnail_url": "https://storage.procore.com/api/v5/files/...",
    "s3_key": "562949953425831/562949954923622/photos/562950208716653/IMG_1128.jpg",
    "description": "HVAC unit installation",
    "location": "Building A, Floor 2",
    "taken_at": "2024-03-15T10:30:00",
    "created_at": "2024-03-15T10:35:00",
    "updated_at": "2024-03-15T10:35:00"
  },
  "relationships": [
    {"type": "project", "target_table": "projects", "target_id": "562949954923622"}
  ],
  "file_references": [
    {
      "s3_key": "562949953425831/562949954923622/photos/562950208716653/IMG_1128.jpg",
      "source_column": "s3_key",
      "filename": "IMG_1128.jpg"
    }
  ],
  "content_text": "HVAC unit installation Building A, Floor 2",
  "created_at": 1710499500000,
  "updated_at": 1710499500000,
  "ingested_at": 1736870400000
}
```

### IngestedRecord Example (Change Order with Attachments)

```json
{
  "doc_id": "change_orders:562949956208422",
  "source_table": "change_orders",
  "source_id": "562949956208422",
  "project_id": 562949954229558,
  "metadata": {
    "id": "562949956208422",
    "project_id": "562949954229558",
    "number": "CO-011",
    "title": "HVAC Equipment Change",
    "description": "Replace AHU-1 with higher capacity unit",
    "status": "approved",
    "attachment_s3_keys": "{\"562951022152066\": \"562949953425831/.../EOS_CO11.pdf\"}"
  },
  "relationships": [
    {"type": "project", "target_table": "projects", "target_id": "562949954229558"}
  ],
  "file_references": [
    {
      "s3_key": "562949953425831/562949954229558/change_orders/562949956208422/EOS_CO11.pdf",
      "source_column": "attachment_s3_keys",
      "filename": "EOS_CO11.pdf"
    },
    {
      "s3_key": "562949953425831/562949954229558/change_orders/562949956208422/another_file.pdf",
      "source_column": "attachment_s3_keys",
      "filename": "another_file.pdf"
    }
  ],
  "content_text": "CO-011 HVAC Equipment Change Replace AHU-1 with higher capacity unit",
  "created_at": 1710499500000,
  "updated_at": 1710600000000,
  "ingested_at": 1736870400000
}
```
