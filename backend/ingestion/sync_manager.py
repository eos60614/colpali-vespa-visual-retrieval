"""
Orchestration of database sync operations.
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from fnmatch import fnmatch
from pathlib import Path
from typing import Any, Optional

from backend.ingestion.change_detector import ChangeDetector
from backend.ingestion.checkpoint import Checkpoint, CheckpointStore
from backend.ingestion.db_connection import DatabaseConnection
from backend.ingestion.file_detector import FileDetector
from backend.ingestion.file_downloader import DownloadStrategy, FileDownloader
from backend.ingestion.record_ingester import RecordIngester
from backend.ingestion.schema_discovery import SchemaMap


@dataclass
class IngestionJob:
    """Tracks the status of an ingestion job."""

    job_id: str
    job_type: str  # FULL, INCREMENTAL, SCHEMA_DISCOVERY
    status: str  # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    started_at: datetime
    completed_at: Optional[datetime] = None
    tables_config: dict = field(default_factory=dict)
    progress: dict = field(default_factory=lambda: {
        "tables_total": 0,
        "tables_completed": 0,
        "records_total": 0,
        "records_processed": 0,
        "records_failed": 0,
        "files_total": 0,
        "files_downloaded": 0,
        "files_failed": 0,
    })
    errors: list = field(default_factory=list)


@dataclass
class SyncConfig:
    """Configuration for sync operations."""

    tables: Optional[list[str]] = None  # None = all tables
    exclude_tables: list[str] = field(default_factory=list)
    batch_size: int = 10000
    download_files: bool = False
    file_workers: int = 2
    download_dir: Optional[Path] = None


@dataclass
class SyncResult:
    """Result of a sync operation."""

    job_id: str
    status: str
    started_at: datetime
    completed_at: Optional[datetime]
    tables_processed: int
    records_processed: int
    records_failed: int
    files_downloaded: int
    files_failed: int
    errors: list[str]


class SyncManager:
    """Orchestrate database sync operations."""

    # Default tables to exclude (system tables)
    DEFAULT_EXCLUDE = [
        "_prisma_migrations",
        "sync_events",
        "webhook_*",
    ]

    def __init__(
        self,
        db: DatabaseConnection,
        vespa_app: Any,
        schema_map: SchemaMap,
        checkpoint_store: CheckpointStore,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize sync manager.

        Args:
            db: Database connection instance
            vespa_app: Vespa application client
            schema_map: Schema map from discovery
            checkpoint_store: Checkpoint persistence store
            logger: Optional logger instance
        """
        self._db = db
        self._vespa = vespa_app
        self._schema_map = schema_map
        self._checkpoint_store = checkpoint_store
        self._logger = logger or logging.getLogger(__name__)
        self._current_job: Optional[IngestionJob] = None

    def get_tables_to_sync(self, config: SyncConfig) -> list[str]:
        """Get list of tables to sync based on config.

        Args:
            config: Sync configuration

        Returns:
            List of table names to sync
        """
        # Get all table names from schema
        all_tables = [t.name for t in self._schema_map.tables]

        # Apply include filter
        if config.tables:
            tables = [t for t in all_tables if t in config.tables]
        else:
            tables = all_tables

        # Apply exclude filter (including defaults)
        exclude_patterns = self.DEFAULT_EXCLUDE + config.exclude_tables

        filtered_tables = []
        for table in tables:
            excluded = False
            for pattern in exclude_patterns:
                if fnmatch(table, pattern):
                    excluded = True
                    break
            if not excluded:
                filtered_tables.append(table)

        return filtered_tables

    async def run_full_sync(self, config: SyncConfig) -> SyncResult:
        """Run full ingestion of all data.

        Args:
            config: Sync configuration

        Returns:
            SyncResult with operation summary
        """
        job = IngestionJob(
            job_id=str(uuid.uuid4()),
            job_type="FULL",
            status="RUNNING",
            started_at=datetime.utcnow(),
            tables_config={
                "include": config.tables,
                "exclude": config.exclude_tables,
            },
        )
        self._current_job = job

        self._logger.info(f"Starting full sync - Job ID: {job.job_id}")

        tables = self.get_tables_to_sync(config)
        job.progress["tables_total"] = len(tables)

        self._logger.info(f"Tables to sync: {len(tables)}")

        records_processed = 0
        records_failed = 0
        tables_completed = 0
        files_downloaded = 0
        files_failed = 0

        try:
            # Create record ingester
            ingester = RecordIngester(
                db=self._db,
                vespa_app=self._vespa,
                schema_map=self._schema_map,
                logger=self._logger,
            )

            # Create file detector and downloader if file download is enabled
            file_detector = None
            file_downloader = None
            if config.download_files:
                file_detector = FileDetector(self._schema_map, self._logger)
                download_dir = config.download_dir or Path("data/downloads")
                file_downloader = FileDownloader(
                    download_dir=download_dir,
                    strategy=DownloadStrategy.PROCORE_URL,
                    logger=self._logger,
                )
                self._logger.info(f"File download enabled, saving to {download_dir}")

            for table in tables:
                self._logger.info(f"Syncing table: {table}")

                table_processed = 0
                table_failed = 0
                table_files_downloaded = 0
                table_files_failed = 0

                try:
                    async for result in ingester.ingest_table(
                        table=table,
                        batch_size=config.batch_size,
                    ):
                        if result.success:
                            table_processed += 1
                            records_processed += 1
                        else:
                            table_failed += 1
                            records_failed += 1
                            if result.error:
                                job.errors.append(
                                    f"{table}:{result.doc_id}: {result.error}"
                                )

                    # Download files if enabled
                    if config.download_files and file_detector and file_downloader:
                        dl_count, dl_failed = await self._download_files_for_table(
                            table=table,
                            file_detector=file_detector,
                            file_downloader=file_downloader,
                            batch_size=config.batch_size,
                            workers=config.file_workers,
                        )
                        table_files_downloaded = dl_count
                        table_files_failed = dl_failed
                        files_downloaded += dl_count
                        files_failed += dl_failed

                    # Save checkpoint after table completion
                    await self._save_checkpoint(
                        table=table,
                        records_processed=table_processed,
                        records_failed=table_failed,
                        status="COMPLETED",
                    )

                    tables_completed += 1
                    job.progress["tables_completed"] = tables_completed
                    job.progress["records_processed"] = records_processed
                    job.progress["records_failed"] = records_failed
                    job.progress["files_downloaded"] = files_downloaded
                    job.progress["files_failed"] = files_failed

                    self._logger.info(
                        f"Completed {table}: {table_processed} records "
                        f"({table_failed} failed)"
                        + (f", {table_files_downloaded} files" if config.download_files else "")
                    )

                except Exception as e:
                    self._logger.error(f"Failed to sync table {table}: {e}")
                    job.errors.append(f"{table}: {str(e)}")

                    await self._save_checkpoint(
                        table=table,
                        records_processed=table_processed,
                        records_failed=table_failed,
                        status="FAILED",
                        error_message=str(e),
                    )

            job.status = "COMPLETED" if records_failed == 0 else "COMPLETED_WITH_ERRORS"
            job.completed_at = datetime.utcnow()

        except Exception as e:
            self._logger.error(f"Full sync failed: {e}")
            job.status = "FAILED"
            job.errors.append(str(e))
            job.completed_at = datetime.utcnow()

        self._current_job = None

        return SyncResult(
            job_id=job.job_id,
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            tables_processed=tables_completed,
            records_processed=records_processed,
            records_failed=records_failed,
            files_downloaded=files_downloaded,
            files_failed=files_failed,
            errors=job.errors,
        )

    async def run_incremental_sync(self, config: SyncConfig) -> SyncResult:
        """Run incremental sync from last checkpoints.

        Args:
            config: Sync configuration

        Returns:
            SyncResult with operation summary
        """
        job = IngestionJob(
            job_id=str(uuid.uuid4()),
            job_type="INCREMENTAL",
            status="RUNNING",
            started_at=datetime.utcnow(),
            tables_config={
                "include": config.tables,
                "exclude": config.exclude_tables,
            },
        )
        self._current_job = job

        self._logger.info(f"Starting incremental sync - Job ID: {job.job_id}")

        tables = self.get_tables_to_sync(config)
        job.progress["tables_total"] = len(tables)

        records_processed = 0
        records_failed = 0
        records_deleted = 0
        tables_completed = 0
        files_downloaded = 0
        files_failed = 0

        try:
            ingester = RecordIngester(
                db=self._db,
                vespa_app=self._vespa,
                schema_map=self._schema_map,
                logger=self._logger,
            )

            # Create change detector for delete detection
            change_detector = ChangeDetector(
                db=self._db,
                checkpoint_store=self._checkpoint_store,
                logger=self._logger,
            )

            # Create file detector and downloader if enabled
            file_detector = None
            file_downloader = None
            if config.download_files:
                file_detector = FileDetector(self._schema_map, self._logger)
                download_dir = config.download_dir or Path("data/downloads")
                file_downloader = FileDownloader(
                    download_dir=download_dir,
                    strategy=DownloadStrategy.PROCORE_URL,
                    logger=self._logger,
                )

            for table in tables:
                # Get last sync time for this table
                last_sync = await self._checkpoint_store.get_last_sync_time(table)

                self._logger.info(
                    f"Syncing table: {table} "
                    f"(since: {last_sync or 'never'})"
                )

                table_processed = 0
                table_failed = 0
                table_deleted = 0

                try:
                    # Process updates and inserts
                    async for result in ingester.ingest_table(
                        table=table,
                        batch_size=config.batch_size,
                        since=last_sync,
                    ):
                        if result.success:
                            table_processed += 1
                            records_processed += 1
                        else:
                            table_failed += 1
                            records_failed += 1
                            if result.error:
                                job.errors.append(
                                    f"{table}:{result.doc_id}: {result.error}"
                                )

                    # Download files for updated records if enabled
                    if config.download_files and file_detector and file_downloader:
                        dl_count, dl_failed = await self._download_files_for_table(
                            table=table,
                            file_detector=file_detector,
                            file_downloader=file_downloader,
                            batch_size=config.batch_size,
                            workers=config.file_workers,
                            since=last_sync,
                        )
                        files_downloaded += dl_count
                        files_failed += dl_failed

                    await self._save_checkpoint(
                        table=table,
                        records_processed=table_processed,
                        records_failed=table_failed,
                        status="COMPLETED",
                    )

                    tables_completed += 1
                    job.progress["tables_completed"] = tables_completed
                    job.progress["records_processed"] = records_processed
                    job.progress["records_failed"] = records_failed
                    job.progress["files_downloaded"] = files_downloaded
                    job.progress["files_failed"] = files_failed

                    if table_processed > 0 or table_deleted > 0:
                        self._logger.info(
                            f"Completed {table}: {table_processed} changes"
                            + (f", {table_deleted} deleted" if table_deleted > 0 else "")
                        )

                except Exception as e:
                    self._logger.error(f"Failed to sync table {table}: {e}")
                    job.errors.append(f"{table}: {str(e)}")

                    await self._save_checkpoint(
                        table=table,
                        records_processed=table_processed,
                        records_failed=table_failed,
                        status="FAILED",
                        error_message=str(e),
                    )

            job.status = "COMPLETED" if records_failed == 0 else "COMPLETED_WITH_ERRORS"
            job.completed_at = datetime.utcnow()

        except Exception as e:
            self._logger.error(f"Incremental sync failed: {e}")
            job.status = "FAILED"
            job.errors.append(str(e))
            job.completed_at = datetime.utcnow()

        self._current_job = None

        return SyncResult(
            job_id=job.job_id,
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            tables_processed=tables_completed,
            records_processed=records_processed,
            records_failed=records_failed,
            files_downloaded=files_downloaded,
            files_failed=files_failed,
            errors=job.errors,
        )

    async def sync_table(
        self,
        table: str,
        full: bool = False,
        config: Optional[SyncConfig] = None,
    ) -> int:
        """Sync a single table.

        Args:
            table: Table name to sync
            full: If True, sync all records; if False, sync only changes
            config: Optional sync configuration

        Returns:
            Number of records processed
        """
        if config is None:
            config = SyncConfig()

        ingester = RecordIngester(
            db=self._db,
            vespa_app=self._vespa,
            schema_map=self._schema_map,
            logger=self._logger,
        )

        since = None
        if not full:
            since = await self._checkpoint_store.get_last_sync_time(table)

        records_processed = 0
        records_failed = 0

        async for result in ingester.ingest_table(
            table=table,
            batch_size=config.batch_size,
            since=since,
        ):
            if result.success:
                records_processed += 1
            else:
                records_failed += 1

        # Download files if enabled
        if config.download_files:
            file_detector = FileDetector(self._schema_map, self._logger)
            download_dir = config.download_dir or Path("data/downloads")
            file_downloader = FileDownloader(
                download_dir=download_dir,
                strategy=DownloadStrategy.PROCORE_URL,
                logger=self._logger,
            )
            await self._download_files_for_table(
                table=table,
                file_detector=file_detector,
                file_downloader=file_downloader,
                batch_size=config.batch_size,
                workers=config.file_workers,
                since=since,
            )

        await self._save_checkpoint(
            table=table,
            records_processed=records_processed,
            records_failed=records_failed,
            status="COMPLETED" if records_failed == 0 else "COMPLETED_WITH_ERRORS",
        )

        return records_processed

    async def delete_records(
        self,
        table: str,
        record_ids: list[str],
    ) -> int:
        """Delete records from Vespa.

        Args:
            table: Source table name
            record_ids: List of record IDs to delete

        Returns:
            Number of records deleted
        """
        deleted = 0
        for record_id in record_ids:
            doc_id = f"{table}:{record_id}"
            try:
                await self._vespa.delete_data(
                    schema="procore_record",
                    data_id=doc_id,
                )
                deleted += 1
                self._logger.debug(f"Deleted record: {doc_id}")
            except Exception as e:
                self._logger.warning(f"Failed to delete {doc_id}: {e}")

        if deleted > 0:
            self._logger.info(f"Deleted {deleted} records from {table}")

        return deleted

    async def detect_and_delete_removed_records(
        self,
        table: str,
        known_ids: set[str],
    ) -> int:
        """Detect and delete records that no longer exist in the database.

        Args:
            table: Table name
            known_ids: Set of record IDs known to be in Vespa

        Returns:
            Number of records deleted
        """
        change_detector = ChangeDetector(
            db=self._db,
            checkpoint_store=self._checkpoint_store,
            logger=self._logger,
        )

        deleted_ids = await change_detector.detect_deletes(table, known_ids)

        if deleted_ids:
            return await self.delete_records(table, deleted_ids)

        return 0

    async def get_status(self) -> dict[str, Any]:
        """Get current sync status for all tables.

        Returns:
            Dictionary with sync status information
        """
        checkpoints = await self._checkpoint_store.get_all()

        tables_status = {}
        for cp in checkpoints:
            tables_status[cp.table_name] = {
                "last_sync": cp.last_sync_timestamp.isoformat(),
                "records_processed": cp.records_processed,
                "records_failed": cp.records_failed,
                "status": cp.sync_status,
                "error": cp.error_message,
            }

        total_records = sum(cp.records_processed for cp in checkpoints)
        total_failed = sum(cp.records_failed for cp in checkpoints)

        return {
            "tables_monitored": len(checkpoints),
            "total_records": total_records,
            "total_failed": total_failed,
            "current_job": self._current_job.job_id if self._current_job else None,
            "tables": tables_status,
        }

    async def _download_files_for_table(
        self,
        table: str,
        file_detector: FileDetector,
        file_downloader: FileDownloader,
        batch_size: int = 1000,
        workers: int = 2,
        since: Optional[datetime] = None,
    ) -> tuple[int, int]:
        """Download files referenced in a table.

        Args:
            table: Table name
            file_detector: FileDetector instance
            file_downloader: FileDownloader instance
            batch_size: Records per batch
            workers: Parallel download workers
            since: Only process records updated since this time

        Returns:
            Tuple of (files_downloaded, files_failed)
        """
        files_downloaded = 0
        files_failed = 0

        # Build query
        if since:
            query = f'SELECT * FROM "{table}" WHERE updated_at > $1'
            args = (since,)
        else:
            query = f'SELECT * FROM "{table}"'
            args = ()

        # Collect all files from records
        all_files = []
        async for batch in self._db.stream(query, *args, batch_size=batch_size):
            for row in batch:
                detected = file_detector.detect_in_record(table, row)
                all_files.extend(detected)

        if not all_files:
            return 0, 0

        self._logger.info(f"Downloading {len(all_files)} files from {table}")

        # Download files in parallel
        async for result in file_downloader.download_batch(all_files, workers=workers):
            if result.success:
                files_downloaded += 1
                self._logger.debug(f"Downloaded: {result.s3_key}")
            elif result.status == "skipped":
                self._logger.debug(f"Skipped: {result.s3_key} - {result.error}")
            else:
                files_failed += 1
                self._logger.warning(f"Failed to download {result.s3_key}: {result.error}")

        return files_downloaded, files_failed

    async def _save_checkpoint(
        self,
        table: str,
        records_processed: int,
        records_failed: int,
        status: str,
        error_message: Optional[str] = None,
    ) -> None:
        """Save checkpoint for a table."""
        now = datetime.utcnow()
        checkpoint = Checkpoint(
            table_name=table,
            last_sync_timestamp=now,
            last_record_id=None,
            records_processed=records_processed,
            records_failed=records_failed,
            sync_status=status,
            error_message=error_message,
            updated_at=now,
        )
        await self._checkpoint_store.set(checkpoint)

    async def index_schema_metadata(self) -> int:
        """Index SchemaMap as navigable metadata documents in Vespa.

        Creates two types of documents:
        1. A full schema document with database-wide summary
        2. Individual table metadata documents for detailed navigation

        Returns:
            Number of metadata documents indexed
        """
        self._logger.info("Indexing schema metadata for agent navigation...")

        indexed = 0
        schema_map = self._schema_map

        # Build relationship lookups for each table
        outgoing_rels: dict[str, list[dict]] = {}
        incoming_rels: dict[str, list[dict]] = {}

        for rel in schema_map.relationships:
            # Outgoing from source table
            if rel.source_table not in outgoing_rels:
                outgoing_rels[rel.source_table] = []
            rel_type = rel.source_column[:-3] if rel.source_column.endswith("_id") else rel.source_column
            outgoing_rels[rel.source_table].append({
                "target_table": rel.target_table,
                "source_column": rel.source_column,
                "relationship_type": rel_type,
                "cardinality": "many_to_one",
            })

            # Incoming to target table
            if rel.target_table not in incoming_rels:
                incoming_rels[rel.target_table] = []
            incoming_type = rel.source_table.rstrip("s") if rel.source_table.endswith("s") else rel.source_table
            incoming_rels[rel.target_table].append({
                "source_table": rel.source_table,
                "source_column": rel.source_column,
                "relationship_type": incoming_type,
                "cardinality": "one_to_many",
            })

        # Table descriptions from RecordIngester
        table_descriptions = RecordIngester.TABLE_DESCRIPTIONS

        # Index individual table metadata documents
        for table in schema_map.tables:
            doc_id = f"table:{table.name}"

            # Build searchable content text
            content_parts = [table.name]
            if table.name in table_descriptions:
                content_parts.append(table_descriptions[table.name])
            content_parts.extend(col.name for col in table.columns)
            content_text = " ".join(content_parts)

            doc = {
                "doc_id": doc_id,
                "metadata_type": "table",
                "database_name": schema_map.database_name,
                "table_name": table.name,
                "table_description": table_descriptions.get(table.name, ""),
                "row_count": table.row_count,
                "columns": [
                    json.dumps({
                        "name": col.name,
                        "data_type": col.data_type,
                        "is_nullable": col.is_nullable,
                        "default_value": col.default_value,
                    })
                    for col in table.columns
                ],
                "timestamp_columns": table.timestamp_columns,
                "file_reference_columns": [
                    json.dumps({
                        "column_name": fc.column_name,
                        "reference_type": fc.reference_type.value,
                        "pattern": fc.pattern,
                    })
                    for fc in table.file_reference_columns
                ],
                "outgoing_relationships": [
                    json.dumps(r) for r in outgoing_rels.get(table.name, [])
                ],
                "incoming_relationships": [
                    json.dumps(r) for r in incoming_rels.get(table.name, [])
                ],
                "primary_key": table.primary_key,
                "discovery_timestamp": schema_map.discovery_timestamp,
                "content_text": content_text,
            }

            try:
                await self._vespa.feed_data_point(
                    schema="procore_schema_metadata",
                    data_id=doc_id,
                    fields=doc,
                )
                indexed += 1
                self._logger.debug(f"Indexed table metadata: {table.name}")
            except Exception as e:
                self._logger.warning(f"Failed to index table metadata {table.name}: {e}")

        # Index full schema summary document
        full_schema_doc_id = f"schema:{schema_map.database_name}"
        file_refs_summary = schema_map.file_references_summary

        schema_summary = {
            "table_count": len(schema_map.tables),
            "relationship_count": len(schema_map.relationships),
            "total_file_ref_columns": file_refs_summary["total_columns"],
            "tables_with_files": file_refs_summary["tables_with_files"],
            "table_names": [t.name for t in schema_map.tables],
        }

        # Build content text for full schema
        schema_content_parts = [
            schema_map.database_name,
            "database schema",
            f"{len(schema_map.tables)} tables",
            f"{len(schema_map.relationships)} relationships",
        ]
        schema_content_parts.extend(t.name for t in schema_map.tables)

        full_schema_doc = {
            "doc_id": full_schema_doc_id,
            "metadata_type": "full_schema",
            "database_name": schema_map.database_name,
            "table_name": "",
            "table_description": f"Full schema for {schema_map.database_name} database",
            "row_count": sum(t.row_count for t in schema_map.tables),
            "columns": [],
            "timestamp_columns": [],
            "file_reference_columns": [],
            "outgoing_relationships": [],
            "incoming_relationships": [],
            "primary_key": [],
            "discovery_timestamp": schema_map.discovery_timestamp,
            "schema_summary": json.dumps(schema_summary),
            "content_text": " ".join(schema_content_parts),
        }

        try:
            await self._vespa.feed_data_point(
                schema="procore_schema_metadata",
                data_id=full_schema_doc_id,
                fields=full_schema_doc,
            )
            indexed += 1
            self._logger.debug(f"Indexed full schema document: {full_schema_doc_id}")
        except Exception as e:
            self._logger.warning(f"Failed to index full schema document: {e}")

        self._logger.info(f"Indexed {indexed} schema metadata documents")
        return indexed
