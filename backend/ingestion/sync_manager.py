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
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from backend.ingestion.pdf_processor import PDFProcessor

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
        "pdfs_processed": 0,
        "pdfs_failed": 0,
        "pdf_pages_indexed": 0,
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
    process_pdfs: bool = False  # Process downloaded PDFs with ColPali
    detect_deletes: bool = False  # Detect and remove deleted records
    delete_detection_interval: int = 10  # Every Nth daemon cycle (0 = disabled)


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
    pdfs_processed: int = 0
    pdfs_failed: int = 0
    pdf_pages_indexed: int = 0
    files_skipped: int = 0
    orphans_cleaned: int = 0
    records_deleted: int = 0
    errors: list[str] = field(default_factory=list)


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
        pdf_processor: Optional["PDFProcessor"] = None,
    ):
        """Initialize sync manager.

        Args:
            db: Database connection instance
            vespa_app: Vespa application client
            schema_map: Schema map from discovery
            checkpoint_store: Checkpoint persistence store
            logger: Optional logger instance
            pdf_processor: Optional PDF processor for ColPali indexing
        """
        self._db = db
        self._vespa = vespa_app
        self._schema_map = schema_map
        self._checkpoint_store = checkpoint_store
        self._logger = logger or logging.getLogger(__name__)
        self._pdf_processor = pdf_processor
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
        pdfs_processed = 0
        pdfs_failed = 0
        pdf_pages_indexed = 0

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
                # Use DIRECT_S3 strategy with AWS credentials from environment
                import os
                aws_config = {
                    "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID"),
                    "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY"),
                    "AWS_REGION": os.environ.get("AWS_REGION", "us-east-1"),
                    "S3_BUCKET": os.environ.get("S3_BUCKET", "procore-integration-files"),
                }
                file_downloader = FileDownloader(
                    download_dir=download_dir,
                    strategy=DownloadStrategy.DIRECT_S3,
                    logger=self._logger,
                    aws_config=aws_config,
                )
                self._logger.info(f"File download enabled, saving to {download_dir}")
                if config.process_pdfs and self._pdf_processor:
                    self._logger.info("PDF processing enabled with ColPali")

            for table in tables:
                self._logger.info(f"Syncing table: {table}")

                table_processed = 0
                table_failed = 0
                table_files_downloaded = 0
                table_files_failed = 0
                table_pdfs_processed = 0
                table_pdfs_failed = 0
                table_pdf_pages = 0

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
                        dl_count, dl_failed, pdf_count, pdf_fail, pdf_pages = await self._download_files_for_table(
                            table=table,
                            file_detector=file_detector,
                            file_downloader=file_downloader,
                            batch_size=config.batch_size,
                            workers=config.file_workers,
                            process_pdfs=config.process_pdfs and self._pdf_processor is not None,
                        )
                        table_files_downloaded = dl_count
                        table_files_failed = dl_failed
                        table_pdfs_processed = pdf_count
                        table_pdfs_failed = pdf_fail
                        table_pdf_pages = pdf_pages
                        files_downloaded += dl_count
                        files_failed += dl_failed
                        pdfs_processed += pdf_count
                        pdfs_failed += pdf_fail
                        pdf_pages_indexed += pdf_pages

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
                    job.progress["pdfs_processed"] = pdfs_processed
                    job.progress["pdfs_failed"] = pdfs_failed
                    job.progress["pdf_pages_indexed"] = pdf_pages_indexed

                    # Build completion message
                    msg = f"Completed {table}: {table_processed} records ({table_failed} failed)"
                    if config.download_files:
                        msg += f", {table_files_downloaded} files"
                    if table_pdfs_processed > 0 or table_pdfs_failed > 0:
                        msg += f", {table_pdfs_processed} PDFs ({table_pdf_pages} pages)"
                    self._logger.info(msg)

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
            pdfs_processed=pdfs_processed,
            pdfs_failed=pdfs_failed,
            pdf_pages_indexed=pdf_pages_indexed,
            errors=job.errors,
        )

    async def run_incremental_sync(
        self, config: SyncConfig, run_delete_detection: bool = False,
    ) -> SyncResult:
        """Run incremental sync from last checkpoints.

        Uses conditional file processing: only downloads/processes files whose
        references actually changed, and cleans up orphaned pdf_pages when
        file references are removed.

        Args:
            config: Sync configuration
            run_delete_detection: If True, detect and delete removed records
                this cycle (overrides config.detect_deletes for one-shot runs)

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
        files_skipped = 0
        orphans_cleaned = 0
        pdfs_processed = 0
        pdfs_failed = 0
        pdf_pages_indexed = 0

        should_detect_deletes = run_delete_detection or config.detect_deletes

        try:
            ingester = RecordIngester(
                db=self._db,
                vespa_app=self._vespa,
                schema_map=self._schema_map,
                logger=self._logger,
            )

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
                import os
                aws_config = {
                    "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID"),
                    "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY"),
                    "AWS_REGION": os.environ.get("AWS_REGION", "us-east-1"),
                    "S3_BUCKET": os.environ.get("S3_BUCKET", "procore-integration-files"),
                }
                file_downloader = FileDownloader(
                    download_dir=download_dir,
                    strategy=DownloadStrategy.DIRECT_S3,
                    logger=self._logger,
                    aws_config=aws_config,
                )
                if config.process_pdfs and self._pdf_processor:
                    self._logger.info("PDF processing enabled with ColPali")

            for table in tables:
                last_sync = await self._checkpoint_store.get_last_sync_time(table)

                self._logger.info(
                    f"Syncing table: {table} "
                    f"(since: {last_sync or 'never'})"
                )

                table_processed = 0
                table_failed = 0
                table_deleted = 0
                table_files_skipped = 0
                table_orphans_cleaned = 0
                table_pdfs_processed = 0
                table_pdfs_failed = 0
                table_pdf_pages = 0
                table_files_downloaded = 0
                table_files_failed = 0

                try:
                    # Step 1: Detect changes to categorize inserts vs updates
                    changeset = await change_detector.detect_changes(table, since=last_sync)

                    # Step 2: Pre-fetch old file references for updates BEFORE overwriting
                    old_file_refs: dict[str, list[dict]] = {}
                    if config.download_files and changeset.updates:
                        for change in changeset.updates:
                            doc_id = f"{table}:{change.record_id}"
                            old_file_refs[doc_id] = await self._fetch_existing_file_references(doc_id)

                    # Step 3: Ingest all changed records (inserts + updates)
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

                    # Step 4-5: Conditional file downloads
                    if config.download_files and file_detector and file_downloader:
                        # Build sets of insert/update record IDs for routing
                        insert_ids = {c.record_id for c in changeset.inserts}
                        update_ids = {c.record_id for c in changeset.updates}

                        # Collect files to download, respecting diff logic
                        files_to_download = []
                        # Build a record_id -> change lookup from changeset
                        change_by_id: dict[str, Any] = {}
                        for c in changeset.inserts:
                            change_by_id[c.record_id] = c
                        for c in changeset.updates:
                            change_by_id[c.record_id] = c

                        for change in list(changeset.inserts) + list(changeset.updates):
                            if change.row is None:
                                continue

                            detected = file_detector.detect_in_record(table, change.row)
                            if not detected:
                                continue

                            if change.record_id in insert_ids:
                                # New record: download all files
                                files_to_download.extend(detected)
                            elif change.record_id in update_ids:
                                # Updated record: diff file references
                                doc_id = f"{table}:{change.record_id}"
                                old_refs = old_file_refs.get(doc_id, [])

                                # Build new refs from detected files
                                new_refs = [
                                    {"s3_key": d.s3_key, "url": d.url or "", "filename": d.filename or ""}
                                    for d in detected
                                ]

                                added, removed, unchanged = self._diff_file_references(old_refs, new_refs)

                                table_files_skipped += len(unchanged)

                                # Only download added files
                                added_keys = {r.get("s3_key") or r.get("url") or "" for r in added}
                                for d in detected:
                                    key = d.s3_key or d.url or ""
                                    if key in added_keys:
                                        files_to_download.append(d)

                                # Cleanup orphaned pdf_pages for removed files
                                if removed:
                                    cleaned = await self._cleanup_orphaned_pdf_pages(
                                        table, change.record_id, removed,
                                    )
                                    table_orphans_cleaned += cleaned

                        if files_to_download:
                            self._logger.info(
                                f"Downloading {len(files_to_download)} files from {table}"
                                f" (skipped {table_files_skipped} unchanged)"
                            )

                            # Track downloaded PDFs for processing
                            downloaded_pdfs: list[tuple] = []
                            file_lookup = {f.s3_key or f.url or "": f for f in files_to_download}

                            async for dl_result in file_downloader.download_batch(
                                files_to_download, workers=config.file_workers,
                            ):
                                if dl_result.success:
                                    table_files_downloaded += 1
                                    if (
                                        config.process_pdfs
                                        and self._pdf_processor
                                        and dl_result.local_path
                                        and dl_result.local_path.suffix.lower() == ".pdf"
                                    ):
                                        detected_file = file_lookup.get(dl_result.s3_key)
                                        if detected_file:
                                            downloaded_pdfs.append((detected_file, dl_result.local_path))
                                elif dl_result.status == "skipped":
                                    self._logger.debug(f"Skipped: {dl_result.s3_key} - {dl_result.error}")
                                else:
                                    table_files_failed += 1
                                    self._logger.warning(
                                        f"Failed to download {dl_result.s3_key}: {dl_result.error}"
                                    )

                            # Process PDFs with ColPali if enabled
                            if config.process_pdfs and downloaded_pdfs and self._pdf_processor:
                                self._logger.info(f"Processing {len(downloaded_pdfs)} PDFs from {table}")
                                results = self._pdf_processor.process_batch(downloaded_pdfs)
                                for pdf_result in results:
                                    if pdf_result.success:
                                        table_pdfs_processed += 1
                                        table_pdf_pages += pdf_result.pages_indexed
                                    else:
                                        table_pdfs_failed += 1
                                        self._logger.warning(
                                            f"Failed to process PDF {pdf_result.file.filename}: {pdf_result.error}"
                                        )
                        elif table_files_skipped > 0:
                            self._logger.info(
                                f"Skipped {table_files_skipped} files (unchanged) in {table}"
                            )

                    # Step 6: Delete detection
                    if should_detect_deletes:
                        vespa_ids = await self._get_vespa_record_ids(table)
                        if vespa_ids:
                            deleted_ids = await change_detector.detect_deletes(table, vespa_ids)
                            if deleted_ids:
                                # Cleanup pdf_pages for deleted records
                                for del_id in deleted_ids:
                                    doc_id = f"{table}:{del_id}"
                                    old_refs = await self._fetch_existing_file_references(doc_id)
                                    if old_refs:
                                        cleaned = await self._cleanup_orphaned_pdf_pages(
                                            table, del_id, old_refs,
                                        )
                                        table_orphans_cleaned += cleaned

                                table_deleted = await self.delete_records(table, deleted_ids)
                                records_deleted += table_deleted

                    # Step 7: Save checkpoint
                    await self._save_checkpoint(
                        table=table,
                        records_processed=table_processed,
                        records_failed=table_failed,
                        status="COMPLETED",
                    )

                    files_downloaded += table_files_downloaded
                    files_failed += table_files_failed
                    files_skipped += table_files_skipped
                    orphans_cleaned += table_orphans_cleaned
                    pdfs_processed += table_pdfs_processed
                    pdfs_failed += table_pdfs_failed
                    pdf_pages_indexed += table_pdf_pages

                    tables_completed += 1
                    job.progress["tables_completed"] = tables_completed
                    job.progress["records_processed"] = records_processed
                    job.progress["records_failed"] = records_failed
                    job.progress["files_downloaded"] = files_downloaded
                    job.progress["files_failed"] = files_failed
                    job.progress["pdfs_processed"] = pdfs_processed
                    job.progress["pdfs_failed"] = pdfs_failed
                    job.progress["pdf_pages_indexed"] = pdf_pages_indexed

                    if table_processed > 0 or table_deleted > 0 or table_pdfs_processed > 0:
                        msg = f"Completed {table}: {table_processed} changes"
                        if table_files_skipped > 0:
                            msg += f", skipped {table_files_skipped} files (unchanged)"
                        if table_deleted > 0:
                            msg += f", {table_deleted} deleted"
                        if table_orphans_cleaned > 0:
                            msg += f", {table_orphans_cleaned} orphans cleaned"
                        if table_pdfs_processed > 0 or table_pdfs_failed > 0:
                            msg += f", {table_pdfs_processed} PDFs ({table_pdf_pages} pages)"
                        self._logger.info(msg)

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
            pdfs_processed=pdfs_processed,
            pdfs_failed=pdfs_failed,
            pdf_pages_indexed=pdf_pages_indexed,
            files_skipped=files_skipped,
            orphans_cleaned=orphans_cleaned,
            records_deleted=records_deleted,
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
                process_pdfs=config.process_pdfs and self._pdf_processor is not None,
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

    async def _fetch_existing_file_references(self, doc_id: str) -> list[dict]:
        """Fetch current file_references from a Vespa procore_record document.

        Args:
            doc_id: Vespa document ID (e.g., "photos:123")

        Returns:
            List of file reference dicts, or empty list if not found
        """
        try:
            response = self._vespa.get_data(
                schema="procore_record",
                data_id=doc_id,
            )
            # pyvespa get_data returns a VespaResponse; extract fields
            if hasattr(response, "json"):
                data = response.json
            elif isinstance(response, dict):
                data = response
            else:
                return []

            fields = data.get("fields", {})
            raw_refs = fields.get("file_references", [])

            # file_references are stored as JSON strings in Vespa
            refs = []
            for ref in raw_refs:
                if isinstance(ref, str):
                    refs.append(json.loads(ref))
                elif isinstance(ref, dict):
                    refs.append(ref)
            return refs
        except Exception as e:
            self._logger.debug(f"Could not fetch existing file refs for {doc_id}: {e}")
            return []

    @staticmethod
    def _diff_file_references(
        old_refs: list[dict], new_refs: list[dict]
    ) -> tuple[list[dict], list[dict], list[dict]]:
        """Compare old and new file references by s3_key/url.

        Args:
            old_refs: File reference dicts from Vespa
            new_refs: File reference dicts from new record

        Returns:
            Tuple of (added, removed, unchanged) reference lists
        """
        def _ref_key(ref: dict) -> str:
            return ref.get("s3_key") or ref.get("url") or ""

        old_keys = {_ref_key(r) for r in old_refs}
        new_keys = {_ref_key(r) for r in new_refs}

        # Filter out empty keys
        old_keys.discard("")
        new_keys.discard("")

        added_keys = new_keys - old_keys
        removed_keys = old_keys - new_keys
        unchanged_keys = old_keys & new_keys

        added = [r for r in new_refs if _ref_key(r) in added_keys]
        removed = [r for r in old_refs if _ref_key(r) in removed_keys]
        unchanged = [r for r in old_refs if _ref_key(r) in unchanged_keys]

        return added, removed, unchanged

    async def _cleanup_orphaned_pdf_pages(
        self,
        source_table: str,
        record_id: str,
        removed_refs: list[dict],
    ) -> int:
        """Delete pdf_page documents for removed file references.

        Args:
            source_table: Source table name
            record_id: Source record ID
            removed_refs: List of removed file reference dicts

        Returns:
            Number of orphaned pdf_page documents deleted
        """
        deleted = 0
        for ref in removed_refs:
            s3_key = ref.get("s3_key", "")
            filename = ref.get("filename", "")
            if not s3_key and not filename:
                continue

            # Query Vespa for pdf_page docs matching this source record and file
            # pdf_page doc_ids follow the pattern: {filename}_page{N}
            # We search by title (filename) and source metadata
            try:
                search_term = filename or s3_key.rsplit("/", 1)[-1] if s3_key else ""
                if not search_term:
                    continue

                response = self._vespa.query(
                    yql=f'select documentid from pdf_page where title contains "{search_term}"',
                    hits=1000,
                )

                if hasattr(response, "json"):
                    data = response.json
                elif isinstance(response, dict):
                    data = response
                else:
                    continue

                children = data.get("root", {}).get("children", [])
                for child in children:
                    doc_id = child.get("id", "")
                    if doc_id:
                        # Extract the Vespa document ID from the full URI
                        # Format: id:namespace:pdf_page::actual_id
                        parts = doc_id.split("::")
                        vespa_id = parts[-1] if parts else doc_id
                        try:
                            self._vespa.delete_data(
                                schema="pdf_page",
                                data_id=vespa_id,
                            )
                            deleted += 1
                        except Exception as e:
                            self._logger.warning(
                                f"Failed to delete orphaned pdf_page {vespa_id}: {e}"
                            )
            except Exception as e:
                self._logger.warning(
                    f"Failed to query orphaned pdf_pages for {source_table}:{record_id}: {e}"
                )

        if deleted > 0:
            self._logger.info(
                f"Cleaned up {deleted} orphaned pdf_page docs for {source_table}:{record_id}"
            )
        return deleted

    async def _get_vespa_record_ids(self, table: str) -> set[str]:
        """Get all source_id values from Vespa for a given table.

        Uses Vespa visiting/query to retrieve all record IDs for a table.

        Args:
            table: Source table name

        Returns:
            Set of record IDs currently in Vespa
        """
        ids: set[str] = set()
        offset = 0
        batch_size = 400

        while True:
            try:
                response = self._vespa.query(
                    yql=f'select source_id from procore_record where source_table contains "{table}"',
                    hits=batch_size,
                    offset=offset,
                )

                if hasattr(response, "json"):
                    data = response.json
                elif isinstance(response, dict):
                    data = response
                else:
                    break

                children = data.get("root", {}).get("children", [])
                if not children:
                    break

                for child in children:
                    fields = child.get("fields", {})
                    source_id = fields.get("source_id")
                    if source_id:
                        ids.add(str(source_id))

                if len(children) < batch_size:
                    break
                offset += batch_size

            except Exception as e:
                self._logger.warning(f"Failed to query Vespa record IDs for {table}: {e}")
                break

        return ids

    async def _download_files_for_table(
        self,
        table: str,
        file_detector: FileDetector,
        file_downloader: FileDownloader,
        batch_size: int = 1000,
        workers: int = 2,
        since: Optional[datetime] = None,
        process_pdfs: bool = False,
    ) -> tuple[int, int, int, int, int]:
        """Download files referenced in a table and optionally process PDFs.

        Args:
            table: Table name
            file_detector: FileDetector instance
            file_downloader: FileDownloader instance
            batch_size: Records per batch
            workers: Parallel download workers
            since: Only process records updated since this time
            process_pdfs: If True and pdf_processor is set, process downloaded PDFs

        Returns:
            Tuple of (files_downloaded, files_failed, pdfs_processed, pdfs_failed, pdf_pages_indexed)
        """
        files_downloaded = 0
        files_failed = 0
        pdfs_processed = 0
        pdfs_failed = 0
        pdf_pages_indexed = 0

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
            return 0, 0, 0, 0, 0

        self._logger.info(f"Downloading {len(all_files)} files from {table}")

        # Track downloaded PDFs for processing
        downloaded_pdfs: list[tuple] = []  # List of (DetectedFile, Path)

        # Build lookup for DetectedFile by s3_key
        file_lookup = {f.s3_key or f.url or "": f for f in all_files}

        # Download files in parallel
        async for result in file_downloader.download_batch(all_files, workers=workers):
            if result.success:
                files_downloaded += 1
                self._logger.debug(f"Downloaded: {result.s3_key}")

                # Track PDFs for processing
                if process_pdfs and result.local_path:
                    file_ext = result.local_path.suffix.lower()
                    if file_ext == ".pdf":
                        detected_file = file_lookup.get(result.s3_key)
                        if detected_file:
                            downloaded_pdfs.append((detected_file, result.local_path))
            elif result.status == "skipped":
                self._logger.debug(f"Skipped: {result.s3_key} - {result.error}")
            else:
                files_failed += 1
                self._logger.warning(f"Failed to download {result.s3_key}: {result.error}")

        # Process PDFs with ColPali if enabled
        if process_pdfs and downloaded_pdfs and self._pdf_processor:
            self._logger.info(f"Processing {len(downloaded_pdfs)} PDFs from {table}")
            results = self._pdf_processor.process_batch(downloaded_pdfs)

            for pdf_result in results:
                if pdf_result.success:
                    pdfs_processed += 1
                    pdf_pages_indexed += pdf_result.pages_indexed
                else:
                    pdfs_failed += 1
                    self._logger.warning(
                        f"Failed to process PDF {pdf_result.file.filename}: {pdf_result.error}"
                    )

        return files_downloaded, files_failed, pdfs_processed, pdfs_failed, pdf_pages_indexed

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
                self._vespa.feed_data_point(
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
            self._vespa.feed_data_point(
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
