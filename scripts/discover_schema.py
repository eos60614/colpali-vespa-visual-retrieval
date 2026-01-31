#!/usr/bin/env python3
"""
Schema Discovery CLI

Discover and document the Procore database schema.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.ingestion.database.db_connection import ConnectionConfig, DatabaseConnection
from backend.ingestion.database.schema_discovery import SchemaDiscovery


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
        description="Discover and document the Procore database schema.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic discovery to stdout
  python scripts/discover_schema.py

  # Export to JSON file
  python scripts/discover_schema.py --format json --output schema-map.json

  # Export to Markdown
  python scripts/discover_schema.py --format markdown --output schema-report.md

  # Export both formats
  python scripts/discover_schema.py --format both --output ./output/

  # Custom database URL
  python scripts/discover_schema.py --database-url "postgresql://user:pass@host:5432/db"
""",
    )

    parser.add_argument(
        "--database-url",
        type=str,
        default=os.environ.get("PROCORE_DATABASE_URL"),
        help="PostgreSQL connection string (default: $PROCORE_DATABASE_URL)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--format",
        "-f",
        type=str,
        choices=["json", "markdown", "both"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--include-samples",
        action="store_true",
        help="Include sample data (first 5 rows per table)",
    )
    parser.add_argument(
        "--include-stats",
        action="store_true",
        default=True,
        help="Include row counts and column statistics (default: true)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Verbose output",
    )

    return parser.parse_args()


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

    try:
        # Parse connection config
        config = ConnectionConfig.from_url(args.database_url)
        logger.info(f"Connecting to {config.database} at {config.host}...")

        # Connect to database
        db = DatabaseConnection(config, logger)
        await db.connect()

        try:
            # Perform schema discovery
            discovery = SchemaDiscovery(db, logger)
            schema_map = await discovery.discover(include_samples=args.include_samples)

            # Generate output
            if args.format == "json":
                output = discovery.to_json(schema_map)
                ext = ".json"
            elif args.format == "markdown":
                output = discovery.to_markdown(schema_map)
                ext = ".md"
            else:  # both
                json_output = discovery.to_json(schema_map)
                md_output = discovery.to_markdown(schema_map)

            # Write output
            if args.output:
                output_path = Path(args.output)

                if args.format == "both":
                    # Output is a directory
                    output_path.mkdir(parents=True, exist_ok=True)
                    json_path = output_path / "schema-map.json"
                    md_path = output_path / "schema-report.md"

                    json_path.write_text(json_output)
                    md_path.write_text(md_output)

                    logger.info(f"Schema map written to {json_path}")
                    logger.info(f"Schema report written to {md_path}")
                else:
                    # Ensure correct extension
                    if not output_path.suffix:
                        output_path = output_path.with_suffix(ext)

                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_text(output)
                    logger.info(f"Schema written to {output_path}")
            else:
                # Print to stdout
                if args.format == "both":
                    print("=== JSON ===")
                    print(json_output)
                    print("\n=== Markdown ===")
                    print(md_output)
                else:
                    print(output)

            # Print summary
            logger.info("=" * 60)
            logger.info("Schema discovery completed successfully")
            logger.info(f"  Tables discovered: {len(schema_map.tables)}")
            logger.info(f"  Relationships found: {len(schema_map.relationships)}")
            logger.info(
                f"  File reference columns: {schema_map.file_references_summary['total_columns']}"
            )
            logger.info("=" * 60)

            return 0

        finally:
            await db.close()

    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except Exception as e:
        logger.error(f"Schema discovery failed: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
