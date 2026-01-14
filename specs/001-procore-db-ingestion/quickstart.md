# Quickstart: Procore Database Ingestion

**Feature**: 001-procore-db-ingestion
**Date**: 2026-01-14

## Overview

This guide covers setting up and running the Procore database ingestion pipeline for the ColPali visual retrieval system.

---

## Prerequisites

### Required

- Python 3.11+
- Local Vespa instance running (or Vespa Cloud connection)
- PostgreSQL database access (read-only)

### Optional (for file ingestion)

- AWS credentials for S3 access
- ColPali model (auto-downloads on first use)

---

## Setup

### 1. Install Dependencies

```bash
# From project root
pip install asyncpg boto3 aiosqlite
```

Or add to requirements.txt:
```
asyncpg>=0.29.0
boto3>=1.34.0
aiosqlite>=0.19.0
```

### 2. Configure Environment

Create or update `.env`:

```bash
# Required: Procore Database
PROCORE_DATABASE_URL=postgresql://user:pass@host:5432/procore_int_v2

# Optional: Vespa (defaults to localhost)
VESPA_LOCAL_URL=http://localhost:8080

# Optional: AWS for S3 file downloads
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1

# Optional: Logging
LOG_LEVEL=INFO
```

### 3. Start Vespa (if not running)

```bash
docker compose up -d
```

Wait for Vespa to be ready:
```bash
curl -s http://localhost:8080/state/v1/health | jq .status
# Should return: "up"
```

---

## Usage

### Step 1: Discover Database Schema

First, investigate the database structure:

```bash
# Generate schema report
python scripts/discover_schema.py --format markdown --output schema-report.md

# Or JSON for programmatic use
python scripts/discover_schema.py --format json --output schema-map.json

# Include sample data
python scripts/discover_schema.py --include-samples --format markdown --output schema-with-samples.md
```

Review the output to understand:
- Available tables and their columns
- Row counts per table
- File reference columns (S3 keys, URLs)
- Implicit relationships

### Step 2: Run Full Ingestion

Ingest all database records:

```bash
# Basic full ingestion
python scripts/ingest_database.py --full

# With specific tables
python scripts/ingest_database.py --full --tables projects photos drawings

# Exclude system tables
python scripts/ingest_database.py --full --exclude _prisma_migrations sync_events webhook_*

# With file downloads (requires AWS credentials)
python scripts/ingest_database.py --full --download-files --file-workers 4

# Dry run to see what would be ingested
python scripts/ingest_database.py --full --dry-run
```

### Step 3: Start Sync Daemon (Optional)

For continuous synchronization:

```bash
# Start daemon (runs in background)
python scripts/sync_database.py --daemon

# Custom sync interval (every 5 minutes)
python scripts/sync_database.py --daemon --interval 300

# Check sync status
python scripts/sync_database.py --status

# Run single sync cycle
python scripts/sync_database.py --once
```

---

## Common Workflows

### Workflow 1: Initial Setup

```bash
# 1. Discover schema
python scripts/discover_schema.py --format both --output specs/001-procore-db-ingestion/

# 2. Review schema-report.md to understand data

# 3. Run full ingestion (no files first)
python scripts/ingest_database.py --full --exclude _prisma_migrations

# 4. Verify data in Vespa
curl -s 'http://localhost:8080/search/?yql=select%20*%20from%20procore_record%20where%20true%20limit%2010' | jq .

# 5. Start sync daemon
python scripts/sync_database.py --daemon &
```

### Workflow 2: Add File Ingestion

```bash
# 1. Check file reference columns
python scripts/discover_schema.py --format json | jq '.tables[].file_reference_columns'

# 2. Ingest with file downloads
python scripts/ingest_database.py --full --download-files

# 3. Verify files are indexed
curl -s 'http://localhost:8080/search/?yql=select%20*%20from%20pdf_page%20where%20true%20limit%205' | jq .
```

### Workflow 3: Resume Failed Ingestion

```bash
# If ingestion fails, get the job ID from output
# Output shows: "Job ID: 550e8400-e29b-41d4-a716-446655440000"

# Resume from checkpoint
python scripts/ingest_database.py --resume 550e8400-e29b-41d4-a716-446655440000

# Or start fresh incremental sync
python scripts/ingest_database.py --incremental
```

---

## Querying Ingested Data

### Search Database Records

```bash
# All records from a table
curl -s 'http://localhost:8080/search/?yql=select%20*%20from%20procore_record%20where%20source_table%20contains%20"projects"' | jq .

# Records for a specific project
curl -s 'http://localhost:8080/search/?yql=select%20*%20from%20procore_record%20where%20project_id%20=%20562949953567479' | jq .

# Full-text search
curl -s 'http://localhost:8080/search/?query=HVAC&type=all' | jq .
```

### Search Files (Visual Retrieval)

Use the main application at `http://localhost:7860` for visual search, or:

```bash
# Get indexed file count
curl -s 'http://localhost:8080/search/?yql=select%20count()%20from%20pdf_page%20where%20true' | jq .

# Search files by filename pattern
curl -s 'http://localhost:8080/search/?yql=select%20*%20from%20pdf_page%20where%20title%20contains%20"drawing"' | jq .
```

---

## Monitoring

### Check Ingestion Status

```bash
# Via CLI
python scripts/sync_database.py --status

# Via logs
tail -f /var/log/procore-ingestion.log
```

### Vespa Statistics

```bash
# Document count by schema
curl -s http://localhost:8080/metrics/v1/values | jq '.nodes[].metrics[] | select(.name | contains("document_count"))'

# Index status
curl -s http://localhost:8080/state/v1/health | jq .
```

---

## Troubleshooting

### Connection Issues

```bash
# Test database connection
PGPASSWORD=xxx psql -h host -U user -d database -c "SELECT 1"

# Test Vespa connection
curl -s http://localhost:8080/state/v1/health
```

### Ingestion Failures

Check logs for specific errors:
```bash
# Show failed records
grep "ERROR" ingestion.log | tail -20

# Check checkpoint status
sqlite3 data/sync_checkpoints.db "SELECT * FROM sync_checkpoints WHERE sync_status = 'FAILED'"
```

### File Download Issues

```bash
# Test S3 access
aws s3 ls s3://bucket-name/path/ --region us-east-1

# Check URL accessibility
curl -I "https://storage.procore.com/api/v5/files/..."
```

---

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PROCORE_DATABASE_URL` | required | PostgreSQL connection string |
| `VESPA_LOCAL_URL` | `http://localhost:8080` | Vespa endpoint |
| `AWS_ACCESS_KEY_ID` | - | AWS access key for S3 |
| `AWS_SECRET_ACCESS_KEY` | - | AWS secret key for S3 |
| `AWS_REGION` | `us-east-1` | AWS region |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

### Ingestion Defaults

| Setting | Default | Description |
|---------|---------|-------------|
| Batch size | 10,000 | Records per batch |
| Vespa workers | 4 | Parallel feeding threads |
| File workers | 2 | Parallel download threads |
| Sync interval | 300s | Time between sync cycles |
| Max file size | 100MB | Skip files larger than this |

---

## Next Steps

After initial setup:

1. **Review schema report** - Understand your data structure
2. **Customize exclusions** - Skip tables you don't need
3. **Enable file ingestion** - Download and index documents
4. **Start sync daemon** - Keep data fresh automatically
5. **Test visual search** - Query documents in the UI
