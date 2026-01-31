"""
Source connectors for file ingestion from external systems.

Connectors provide a unified interface for discovering and downloading files
from various sources (Procore, SharePoint, Google Drive, etc.) with rich
metadata for filtering and organization.
"""

from backend.ingestion.connectors.base import (
    FileMetadata,
    SourceConnector,
    ConnectorConfig,
    DownloadResult,
)
from backend.ingestion.connectors.procore import ProcoreConnector

__all__ = [
    "FileMetadata",
    "SourceConnector",
    "ConnectorConfig",
    "DownloadResult",
    "ProcoreConnector",
]
