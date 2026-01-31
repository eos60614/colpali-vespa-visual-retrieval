"""
Procore connector for file ingestion.

Discovers and downloads files from Procore database records with rich metadata
extracted from related tables (projects, vendors, users, etc.).
"""

import asyncio
from datetime import datetime
from logging import Logger
from pathlib import Path
from typing import Any, AsyncIterator, Optional

import aiohttp

from backend.config import get
from backend.logging_config import get_logger
from backend.ingestion.connectors.base import (
    ConnectorConfig,
    DocumentCategory,
    DocumentStatus,
    DownloadResult,
    FileMetadata,
    SourceConnector,
)
from backend.ingestion.db_connection import DatabaseConnection
from backend.ingestion.schema_discovery import SchemaMap


# Map Procore tables to document categories
TABLE_CATEGORY_MAP: dict[str, DocumentCategory] = {
    "drawings": DocumentCategory.DRAWING,
    "drawing_revisions": DocumentCategory.DRAWING,
    "photos": DocumentCategory.PHOTO,
    "submittals": DocumentCategory.SUBMITTAL,
    "submittal_attachments": DocumentCategory.SUBMITTAL,
    "rfis": DocumentCategory.RFI,
    "specification_sections": DocumentCategory.SPECIFICATION,
    "specification_section_revisions": DocumentCategory.SPECIFICATION,
    "commitment_contracts": DocumentCategory.CONTRACT,
    "prime_contracts": DocumentCategory.CONTRACT,
    "owner_invoices": DocumentCategory.INVOICE,
    "requisitions": DocumentCategory.INVOICE,
    "daily_logs": DocumentCategory.REPORT,
    "timesheets": DocumentCategory.REPORT,
    "documents": DocumentCategory.OTHER,
}

# Map Procore status values to DocumentStatus
STATUS_MAP: dict[str, DocumentStatus] = {
    "draft": DocumentStatus.DRAFT,
    "pending": DocumentStatus.PENDING_REVIEW,
    "pending_review": DocumentStatus.PENDING_REVIEW,
    "approved": DocumentStatus.APPROVED,
    "rejected": DocumentStatus.REJECTED,
    "superseded": DocumentStatus.SUPERSEDED,
    "archived": DocumentStatus.ARCHIVED,
    "active": DocumentStatus.ACTIVE,
    "open": DocumentStatus.ACTIVE,
    "closed": DocumentStatus.ARCHIVED,
}


class ProcoreConnector(SourceConnector):
    """Connector for Procore construction management system.

    Discovers files from Procore database records and enriches them with
    metadata from related tables (projects, vendors, users).
    """

    def __init__(
        self,
        db: DatabaseConnection,
        schema_map: SchemaMap,
        config: Optional[ConnectorConfig] = None,
        logger: Optional[Logger] = None,
    ):
        """Initialize Procore connector.

        Args:
            db: Database connection to Procore PostgreSQL
            schema_map: Schema map from discovery
            config: Optional connector configuration
            logger: Optional logger instance
        """
        if config is None:
            config = ConnectorConfig(
                name="procore",
                download_workers=get("ingestion", "files", "download_workers"),
                download_timeout_seconds=get("ingestion", "files", "download_timeout_seconds"),
                max_file_size_mb=get("ingestion", "files", "max_file_size_mb"),
                supported_types=get("ingestion", "files", "supported_types"),
            )
        super().__init__(config, logger)

        self._db = db
        self._schema_map = schema_map

        # Cache for project/vendor metadata
        self._project_cache: dict[int, dict[str, Any]] = {}
        self._vendor_cache: dict[int, dict[str, Any]] = {}
        self._user_cache: dict[int, dict[str, Any]] = {}

    async def discover_files(
        self,
        since: Optional[datetime] = None,
        filters: Optional[dict[str, Any]] = None,
    ) -> AsyncIterator[FileMetadata]:
        """Discover files from Procore database.

        Args:
            since: Only return files modified since this timestamp
            filters: Optional filters:
                - project_id: Filter by project ID
                - tables: List of tables to scan (default: all with file refs)
                - category: Filter by document category

        Yields:
            FileMetadata for each discovered file
        """
        filters = filters or {}
        project_filter = filters.get("project_id")
        table_filter = filters.get("tables")
        category_filter = filters.get("category")

        # Get tables with file references
        tables_with_files = [
            t for t in self._schema_map.tables
            if t.file_reference_columns
        ]

        if table_filter:
            tables_with_files = [
                t for t in tables_with_files
                if t.name in table_filter
            ]

        if category_filter:
            # Map category to tables
            category_enum = (
                DocumentCategory(category_filter)
                if isinstance(category_filter, str)
                else category_filter
            )
            matching_tables = {
                table for table, cat in TABLE_CATEGORY_MAP.items()
                if cat == category_enum
            }
            tables_with_files = [
                t for t in tables_with_files
                if t.name in matching_tables
            ]

        for table in tables_with_files:
            async for metadata in self._scan_table(
                table.name,
                table.file_reference_columns,
                since=since,
                project_id=project_filter,
            ):
                yield metadata

    async def _scan_table(
        self,
        table_name: str,
        file_columns: list,
        since: Optional[datetime] = None,
        project_id: Optional[int] = None,
    ) -> AsyncIterator[FileMetadata]:
        """Scan a table for file references.

        Args:
            table_name: Table to scan
            file_columns: File reference column definitions
            since: Only return files modified after this time
            project_id: Optional project filter

        Yields:
            FileMetadata for each file found
        """
        # Build query
        conditions = []
        args = []
        arg_idx = 1

        if since:
            ts_col = self._get_timestamp_column(table_name)
            if ts_col:
                conditions.append(f'"{ts_col}" > ${arg_idx}')
                args.append(since)
                arg_idx += 1

        if project_id:
            if self._has_column(table_name, "project_id"):
                conditions.append(f'"project_id" = ${arg_idx}')
                args.append(project_id)
                arg_idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        query = f'SELECT * FROM "{table_name}" {where}'

        self._logger.debug(f"Scanning table {table_name} for files")

        async for batch in self._db.stream(query, *args, batch_size=1000):
            for row in batch:
                # Extract files from this row
                for fc in file_columns:
                    value = row.get(fc.column_name)
                    if value is None:
                        continue

                    metadata = await self._extract_file_metadata(
                        table_name=table_name,
                        row=row,
                        column=fc.column_name,
                        value=value,
                        reference_type=fc.reference_type,
                    )
                    if metadata:
                        yield metadata

    async def _extract_file_metadata(
        self,
        table_name: str,
        row: dict[str, Any],
        column: str,
        value: Any,
        reference_type: Any,
    ) -> Optional[FileMetadata]:
        """Extract rich metadata for a file reference.

        Args:
            table_name: Source table name
            row: Full database row
            column: Column containing file reference
            value: File reference value (S3 key, URL, or JSONB)
            reference_type: Type of file reference

        Returns:
            FileMetadata with rich context or None if invalid
        """
        from backend.ingestion.schema_discovery import FileReferenceType

        # Extract S3 key or URL
        s3_key = None
        url = None
        filename = None

        if reference_type == FileReferenceType.S3_KEY:
            if isinstance(value, str) and value.strip():
                s3_key = value.strip()
                filename = s3_key.rsplit("/", 1)[-1] if "/" in s3_key else s3_key
        elif reference_type == FileReferenceType.URL:
            if isinstance(value, str) and value.strip():
                url = value.strip()
                # Extract filename from URL path
                from urllib.parse import urlparse
                parsed = urlparse(url)
                if parsed.path:
                    filename = parsed.path.rsplit("/", 1)[-1]
        elif reference_type == FileReferenceType.JSONB_S3_MAP:
            # JSONB maps handled separately - skip for now
            # TODO: Handle JSONB file maps
            return None

        if not s3_key and not url:
            return None

        # Build source ID
        record_id = str(row.get("id", "unknown"))
        source_id = f"{table_name}:{record_id}:{column}"

        # Extract timestamps
        created_at = self._parse_timestamp(row.get("created_at"))
        modified_at = self._parse_timestamp(
            row.get("updated_at") or row.get("last_synced_at") or row.get("created_at")
        )

        # Get project info
        project_id = row.get("project_id")
        project_name = None
        if project_id:
            project_info = await self._get_project_info(project_id)
            if project_info:
                project_name = project_info.get("name")

        # Get vendor/company info
        company = None
        company_id = None
        vendor_id = row.get("vendor_id")
        if vendor_id:
            vendor_info = await self._get_vendor_info(vendor_id)
            if vendor_info:
                company = vendor_info.get("name")
                company_id = str(vendor_id)

        # Get author info
        author = None
        created_by_id = row.get("created_by_id") or row.get("uploaded_by_id")
        if created_by_id:
            user_info = await self._get_user_info(created_by_id)
            if user_info:
                author = user_info.get("name")

        # Determine category
        category = TABLE_CATEGORY_MAP.get(table_name, DocumentCategory.OTHER)

        # Determine status
        status = None
        status_value = row.get("status")
        if status_value:
            status = STATUS_MAP.get(str(status_value).lower())

        # Extract document type/discipline for drawings
        document_type = None
        discipline = None
        if table_name in ("drawings", "drawing_revisions"):
            discipline = row.get("discipline")
            document_type = row.get("drawing_type") or row.get("type")

        # Extract revision
        revision = row.get("revision") or row.get("revision_number")

        # Extract document number
        number = (
            row.get("number") or
            row.get("drawing_number") or
            row.get("invoice_number") or
            row.get("document_number")
        )

        # Extract title/description
        title = row.get("title") or row.get("name") or filename
        description = row.get("description")

        # File properties
        file_size = row.get("file_size")
        file_type = None
        if filename and "." in filename:
            file_type = filename.rsplit(".", 1)[-1].lower()

        # Tags from row
        tags = []
        if row.get("tags"):
            if isinstance(row["tags"], list):
                tags = row["tags"]
            elif isinstance(row["tags"], str):
                tags = [t.strip() for t in row["tags"].split(",") if t.strip()]

        # Custom fields
        custom_fields = {
            "source_table": table_name,
            "source_column": column,
            "source_record_id": record_id,
        }

        # Add table-specific fields
        if table_name == "drawings":
            if row.get("drawing_set_id"):
                custom_fields["drawing_set_id"] = str(row["drawing_set_id"])
            if row.get("drawing_area_id"):
                custom_fields["drawing_area_id"] = str(row["drawing_area_id"])
        elif table_name == "submittals":
            if row.get("spec_section_id"):
                custom_fields["spec_section_id"] = str(row["spec_section_id"])
        elif table_name == "rfis":
            if row.get("subject"):
                custom_fields["subject"] = row["subject"]

        return FileMetadata(
            source_system="procore",
            source_id=source_id,
            source_url=url,
            project_id=str(project_id) if project_id else None,
            project_name=project_name,
            parent_record_id=record_id,
            parent_record_type=table_name,
            category=category,
            document_type=document_type,
            discipline=discipline,
            status=status,
            revision=str(revision) if revision else None,
            author=author,
            company=company,
            company_id=company_id,
            created_at=created_at,
            modified_at=modified_at,
            filename=filename,
            file_size=file_size,
            file_type=file_type,
            title=title,
            description=description,
            number=str(number) if number else None,
            tags=tags,
            custom_fields=custom_fields,
        )

    async def download_file(
        self,
        file: FileMetadata,
        dest_dir: Path,
    ) -> DownloadResult:
        """Download a file from Procore (S3 or signed URL).

        Args:
            file: File metadata from discover_files
            dest_dir: Directory to download into

        Returns:
            DownloadResult with success status and local path
        """
        # Validate file should be processed
        should_process, reason = self.should_process_file(file)
        if not should_process:
            return DownloadResult(
                success=False,
                metadata=file,
                error=reason,
                status="skipped",
            )

        # Determine source
        url = file.source_url or file.custom_fields.get("url")

        if not url:
            # Try to get URL from S3 key
            s3_key = file.custom_fields.get("s3_key")
            if s3_key:
                # Would need to generate signed URL or use direct S3 access
                return DownloadResult(
                    success=False,
                    metadata=file,
                    error="Direct S3 download not yet implemented",
                    status="failed",
                )
            return DownloadResult(
                success=False,
                metadata=file,
                error="No download URL available",
                status="failed",
            )

        # Build local path
        subfolder = file.parent_record_type or "files"
        filename = file.filename or f"{file.source_id.replace(':', '_')}"
        local_path = dest_dir / subfolder / filename
        local_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            async with aiohttp.ClientSession() as session:
                timeout = aiohttp.ClientTimeout(
                    total=self._config.download_timeout_seconds
                )
                async with session.get(url, timeout=timeout) as response:
                    if response.status != 200:
                        return DownloadResult(
                            success=False,
                            metadata=file,
                            error=f"HTTP {response.status}",
                            status="failed",
                        )

                    # Check content length
                    content_length = response.content_length
                    max_bytes = self._config.max_file_size_mb * 1024 * 1024
                    if content_length and content_length > max_bytes:
                        return DownloadResult(
                            success=False,
                            metadata=file,
                            error=f"File too large: {content_length} bytes",
                            status="skipped",
                        )

                    # Download to file
                    with open(local_path, "wb") as f:
                        chunk_size = get("ingestion", "files", "chunk_size")
                        async for chunk in response.content.iter_chunked(chunk_size):
                            f.write(chunk)

                    file_size = local_path.stat().st_size

                    return DownloadResult(
                        success=True,
                        local_path=local_path,
                        metadata=file,
                        file_size=file_size,
                        status="success",
                    )

        except asyncio.TimeoutError:
            return DownloadResult(
                success=False,
                metadata=file,
                error="Download timeout",
                status="failed",
            )
        except Exception as e:
            self._logger.warning(f"Download failed for {file.source_id}: {e}")
            return DownloadResult(
                success=False,
                metadata=file,
                error=str(e),
                status="failed",
            )

    async def get_metadata(
        self,
        source_id: str,
    ) -> Optional[FileMetadata]:
        """Fetch full metadata for a specific file.

        Args:
            source_id: Source ID in format "table:record_id:column"

        Returns:
            FileMetadata or None if not found
        """
        try:
            parts = source_id.split(":")
            if len(parts) != 3:
                return None

            table_name, record_id, column = parts

            # Query the record
            query = f'SELECT * FROM "{table_name}" WHERE id = $1'
            async for batch in self._db.stream(query, int(record_id), batch_size=1):
                for row in batch:
                    # Get file reference column info
                    table_info = next(
                        (t for t in self._schema_map.tables if t.name == table_name),
                        None,
                    )
                    if not table_info:
                        return None

                    fc = next(
                        (c for c in table_info.file_reference_columns if c.column_name == column),
                        None,
                    )
                    if not fc:
                        return None

                    value = row.get(column)
                    if value:
                        return await self._extract_file_metadata(
                            table_name=table_name,
                            row=row,
                            column=column,
                            value=value,
                            reference_type=fc.reference_type,
                        )

            return None

        except Exception as e:
            self._logger.error(f"Failed to get metadata for {source_id}: {e}")
            return None

    async def validate_connection(self) -> bool:
        """Validate database connection."""
        try:
            async for batch in self._db.stream("SELECT 1", batch_size=1):
                return True
            return False
        except Exception:
            return False

    async def get_project_list(self) -> list[dict[str, str]]:
        """Get list of Procore projects."""
        projects = []
        query = 'SELECT id, name FROM projects ORDER BY name'
        try:
            async for batch in self._db.stream(query, batch_size=1000):
                for row in batch:
                    projects.append({
                        "id": str(row["id"]),
                        "name": row.get("name", f"Project {row['id']}"),
                    })
        except Exception as e:
            self._logger.error(f"Failed to get project list: {e}")
        return projects

    # Helper methods

    def _get_timestamp_column(self, table_name: str) -> Optional[str]:
        """Get best timestamp column for a table."""
        table_info = next(
            (t for t in self._schema_map.tables if t.name == table_name),
            None,
        )
        if not table_info:
            return None

        for preferred in ["updated_at", "last_synced_at", "created_at"]:
            if preferred in table_info.timestamp_columns:
                return preferred
        return None

    def _has_column(self, table_name: str, column_name: str) -> bool:
        """Check if table has a column."""
        table_info = next(
            (t for t in self._schema_map.tables if t.name == table_name),
            None,
        )
        if not table_info:
            return False
        return any(c.name == column_name for c in table_info.columns)

    def _parse_timestamp(self, value: Any) -> Optional[datetime]:
        """Parse timestamp from database value."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None

    async def _get_project_info(self, project_id: int) -> Optional[dict[str, Any]]:
        """Get cached project info."""
        if project_id in self._project_cache:
            return self._project_cache[project_id]

        try:
            query = 'SELECT id, name, display_name, project_number FROM projects WHERE id = $1'
            async for batch in self._db.stream(query, project_id, batch_size=1):
                for row in batch:
                    info = dict(row)
                    self._project_cache[project_id] = info
                    return info
        except Exception:
            pass
        return None

    async def _get_vendor_info(self, vendor_id: int) -> Optional[dict[str, Any]]:
        """Get cached vendor info."""
        if vendor_id in self._vendor_cache:
            return self._vendor_cache[vendor_id]

        try:
            query = 'SELECT id, name, abbreviated_name FROM vendors WHERE id = $1'
            async for batch in self._db.stream(query, vendor_id, batch_size=1):
                for row in batch:
                    info = dict(row)
                    self._vendor_cache[vendor_id] = info
                    return info
        except Exception:
            pass
        return None

    async def _get_user_info(self, user_id: int) -> Optional[dict[str, Any]]:
        """Get cached user info."""
        if user_id in self._user_cache:
            return self._user_cache[user_id]

        try:
            query = 'SELECT id, name, email_address FROM company_users WHERE id = $1'
            async for batch in self._db.stream(query, user_id, batch_size=1):
                for row in batch:
                    info = dict(row)
                    self._user_cache[user_id] = info
                    return info
        except Exception:
            pass
        return None
