"""
Checkpoint persistence for sync state using SQLite.
"""

from dataclasses import dataclass
from logging import Logger

from backend.core.logging_config import get_logger
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import aiosqlite


@dataclass
class Checkpoint:
    """Sync checkpoint for a table."""

    table_name: str
    last_sync_timestamp: datetime
    last_record_id: Optional[str]
    records_processed: int
    records_failed: int
    sync_status: str
    error_message: Optional[str]
    updated_at: datetime


class CheckpointStore:
    """Persist sync checkpoints in SQLite."""

    def __init__(self, db_path: Path, logger: Optional[Logger] = None):
        """Initialize checkpoint store.

        Args:
            db_path: Path to SQLite database file
            logger: Optional logger instance
        """
        self._db_path = db_path
        self._logger = logger or get_logger(__name__)

    async def initialize(self) -> None:
        """Create checkpoint table if not exists."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS sync_checkpoints (
                    table_name TEXT PRIMARY KEY,
                    last_sync_timestamp TEXT,
                    last_record_id TEXT,
                    records_processed INTEGER DEFAULT 0,
                    records_failed INTEGER DEFAULT 0,
                    sync_status TEXT DEFAULT 'IDLE',
                    error_message TEXT,
                    updated_at TEXT
                )
                """
            )
            await db.commit()
            self._logger.info(f"Checkpoint store initialized at {self._db_path}")

    async def get(self, table_name: str) -> Optional[Checkpoint]:
        """Get checkpoint for a table."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM sync_checkpoints WHERE table_name = ?",
                (table_name,),
            ) as cursor:
                row = await cursor.fetchone()
                if row is None:
                    return None
                return self._row_to_checkpoint(row)

    async def set(self, checkpoint: Checkpoint) -> None:
        """Update checkpoint for a table."""
        async with aiosqlite.connect(self._db_path) as db:
            await db.execute(
                """
                INSERT OR REPLACE INTO sync_checkpoints (
                    table_name, last_sync_timestamp, last_record_id,
                    records_processed, records_failed, sync_status,
                    error_message, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.table_name,
                    checkpoint.last_sync_timestamp.isoformat(),
                    checkpoint.last_record_id,
                    checkpoint.records_processed,
                    checkpoint.records_failed,
                    checkpoint.sync_status,
                    checkpoint.error_message,
                    checkpoint.updated_at.isoformat(),
                ),
            )
            await db.commit()

    async def get_all(self) -> list[Checkpoint]:
        """Get all checkpoints."""
        async with aiosqlite.connect(self._db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM sync_checkpoints") as cursor:
                rows = await cursor.fetchall()
                return [self._row_to_checkpoint(row) for row in rows]

    async def clear(self, table_name: Optional[str] = None) -> None:
        """Clear checkpoint(s)."""
        async with aiosqlite.connect(self._db_path) as db:
            if table_name:
                await db.execute(
                    "DELETE FROM sync_checkpoints WHERE table_name = ?",
                    (table_name,),
                )
            else:
                await db.execute("DELETE FROM sync_checkpoints")
            await db.commit()

    async def get_last_sync_time(self, table_name: str) -> Optional[datetime]:
        """Get last successful sync timestamp for a table.

        Returns a naive UTC datetime for compatibility with PostgreSQL
        timestamp columns (which store naive UTC).
        """
        checkpoint = await self.get(table_name)
        if checkpoint and checkpoint.sync_status == "COMPLETED":
            ts = checkpoint.last_sync_timestamp
            # Strip tzinfo so comparisons with naive PG timestamps work
            return ts.replace(tzinfo=None) if ts.tzinfo else ts
        return None

    @staticmethod
    def _ensure_aware(dt: datetime) -> datetime:
        """Ensure a datetime is timezone-aware (UTC).

        Handles legacy naive datetimes stored before the utcnow→now(UTC) migration.
        """
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    def _row_to_checkpoint(self, row: aiosqlite.Row) -> Checkpoint:
        """Convert a database row to a Checkpoint object."""
        return Checkpoint(
            table_name=row["table_name"],
            last_sync_timestamp=self._ensure_aware(
                datetime.fromisoformat(row["last_sync_timestamp"])
            )
            if row["last_sync_timestamp"]
            else datetime.min.replace(tzinfo=timezone.utc),
            last_record_id=row["last_record_id"],
            records_processed=row["records_processed"] or 0,
            records_failed=row["records_failed"] or 0,
            sync_status=row["sync_status"] or "IDLE",
            error_message=row["error_message"],
            updated_at=self._ensure_aware(
                datetime.fromisoformat(row["updated_at"])
            )
            if row["updated_at"]
            else datetime.now(timezone.utc),
        )
