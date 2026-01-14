# CLI Interface Contracts

**Feature**: 001-procore-db-ingestion
**Date**: 2026-01-14

## Overview

Three CLI scripts provide the primary interface for database ingestion:
1. `discover_schema.py` - Database schema discovery and documentation
2. `ingest_database.py` - Full or incremental data ingestion
3. `sync_database.py` - Continuous change detection and sync daemon

All scripts follow the existing pattern in `scripts/feed_data.py`.

---

## 1. Schema Discovery CLI

**Script**: `scripts/discover_schema.py`

### Usage

```bash
# Basic discovery
python scripts/discover_schema.py

# With custom output
python scripts/discover_schema.py --output schema-map.json --format json

# Human-readable report
python scripts/discover_schema.py --format markdown --output schema-report.md

# Target specific database
python scripts/discover_schema.py --database-url "postgresql://user:pass@host:5432/db"
```

### Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--database-url` | string | `$PROCORE_DATABASE_URL` | PostgreSQL connection string |
| `--output` | path | stdout | Output file path |
| `--format` | enum | `json` | Output format: `json`, `markdown`, `both` |
| `--include-samples` | flag | false | Include sample data (first 5 rows per table) |
| `--include-stats` | flag | true | Include row counts and column statistics |

### Output (JSON format)

```json
{
  "discovery_timestamp": "2026-01-14T10:30:00Z",
  "database_name": "procore_int_v2",
  "database_host": "database-3.xxx.rds.amazonaws.com",
  "schemas": [
    {
      "name": "public",
      "tables": [
        {
          "name": "projects",
          "row_count": 31,
          "columns": [
            {
              "name": "id",
              "data_type": "bigint",
              "is_nullable": false,
              "default_value": null
            }
          ],
          "timestamp_columns": ["created_at", "updated_at", "last_synced_at"],
          "file_reference_columns": []
        }
      ]
    }
  ],
  "relationships": [
    {
      "source_table": "photos",
      "source_column": "project_id",
      "target_table": "projects",
      "target_column": "id"
    }
  ],
  "file_references_summary": {
    "total_columns": 33,
    "tables_with_files": 16,
    "estimated_file_count": 16000
  }
}
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Connection error |
| 2 | Permission denied |
| 3 | Output write error |

---

## 2. Database Ingestion CLI

**Script**: `scripts/ingest_database.py`

### Usage

```bash
# Full ingestion of all tables
python scripts/ingest_database.py --full

# Ingestion with table selection
python scripts/ingest_database.py --full --tables photos drawings projects

# Exclude specific tables
python scripts/ingest_database.py --full --exclude _prisma_migrations sync_events

# Incremental ingestion (since last checkpoint)
python scripts/ingest_database.py --incremental

# Resume a failed job
python scripts/ingest_database.py --resume job-uuid-here

# Dry run (no actual ingestion)
python scripts/ingest_database.py --full --dry-run
```

### Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--database-url` | string | `$PROCORE_DATABASE_URL` | PostgreSQL connection string |
| `--vespa-url` | string | `$VESPA_LOCAL_URL` or `http://localhost:8080` | Vespa endpoint |
| `--full` | flag | - | Run full ingestion |
| `--incremental` | flag | - | Run incremental ingestion from last checkpoint |
| `--tables` | list | all | Specific tables to ingest |
| `--exclude` | list | none | Tables to exclude |
| `--batch-size` | int | 10000 | Records per batch |
| `--workers` | int | 4 | Parallel workers for Vespa feeding |
| `--download-files` | flag | false | Download and index S3 files |
| `--file-workers` | int | 2 | Parallel workers for file downloads |
| `--dry-run` | flag | false | Show what would be ingested without doing it |
| `--resume` | string | - | Resume a specific job by ID |
| `--verbose` | flag | false | Verbose output |
| `--progress` | flag | true | Show progress bar |

### Output

```
[2026-01-14 10:30:00] Starting full ingestion...
[2026-01-14 10:30:00] Job ID: 550e8400-e29b-41d4-a716-446655440000
[2026-01-14 10:30:01] Schema loaded: 50 tables, 164 relationships
[2026-01-14 10:30:01] Tables to process: 48 (excluding: _prisma_migrations, sync_events)

Processing tables:
  projects          [████████████████████████████████████████] 31/31 (100%)
  photos            [████████████████████████████████████████] 7631/7631 (100%)
  drawings          [████████████████████████████████████████] 5701/5701 (100%)
  ...

[2026-01-14 10:45:00] ════════════════════════════════════════════════════════
[2026-01-14 10:45:00] Ingestion completed
[2026-01-14 10:45:00]   Tables processed: 48
[2026-01-14 10:45:00]   Records indexed: 39,847
[2026-01-14 10:45:00]   Records failed: 0
[2026-01-14 10:45:00]   Duration: 15m 0s
[2026-01-14 10:45:00] ════════════════════════════════════════════════════════
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Database connection error |
| 2 | Vespa connection error |
| 3 | Partial failure (some records failed) |
| 4 | Complete failure |
| 5 | Job cancelled |

---

## 3. Sync Daemon CLI

**Script**: `scripts/sync_database.py`

### Usage

```bash
# Start sync daemon
python scripts/sync_database.py --daemon

# Run single sync cycle
python scripts/sync_database.py --once

# Sync specific tables only
python scripts/sync_database.py --daemon --tables photos drawings

# Custom sync interval
python scripts/sync_database.py --daemon --interval 300

# Check sync status
python scripts/sync_database.py --status
```

### Arguments

| Argument | Type | Default | Description |
|----------|------|---------|-------------|
| `--database-url` | string | `$PROCORE_DATABASE_URL` | PostgreSQL connection string |
| `--vespa-url` | string | `$VESPA_LOCAL_URL` | Vespa endpoint |
| `--daemon` | flag | - | Run as continuous daemon |
| `--once` | flag | - | Run single sync cycle and exit |
| `--status` | flag | - | Show current sync status |
| `--interval` | int | 300 | Sync interval in seconds (daemon mode) |
| `--tables` | list | all | Tables to sync |
| `--exclude` | list | none | Tables to exclude from sync |
| `--batch-size` | int | 1000 | Records per batch |
| `--pid-file` | path | `/tmp/procore-sync.pid` | PID file for daemon |

### Status Output

```
Sync Status Report
══════════════════════════════════════════════════════
Last sync: 2026-01-14 10:45:00 (5 minutes ago)
Next sync: 2026-01-14 10:50:00 (in 0 minutes)

Table Status:
  projects          : synced at 10:45:00 (31 records, 0 changes)
  photos            : synced at 10:45:00 (7631 records, 12 changes)
  drawings          : synced at 10:45:00 (5701 records, 3 changes)
  drawing_revisions : synced at 10:45:00 (5481 records, 3 changes)
  ...

Overall:
  Tables monitored: 48
  Total records: 39,847
  Changes detected: 18
  Sync errors: 0
══════════════════════════════════════════════════════
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success (--once or --status) |
| 1 | Connection error |
| 2 | Already running (--daemon) |
| 130 | Interrupted (SIGINT) |
| 143 | Terminated (SIGTERM) |

---

## Environment Variables

All scripts respect these environment variables:

| Variable | Description | Required |
|----------|-------------|----------|
| `PROCORE_DATABASE_URL` | PostgreSQL connection string | Yes |
| `VESPA_LOCAL_URL` | Vespa endpoint URL | No (default: http://localhost:8080) |
| `AWS_ACCESS_KEY_ID` | AWS credentials for S3 | For file download |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials for S3 | For file download |
| `AWS_REGION` | AWS region | For file download |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | No (default: INFO) |

---

## Common Patterns

### Progress Reporting

All scripts use consistent progress reporting:

```python
from tqdm import tqdm

for table in tqdm(tables, desc="Processing tables"):
    for batch in tqdm(batches, desc=f"  {table}", leave=False):
        process_batch(batch)
```

### Error Handling

All scripts catch and report errors consistently:

```python
try:
    result = operation()
except ConnectionError as e:
    logger.error(f"Connection failed: {e}")
    sys.exit(1)
except PermissionError as e:
    logger.error(f"Permission denied: {e}")
    sys.exit(2)
```

### Logging Format

```
%(levelname)s: \t %(asctime)s \t %(message)s
```

Example:
```
INFO:    2026-01-14 10:30:00    Starting ingestion for table: photos
DEBUG:   2026-01-14 10:30:01    Fetched batch 1/8 (1000 records)
ERROR:   2026-01-14 10:30:02    Failed to index record photos:123 - timeout
```
