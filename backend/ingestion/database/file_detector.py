"""
File reference detection and extraction from database records.
"""

import json
import re
from logging import Logger

from backend.core.logging_config import get_logger
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

from backend.ingestion.database.schema_discovery import FileReferenceType, SchemaMap


@dataclass
class DetectedFile:
    """A file reference detected in a database record."""

    s3_key: str
    source_table: str
    source_record_id: str
    source_column: str
    filename: Optional[str]
    file_size: Optional[int]
    url: Optional[str]

    @property
    def file_type(self) -> Optional[str]:
        """Extract file extension from filename."""
        if self.filename:
            if "." in self.filename:
                return self.filename.rsplit(".", 1)[-1].lower()
        return None


class FileDetector:
    """Detect and extract file references from database records."""

    # S3 key pattern: {company_id}/{project_id}/{resource_type}/{resource_id}/{filename}
    S3_KEY_PATTERN = re.compile(r"^\d+/\d+/\w+/\d+/.+$")

    # Procore URL pattern
    PROCORE_URL_PATTERN = re.compile(r"https?://storage\.procore\.com")

    def __init__(
        self, schema_map: SchemaMap, logger: Optional[Logger] = None
    ):
        """Initialize file detector.

        Args:
            schema_map: Schema map from discovery
            logger: Optional logger instance
        """
        self._schema_map = schema_map
        self._logger = logger or get_logger(__name__)

        # Build lookup for file reference columns
        self._file_ref_columns = {
            t.name: t.file_reference_columns for t in schema_map.tables
        }

    def detect_in_record(
        self, table: str, row: dict[str, Any]
    ) -> list[DetectedFile]:
        """Detect all file references in a record.

        Args:
            table: Source table name
            row: Database row dictionary

        Returns:
            List of DetectedFile instances
        """
        detected_files = []
        record_id = str(row.get("id", "unknown"))

        # Get file reference columns for this table
        file_columns = self._file_ref_columns.get(table, [])

        for fc in file_columns:
            value = row.get(fc.column_name)
            if value is None:
                continue

            try:
                if fc.reference_type == FileReferenceType.S3_KEY:
                    file = self.parse_s3_key(
                        column=fc.column_name,
                        value=value,
                        table=table,
                        record_id=record_id,
                    )
                    if file:
                        detected_files.append(file)

                elif fc.reference_type == FileReferenceType.JSONB_S3_MAP:
                    files = self.parse_jsonb_attachments(
                        column=fc.column_name,
                        value=value,
                        table=table,
                        record_id=record_id,
                    )
                    detected_files.extend(files)

                elif fc.reference_type == FileReferenceType.URL:
                    file = self.parse_url(
                        column=fc.column_name,
                        value=value,
                        table=table,
                        record_id=record_id,
                    )
                    if file:
                        detected_files.append(file)

            except Exception as e:
                self._logger.debug(
                    f"Failed to parse file reference in {table}.{fc.column_name}: {e}"
                )

        # Also check for file size if available
        for df in detected_files:
            if df.file_size is None:
                # Try to get file size from row
                size_col = "file_size"
                if size_col in row and row[size_col] is not None:
                    df.file_size = int(row[size_col])

        return detected_files

    def parse_s3_key(
        self,
        column: str,
        value: Any,
        table: str,
        record_id: str,
    ) -> Optional[DetectedFile]:
        """Parse a direct S3 key value.

        Args:
            column: Column name
            value: Column value
            table: Source table name
            record_id: Source record ID

        Returns:
            DetectedFile if valid S3 key, None otherwise
        """
        if not isinstance(value, str) or not value.strip():
            return None

        s3_key = value.strip()

        # Validate S3 key pattern
        if not self.S3_KEY_PATTERN.match(s3_key):
            self._logger.debug(f"S3 key doesn't match expected pattern: {s3_key}")

        return DetectedFile(
            s3_key=s3_key,
            source_table=table,
            source_record_id=record_id,
            source_column=column,
            filename=self.extract_filename(s3_key),
            file_size=None,
            url=None,
        )

    def parse_jsonb_attachments(
        self,
        column: str,
        value: Any,
        table: str,
        record_id: str,
    ) -> list[DetectedFile]:
        """Parse JSONB map of file ID to S3 key.

        Args:
            column: Column name
            value: Column value (dict or JSON string)
            table: Source table name
            record_id: Source record ID

        Returns:
            List of DetectedFile instances
        """
        files = []

        # Parse JSON if needed
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                return files

        if not isinstance(value, dict):
            return files

        for file_id, s3_key in value.items():
            if not s3_key:
                continue

            s3_key = str(s3_key).strip()
            if not s3_key:
                continue

            files.append(
                DetectedFile(
                    s3_key=s3_key,
                    source_table=table,
                    source_record_id=record_id,
                    source_column=column,
                    filename=self.extract_filename(s3_key),
                    file_size=None,
                    url=None,
                )
            )

        return files

    def parse_url(
        self,
        column: str,
        value: Any,
        table: str,
        record_id: str,
    ) -> Optional[DetectedFile]:
        """Parse a URL reference (Procore signed URL).

        Args:
            column: Column name
            value: Column value
            table: Source table name
            record_id: Source record ID

        Returns:
            DetectedFile if valid URL, None otherwise
        """
        if not isinstance(value, str) or not value.strip():
            return None

        url = value.strip()

        # Validate URL
        try:
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                return None
        except Exception:
            return None

        # Try to extract filename from URL path
        filename = None
        if parsed.path:
            path_parts = parsed.path.split("/")
            if path_parts:
                filename = path_parts[-1]

        return DetectedFile(
            s3_key="",  # URL-based files don't have S3 keys
            source_table=table,
            source_record_id=record_id,
            source_column=column,
            filename=filename,
            file_size=None,
            url=url,
        )

    def extract_filename(self, s3_key: str) -> str:
        """Extract filename from S3 key path.

        Args:
            s3_key: S3 key path

        Returns:
            Filename portion of the path
        """
        if "/" in s3_key:
            return s3_key.rsplit("/", 1)[-1]
        return s3_key

    def infer_file_type(self, filename: str) -> str:
        """Infer file type from filename extension.

        Args:
            filename: Filename to analyze

        Returns:
            File extension (lowercase) or empty string
        """
        if "." in filename:
            return filename.rsplit(".", 1)[-1].lower()
        return ""
