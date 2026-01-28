#!/usr/bin/env python3
"""
Database Sync Daemon CLI

Continuous change detection and synchronization.
"""

import argparse
import asyncio
import logging
import os
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.config import get, get_env
from backend.ingestion.checkpoint import CheckpointStore
from backend.ingestion.db_connection import ConnectionConfig, DatabaseConnection
from backend.ingestion.schema_discovery import SchemaDiscovery
from backend.ingestion.sync_manager import SyncConfig, SyncManager


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s:\t%(asctime)s\t%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Database sync daemon for continuous synchronization.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Start sync daemon
  python scripts/sync_database.py --daemon

  # Run single sync cycle
  python scripts/sync_database.py --once

  # Check sync status
  python scripts/sync_database.py --status

  # Custom sync interval (5 minutes)
  python scripts/sync_database.py --daemon --interval 300
""",
    )

    parser.add_argument(
        "--database-url",
        type=str,
        default=os.environ.get("PROCORE_DATABASE_URL"),
        help="PostgreSQL connection string (default: $PROCORE_DATABASE_URL)",
    )
    parser.add_argument(
        "--vespa-url",
        type=str,
        default=get_env("VESPA_LOCAL_URL") or get("app", "default_vespa_url"),
        help="Vespa endpoint URL",
    )

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--daemon",
        action="store_true",
        help="Run as continuous daemon",
    )
    mode_group.add_argument(
        "--once",
        action="store_true",
        help="Run single sync cycle and exit",
    )
    mode_group.add_argument(
        "--status",
        action="store_true",
        help="Show current sync status",
    )

    # Daemon options
    parser.add_argument(
        "--interval",
        type=int,
        default=get("ingestion", "sync", "sync_interval_seconds"),
        help="Sync interval in seconds for daemon mode",
    )
    parser.add_argument(
        "--pid-file",
        type=str,
        default="/tmp/procore-sync.pid",
        help="PID file for daemon (default: /tmp/procore-sync.pid)",
    )

    # Table selection
    parser.add_argument(
        "--tables",
        type=str,
        nargs="+",
        default=None,
        help="Specific tables to sync (default: all)",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="+",
        default=[],
        help="Tables to exclude from sync",
    )

    # Performance options
    parser.add_argument(
        "--batch-size",
        type=int,
        default=get("ingestion", "sync", "streaming_batch_size"),
        help="Records per batch",
    )

    # File processing options (enabled by default — use --no-* to disable)
    parser.add_argument(
        "--download-files",
        action="store_true",
        default=True,
        help="Download and index S3 files during sync (default: enabled)",
    )
    parser.add_argument(
        "--no-download-files",
        action="store_false",
        dest="download_files",
        help="Disable file downloading",
    )
    parser.add_argument(
        "--file-workers",
        type=int,
        default=get("ingestion", "files", "download_workers"),
        help="Parallel workers for file downloads",
    )
    parser.add_argument(
        "--process-pdfs",
        action="store_true",
        default=True,
        help="Process downloaded PDFs with ColPali for visual retrieval (default: enabled)",
    )
    parser.add_argument(
        "--no-process-pdfs",
        action="store_false",
        dest="process_pdfs",
        help="Disable PDF processing with ColPali",
    )

    # Delete detection
    parser.add_argument(
        "--detect-deletes",
        action="store_true",
        help="Detect and remove records deleted from the source database",
    )
    parser.add_argument(
        "--delete-interval",
        type=int,
        default=10,
        help="In daemon mode, run delete detection every N cycles (default: 10, 0=every cycle)",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args()


class SyncDaemon:
    """Daemon for continuous database synchronization."""

    def __init__(
        self,
        sync_manager: SyncManager,
        sync_config: SyncConfig,
        interval: int,
        pid_file: Path,
        logger: logging.Logger,
    ):
        self._sync_manager = sync_manager
        self._sync_config = sync_config
        self._interval = interval
        self._pid_file = pid_file
        self._logger = logger
        self._running = False
        self._cycle_count = 0

    async def start(self):
        """Start the daemon."""
        self._running = True

        # Write PID file
        self._pid_file.write_text(str(os.getpid()))
        self._logger.info(f"Daemon started (PID: {os.getpid()})")

        # Set up signal handlers
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_shutdown)

        try:
            while self._running:
                try:
                    await self._run_sync_cycle()
                except Exception as e:
                    self._logger.error(f"Sync cycle failed: {e}")

                if self._running:
                    self._logger.info(f"Next sync in {self._interval} seconds")
                    await asyncio.sleep(self._interval)

        finally:
            self._cleanup()

    def _handle_shutdown(self):
        """Handle shutdown signal."""
        self._logger.info("Shutdown signal received")
        self._running = False

    def _cleanup(self):
        """Clean up on shutdown."""
        if self._pid_file.exists():
            self._pid_file.unlink()
        self._logger.info("Daemon stopped")

    async def _run_sync_cycle(self):
        """Run a single sync cycle."""
        self._cycle_count += 1
        self._logger.info(f"Starting sync cycle #{self._cycle_count}...")
        start_time = datetime.now(timezone.utc)

        # Determine if delete detection should run this cycle
        run_deletes = False
        if self._sync_config.detect_deletes:
            interval = self._sync_config.delete_detection_interval
            if interval == 0 or (self._cycle_count % interval == 0):
                run_deletes = True
                self._logger.info("Delete detection enabled for this cycle")

        result = await self._sync_manager.run_incremental_sync(
            self._sync_config, run_delete_detection=run_deletes,
        )

        duration = datetime.now(timezone.utc) - start_time

        # Build status message
        stats = [f"{result.records_processed} records"]
        if result.files_downloaded > 0:
            stats.append(f"{result.files_downloaded} files")
        if result.files_skipped > 0:
            stats.append(f"{result.files_skipped} skipped (unchanged)")
        if result.orphans_cleaned > 0:
            stats.append(f"{result.orphans_cleaned} orphans cleaned")
        if result.records_deleted > 0:
            stats.append(f"{result.records_deleted} deleted")
        if result.pdfs_processed > 0:
            stats.append(f"{result.pdfs_processed} PDFs ({result.pdf_pages_indexed} pages)")

        self._logger.info(
            f"Sync cycle #{self._cycle_count} completed: {', '.join(stats)} "
            f"in {duration.total_seconds():.1f}s"
        )

        return result


async def print_status(
    sync_manager: SyncManager,
    logger: logging.Logger,
):
    """Print current sync status."""
    status = await sync_manager.get_status()

    print("\nSync Status Report")
    print("=" * 60)
    print(f"Tables monitored: {status['tables_monitored']}")
    print(f"Total records: {status['total_records']:,}")
    print(f"Total failed: {status['total_failed']:,}")

    if status.get("current_job"):
        print(f"Current job: {status['current_job']}")

    print("\nTable Status:")
    for table_name, table_status in sorted(status.get("tables", {}).items()):
        sync_time = table_status.get("last_sync", "never")
        records = table_status.get("records_processed", 0)
        status_str = table_status.get("status", "unknown")
        print(f"  {table_name:30} : {status_str:10} ({records:,} records, last: {sync_time})")

    print("=" * 60)


class MockVespaApp:
    """Mock Vespa app when real one is not available (matches pyvespa sync API)."""

    url = "http://localhost:8080"

    def feed_data_point(self, schema: str, data_id: str, fields: dict):
        pass

    def delete_data(self, schema: str, data_id: str):
        pass

    def get_data(self, schema: str, data_id: str):
        return {"fields": {}}

    def query(self, **kwargs):
        return {"root": {"children": []}}


async def main() -> int:
    """Main entry point."""
    args = parse_args()
    logger = setup_logging(args.verbose)

    # Validate database URL for daemon/once modes
    if not args.status and not args.database_url:
        logger.error(
            "Database URL not provided. Set PROCORE_DATABASE_URL environment variable "
            "or use --database-url argument."
        )
        return 1

    # process-pdfs requires download-files — auto-disable if files are off
    if args.process_pdfs and not args.download_files:
        args.process_pdfs = False

    try:
        # Initialize checkpoint store (needed for all modes)
        checkpoint_path = Path("data/sync_checkpoints.db")
        checkpoint_store = CheckpointStore(checkpoint_path, logger)
        await checkpoint_store.initialize()

        if args.status:
            # Status mode - just need checkpoint store
            # Create minimal sync manager for status
            if args.database_url:
                config = ConnectionConfig.from_url(args.database_url)
                db = DatabaseConnection(config, logger)
                await db.connect()

                try:
                    discovery = SchemaDiscovery(db, logger)
                    schema_map = await discovery.discover()

                    vespa_app = MockVespaApp()
                    sync_manager = SyncManager(
                        db=db,
                        vespa_app=vespa_app,
                        schema_map=schema_map,
                        checkpoint_store=checkpoint_store,
                        logger=logger,
                    )

                    await print_status(sync_manager, logger)
                finally:
                    await db.close()
            else:
                # Just show checkpoint status without database
                checkpoints = await checkpoint_store.get_all()
                print("\nSync Status (from checkpoints)")
                print("=" * 60)
                for cp in checkpoints:
                    print(f"  {cp.table_name:30} : {cp.sync_status:10} "
                          f"(last: {cp.last_sync_timestamp})")
                print("=" * 60)

            return 0

        # Connect to database
        config = ConnectionConfig.from_url(args.database_url)
        logger.info(f"Connecting to {config.database} at {config.host}...")

        db = DatabaseConnection(config, logger)
        await db.connect()

        try:
            # Discover schema
            logger.info("Discovering database schema...")
            discovery = SchemaDiscovery(db, logger)
            schema_map = await discovery.discover()
            logger.info(f"Schema loaded: {len(schema_map.tables)} tables")

            # Set up Vespa client
            from vespa.application import Vespa
            logger.info(f"Connecting to Vespa at {args.vespa_url}...")
            vespa_app = Vespa(url=args.vespa_url)
            vespa_app.wait_for_application_up(max_wait=60)
            logger.info("Connected to Vespa")

            # Initialize PDF processor if enabled
            pdf_processor = None
            if args.process_pdfs:
                from backend.ingestion.pdf_processor import PDFProcessor
                logger.info("Initializing PDF processor (model loads on first PDF)...")
                pdf_processor = PDFProcessor(
                    vespa_app=vespa_app,
                    logger=logger,
                )

            # Create sync manager
            sync_manager = SyncManager(
                db=db,
                vespa_app=vespa_app,
                schema_map=schema_map,
                checkpoint_store=checkpoint_store,
                logger=logger,
                pdf_processor=pdf_processor,
            )

            # Build sync config
            sync_config = SyncConfig(
                tables=args.tables,
                exclude_tables=args.exclude,
                batch_size=args.batch_size,
                download_files=args.download_files,
                file_workers=args.file_workers,
                process_pdfs=args.process_pdfs,
                detect_deletes=args.detect_deletes,
                delete_detection_interval=args.delete_interval,
            )

            if args.daemon:
                # Run daemon
                daemon = SyncDaemon(
                    sync_manager=sync_manager,
                    sync_config=sync_config,
                    interval=args.interval,
                    pid_file=Path(args.pid_file),
                    logger=logger,
                )
                await daemon.start()
                return 0

            elif args.once:
                # Run single sync cycle
                result = await sync_manager.run_incremental_sync(
                    sync_config,
                    run_delete_detection=args.detect_deletes,
                )

                logger.info("=" * 60)
                logger.info(f"Sync completed: {result.status}")
                logger.info(f"Records processed: {result.records_processed:,}")
                logger.info(f"Records failed: {result.records_failed:,}")
                if result.files_downloaded > 0 or result.files_skipped > 0:
                    logger.info(f"Files downloaded: {result.files_downloaded:,}")
                    logger.info(f"Files skipped (unchanged): {result.files_skipped:,}")
                    logger.info(f"Files failed: {result.files_failed:,}")
                if result.orphans_cleaned > 0:
                    logger.info(f"Orphaned pdf_pages cleaned: {result.orphans_cleaned:,}")
                if result.records_deleted > 0:
                    logger.info(f"Records deleted: {result.records_deleted:,}")
                if result.pdfs_processed > 0 or result.pdfs_failed > 0:
                    logger.info(f"PDFs processed: {result.pdfs_processed:,}")
                    logger.info(f"PDFs failed: {result.pdfs_failed:,}")
                    logger.info(f"PDF pages indexed: {result.pdf_pages_indexed:,}")
                logger.info("=" * 60)

                if result.errors:
                    for error in result.errors[:5]:
                        logger.warning(f"  {error}")

                return 0 if result.status == "COMPLETED" else 1

        finally:
            await db.close()

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
