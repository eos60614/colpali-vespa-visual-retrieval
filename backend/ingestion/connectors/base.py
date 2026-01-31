"""
Base classes and interfaces for source connectors.

Provides abstract base class for implementing connectors to external systems
(Procore, SharePoint, Google Drive, Box, etc.) with rich metadata support
for filtering and organization.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from logging import Logger
from pathlib import Path
from typing import Any, AsyncIterator, Optional

from backend.logging_config import get_logger


class DocumentCategory(str, Enum):
    """Standard document categories for filtering."""

    DRAWING = "drawing"
    PHOTO = "photo"
    SPECIFICATION = "specification"
    SUBMITTAL = "submittal"
    RFI = "rfi"
    CONTRACT = "contract"
    INVOICE = "invoice"
    REPORT = "report"
    CORRESPONDENCE = "correspondence"
    MEETING_MINUTES = "meeting_minutes"
    SCHEDULE = "schedule"
    PERMIT = "permit"
    INSPECTION = "inspection"
    SAFETY = "safety"
    CLOSEOUT = "closeout"
    OTHER = "other"


class DocumentStatus(str, Enum):
    """Document workflow status for filtering."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"
    ARCHIVED = "archived"
    ACTIVE = "active"


@dataclass
class FileMetadata:
    """Rich metadata for a file from an external source.

    This metadata is populated by connectors and flows through the ingestion
    pipeline to be stored in Vespa for filtering and organization.

    Attributes:
        # Identity
        source_system: Name of the source system (e.g., "procore", "sharepoint")
        source_id: Unique ID within the source system
        source_url: Direct URL to view in source system (if available)

        # Location & Hierarchy
        project_id: Project identifier
        project_name: Human-readable project name
        folder_path: Full folder path within the source system
        parent_record_id: ID of parent record (e.g., submittal containing attachment)
        parent_record_type: Type of parent record

        # Classification
        category: Document category for filtering
        document_type: More specific type within category (e.g., "floor_plan", "elevation")
        discipline: Engineering discipline (e.g., "architectural", "structural", "mep")
        status: Document workflow status
        revision: Revision identifier (e.g., "A", "1", "Rev 2")
        is_current_revision: Whether this is the current/latest revision

        # Attribution
        author: Person who created the document
        author_email: Email of author
        uploaded_by: Person who uploaded to source system
        uploaded_by_email: Email of uploader
        company: Company/vendor associated with document
        company_id: Company identifier in source system

        # Timestamps
        created_at: When document was created
        modified_at: When document was last modified
        uploaded_at: When document was uploaded to source system

        # File Properties
        filename: Original filename
        file_size: File size in bytes
        file_type: File extension (e.g., "pdf", "dwg", "jpg")
        mime_type: MIME type
        checksum: Content hash for deduplication (MD5, SHA256)

        # Content Metadata
        title: Document title (may differ from filename)
        description: Document description
        number: Document number (e.g., drawing number, submittal number)
        tags: User-defined tags for additional filtering
        custom_fields: Additional source-specific metadata

        # Relationships
        related_documents: IDs of related documents in source system
        supersedes: ID of document this supersedes
        superseded_by: ID of document that supersedes this
    """

    # Identity
    source_system: str
    source_id: str
    source_url: Optional[str] = None

    # Location & Hierarchy
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    folder_path: Optional[str] = None
    parent_record_id: Optional[str] = None
    parent_record_type: Optional[str] = None

    # Classification
    category: Optional[DocumentCategory] = None
    document_type: Optional[str] = None
    discipline: Optional[str] = None
    status: Optional[DocumentStatus] = None
    revision: Optional[str] = None
    is_current_revision: bool = True

    # Attribution
    author: Optional[str] = None
    author_email: Optional[str] = None
    uploaded_by: Optional[str] = None
    uploaded_by_email: Optional[str] = None
    company: Optional[str] = None
    company_id: Optional[str] = None

    # Timestamps
    created_at: Optional[datetime] = None
    modified_at: Optional[datetime] = None
    uploaded_at: Optional[datetime] = None

    # File Properties
    filename: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    mime_type: Optional[str] = None
    checksum: Optional[str] = None

    # Content Metadata
    title: Optional[str] = None
    description: Optional[str] = None
    number: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    custom_fields: dict[str, Any] = field(default_factory=dict)

    # Relationships
    related_documents: list[str] = field(default_factory=list)
    supersedes: Optional[str] = None
    superseded_by: Optional[str] = None

    def to_vespa_fields(self) -> dict[str, Any]:
        """Convert metadata to Vespa document fields.

        Returns dict with field names matching pdf_page schema.
        """
        fields = {
            "source_system": self.source_system,
            "source_id": self.source_id,
        }

        # String fields
        if self.source_url:
            fields["source_url"] = self.source_url
        if self.project_id:
            fields["project_id"] = self.project_id
        if self.project_name:
            fields["project_name"] = self.project_name
        if self.folder_path:
            fields["folder_path"] = self.folder_path
        if self.parent_record_id:
            fields["parent_record_id"] = self.parent_record_id
        if self.parent_record_type:
            fields["parent_record_type"] = self.parent_record_type
        if self.category:
            fields["category"] = self.category.value
        if self.document_type:
            fields["document_type"] = self.document_type
        if self.discipline:
            fields["discipline"] = self.discipline
        if self.status:
            fields["status"] = self.status.value
        if self.revision:
            fields["revision"] = self.revision
        fields["is_current_revision"] = self.is_current_revision
        if self.author:
            fields["author"] = self.author
        if self.company:
            fields["company"] = self.company
        if self.company_id:
            fields["company_id"] = self.company_id
        if self.filename:
            fields["filename"] = self.filename
        if self.file_type:
            fields["file_type"] = self.file_type
        if self.title:
            fields["title"] = self.title
        if self.description:
            fields["description"] = self.description
        if self.number:
            fields["document_number"] = self.number

        # Timestamps as epoch milliseconds
        if self.created_at:
            fields["source_created_at"] = int(self.created_at.timestamp() * 1000)
        if self.modified_at:
            fields["source_modified_at"] = int(self.modified_at.timestamp() * 1000)

        # Arrays
        if self.tags:
            fields["tags"] = self.tags

        return fields

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "source_system": self.source_system,
            "source_id": self.source_id,
        }

        # Add all non-None optional fields
        optional_fields = [
            "source_url", "project_id", "project_name", "folder_path",
            "parent_record_id", "parent_record_type", "document_type",
            "discipline", "revision", "author", "author_email",
            "uploaded_by", "uploaded_by_email", "company", "company_id",
            "filename", "file_size", "file_type", "mime_type", "checksum",
            "title", "description", "number", "supersedes", "superseded_by",
        ]
        for field_name in optional_fields:
            value = getattr(self, field_name)
            if value is not None:
                result[field_name] = value

        # Enums
        if self.category:
            result["category"] = self.category.value
        if self.status:
            result["status"] = self.status.value

        # Boolean
        result["is_current_revision"] = self.is_current_revision

        # Timestamps
        if self.created_at:
            result["created_at"] = self.created_at.isoformat()
        if self.modified_at:
            result["modified_at"] = self.modified_at.isoformat()
        if self.uploaded_at:
            result["uploaded_at"] = self.uploaded_at.isoformat()

        # Lists
        if self.tags:
            result["tags"] = self.tags
        if self.related_documents:
            result["related_documents"] = self.related_documents
        if self.custom_fields:
            result["custom_fields"] = self.custom_fields

        return result


@dataclass
class DownloadResult:
    """Result of downloading a file from external source."""

    success: bool
    local_path: Optional[Path] = None
    metadata: Optional[FileMetadata] = None
    file_size: Optional[int] = None
    error: Optional[str] = None
    status: str = "pending"  # pending, success, failed, skipped


@dataclass
class ConnectorConfig:
    """Configuration for a source connector."""

    name: str
    enabled: bool = True
    download_workers: int = 2
    download_timeout_seconds: int = 300
    max_file_size_mb: int = 100
    supported_types: list[str] = field(
        default_factory=lambda: ["pdf", "jpg", "jpeg", "png", "gif", "tiff"]
    )
    extra: dict[str, Any] = field(default_factory=dict)


class SourceConnector(ABC):
    """Abstract base class for source system connectors.

    Implement this interface to add support for new external sources
    (SharePoint, Google Drive, Box, Dropbox, etc.).

    Example:
        class SharePointConnector(SourceConnector):
            async def discover_files(self, since=None, filters=None):
                # Query SharePoint API for files
                async for file_meta in self._list_drive_items(since):
                    yield file_meta

            async def download_file(self, file: FileMetadata, dest_dir: Path):
                # Download via Graph API
                path = await self._download_drive_item(file.source_id, dest_dir)
                return DownloadResult(success=True, local_path=path, metadata=file)

            async def get_metadata(self, source_id: str):
                # Fetch full metadata from SharePoint
                return await self._get_drive_item_metadata(source_id)
    """

    def __init__(
        self,
        config: ConnectorConfig,
        logger: Optional[Logger] = None,
    ):
        """Initialize connector.

        Args:
            config: Connector configuration
            logger: Optional logger instance
        """
        self._config = config
        self._logger = logger or get_logger(self.__class__.__name__)

    @property
    def name(self) -> str:
        """Connector name (e.g., 'procore', 'sharepoint')."""
        return self._config.name

    @property
    def config(self) -> ConnectorConfig:
        """Connector configuration."""
        return self._config

    @abstractmethod
    async def discover_files(
        self,
        since: Optional[datetime] = None,
        filters: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[FileMetadata]:
        """Discover files from the source system.

        Args:
            since: Only return files modified since this timestamp
            filters: Optional filters to apply:
                - project_id: Filter by project
                - category: Filter by document category
                - folder_path: Filter by folder
                - file_types: List of extensions to include

        Yields:
            FileMetadata for each discovered file
        """
        pass

    @abstractmethod
    async def download_file(
        self,
        file: FileMetadata,
        dest_dir: Path,
    ) -> DownloadResult:
        """Download a file to local storage.

        Args:
            file: File metadata from discover_files
            dest_dir: Directory to download into

        Returns:
            DownloadResult with success status and local path
        """
        pass

    @abstractmethod
    async def get_metadata(
        self,
        source_id: str,
    ) -> Optional[FileMetadata]:
        """Fetch full metadata for a specific file.

        Args:
            source_id: Unique ID within source system

        Returns:
            FileMetadata or None if not found
        """
        pass

    async def validate_connection(self) -> bool:
        """Validate that the connector can reach the source system.

        Returns:
            True if connection is valid, False otherwise
        """
        return True

    async def get_project_list(self) -> list[dict[str, str]]:
        """Get list of available projects.

        Returns:
            List of dicts with 'id' and 'name' keys
        """
        return []

    async def get_folder_tree(
        self,
        project_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Get folder hierarchy for a project.

        Args:
            project_id: Optional project to scope folder tree

        Returns:
            Nested list of folder dicts with 'id', 'name', 'children'
        """
        return []

    def should_process_file(self, file: FileMetadata) -> tuple[bool, str]:
        """Check if a file should be processed based on config.

        Args:
            file: File metadata to check

        Returns:
            Tuple of (should_process, reason)
        """
        # Check file type
        if file.file_type:
            if file.file_type.lower() not in self._config.supported_types:
                return False, f"Unsupported file type: {file.file_type}"

        # Check file size
        if file.file_size:
            max_bytes = self._config.max_file_size_mb * 1024 * 1024
            if file.file_size > max_bytes:
                return False, f"File too large: {file.file_size} bytes"

        return True, "OK"

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        pass
