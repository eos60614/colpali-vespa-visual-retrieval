# Internal API Contracts

**Feature**: 001-procore-db-ingestion
**Date**: 2026-01-14

## Overview

This document defines the internal Python API contracts for the ingestion module components. These are not HTTP APIs but Python interfaces used between modules.

---

## 1. Database Connection Module

**Module**: `backend/ingestion/db_connection.py`

### DatabaseConnection Class

```python
from typing import AsyncContextManager, List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class ConnectionConfig:
    """Database connection configuration."""
    host: str
    port: int
    database: str
    user: str
    password: str
    ssl: bool = True
    pool_size: int = 5

    @classmethod
    def from_url(cls, url: str) -> 'ConnectionConfig':
        """Parse PostgreSQL connection URL."""
        ...

class DatabaseConnection:
    """Async PostgreSQL connection manager."""

    def __init__(self, config: ConnectionConfig, logger: logging.Logger):
        """Initialize connection with config."""
        ...

    async def connect(self) -> None:
        """Establish connection pool."""
        ...

    async def close(self) -> None:
        """Close connection pool."""
        ...

    async def execute(self, query: str, *args) -> List[Dict[str, Any]]:
        """Execute query and return results as list of dicts."""
        ...

    async def execute_many(self, query: str, args_list: List[tuple]) -> int:
        """Execute query for multiple parameter sets. Returns row count."""
        ...

    async def stream(self, query: str, *args, batch_size: int = 1000) -> AsyncIterator[Dict[str, Any]]:
        """Stream query results in batches."""
        ...

    def transaction(self) -> AsyncContextManager:
        """Context manager for transactions."""
        ...

    @property
    def is_connected(self) -> bool:
        """Check if connection is active."""
        ...
```

### Usage Example

```python
config = ConnectionConfig.from_url(os.environ['PROCORE_DATABASE_URL'])
db = DatabaseConnection(config, logger)

await db.connect()
try:
    rows = await db.execute("SELECT * FROM projects WHERE active = $1", True)
    async for batch in db.stream("SELECT * FROM photos", batch_size=1000):
        process_batch(batch)
finally:
    await db.close()
```

---

## 2. Schema Discovery Module

**Module**: `backend/ingestion/schema_discovery.py`

### Types

```python
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class FileReferenceType(Enum):
    S3_KEY = "s3_key"
    URL = "url"
    JSONB_S3_MAP = "jsonb_s3_map"

@dataclass
class Column:
    name: str
    data_type: str
    is_nullable: bool
    default_value: Optional[str] = None
    max_length: Optional[int] = None

@dataclass
class FileReferenceColumn:
    column_name: str
    reference_type: FileReferenceType
    pattern: str

@dataclass
class Table:
    name: str
    row_count: int
    columns: List[Column] = field(default_factory=list)
    timestamp_columns: List[str] = field(default_factory=list)
    file_reference_columns: List[FileReferenceColumn] = field(default_factory=list)

@dataclass
class ImplicitRelationship:
    source_table: str
    source_column: str
    target_table: str
    target_column: str = "id"

@dataclass
class SchemaMap:
    discovery_timestamp: str
    database_name: str
    tables: List[Table] = field(default_factory=list)
    relationships: List[ImplicitRelationship] = field(default_factory=list)
```

### SchemaDiscovery Class

```python
class SchemaDiscovery:
    """Database schema introspection."""

    def __init__(self, db: DatabaseConnection, logger: logging.Logger):
        ...

    async def discover(self, include_samples: bool = False) -> SchemaMap:
        """Perform full schema discovery."""
        ...

    async def get_tables(self, schema: str = "public") -> List[str]:
        """Get list of table names."""
        ...

    async def get_columns(self, table: str) -> List[Column]:
        """Get columns for a table."""
        ...

    async def get_row_count(self, table: str) -> int:
        """Get row count for a table."""
        ...

    async def detect_file_columns(self, table: str, columns: List[Column]) -> List[FileReferenceColumn]:
        """Detect columns containing file references."""
        ...

    async def infer_relationships(self, tables: List[Table]) -> List[ImplicitRelationship]:
        """Infer relationships from _id column patterns."""
        ...

    def to_json(self, schema_map: SchemaMap) -> str:
        """Export schema map to JSON."""
        ...

    def to_markdown(self, schema_map: SchemaMap) -> str:
        """Export schema map to Markdown."""
        ...
```

---

## 3. Record Ingester Module

**Module**: `backend/ingestion/record_ingester.py`

### Types

```python
@dataclass
class IngestedRecord:
    doc_id: str
    source_table: str
    source_id: str
    project_id: Optional[int]
    metadata: Dict[str, str]
    relationships: List[Dict[str, str]]
    file_references: List[Dict[str, str]]
    content_text: str
    created_at: int
    updated_at: int
    ingested_at: int

@dataclass
class IngestionResult:
    success: bool
    doc_id: str
    error: Optional[str] = None
```

### RecordIngester Class

```python
class RecordIngester:
    """Transform and index database records to Vespa."""

    def __init__(
        self,
        db: DatabaseConnection,
        vespa: Vespa,
        schema_map: SchemaMap,
        logger: logging.Logger
    ):
        ...

    async def ingest_table(
        self,
        table: str,
        batch_size: int = 10000,
        since: Optional[datetime] = None
    ) -> AsyncIterator[IngestionResult]:
        """Ingest records from a table. Yields result for each record."""
        ...

    def transform_record(self, table: str, row: Dict[str, Any]) -> IngestedRecord:
        """Transform a database row to IngestedRecord."""
        ...

    def extract_relationships(self, table: str, row: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract relationship references from row."""
        ...

    def extract_file_references(self, table: str, row: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract file references from row."""
        ...

    def generate_content_text(self, table: str, row: Dict[str, Any]) -> str:
        """Generate searchable text content from row."""
        ...

    async def index_record(self, record: IngestedRecord) -> IngestionResult:
        """Index a single record to Vespa."""
        ...

    async def index_batch(self, records: List[IngestedRecord]) -> List[IngestionResult]:
        """Index a batch of records to Vespa in parallel."""
        ...
```

---

## 4. File Detector Module

**Module**: `backend/ingestion/file_detector.py`

### FileDetector Class

```python
@dataclass
class DetectedFile:
    s3_key: str
    source_table: str
    source_record_id: str
    source_column: str
    filename: Optional[str]
    file_size: Optional[int]
    url: Optional[str]

class FileDetector:
    """Detect and extract file references from database records."""

    def __init__(self, schema_map: SchemaMap, logger: logging.Logger):
        ...

    def detect_in_record(self, table: str, row: Dict[str, Any]) -> List[DetectedFile]:
        """Detect all file references in a record."""
        ...

    def parse_s3_key(self, column: str, value: str) -> Optional[DetectedFile]:
        """Parse a direct S3 key value."""
        ...

    def parse_jsonb_attachments(self, column: str, value: dict) -> List[DetectedFile]:
        """Parse JSONB map of file ID to S3 key."""
        ...

    def parse_url(self, column: str, value: str) -> Optional[DetectedFile]:
        """Parse a URL reference (Procore signed URL)."""
        ...

    def extract_filename(self, s3_key: str) -> str:
        """Extract filename from S3 key path."""
        ...

    def infer_file_type(self, filename: str) -> str:
        """Infer file type from filename extension."""
        ...
```

---

## 5. File Downloader Module

**Module**: `backend/ingestion/file_downloader.py`

### Types

```python
@dataclass
class DownloadResult:
    s3_key: str
    success: bool
    local_path: Optional[Path] = None
    file_size: Optional[int] = None
    error: Optional[str] = None
    status: str = "pending"  # pending, success, failed, skipped

class DownloadStrategy(Enum):
    PROCORE_URL = "procore_url"  # Use signed URL from database
    DIRECT_S3 = "direct_s3"      # Use boto3 with AWS credentials
```

### FileDownloader Class

```python
class FileDownloader:
    """Download files from S3/URLs for indexing."""

    def __init__(
        self,
        download_dir: Path,
        strategy: DownloadStrategy = DownloadStrategy.PROCORE_URL,
        logger: logging.Logger = None,
        aws_config: Optional[Dict[str, str]] = None
    ):
        ...

    async def download(self, file: DetectedFile) -> DownloadResult:
        """Download a single file."""
        ...

    async def download_batch(
        self,
        files: List[DetectedFile],
        workers: int = 2
    ) -> AsyncIterator[DownloadResult]:
        """Download files in parallel, yielding results."""
        ...

    async def download_from_url(self, url: str, dest: Path) -> DownloadResult:
        """Download file from Procore signed URL."""
        ...

    async def download_from_s3(self, s3_key: str, dest: Path) -> DownloadResult:
        """Download file directly from S3 using boto3."""
        ...

    def should_skip(self, file: DetectedFile) -> tuple[bool, str]:
        """Check if file should be skipped (unsupported type, too large)."""
        ...

    @property
    def supported_types(self) -> set[str]:
        """File extensions supported for visual retrieval."""
        return {'pdf', 'jpg', 'jpeg', 'png', 'gif', 'tiff'}

    @property
    def max_file_size(self) -> int:
        """Maximum file size in bytes (default 100MB)."""
        return 100 * 1024 * 1024
```

---

## 6. Change Detector Module

**Module**: `backend/ingestion/change_detector.py`

### Types

```python
@dataclass
class Change:
    table: str
    record_id: str
    change_type: str  # "insert", "update", "delete"
    updated_at: datetime
    row: Optional[Dict[str, Any]] = None

@dataclass
class ChangeSet:
    table: str
    since: datetime
    until: datetime
    inserts: List[Change]
    updates: List[Change]
    deletes: List[Change]

    @property
    def total_changes(self) -> int:
        return len(self.inserts) + len(self.updates) + len(self.deletes)
```

### ChangeDetector Class

```python
class ChangeDetector:
    """Detect changes in database tables since last sync."""

    def __init__(
        self,
        db: DatabaseConnection,
        checkpoint_store: CheckpointStore,
        logger: logging.Logger
    ):
        ...

    async def detect_changes(
        self,
        table: str,
        since: Optional[datetime] = None
    ) -> ChangeSet:
        """Detect all changes in a table since timestamp."""
        ...

    async def get_updated_records(
        self,
        table: str,
        since: datetime,
        batch_size: int = 1000
    ) -> AsyncIterator[Dict[str, Any]]:
        """Stream records updated since timestamp."""
        ...

    async def detect_deletes(
        self,
        table: str,
        known_ids: Set[str],
        sample_size: int = 1000
    ) -> List[str]:
        """Detect deleted records by comparing with known IDs."""
        ...

    def get_timestamp_column(self, table: str) -> str:
        """Get the best timestamp column for change detection."""
        ...
```

---

## 7. Checkpoint Module

**Module**: `backend/ingestion/checkpoint.py`

### CheckpointStore Class

```python
@dataclass
class Checkpoint:
    table_name: str
    last_sync_timestamp: datetime
    last_record_id: Optional[str]
    records_processed: int
    records_failed: int
    sync_status: str
    error_message: Optional[str]
    updated_at: datetime

class CheckpointStore:
    """Persist sync checkpoints in SQLite."""

    def __init__(self, db_path: Path):
        ...

    async def initialize(self) -> None:
        """Create checkpoint table if not exists."""
        ...

    async def get(self, table_name: str) -> Optional[Checkpoint]:
        """Get checkpoint for a table."""
        ...

    async def set(self, checkpoint: Checkpoint) -> None:
        """Update checkpoint for a table."""
        ...

    async def get_all(self) -> List[Checkpoint]:
        """Get all checkpoints."""
        ...

    async def clear(self, table_name: Optional[str] = None) -> None:
        """Clear checkpoint(s)."""
        ...

    async def get_last_sync_time(self, table_name: str) -> Optional[datetime]:
        """Get last successful sync timestamp for a table."""
        ...
```

---

## 8. Sync Manager Module

**Module**: `backend/ingestion/sync_manager.py`

### Types

```python
@dataclass
class SyncConfig:
    tables: Optional[List[str]] = None  # None = all
    exclude_tables: List[str] = field(default_factory=list)
    batch_size: int = 1000
    download_files: bool = False
    file_workers: int = 2

@dataclass
class SyncResult:
    job_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    tables_processed: int
    records_processed: int
    records_failed: int
    files_downloaded: int
    files_failed: int
    errors: List[str]
```

### SyncManager Class

```python
class SyncManager:
    """Orchestrate database sync operations."""

    def __init__(
        self,
        db: DatabaseConnection,
        vespa: Vespa,
        schema_map: SchemaMap,
        checkpoint_store: CheckpointStore,
        logger: logging.Logger
    ):
        ...

    async def run_full_sync(self, config: SyncConfig) -> SyncResult:
        """Run full ingestion of all data."""
        ...

    async def run_incremental_sync(self, config: SyncConfig) -> SyncResult:
        """Run incremental sync from last checkpoints."""
        ...

    async def sync_table(
        self,
        table: str,
        full: bool = False,
        config: SyncConfig = None
    ) -> int:
        """Sync a single table. Returns records processed."""
        ...

    async def get_status(self) -> Dict[str, Any]:
        """Get current sync status for all tables."""
        ...

    def get_tables_to_sync(self, config: SyncConfig) -> List[str]:
        """Get list of tables to sync based on config."""
        ...
```

---

## Error Handling

All modules use consistent exception types:

```python
class IngestionError(Exception):
    """Base exception for ingestion errors."""
    pass

class ConnectionError(IngestionError):
    """Database or Vespa connection error."""
    pass

class SchemaError(IngestionError):
    """Schema discovery or validation error."""
    pass

class TransformError(IngestionError):
    """Record transformation error."""
    pass

class IndexError(IngestionError):
    """Vespa indexing error."""
    pass

class DownloadError(IngestionError):
    """File download error."""
    pass
```
