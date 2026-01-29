"""
Change detection for incremental sync operations.
"""

from dataclasses import dataclass, field
from logging import Logger

from backend.logging_config import get_logger
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional, Set

from backend.ingestion.checkpoint import CheckpointStore
from backend.ingestion.db_connection import DatabaseConnection
from backend.ingestion.schema_discovery import SchemaMap


@dataclass
class Change:
    """Represents a single record change."""

    table: str
    record_id: str
    change_type: str  # "insert", "update", "delete"
    updated_at: datetime
    row: Optional[dict[str, Any]] = None


@dataclass
class ChangeSet:
    """Set of changes for a table."""

    table: str
    since: datetime
    until: datetime
    inserts: list[Change] = field(default_factory=list)
    updates: list[Change] = field(default_factory=list)
    deletes: list[Change] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        """Total number of changes in this set."""
        return len(self.inserts) + len(self.updates) + len(self.deletes)


class ChangeDetector:
    """Detect changes in database tables since last sync."""

    # Preferred timestamp columns in order of priority
    TIMESTAMP_COLUMNS = ["updated_at", "last_synced_at", "created_at"]

    def __init__(
        self,
        db: DatabaseConnection,
        checkpoint_store: CheckpointStore,
        logger: Optional[Logger] = None,
        schema_map: Optional[SchemaMap] = None,
    ):
        """Initialize change detector.

        Args:
            db: Database connection instance
            checkpoint_store: Checkpoint persistence store
            logger: Optional logger instance
            schema_map: Optional schema map for timestamp column lookup
        """
        self._db = db
        self._checkpoint_store = checkpoint_store
        self._logger = logger or get_logger(__name__)
        # Build per-table timestamp column lookup from schema
        self._table_timestamp_columns: dict[str, list[str]] = {}
        if schema_map:
            for table in schema_map.tables:
                self._table_timestamp_columns[table.name] = table.timestamp_columns

    async def detect_changes(
        self,
        table: str,
        since: Optional[datetime] = None,
    ) -> ChangeSet:
        """Detect all changes in a table since timestamp.

        Args:
            table: Table name
            since: Timestamp to detect changes from (None = all records)

        Returns:
            ChangeSet with categorized changes
        """
        if since is None:
            # Get from checkpoint
            since = await self._checkpoint_store.get_last_sync_time(table)

        if since is None:
            since = datetime.min

        until = datetime.now(timezone.utc)

        self._logger.debug(f"Detecting changes in {table} since {since}")

        # Get timestamp column for this table
        ts_column = self.get_timestamp_column(table)

        if ts_column is None:
            self._logger.info(
                f"Table {table} has no timestamp column — "
                f"change detection skipped, full resync will be used"
            )
            return ChangeSet(
                table=table, since=since, until=until,
                inserts=[], updates=[], deletes=[],
            )

        # Fetch updated records
        inserts = []
        updates = []

        async for row in self.get_updated_records(table, since):
            change = Change(
                table=table,
                record_id=str(row.get("id", "")),
                change_type="update",  # We'll differentiate inserts vs updates below
                updated_at=row.get(ts_column, until),
                row=row,
            )

            # Determine if insert or update based on created_at
            created_at = row.get("created_at")
            if created_at and isinstance(created_at, datetime):
                if created_at > since:
                    change.change_type = "insert"
                    inserts.append(change)
                else:
                    updates.append(change)
            else:
                updates.append(change)

        return ChangeSet(
            table=table,
            since=since,
            until=until,
            inserts=inserts,
            updates=updates,
            deletes=[],  # Delete detection is separate
        )

    async def get_updated_records(
        self,
        table: str,
        since: datetime,
        batch_size: int = 1000,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream records updated since timestamp.

        Args:
            table: Table name
            since: Timestamp to detect changes from
            batch_size: Number of records per batch

        Yields:
            Database rows that have been updated
        """
        ts_column = self.get_timestamp_column(table)

        if ts_column is None:
            self._logger.debug(
                f"Table {table} has no timestamp column — "
                f"no incremental records to stream"
            )
            return

        query = f"""
            SELECT * FROM "{table}"
            WHERE "{ts_column}" > $1
            ORDER BY "{ts_column}" ASC
        """

        async for batch in self._db.stream(query, since, batch_size=batch_size):
            for row in batch:
                yield row

    async def detect_deletes(
        self,
        table: str,
        known_ids: Set[str],
        sample_size: int = 1000,
    ) -> list[str]:
        """Detect deleted records by comparing with known IDs.

        This is an expensive operation - use sparingly.

        Args:
            table: Table name
            known_ids: Set of record IDs known to be in Vespa
            sample_size: Batch size for querying current IDs

        Returns:
            List of record IDs that have been deleted
        """
        self._logger.debug(
            f"Detecting deletes in {table} (checking {len(known_ids)} known IDs)"
        )

        # Get current IDs from database
        query = f'SELECT id FROM "{table}"'

        current_ids = set()
        async for batch in self._db.stream(query, batch_size=sample_size):
            for row in batch:
                current_ids.add(str(row["id"]))

        # Find IDs that are in known_ids but not in current_ids
        deleted_ids = known_ids - current_ids

        if deleted_ids:
            self._logger.info(f"Detected {len(deleted_ids)} deleted records in {table}")

        return list(deleted_ids)

    def get_timestamp_column(self, table: str) -> Optional[str]:
        """Get the best timestamp column for change detection.

        Checks available columns from schema discovery and picks the best
        option in priority order: updated_at > last_synced_at > created_at.

        Args:
            table: Table name

        Returns:
            Name of the timestamp column to use, or None if table has no
            recognized timestamp columns
        """
        available = self._table_timestamp_columns.get(table, [])
        for preferred in self.TIMESTAMP_COLUMNS:
            if preferred in available:
                return preferred
        return None

    async def get_table_id_set(self, table: str) -> Set[str]:
        """Get set of all record IDs in a table.

        Args:
            table: Table name

        Returns:
            Set of all record IDs
        """
        query = f'SELECT id FROM "{table}"'
        ids = set()

        async for batch in self._db.stream(query, batch_size=10000):
            for row in batch:
                ids.add(str(row["id"]))

        return ids
