#!/usr/bin/env python3
"""
Ingest 5 random records from each table into Vespa.
"""

import asyncio
import os
import sys
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from backend.core.config import get, get_env  # noqa: E402
from backend.ingestion.database.db_connection import ConnectionConfig, DatabaseConnection  # noqa: E402
from backend.ingestion.database.schema_discovery import SchemaDiscovery  # noqa: E402
from backend.ingestion.database.record_ingester import RecordIngester  # noqa: E402


class SimpleVespaClient:
    """Simple async Vespa client for feeding documents."""

    def __init__(self, url: str = None):
        if url is None:
            url = get_env("VESPA_LOCAL_URL") or get("app", "default_vespa_url")
        self.url = url.rstrip("/")
        self.session = None

    async def connect(self):
        self.session = aiohttp.ClientSession()

    async def close(self):
        if self.session:
            await self.session.close()

    async def feed_data_point(self, schema: str, data_id: str, fields: dict):
        """Feed a single document to Vespa."""
        # Vespa document API endpoint
        url = f"{self.url}/document/v1/{schema}/{schema}/docid/{data_id}"

        # Prepare document
        doc = {"fields": fields}

        async with self.session.post(url, json=doc) as resp:
            if resp.status not in (200, 201):
                text = await resp.text()
                raise Exception(f"Vespa feed failed ({resp.status}): {text[:200]}")
            return await resp.json()


async def main():
    print("\n" + "=" * 70)
    print(" INGESTING 5 RANDOM RECORDS FROM EACH TABLE")
    print("=" * 70)

    db_url = os.environ.get("PROCORE_DATABASE_URL")
    if not db_url:
        print("ERROR: PROCORE_DATABASE_URL not set")
        return 1

    # Connect to database
    config = ConnectionConfig.from_url(db_url)
    db = DatabaseConnection(config)

    print("\nConnecting to database...")
    await db.connect()
    print("  ✓ Database connected")

    # Connect to Vespa
    vespa = SimpleVespaClient()
    await vespa.connect()
    print("  ✓ Vespa connected")

    try:
        # Discover schema
        print("\nDiscovering schema...")
        discovery = SchemaDiscovery(db)
        schema_map = await discovery.discover()
        print(f"  Found {len(schema_map.tables)} tables")

        # Create ingester
        ingester = RecordIngester(
            db=db,
            vespa_app=vespa,
            schema_map=schema_map,
        )

        # Tables to skip (system tables)
        skip_tables = {"_prisma_migrations", "sync_events", "webhook_events", "webhook_subscriptions"}

        total_ingested = 0
        total_failed = 0
        results_by_table = {}

        print("\n" + "-" * 70)
        print("Ingesting records...")
        print("-" * 70)

        for table in schema_map.tables:
            if table.name in skip_tables:
                print(f"\n  Skipping: {table.name} (system table)")
                continue

            if table.row_count == 0:
                print(f"\n  Skipping: {table.name} (empty)")
                continue

            print(f"\n  {table.name} ({table.row_count:,} rows)")

            try:
                # Fetch 5 random records
                # Use ORDER BY RANDOM() for true randomness
                limit = min(5, table.row_count)
                query = f'SELECT * FROM "{table.name}" ORDER BY RANDOM() LIMIT {limit}'
                rows = await db.execute(query)

                ingested = 0
                failed = 0

                for row in rows:
                    try:
                        record = ingester.transform_record(table.name, row)
                        result = await ingester.index_record(record)

                        if result.success:
                            ingested += 1
                            print(f"    ✓ {record.doc_id}")
                        else:
                            failed += 1
                            print(f"    ✗ {record.doc_id}: {result.error[:50]}")
                    except Exception as e:
                        failed += 1
                        print(f"    ✗ Error: {str(e)[:50]}")

                results_by_table[table.name] = {"ingested": ingested, "failed": failed}
                total_ingested += ingested
                total_failed += failed

            except Exception as e:
                print(f"    ✗ Table error: {str(e)[:60]}")
                results_by_table[table.name] = {"ingested": 0, "failed": 0, "error": str(e)}

        # Summary
        print("\n" + "=" * 70)
        print(" INGESTION SUMMARY")
        print("=" * 70)

        print(f"\n  Total records ingested: {total_ingested}")
        print(f"  Total records failed: {total_failed}")
        print(f"  Tables processed: {len(results_by_table)}")

        # Show tables with most records ingested
        print("\n  Records by table:")
        for table_name, stats in sorted(results_by_table.items(), key=lambda x: x[1].get("ingested", 0), reverse=True):
            if stats.get("ingested", 0) > 0:
                print(f"    {table_name}: {stats['ingested']} ingested")

        # Verify in Vespa
        print("\n" + "-" * 70)
        print("Verifying in Vespa...")
        print("-" * 70)

        async with aiohttp.ClientSession() as session:
            # Query total count
            vespa_base = get_env("VESPA_LOCAL_URL") or get("app", "default_vespa_url")
            procore_schema = get("vespa", "procore_record_schema")
            query_url = f"{vespa_base}/search/?yql=select%20*%20from%20{procore_schema}%20where%20true&hits=0"
            async with session.get(query_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    total = data.get("root", {}).get("fields", {}).get("totalCount", 0)
                    print(f"\n  Total documents in Vespa: {total}")

            # Sample query
            sample_url = f"{vespa_base}/search/?yql=select%20doc_id,source_table,table_description%20from%20{procore_schema}%20where%20true&hits=5"
            async with session.get(sample_url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    hits = data.get("root", {}).get("children", [])
                    if hits:
                        print("\n  Sample documents:")
                        for hit in hits[:5]:
                            fields = hit.get("fields", {})
                            print(f"    - {fields.get('doc_id')}: {fields.get('table_description', 'N/A')[:50]}")

        print("\n" + "=" * 70)
        print(" DONE ✓")
        print("=" * 70 + "\n")

        return 0

    finally:
        await vespa.close()
        await db.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
