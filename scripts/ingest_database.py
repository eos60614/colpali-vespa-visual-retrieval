#!/usr/bin/env python3
"""
Database Ingestion CLI

Ingest Procore database records into Vespa for search.
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from tqdm import tqdm

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
        description="Ingest Procore database records into Vespa.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full ingestion of all tables
  python scripts/ingest_database.py --full

  # Specific tables only
  python scripts/ingest_database.py --full --tables photos drawings projects

  # Exclude system tables
  python scripts/ingest_database.py --full --exclude _prisma_migrations sync_events

  # Incremental ingestion (since last checkpoint)
  python scripts/ingest_database.py --incremental

  # Dry run
  python scripts/ingest_database.py --full --dry-run
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
        default=os.environ.get("VESPA_LOCAL_URL", "http://localhost:8080"),
        help="Vespa endpoint URL (default: $VESPA_LOCAL_URL or localhost:8080)",
    )

    # Mode selection
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--full",
        action="store_true",
        help="Run full ingestion of all records",
    )
    mode_group.add_argument(
        "--incremental",
        action="store_true",
        help="Run incremental ingestion from last checkpoint",
    )
    mode_group.add_argument(
        "--resume",
        type=str,
        metavar="JOB_ID",
        help="Resume a specific job by ID",
    )

    # Table selection
    parser.add_argument(
        "--tables",
        type=str,
        nargs="+",
        default=None,
        help="Specific tables to ingest (default: all)",
    )
    parser.add_argument(
        "--exclude",
        type=str,
        nargs="+",
        default=[],
        help="Tables to exclude from ingestion",
    )

    # Performance options
    parser.add_argument(
        "--batch-size",
        type=int,
        default=10000,
        help="Records per batch (default: 10000)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=4,
        help="Parallel workers for Vespa feeding (default: 4)",
    )

    # File options
    parser.add_argument(
        "--download-files",
        action="store_true",
        help="Download and index S3 files",
    )
    parser.add_argument(
        "--file-workers",
        type=int,
        default=2,
        help="Parallel workers for file downloads (default: 2)",
    )

    # Other options
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be ingested without doing it",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )
    parser.add_argument(
        "--progress",
        action="store_true",
        default=True,
        help="Show progress bar (default: true)",
    )

    return parser.parse_args()


class MockVespaApp:
    """Mock Vespa app for dry-run mode."""

    async def feed_data_point(self, schema: str, data_id: str, fields: dict):
        pass

    async def delete_data(self, schema: str, data_id: str):
        pass


async def main() -> int:
    """Main entry point."""
    args = parse_args()
    logger = setup_logging(args.verbose)

    # Validate database URL
    if not args.database_url:
        logger.error(
            "Database URL not provided. Set PROCORE_DATABASE_URL environment variable "
            "or use --database-url argument."
        )
        return 1

    start_time = datetime.utcnow()

    try:
        # Parse connection config
        config = ConnectionConfig.from_url(args.database_url)
        logger.info(f"Connecting to {config.database} at {config.host}...")

        # Connect to database
        db = DatabaseConnection(config, logger)
        await db.connect()

        try:
            # Perform schema discovery first
            logger.info("Discovering database schema...")
            discovery = SchemaDiscovery(db, logger)
            schema_map = await discovery.discover()
            logger.info(f"Schema loaded: {len(schema_map.tables)} tables")

            # Initialize checkpoint store
            checkpoint_path = Path("data/sync_checkpoints.db")
            checkpoint_store = CheckpointStore(checkpoint_path, logger)
            await checkpoint_store.initialize()

            # Set up Vespa client
            if args.dry_run:
                logger.info("DRY RUN MODE - No data will be indexed")
                vespa_app = MockVespaApp()
            else:
                # Import actual Vespa app
                try:
                    from backend.vespa_app import vespa_app
                except ImportError:
                    logger.warning(
                        "Could not import vespa_app, using mock client. "
                        "Ensure Vespa is configured."
                    )
                    vespa_app = MockVespaApp()

            # Create sync manager
            sync_manager = SyncManager(
                db=db,
                vespa_app=vespa_app,
                schema_map=schema_map,
                checkpoint_store=checkpoint_store,
                logger=logger,
            )

            # Build sync config
            sync_config = SyncConfig(
                tables=args.tables,
                exclude_tables=args.exclude,
                batch_size=args.batch_size,
                download_files=args.download_files,
                file_workers=args.file_workers,
            )

            # Get tables to process
            tables = sync_manager.get_tables_to_sync(sync_config)
            logger.info(
                f"Tables to process: {len(tables)} "
                f"(excluding: {', '.join(sync_config.exclude_tables) or 'none'})"
            )

            if args.dry_run:
                # Just show what would be done
                logger.info("\nDry run - Tables that would be processed:")
                for table in tables:
                    table_info = next(
                        (t for t in schema_map.tables if t.name == table), None
                    )
                    if table_info:
                        logger.info(f"  {table}: {table_info.row_count:,} records")
                return 0

            # Run the appropriate sync mode
            if args.full:
                logger.info("Starting full ingestion...")
                result = await sync_manager.run_full_sync(sync_config)
            elif args.incremental:
                logger.info("Starting incremental ingestion...")
                result = await sync_manager.run_incremental_sync(sync_config)
            elif args.resume:
                logger.error("Resume functionality not yet implemented")
                return 1

            # Print results
            end_time = datetime.utcnow()
            duration = end_time - start_time

            logger.info("=" * 60)
            logger.info(f"Job ID: {result.job_id}")
            logger.info(f"Status: {result.status}")
            logger.info(f"Tables processed: {result.tables_processed}")
            logger.info(f"Records indexed: {result.records_processed:,}")
            logger.info(f"Records failed: {result.records_failed:,}")
            if result.files_downloaded > 0:
                logger.info(f"Files downloaded: {result.files_downloaded:,}")
                logger.info(f"Files failed: {result.files_failed:,}")
            logger.info(f"Duration: {duration}")
            logger.info("=" * 60)

            if result.errors:
                logger.warning(f"Errors encountered ({len(result.errors)}):")
                for error in result.errors[:10]:
                    logger.warning(f"  {error}")
                if len(result.errors) > 10:
                    logger.warning(f"  ... and {len(result.errors) - 10} more")

            # Return appropriate exit code
            if result.status == "COMPLETED":
                return 0
            elif result.status == "COMPLETED_WITH_ERRORS":
                return 3
            else:
                return 4

        finally:
            await db.close()

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Ingestion failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 4


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
