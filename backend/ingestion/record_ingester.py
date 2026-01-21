"""
Record extraction, transformation, and Vespa indexing.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, AsyncIterator, Optional

from backend.ingestion.db_connection import DatabaseConnection
from backend.ingestion.exceptions import IndexError, TransformError
from backend.ingestion.schema_discovery import FileReferenceType, SchemaMap


@dataclass
class RelationshipLink:
    """A navigable relationship link for agent traversal.

    Provides full context for navigating between related records,
    including direction, type, and human-readable descriptions.
    """

    target_doc_id: str  # Full Vespa doc_id (e.g., "projects:123")
    target_table: str  # Target table name
    target_id: str  # Target record ID
    source_column: str  # Column containing the reference
    relationship_type: str  # Semantic type (e.g., "project", "vendor")
    direction: str  # "outgoing" (this record references target) or "incoming" (target references this)
    cardinality: str  # "many_to_one" or "one_to_many"

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for JSON serialization."""
        return {
            "target_doc_id": self.target_doc_id,
            "target_table": self.target_table,
            "target_id": self.target_id,
            "source_column": self.source_column,
            "relationship_type": self.relationship_type,
            "direction": self.direction,
            "cardinality": self.cardinality,
        }


@dataclass
class FileReferenceLink:
    """A file reference with complete provenance for agent navigation.

    Tracks exactly where in the source record this file reference
    came from, enabling agents to understand file context.
    """

    s3_key: str
    source_column: str  # Column containing the reference
    reference_type: str  # "s3_key", "url", "jsonb_s3_map"
    filename: Optional[str] = None
    file_id: Optional[str] = None  # For JSONB maps, the key in the map
    url: Optional[str] = None  # For URL references

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "s3_key": self.s3_key,
            "source_column": self.source_column,
            "reference_type": self.reference_type,
        }
        if self.filename:
            result["filename"] = self.filename
        if self.file_id:
            result["file_id"] = self.file_id
        if self.url:
            result["url"] = self.url
        return result


@dataclass
class IngestedRecord:
    """A database record transformed for Vespa indexing.

    Enhanced with full navigation context for agent traversal:
    - relationships: Typed links with direction and cardinality
    - file_references: Complete provenance for each file
    - table_description: Human-readable table context
    - column_types: Type information for field interpretation
    """

    doc_id: str
    source_table: str
    source_id: str
    project_id: Optional[int]
    metadata: dict[str, str]
    relationships: list[RelationshipLink]
    file_references: list[FileReferenceLink]
    content_text: str
    created_at: int
    updated_at: int
    ingested_at: int
    # Schema documentation fields for agent reference
    table_description: Optional[str] = None
    column_types: Optional[dict[str, str]] = None


@dataclass
class IngestionResult:
    """Result of indexing a single record."""

    success: bool
    doc_id: str
    error: Optional[str] = None


# Table-specific field selections for content text generation
CONTENT_FIELDS = {
    "projects": ["name", "display_name", "address", "city", "project_number"],
    "photos": ["description", "location"],
    "drawings": ["drawing_number", "title", "discipline"],
    "drawing_revisions": ["revision_number", "filename"],
    "rfis": ["number", "subject", "question"],
    "submittals": ["number", "title", "description"],
    "change_orders": ["number", "title", "description"],
    "commitment_contracts": ["number", "title", "description"],
    "vendors": ["name", "company"],
    "companies": ["name"],
    "budget_line_items": ["description", "code"],
    "direct_costs": ["description"],
    "specification_sections": ["number", "title"],
}


class RecordIngester:
    """Transform and index database records to Vespa."""

    # Human-readable table descriptions for agent context
    TABLE_DESCRIPTIONS = {
        "projects": "Construction projects with location, dates, and status",
        "photos": "Site photos with descriptions and locations",
        "drawings": "Project drawings with discipline and drawing numbers",
        "drawing_revisions": "Revisions of drawings with version history",
        "drawing_sets": "Collections of related drawings",
        "drawing_areas": "Areas within a project for drawing organization",
        "rfis": "Requests for Information with questions and responses",
        "submittals": "Submittals for approval with attachments",
        "change_orders": "Contract change orders with financial details",
        "commitment_contracts": "Vendor contracts with payment terms",
        "commitment_contract_items": "Line items within commitment contracts",
        "commitment_change_orders": "Change orders to commitment contracts",
        "prime_contracts": "Prime contracts with the owner",
        "vendors": "Vendor/subcontractor companies",
        "companies": "Company entities in the system",
        "budget_line_items": "Budget line items with costs",
        "direct_costs": "Direct cost entries",
        "specification_sections": "Specification document sections",
        "specification_section_revisions": "Revisions of specification sections",
        "timesheets": "Worker timesheet entries",
        "daily_logs": "Daily log entries with site activities",
        "project_users": "Users assigned to projects",
        "project_roles": "Roles defined for projects",
        "company_users": "Users within companies",
    }

    def __init__(
        self,
        db: DatabaseConnection,
        vespa_app: Any,
        schema_map: SchemaMap,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize record ingester.

        Args:
            db: Database connection instance
            vespa_app: Vespa application client (from backend.vespa_app)
            schema_map: Schema map from discovery
            logger: Optional logger instance
        """
        self._db = db
        self._vespa = vespa_app
        self._schema_map = schema_map
        self._logger = logger or logging.getLogger(__name__)

        # Build lookup tables from schema map
        self._table_columns = {t.name: t.columns for t in schema_map.tables}
        self._file_ref_columns = {
            t.name: t.file_reference_columns for t in schema_map.tables
        }
        # Build bidirectional relationship lookups
        self._outgoing_relationships = self._build_outgoing_relationship_lookup()
        self._incoming_relationships = self._build_incoming_relationship_lookup()
        # Build column type lookup for each table
        self._column_types = self._build_column_type_lookup()

    def _build_outgoing_relationship_lookup(
        self,
    ) -> dict[str, list[tuple[str, str, str]]]:
        """Build lookup of table -> [(column, target_table, relationship_type), ...].

        These are relationships where this table references another table.
        """
        lookup: dict[str, list[tuple[str, str, str]]] = {}
        for rel in self._schema_map.relationships:
            if rel.source_table not in lookup:
                lookup[rel.source_table] = []
            # Derive relationship type from column name
            rel_type = rel.source_column[:-3] if rel.source_column.endswith("_id") else rel.source_column
            lookup[rel.source_table].append((rel.source_column, rel.target_table, rel_type))
        return lookup

    def _build_incoming_relationship_lookup(
        self,
    ) -> dict[str, list[tuple[str, str, str]]]:
        """Build lookup of table -> [(source_table, source_column, relationship_type), ...].

        These are relationships where another table references this table (reverse links).
        """
        lookup: dict[str, list[tuple[str, str, str]]] = {}
        for rel in self._schema_map.relationships:
            if rel.target_table not in lookup:
                lookup[rel.target_table] = []
            # Derive relationship type from source table name (e.g., photos -> photo)
            rel_type = rel.source_table.rstrip("s") if rel.source_table.endswith("s") else rel.source_table
            lookup[rel.target_table].append((rel.source_table, rel.source_column, rel_type))
        return lookup

    def _build_column_type_lookup(self) -> dict[str, dict[str, str]]:
        """Build lookup of table -> {column_name: data_type}."""
        lookup: dict[str, dict[str, str]] = {}
        for table in self._schema_map.tables:
            lookup[table.name] = {col.name: col.data_type for col in table.columns}
        return lookup

    async def ingest_table(
        self,
        table: str,
        batch_size: int = 10000,
        since: Optional[datetime] = None,
    ) -> AsyncIterator[IngestionResult]:
        """Ingest records from a table.

        Args:
            table: Table name to ingest
            batch_size: Number of records per batch
            since: Only ingest records updated since this timestamp

        Yields:
            IngestionResult for each processed record
        """
        # Build query
        if since:
            query = f"""
                SELECT * FROM "{table}"
                WHERE updated_at > $1
                ORDER BY updated_at ASC
            """
            args = (since,)
        else:
            query = f'SELECT * FROM "{table}" ORDER BY id'
            args = ()

        self._logger.info(f"Ingesting table: {table}")

        record_count = 0
        async for batch in self._db.stream(query, *args, batch_size=batch_size):
            # Transform and index batch
            records = []
            for row in batch:
                try:
                    record = self.transform_record(table, row)
                    records.append(record)
                except TransformError as e:
                    yield IngestionResult(
                        success=False,
                        doc_id=f"{table}:{row.get('id', 'unknown')}",
                        error=str(e),
                    )

            # Index batch
            results = await self.index_batch(records)
            for result in results:
                yield result
                if result.success:
                    record_count += 1

        self._logger.info(f"Ingested {record_count} records from {table}")

    def transform_record(self, table: str, row: dict[str, Any]) -> IngestedRecord:
        """Transform a database row to IngestedRecord.

        Args:
            table: Source table name
            row: Database row as dictionary

        Returns:
            Transformed IngestedRecord with full navigation context
        """
        try:
            # Extract record ID
            record_id = str(row.get("id", ""))
            if not record_id:
                raise TransformError(f"Record in {table} missing id field")

            # Generate doc_id
            doc_id = f"{table}:{record_id}"

            # Extract project_id if present
            project_id = row.get("project_id")
            if project_id is not None:
                project_id = int(project_id)

            # Convert all fields to metadata map
            metadata = self._convert_to_metadata(row)

            # Extract relationships with full navigation context
            relationships = self.extract_relationships(table, row)

            # Extract file references with complete provenance
            file_references = self.extract_file_references(table, row)

            # Generate content text
            content_text = self.generate_content_text(table, row)

            # Handle timestamps
            now_ms = int(datetime.utcnow().timestamp() * 1000)
            created_at = self._timestamp_to_ms(row.get("created_at")) or now_ms
            updated_at = self._timestamp_to_ms(row.get("updated_at")) or now_ms

            # Get schema documentation fields
            table_description = self.TABLE_DESCRIPTIONS.get(table)
            column_types = self._column_types.get(table)

            return IngestedRecord(
                doc_id=doc_id,
                source_table=table,
                source_id=record_id,
                project_id=project_id,
                metadata=metadata,
                relationships=relationships,
                file_references=file_references,
                content_text=content_text,
                created_at=created_at,
                updated_at=updated_at,
                ingested_at=now_ms,
                table_description=table_description,
                column_types=column_types,
            )

        except Exception as e:
            raise TransformError(f"Failed to transform record: {e}") from e

    def _convert_to_metadata(self, row: dict[str, Any]) -> dict[str, str]:
        """Convert all row values to string metadata."""
        metadata = {}
        for key, value in row.items():
            if value is None:
                continue

            if isinstance(value, bool):
                metadata[key] = str(value).lower()
            elif isinstance(value, (dict, list)):
                metadata[key] = json.dumps(value)
            elif isinstance(value, datetime):
                metadata[key] = value.isoformat()
            else:
                metadata[key] = str(value)

        return metadata

    def _timestamp_to_ms(self, value: Any) -> Optional[int]:
        """Convert timestamp to milliseconds."""
        if value is None:
            return None
        if isinstance(value, datetime):
            return int(value.timestamp() * 1000)
        if isinstance(value, (int, float)):
            return int(value * 1000)
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        except (ValueError, TypeError):
            return None

    def extract_relationships(
        self, table: str, row: dict[str, Any]
    ) -> list[RelationshipLink]:
        """Extract relationship references from row with full navigation context.

        This method extracts both outgoing relationships (this record references
        another) and provides metadata about incoming relationships (other tables
        that may reference this record's table).

        Args:
            table: Source table name
            row: Database row

        Returns:
            List of RelationshipLink objects with direction and cardinality
        """
        relationships = []

        # Get outgoing relationships (this table -> target table)
        outgoing_rels = self._outgoing_relationships.get(table, [])

        for column, target_table, rel_type in outgoing_rels:
            value = row.get(column)
            if value is not None:
                target_id = str(value)
                target_doc_id = f"{target_table}:{target_id}"

                relationships.append(
                    RelationshipLink(
                        target_doc_id=target_doc_id,
                        target_table=target_table,
                        target_id=target_id,
                        source_column=column,
                        relationship_type=rel_type,
                        direction="outgoing",
                        cardinality="many_to_one",
                    )
                )

        return relationships

    def generate_relationship_links_from_schema(
        self, table: str, record_id: str
    ) -> list[dict[str, Any]]:
        """Generate navigation hints for potential incoming relationships.

        This provides agents with information about what other tables
        might reference records of this type, enabling reverse traversal.

        Args:
            table: Table name
            record_id: Record ID

        Returns:
            List of potential incoming relationship metadata
        """
        incoming_rels = self._incoming_relationships.get(table, [])

        hints = []
        for source_table, source_column, rel_type in incoming_rels:
            hints.append(
                {
                    "source_table": source_table,
                    "source_column": source_column,
                    "relationship_type": rel_type,
                    "cardinality": "one_to_many",
                    "query_hint": f"Find {source_table} where {source_column} = {record_id}",
                }
            )

        return hints

    def extract_file_references(
        self, table: str, row: dict[str, Any]
    ) -> list[FileReferenceLink]:
        """Extract file references from row with complete provenance.

        Tracks exactly where in the source record each file reference
        came from, enabling agents to understand file context and
        navigate back to the source record.

        Args:
            table: Source table name
            row: Database row

        Returns:
            List of FileReferenceLink objects with full provenance
        """
        file_refs = []
        file_columns = self._file_ref_columns.get(table, [])

        for fc in file_columns:
            value = row.get(fc.column_name)
            if value is None:
                continue

            if fc.reference_type == FileReferenceType.S3_KEY:
                # Direct S3 key
                if isinstance(value, str) and value:
                    file_refs.append(
                        FileReferenceLink(
                            s3_key=value,
                            source_column=fc.column_name,
                            reference_type="s3_key",
                            filename=self._extract_filename(value),
                        )
                    )

            elif fc.reference_type == FileReferenceType.JSONB_S3_MAP:
                # JSONB map of file_id -> s3_key
                if isinstance(value, dict):
                    for file_id, s3_key in value.items():
                        if s3_key:
                            file_refs.append(
                                FileReferenceLink(
                                    s3_key=str(s3_key),
                                    source_column=fc.column_name,
                                    reference_type="jsonb_s3_map",
                                    filename=self._extract_filename(str(s3_key)),
                                    file_id=str(file_id),
                                )
                            )
                elif isinstance(value, str):
                    # Try parsing as JSON
                    try:
                        parsed = json.loads(value)
                        if isinstance(parsed, dict):
                            for file_id, s3_key in parsed.items():
                                if s3_key:
                                    file_refs.append(
                                        FileReferenceLink(
                                            s3_key=str(s3_key),
                                            source_column=fc.column_name,
                                            reference_type="jsonb_s3_map",
                                            filename=self._extract_filename(str(s3_key)),
                                            file_id=str(file_id),
                                        )
                                    )
                    except json.JSONDecodeError:
                        pass

            elif fc.reference_type == FileReferenceType.URL:
                # URL reference - generate a placeholder s3_key from URL
                if isinstance(value, str) and value:
                    file_refs.append(
                        FileReferenceLink(
                            s3_key="",  # URL references don't have direct S3 keys
                            source_column=fc.column_name,
                            reference_type="url",
                            url=value,
                        )
                    )

        return file_refs

    def _extract_filename(self, s3_key: str) -> str:
        """Extract filename from S3 key path."""
        if "/" in s3_key:
            return s3_key.rsplit("/", 1)[-1]
        return s3_key

    def generate_content_text(self, table: str, row: dict[str, Any]) -> str:
        """Generate searchable text content from row.

        Args:
            table: Source table name
            row: Database row

        Returns:
            Concatenated text from relevant fields
        """
        # Get table-specific fields or use defaults
        fields = CONTENT_FIELDS.get(
            table, ["name", "title", "description", "number"]
        )

        parts = []
        for field in fields:
            value = row.get(field)
            if value is not None and isinstance(value, str) and value.strip():
                parts.append(value.strip())

        return " ".join(parts)

    async def index_record(self, record: IngestedRecord) -> IngestionResult:
        """Index a single record to Vespa.

        Args:
            record: Record to index

        Returns:
            IngestionResult indicating success or failure
        """
        try:
            # Convert relationships and file_references to JSON strings for Vespa
            # Using to_dict() methods for full navigation context
            doc = {
                "doc_id": record.doc_id,
                "source_table": record.source_table,
                "source_id": record.source_id,
                "project_id": record.project_id,
                "metadata": record.metadata,
                "relationships": [json.dumps(r.to_dict()) for r in record.relationships],
                "file_references": [json.dumps(f.to_dict()) for f in record.file_references],
                "created_at": record.created_at,
                "updated_at": record.updated_at,
                "ingested_at": record.ingested_at,
                "content_text": record.content_text,
            }

            # Add schema documentation fields if available
            if record.table_description:
                doc["table_description"] = record.table_description
            if record.column_types:
                doc["column_types"] = record.column_types

            # Generate incoming relationship hints for navigation
            incoming_hints = self.generate_relationship_links_from_schema(
                record.source_table, record.source_id
            )
            if incoming_hints:
                doc["incoming_relationships"] = [json.dumps(h) for h in incoming_hints]

            # Feed to Vespa
            await self._vespa.feed_data_point(
                schema="procore_record",
                data_id=record.doc_id,
                fields=doc,
            )

            return IngestionResult(success=True, doc_id=record.doc_id)

        except Exception as e:
            return IngestionResult(
                success=False, doc_id=record.doc_id, error=str(e)
            )

    async def index_batch(
        self, records: list[IngestedRecord]
    ) -> list[IngestionResult]:
        """Index a batch of records to Vespa in parallel.

        Args:
            records: List of records to index

        Returns:
            List of IngestionResults
        """
        import asyncio

        # Create tasks for all records
        tasks = [self.index_record(record) for record in records]

        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed results
        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(
                    IngestionResult(
                        success=False,
                        doc_id=records[i].doc_id if i < len(records) else "unknown",
                        error=str(result),
                    )
                )
            else:
                final_results.append(result)

        return final_results
