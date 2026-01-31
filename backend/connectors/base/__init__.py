"""
Base connector interface for external document sources.

All source connectors (Procore, Google Drive, Dropbox, etc.) must implement
the BaseConnector interface to integrate with the gateway.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional

from backend.core.logging_config import get_logger
from backend.gateway.schemas import (
    FileInfo,
    DocumentMetadata,
    IngestRequest,
    SourceInfo,
    SourceType,
    IngestOptions,
)

logger = get_logger(__name__)


class ConnectorState(str, Enum):
    """Connector lifecycle states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    SYNCING = "syncing"
    ERROR = "error"


@dataclass
class ConnectorConfig:
    """Base configuration for a connector."""
    source_type: SourceType
    source_id: str
    name: str
    enabled: bool = True
    sync_interval_seconds: int = 3600  # 1 hour default
    webhook_url: Optional[str] = None
    credentials: Dict[str, str] = field(default_factory=dict)
    settings: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    documents_found: int = 0
    documents_ingested: int = 0
    documents_updated: int = 0
    documents_deleted: int = 0
    errors: List[str] = field(default_factory=list)
    started_at: datetime = field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0


@dataclass
class DocumentReference:
    """Reference to a document in the source system."""
    source_path: str
    source_id: str
    filename: str
    mime_type: str
    size_bytes: Optional[int] = None
    modified_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    download_url: Optional[str] = None


class BaseConnector(ABC):
    """
    Abstract base class for document source connectors.

    All connectors must implement these methods to integrate with
    the universal gateway API.
    """

    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.state = ConnectorState.DISCONNECTED
        self.last_sync: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.logger = get_logger(f"connector.{config.source_type.value}")

    @property
    def source_type(self) -> SourceType:
        return self.config.source_type

    @property
    def source_id(self) -> str:
        return self.config.source_id

    @property
    def is_connected(self) -> bool:
        return self.state == ConnectorState.CONNECTED

    # =========================================================================
    # Abstract methods - must be implemented by subclasses
    # =========================================================================

    @abstractmethod
    async def connect(self) -> bool:
        """
        Establish connection to the source system.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    async def disconnect(self):
        """Disconnect from the source system."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if the connection is healthy.

        Returns:
            True if healthy, False otherwise
        """
        pass

    @abstractmethod
    async def list_documents(
        self,
        path: Optional[str] = None,
        recursive: bool = True,
        modified_since: Optional[datetime] = None,
    ) -> AsyncIterator[DocumentReference]:
        """
        List documents available in the source.

        Args:
            path: Optional path to list from (e.g., folder)
            recursive: Whether to list recursively
            modified_since: Only list documents modified after this time

        Yields:
            DocumentReference for each document found
        """
        pass

    @abstractmethod
    async def download_document(
        self,
        doc_ref: DocumentReference,
    ) -> bytes:
        """
        Download a document's content.

        Args:
            doc_ref: Reference to the document

        Returns:
            Raw document bytes
        """
        pass

    @abstractmethod
    async def get_document_metadata(
        self,
        doc_ref: DocumentReference,
    ) -> DocumentMetadata:
        """
        Get metadata for a document.

        Args:
            doc_ref: Reference to the document

        Returns:
            DocumentMetadata with title, description, tags, etc.
        """
        pass

    # =========================================================================
    # Optional methods - can be overridden by subclasses
    # =========================================================================

    async def watch_changes(self) -> AsyncIterator[DocumentReference]:
        """
        Watch for document changes in real-time (if supported).

        Override this method for connectors that support webhooks
        or change notifications.

        Yields:
            DocumentReference for each changed document
        """
        raise NotImplementedError(
            f"{self.source_type.value} connector does not support real-time watching"
        )

    async def get_download_url(
        self,
        doc_ref: DocumentReference,
        expires_in: int = 3600,
    ) -> Optional[str]:
        """
        Get a pre-signed download URL for a document (if supported).

        Args:
            doc_ref: Reference to the document
            expires_in: URL expiration time in seconds

        Returns:
            Pre-signed URL or None if not supported
        """
        return None

    # =========================================================================
    # Helper methods
    # =========================================================================

    def to_ingest_request(
        self,
        doc_ref: DocumentReference,
        content: bytes,
        metadata: DocumentMetadata,
        options: Optional[IngestOptions] = None,
    ) -> IngestRequest:
        """
        Convert a document reference to an IngestRequest.

        Args:
            doc_ref: Document reference
            content: Document content bytes
            metadata: Document metadata
            options: Ingestion options

        Returns:
            IngestRequest ready for the gateway
        """
        import base64

        return IngestRequest(
            source=SourceInfo(
                type=self.source_type,
                id=self.source_id,
                path=doc_ref.source_path,
            ),
            file=FileInfo(
                content=base64.b64encode(content).decode(),
                filename=doc_ref.filename,
                mime_type=doc_ref.mime_type,
                size_bytes=len(content),
            ),
            metadata=metadata,
            options=options or IngestOptions(
                webhook_url=self.config.webhook_url,
            ),
        )

    async def sync(
        self,
        path: Optional[str] = None,
        full_sync: bool = False,
    ) -> SyncResult:
        """
        Sync documents from the source to the gateway.

        This is the main entry point for periodic sync operations.

        Args:
            path: Optional path to sync from
            full_sync: If True, sync all documents; otherwise only changes

        Returns:
            SyncResult with statistics
        """
        from backend.gateway.jobs import job_queue

        result = SyncResult(success=True)
        self.state = ConnectorState.SYNCING

        try:
            modified_since = None if full_sync else self.last_sync

            async for doc_ref in self.list_documents(
                path=path,
                modified_since=modified_since,
            ):
                result.documents_found += 1

                try:
                    # Download document
                    content = await self.download_document(doc_ref)

                    # Get metadata
                    metadata = await self.get_document_metadata(doc_ref)

                    # Create ingest request
                    request = self.to_ingest_request(doc_ref, content, metadata)

                    # Submit to job queue
                    job_queue.create_job(request)
                    result.documents_ingested += 1

                except Exception as e:
                    self.logger.error(f"Error syncing {doc_ref.source_path}: {e}")
                    result.errors.append(f"{doc_ref.source_path}: {str(e)}")

            result.completed_at = datetime.utcnow()
            result.duration_seconds = (
                result.completed_at - result.started_at
            ).total_seconds()
            self.last_sync = result.completed_at
            self.state = ConnectorState.CONNECTED

        except Exception as e:
            result.success = False
            result.errors.append(str(e))
            self.state = ConnectorState.ERROR
            self.last_error = str(e)
            self.logger.exception(f"Sync failed: {e}")

        return result

    def get_status(self) -> Dict[str, Any]:
        """Get connector status information."""
        return {
            "source_type": self.source_type.value,
            "source_id": self.source_id,
            "name": self.config.name,
            "state": self.state.value,
            "enabled": self.config.enabled,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "last_error": self.last_error,
        }


class ConnectorRegistry:
    """
    Registry for managing connector instances.

    Tracks all active connectors and provides lookup/management.
    """

    def __init__(self):
        self._connectors: Dict[str, BaseConnector] = {}

    def register(self, connector: BaseConnector):
        """Register a connector."""
        key = f"{connector.source_type.value}:{connector.source_id}"
        self._connectors[key] = connector
        logger.info(f"Registered connector: {key}")

    def unregister(self, source_type: SourceType, source_id: str):
        """Unregister a connector."""
        key = f"{source_type.value}:{source_id}"
        if key in self._connectors:
            del self._connectors[key]
            logger.info(f"Unregistered connector: {key}")

    def get(
        self,
        source_type: SourceType,
        source_id: str,
    ) -> Optional[BaseConnector]:
        """Get a connector by type and ID."""
        key = f"{source_type.value}:{source_id}"
        return self._connectors.get(key)

    def get_all(self) -> List[BaseConnector]:
        """Get all registered connectors."""
        return list(self._connectors.values())

    def get_by_type(self, source_type: SourceType) -> List[BaseConnector]:
        """Get all connectors of a specific type."""
        return [
            c for c in self._connectors.values()
            if c.source_type == source_type
        ]

    async def connect_all(self):
        """Connect all registered connectors."""
        for connector in self._connectors.values():
            if connector.config.enabled:
                try:
                    await connector.connect()
                except Exception as e:
                    logger.error(
                        f"Failed to connect {connector.source_type.value}/"
                        f"{connector.source_id}: {e}"
                    )

    async def disconnect_all(self):
        """Disconnect all registered connectors."""
        for connector in self._connectors.values():
            try:
                await connector.disconnect()
            except Exception as e:
                logger.error(
                    f"Error disconnecting {connector.source_type.value}/"
                    f"{connector.source_id}: {e}"
                )

    async def health_check_all(self) -> Dict[str, bool]:
        """Run health checks on all connectors."""
        results = {}
        for key, connector in self._connectors.items():
            try:
                results[key] = await connector.health_check()
            except Exception:
                results[key] = False
        return results


# Global connector registry
connector_registry = ConnectorRegistry()
