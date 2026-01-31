"""
Database ingestion module for Procore PostgreSQL.

Provides automatic data ingestion from Procore PostgreSQL database into Vespa.
"""

from backend.ingestion.database.exceptions import (
    IngestionError,
    ConnectionError,
    SchemaError,
    TransformError,
    IndexError,
    DownloadError,
)
from backend.ingestion.database.db_connection import ConnectionConfig, DatabaseConnection
from backend.ingestion.database.checkpoint import CheckpointStore, Checkpoint
from backend.ingestion.database.schema_discovery import (
    SchemaDiscovery,
    SchemaMap,
    Table,
    Column,
    FileReferenceColumn,
    FileReferenceType,
    ImplicitRelationship,
)
from backend.ingestion.database.record_ingester import (
    RecordIngester,
    IngestedRecord,
    IngestionResult,
    RelationshipLink,
    FileReferenceLink,
)
from backend.ingestion.database.file_detector import (
    FileDetector,
    DetectedFile,
)
from backend.ingestion.database.file_downloader import (
    FileDownloader,
    DownloadResult,
    DownloadStrategy,
)
from backend.ingestion.database.change_detector import (
    ChangeDetector,
    Change,
    ChangeSet,
)
from backend.ingestion.database.sync_manager import (
    SyncManager,
    SyncConfig,
    SyncResult,
    IngestionJob,
)
from backend.ingestion.database.pdf_processor import (
    DocumentProcessor,
    PDFProcessingResult,
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
    # Document Processing
    "DocumentProcessor",
    "PDFProcessingResult",
]
