"""
Procore Database Ingestion Module

Automatic data ingestion from Procore PostgreSQL database into Vespa.
"""

from backend.ingestion.exceptions import (
    IngestionError,
    ConnectionError,
    SchemaError,
    TransformError,
    IndexError,
    DownloadError,
)
from backend.ingestion.db_connection import ConnectionConfig, DatabaseConnection
from backend.ingestion.checkpoint import CheckpointStore, Checkpoint
from backend.ingestion.schema_discovery import (
    SchemaDiscovery,
    SchemaMap,
    Table,
    Column,
    FileReferenceColumn,
    FileReferenceType,
    ImplicitRelationship,
)
from backend.ingestion.record_ingester import (
    RecordIngester,
    IngestedRecord,
    IngestionResult,
    RelationshipLink,
    FileReferenceLink,
)
from backend.ingestion.file_detector import (
    FileDetector,
    DetectedFile,
)
from backend.ingestion.file_downloader import (
    FileDownloader,
    DownloadResult,
    DownloadStrategy,
)
from backend.ingestion.change_detector import (
    ChangeDetector,
    Change,
    ChangeSet,
)
from backend.ingestion.sync_manager import (
    SyncManager,
    SyncConfig,
    SyncResult,
    IngestionJob,
)

__all__ = [
    # Exceptions
    "IngestionError",
    "ConnectionError",
    "SchemaError",
    "TransformError",
    "IndexError",
    "DownloadError",
    # Database
    "ConnectionConfig",
    "DatabaseConnection",
    # Checkpoint
    "CheckpointStore",
    "Checkpoint",
    # Schema Discovery
    "SchemaDiscovery",
    "SchemaMap",
    "Table",
    "Column",
    "FileReferenceColumn",
    "FileReferenceType",
    "ImplicitRelationship",
    # Record Ingester
    "RecordIngester",
    "IngestedRecord",
    "IngestionResult",
    "RelationshipLink",
    "FileReferenceLink",
    # File Detection
    "FileDetector",
    "DetectedFile",
    # File Download
    "FileDownloader",
    "DownloadResult",
    "DownloadStrategy",
    # Change Detection
    "ChangeDetector",
    "Change",
    "ChangeSet",
    # Sync Manager
    "SyncManager",
    "SyncConfig",
    "SyncResult",
    "IngestionJob",
]
