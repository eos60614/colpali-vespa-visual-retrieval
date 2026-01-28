"""
Database schema introspection and documentation generation.
"""

import json
import logging
import re

from backend.logging_config import get_logger
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from backend.ingestion.db_connection import DatabaseConnection
from backend.ingestion.exceptions import SchemaError


class FileReferenceType(Enum):
    """Types of file references in database columns."""

    S3_KEY = "s3_key"
    URL = "url"
    JSONB_S3_MAP = "jsonb_s3_map"


@dataclass
class Column:
    """Database column definition."""

    name: str
    data_type: str
    is_nullable: bool
    default_value: Optional[str] = None
    max_length: Optional[int] = None


@dataclass
class FileReferenceColumn:
    """Column containing file references."""

    column_name: str
    reference_type: FileReferenceType
    pattern: str


@dataclass
class Table:
    """Database table with columns and metadata."""

    name: str
    row_count: int
    columns: list[Column] = field(default_factory=list)
    timestamp_columns: list[str] = field(default_factory=list)
    file_reference_columns: list[FileReferenceColumn] = field(default_factory=list)

    @property
    def primary_key(self) -> list[str]:
        """Infer primary key from id column."""
        for col in self.columns:
            if col.name == "id":
                return ["id"]
        return []


@dataclass
class ImplicitRelationship:
    """Implied relationship from _id column patterns."""

    source_table: str
    source_column: str
    target_table: str
    target_column: str = "id"

    @property
    def cardinality(self) -> str:
        """Relationship cardinality (always MANY_TO_ONE for _id columns)."""
        return "MANY_TO_ONE"


@dataclass
class SchemaMap:
    """Complete database schema discovery result."""

    discovery_timestamp: str
    database_name: str
    tables: list[Table] = field(default_factory=list)
    relationships: list[ImplicitRelationship] = field(default_factory=list)

    @property
    def file_references_summary(self) -> dict[str, Any]:
        """Summary of file reference columns."""
        total_columns = sum(len(t.file_reference_columns) for t in self.tables)
        tables_with_files = len([t for t in self.tables if t.file_reference_columns])
        return {
            "total_columns": total_columns,
            "tables_with_files": tables_with_files,
        }


class SchemaDiscovery:
    """Database schema introspection."""

    # Patterns for detecting file reference columns
    S3_KEY_PATTERNS = [
        r"^s3_key$",
        r"_s3_key$",
        r"^s3_",
    ]
    URL_PATTERNS = [
        r"^url$",
        r"_url$",
        r"^thumbnail_url$",
    ]
    JSONB_S3_PATTERNS = [
        r"_s3_keys$",
        r"^attachment_s3_keys$",
        r"^attachments_s3_keys$",
    ]

    # Timestamp column patterns
    TIMESTAMP_PATTERNS = [
        "created_at",
        "updated_at",
        "last_synced_at",
        "deleted_at",
    ]

    def __init__(self, db: DatabaseConnection, logger: Optional[logging.Logger] = None):
        """Initialize schema discovery.

        Args:
            db: Database connection instance
            logger: Optional logger instance
        """
        self._db = db
        self._logger = logger or get_logger(__name__)

    async def discover(self, include_samples: bool = False) -> SchemaMap:
        """Perform full schema discovery.

        Args:
            include_samples: Whether to include sample data (not implemented)

        Returns:
            SchemaMap with all tables, columns, and relationships
        """
        self._logger.info("Starting schema discovery...")

        # Get database name
        result = await self._db.execute("SELECT current_database()")
        database_name = result[0]["current_database"] if result else "unknown"

        # Get all tables
        table_names = await self.get_tables()
        self._logger.info(f"Found {len(table_names)} tables")

        # Build table definitions
        tables = []
        for table_name in table_names:
            self._logger.debug(f"Discovering table: {table_name}")
            columns = await self.get_columns(table_name)
            row_count = await self.get_row_count(table_name)
            file_columns = await self.detect_file_columns(table_name, columns)
            timestamp_columns = [
                c.name for c in columns if c.name in self.TIMESTAMP_PATTERNS
            ]

            table = Table(
                name=table_name,
                row_count=row_count,
                columns=columns,
                timestamp_columns=timestamp_columns,
                file_reference_columns=file_columns,
            )
            tables.append(table)

        # Infer relationships
        relationships = await self.infer_relationships(tables)

        schema_map = SchemaMap(
            discovery_timestamp=datetime.utcnow().isoformat() + "Z",
            database_name=database_name,
            tables=tables,
            relationships=relationships,
        )

        self._logger.info(
            f"Schema discovery complete: {len(tables)} tables, "
            f"{len(relationships)} relationships"
        )

        return schema_map

    async def get_tables(self, schema: str = "public") -> list[str]:
        """Get list of table names.

        Args:
            schema: Database schema to query (default: public)

        Returns:
            List of table names
        """
        query = """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = $1
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        try:
            rows = await self._db.execute(query, schema)
            return [row["table_name"] for row in rows]
        except Exception as e:
            raise SchemaError(f"Failed to get tables: {e}") from e

    async def get_columns(self, table: str, schema: str = "public") -> list[Column]:
        """Get columns for a table.

        Args:
            table: Table name
            schema: Database schema (default: public)

        Returns:
            List of Column definitions
        """
        query = """
            SELECT
                column_name,
                data_type,
                is_nullable,
                column_default,
                character_maximum_length
            FROM information_schema.columns
            WHERE table_schema = $1
              AND table_name = $2
            ORDER BY ordinal_position
        """
        try:
            rows = await self._db.execute(query, schema, table)
            return [
                Column(
                    name=row["column_name"],
                    data_type=row["data_type"],
                    is_nullable=row["is_nullable"] == "YES",
                    default_value=row["column_default"],
                    max_length=row["character_maximum_length"],
                )
                for row in rows
            ]
        except Exception as e:
            raise SchemaError(f"Failed to get columns for {table}: {e}") from e

    async def get_row_count(self, table: str) -> int:
        """Get row count for a table.

        Args:
            table: Table name

        Returns:
            Number of rows in the table
        """
        # Use identifier quoting to prevent SQL injection
        query = f'SELECT COUNT(*) as count FROM "{table}"'
        try:
            rows = await self._db.execute(query)
            return rows[0]["count"] if rows else 0
        except Exception as e:
            self._logger.warning(f"Failed to get row count for {table}: {e}")
            return 0

    async def detect_file_columns(
        self, table: str, columns: list[Column]
    ) -> list[FileReferenceColumn]:
        """Detect columns containing file references.

        Args:
            table: Table name
            columns: List of columns in the table

        Returns:
            List of FileReferenceColumn definitions
        """
        file_columns = []

        for column in columns:
            col_name = column.name.lower()
            data_type = column.data_type.lower()

            # Check for JSONB S3 keys (highest priority)
            if data_type == "jsonb":
                for pattern in self.JSONB_S3_PATTERNS:
                    if re.search(pattern, col_name):
                        file_columns.append(
                            FileReferenceColumn(
                                column_name=column.name,
                                reference_type=FileReferenceType.JSONB_S3_MAP,
                                pattern=pattern,
                            )
                        )
                        break

            # Check for direct S3 key columns
            elif data_type in ("text", "character varying"):
                for pattern in self.S3_KEY_PATTERNS:
                    if re.search(pattern, col_name):
                        file_columns.append(
                            FileReferenceColumn(
                                column_name=column.name,
                                reference_type=FileReferenceType.S3_KEY,
                                pattern=pattern,
                            )
                        )
                        break
                else:
                    # Check for URL columns
                    for pattern in self.URL_PATTERNS:
                        if re.search(pattern, col_name):
                            file_columns.append(
                                FileReferenceColumn(
                                    column_name=column.name,
                                    reference_type=FileReferenceType.URL,
                                    pattern=pattern,
                                )
                            )
                            break

        return file_columns

    async def infer_relationships(
        self, tables: list[Table]
    ) -> list[ImplicitRelationship]:
        """Infer relationships from _id column patterns.

        Args:
            tables: List of discovered tables

        Returns:
            List of ImplicitRelationship definitions
        """
        # Build a set of known table names for validation
        table_names = {t.name for t in tables}

        relationships = []

        for table in tables:
            for column in table.columns:
                col_name = column.name

                # Skip the primary key 'id' column
                if col_name == "id":
                    continue

                # Check for _id suffix pattern
                if col_name.endswith("_id"):
                    # Infer target table from column name
                    # e.g., project_id -> projects, vendor_id -> vendors
                    base_name = col_name[:-3]  # Remove '_id'

                    # Try plural form first
                    target_table = base_name + "s"
                    if target_table not in table_names:
                        # Try other common patterns
                        if base_name.endswith("y"):
                            target_table = base_name[:-1] + "ies"
                        elif base_name.endswith("s"):
                            target_table = base_name + "es"
                        else:
                            target_table = base_name

                    # Only add if target table exists
                    if target_table in table_names:
                        relationships.append(
                            ImplicitRelationship(
                                source_table=table.name,
                                source_column=col_name,
                                target_table=target_table,
                                target_column="id",
                            )
                        )

        return relationships

    def to_json(self, schema_map: SchemaMap) -> str:
        """Export schema map to JSON.

        Args:
            schema_map: SchemaMap to export

        Returns:
            JSON string representation
        """
        return json.dumps(self._schema_map_to_dict(schema_map), indent=2)

    def to_markdown(self, schema_map: SchemaMap) -> str:
        """Export schema map to Markdown.

        Args:
            schema_map: SchemaMap to export

        Returns:
            Markdown string representation
        """
        lines = [
            f"# Database Schema: {schema_map.database_name}",
            "",
            f"**Discovery Time**: {schema_map.discovery_timestamp}",
            f"**Tables**: {len(schema_map.tables)}",
            f"**Relationships**: {len(schema_map.relationships)}",
            "",
            "---",
            "",
            "## Tables",
            "",
        ]

        # Sort tables by row count (descending)
        sorted_tables = sorted(schema_map.tables, key=lambda t: t.row_count, reverse=True)

        for table in sorted_tables:
            lines.extend(
                [
                    f"### {table.name}",
                    "",
                    f"**Rows**: {table.row_count:,}",
                    "",
                ]
            )

            # Columns table
            lines.append("| Column | Type | Nullable | Default |")
            lines.append("|--------|------|----------|---------|")

            for col in table.columns:
                nullable = "YES" if col.is_nullable else "NO"
                default = col.default_value or "-"
                if len(default) > 30:
                    default = default[:27] + "..."
                lines.append(f"| {col.name} | {col.data_type} | {nullable} | {default} |")

            lines.append("")

            # File reference columns
            if table.file_reference_columns:
                lines.append("**File Reference Columns**:")
                for fc in table.file_reference_columns:
                    lines.append(f"- `{fc.column_name}` ({fc.reference_type.value})")
                lines.append("")

            # Timestamp columns
            if table.timestamp_columns:
                lines.append(
                    f"**Timestamp Columns**: {', '.join(table.timestamp_columns)}"
                )
                lines.append("")

            lines.append("---")
            lines.append("")

        # Relationships section
        if schema_map.relationships:
            lines.extend(
                [
                    "## Relationships",
                    "",
                    "| Source Table | Source Column | Target Table | Target Column |",
                    "|--------------|---------------|--------------|---------------|",
                ]
            )

            for rel in schema_map.relationships:
                lines.append(
                    f"| {rel.source_table} | {rel.source_column} | "
                    f"{rel.target_table} | {rel.target_column} |"
                )

            lines.append("")

        # Summary
        summary = schema_map.file_references_summary
        lines.extend(
            [
                "## File References Summary",
                "",
                f"- **Total file reference columns**: {summary['total_columns']}",
                f"- **Tables with file references**: {summary['tables_with_files']}",
                "",
            ]
        )

        return "\n".join(lines)

    def _schema_map_to_dict(self, schema_map: SchemaMap) -> dict:
        """Convert SchemaMap to dictionary for JSON serialization."""
        return {
            "discovery_timestamp": schema_map.discovery_timestamp,
            "database_name": schema_map.database_name,
            "tables": [
                {
                    "name": t.name,
                    "row_count": t.row_count,
                    "columns": [
                        {
                            "name": c.name,
                            "data_type": c.data_type,
                            "is_nullable": c.is_nullable,
                            "default_value": c.default_value,
                            "max_length": c.max_length,
                        }
                        for c in t.columns
                    ],
                    "timestamp_columns": t.timestamp_columns,
                    "file_reference_columns": [
                        {
                            "column_name": fc.column_name,
                            "reference_type": fc.reference_type.value,
                            "pattern": fc.pattern,
                        }
                        for fc in t.file_reference_columns
                    ],
                }
                for t in schema_map.tables
            ],
            "relationships": [
                {
                    "source_table": r.source_table,
                    "source_column": r.source_column,
                    "target_table": r.target_table,
                    "target_column": r.target_column,
                }
                for r in schema_map.relationships
            ],
            "file_references_summary": schema_map.file_references_summary,
        }
