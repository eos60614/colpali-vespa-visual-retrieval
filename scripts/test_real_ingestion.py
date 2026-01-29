#!/usr/bin/env python3
"""
Test script to verify ingestion with real Procore database.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

from backend.ingestion.db_connection import ConnectionConfig, DatabaseConnection  # noqa: E402
from backend.ingestion.schema_discovery import SchemaDiscovery  # noqa: E402
from backend.ingestion.record_ingester import RecordIngester  # noqa: E402


class MockVespaApp:
    """Mock Vespa app for testing (prints instead of actually indexing)."""

    def __init__(self):
        self.documents = []

    async def feed_data_point(self, schema: str, data_id: str, fields: dict):
        self.documents.append({
            "schema": schema,
            "data_id": data_id,
            "fields": fields,
        })


async def main():
    print("\n" + "=" * 70)
    print(" REAL DATABASE INGESTION TEST")
    print("=" * 70)

    # Get database URL
    db_url = os.environ.get("PROCORE_DATABASE_URL")
    if not db_url:
        print("ERROR: PROCORE_DATABASE_URL not set")
        return 1

    print("\nConnecting to database...")

    # Parse connection config
    config = ConnectionConfig.from_url(db_url)
    print(f"  Host: {config.host}")
    print(f"  Database: {config.database}")
    print(f"  User: {config.user}")

    # Connect to database
    db = DatabaseConnection(config)
    try:
        await db.connect()
        print("  ✓ Connected successfully!")
    except Exception as e:
        print(f"  ✗ Connection failed: {e}")
        return 1

    try:
        # Discover schema
        print("\n" + "-" * 70)
        print("Step 1: Schema Discovery")
        print("-" * 70)

        discovery = SchemaDiscovery(db)
        schema_map = await discovery.discover()

        print(f"\n  Database: {schema_map.database_name}")
        print(f"  Tables: {len(schema_map.tables)}")
        print(f"  Relationships: {len(schema_map.relationships)}")

        # Show top 5 tables by row count
        sorted_tables = sorted(schema_map.tables, key=lambda t: t.row_count, reverse=True)
        print("\n  Top 5 tables by row count:")
        for t in sorted_tables[:5]:
            file_refs = len(t.file_reference_columns)
            print(f"    - {t.name}: {t.row_count:,} rows" + (f" ({file_refs} file columns)" if file_refs else ""))

        # Test ingestion on a few tables
        print("\n" + "-" * 70)
        print("Step 2: Test Record Transformation")
        print("-" * 70)

        mock_vespa = MockVespaApp()
        ingester = RecordIngester(
            db=db,
            vespa_app=mock_vespa,
            schema_map=schema_map,
        )

        # Test tables to ingest (small samples)
        test_tables = ["projects", "photos", "change_orders"]

        for table_name in test_tables:
            table = next((t for t in schema_map.tables if t.name == table_name), None)
            if not table:
                print(f"\n  Skipping {table_name} (not found)")
                continue

            print(f"\n  Testing: {table_name} ({table.row_count:,} rows)")

            # Fetch 3 sample records
            query = f'SELECT * FROM "{table_name}" LIMIT 3'
            rows = await db.execute(query)

            for i, row in enumerate(rows):
                try:
                    record = ingester.transform_record(table_name, row)

                    print(f"\n    Record {i+1}: {record.doc_id}")
                    print(f"      table_description: {record.table_description or 'N/A'}")
                    print(f"      relationships: {len(record.relationships)}")

                    for rel in record.relationships[:2]:
                        print(f"        - {rel.relationship_type} -> {rel.target_doc_id} ({rel.direction})")

                    print(f"      file_references: {len(record.file_references)}")
                    for ref in record.file_references[:2]:
                        print(f"        - {ref.reference_type}: {ref.filename or ref.url or 'N/A'}")

                    print(f"      content_text: {record.content_text[:80]}..." if len(record.content_text) > 80 else f"      content_text: {record.content_text}")

                    # Test indexing
                    result = await ingester.index_record(record)
                    if result.success:
                        print("      ✓ Index simulation successful")
                    else:
                        print(f"      ✗ Index failed: {result.error}")

                except Exception as e:
                    print(f"    ✗ Transform failed: {e}")

        # Show sample indexed document
        print("\n" + "-" * 70)
        print("Step 3: Sample Indexed Document")
        print("-" * 70)

        if mock_vespa.documents:
            doc = mock_vespa.documents[0]
            fields = doc["fields"]

            print(f"\n  Schema: {doc['schema']}")
            print(f"  Doc ID: {doc['data_id']}")
            print("\n  Fields:")
            print(f"    source_table: {fields['source_table']}")
            print(f"    table_description: {fields.get('table_description', 'N/A')}")
            print(f"    relationships: {len(fields['relationships'])} items")
            print(f"    file_references: {len(fields['file_references'])} items")
            print(f"    incoming_relationships: {len(fields.get('incoming_relationships', []))} items")

            if fields['relationships']:
                print("\n  Sample relationship JSON:")
                rel = json.loads(fields['relationships'][0])
                print(f"    {json.dumps(rel, indent=4)}")

        print("\n" + "=" * 70)
        print(" TEST COMPLETED SUCCESSFULLY ✓")
        print("=" * 70)
        print(f"\n  Total documents indexed (mock): {len(mock_vespa.documents)}")
        print()

        return 0

    finally:
        await db.close()
        print("  Database connection closed.")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
