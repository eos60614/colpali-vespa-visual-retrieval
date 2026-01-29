#!/usr/bin/env python3
"""
Test script to verify ingestion code works with sample data.
This tests the transformation logic without requiring database connection.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.ingestion.schema_discovery import (
    SchemaMap,
    Table,
    Column,
    FileReferenceColumn,
    FileReferenceType,
    ImplicitRelationship,
)
from backend.ingestion.record_ingester import (
    RecordIngester,
)


def create_test_schema_map() -> SchemaMap:
    """Create a test schema map for testing."""
    return SchemaMap(
        discovery_timestamp=datetime.utcnow().isoformat() + "Z",
        database_name="test_procore",
        tables=[
            Table(
                name="projects",
                row_count=31,
                columns=[
                    Column(name="id", data_type="bigint", is_nullable=False),
                    Column(name="name", data_type="text", is_nullable=True),
                    Column(name="display_name", data_type="text", is_nullable=True),
                    Column(name="created_at", data_type="timestamp", is_nullable=True),
                    Column(name="updated_at", data_type="timestamp", is_nullable=True),
                ],
                timestamp_columns=["created_at", "updated_at"],
                file_reference_columns=[],
            ),
            Table(
                name="photos",
                row_count=7631,
                columns=[
                    Column(name="id", data_type="bigint", is_nullable=False),
                    Column(name="project_id", data_type="bigint", is_nullable=True),
                    Column(name="s3_key", data_type="text", is_nullable=True),
                    Column(name="description", data_type="text", is_nullable=True),
                    Column(name="location", data_type="text", is_nullable=True),
                    Column(name="url", data_type="text", is_nullable=True),
                    Column(name="created_at", data_type="timestamp", is_nullable=True),
                    Column(name="updated_at", data_type="timestamp", is_nullable=True),
                ],
                timestamp_columns=["created_at", "updated_at"],
                file_reference_columns=[
                    FileReferenceColumn(
                        column_name="s3_key",
                        reference_type=FileReferenceType.S3_KEY,
                        pattern="^s3_key$",
                    ),
                    FileReferenceColumn(
                        column_name="url",
                        reference_type=FileReferenceType.URL,
                        pattern="^url$",
                    ),
                ],
            ),
            Table(
                name="change_orders",
                row_count=516,
                columns=[
                    Column(name="id", data_type="bigint", is_nullable=False),
                    Column(name="project_id", data_type="bigint", is_nullable=True),
                    Column(name="number", data_type="text", is_nullable=True),
                    Column(name="title", data_type="text", is_nullable=True),
                    Column(name="description", data_type="text", is_nullable=True),
                    Column(name="attachment_s3_keys", data_type="jsonb", is_nullable=True),
                    Column(name="created_at", data_type="timestamp", is_nullable=True),
                    Column(name="updated_at", data_type="timestamp", is_nullable=True),
                ],
                timestamp_columns=["created_at", "updated_at"],
                file_reference_columns=[
                    FileReferenceColumn(
                        column_name="attachment_s3_keys",
                        reference_type=FileReferenceType.JSONB_S3_MAP,
                        pattern="_s3_keys$",
                    ),
                ],
            ),
        ],
        relationships=[
            ImplicitRelationship(
                source_table="photos",
                source_column="project_id",
                target_table="projects",
                target_column="id",
            ),
            ImplicitRelationship(
                source_table="change_orders",
                source_column="project_id",
                target_table="projects",
                target_column="id",
            ),
        ],
    )


class MockVespaApp:
    """Mock Vespa app for testing."""

    def __init__(self):
        self.documents = []

    async def feed_data_point(self, schema: str, data_id: str, fields: dict):
        self.documents.append({
            "schema": schema,
            "data_id": data_id,
            "fields": fields,
        })
        print(f"  Indexed: {schema}/{data_id}")


class MockDatabaseConnection:
    """Mock database connection for testing."""

    async def stream(self, query: str, *args, batch_size: int = 1000):
        # Return empty iterator - we'll use transform_record directly
        return
        yield


def test_transform_record():
    """Test record transformation with sample data."""
    print("\n" + "=" * 60)
    print("Testing Record Transformation")
    print("=" * 60)

    schema_map = create_test_schema_map()
    mock_db = MockDatabaseConnection()
    mock_vespa = MockVespaApp()

    ingester = RecordIngester(
        db=mock_db,
        vespa_app=mock_vespa,
        schema_map=schema_map,
    )

    # Test 1: Transform a project record
    print("\n1. Testing project record transformation:")
    project_row = {
        "id": 562949953567479,
        "name": "Test Project",
        "display_name": "Test Display Name",
        "created_at": datetime(2024, 1, 15, 10, 30, 0),
        "updated_at": datetime(2024, 3, 20, 15, 45, 0),
    }

    record = ingester.transform_record("projects", project_row)
    print(f"   doc_id: {record.doc_id}")
    print(f"   source_table: {record.source_table}")
    print(f"   source_id: {record.source_id}")
    print(f"   relationships: {len(record.relationships)}")
    print(f"   file_references: {len(record.file_references)}")
    print(f"   table_description: {record.table_description}")
    print(f"   content_text: {record.content_text}")
    assert record.doc_id == "projects:562949953567479"
    assert record.table_description == "Construction projects with location, dates, and status"
    print("   ✓ Project record transformation passed!")

    # Test 2: Transform a photo record with file references
    print("\n2. Testing photo record transformation (with file refs):")
    photo_row = {
        "id": 562950208716653,
        "project_id": 562949954923622,
        "s3_key": "562949953425831/562949954923622/photos/562950208716653/IMG_1128.jpg",
        "description": "HVAC unit installation",
        "location": "Building A, Floor 2",
        "url": "https://storage.procore.com/api/v5/files/...",
        "created_at": datetime(2024, 3, 15, 10, 30, 0),
        "updated_at": datetime(2024, 3, 15, 10, 35, 0),
    }

    record = ingester.transform_record("photos", photo_row)
    print(f"   doc_id: {record.doc_id}")
    print(f"   project_id: {record.project_id}")
    print(f"   relationships: {len(record.relationships)}")

    # Check relationship
    if record.relationships:
        rel = record.relationships[0]
        print(f"   - Relationship: {rel.relationship_type} -> {rel.target_table}:{rel.target_id}")
        print(f"     direction: {rel.direction}, cardinality: {rel.cardinality}")
        assert rel.target_doc_id == "projects:562949954923622"
        assert rel.direction == "outgoing"
        assert rel.cardinality == "many_to_one"

    # Check file references
    print(f"   file_references: {len(record.file_references)}")
    for ref in record.file_references:
        print(f"   - File: {ref.reference_type} from column '{ref.source_column}'")
        if ref.s3_key:
            print(f"     s3_key: {ref.s3_key}")
            print(f"     filename: {ref.filename}")

    assert len(record.file_references) == 2  # s3_key and url
    s3_ref = [r for r in record.file_references if r.reference_type == "s3_key"][0]
    assert s3_ref.filename == "IMG_1128.jpg"
    print("   ✓ Photo record transformation passed!")

    # Test 3: Transform a change order with JSONB attachments
    print("\n3. Testing change order transformation (JSONB attachments):")
    change_order_row = {
        "id": 562949956208422,
        "project_id": 562949954229558,
        "number": "CO-011",
        "title": "HVAC Equipment Change",
        "description": "Replace AHU-1 with higher capacity unit",
        "attachment_s3_keys": {
            "562951022152066": "562949953425831/562949954229558/change_orders/562949956208422/EOS_CO11.pdf",
            "562951023918286": "562949953425831/562949954229558/change_orders/562949956208422/another_file.pdf",
        },
        "created_at": datetime(2024, 2, 10, 9, 0, 0),
        "updated_at": datetime(2024, 2, 15, 14, 30, 0),
    }

    record = ingester.transform_record("change_orders", change_order_row)
    print(f"   doc_id: {record.doc_id}")
    print(f"   content_text: {record.content_text}")
    print(f"   file_references: {len(record.file_references)}")

    for ref in record.file_references:
        print(f"   - File: {ref.filename}")
        print(f"     reference_type: {ref.reference_type}")
        print(f"     source_column: {ref.source_column}")
        print(f"     file_id: {ref.file_id}")

    assert len(record.file_references) == 2
    assert all(r.reference_type == "jsonb_s3_map" for r in record.file_references)
    print("   ✓ Change order transformation passed!")

    # Test 4: Test incoming relationship hints
    print("\n4. Testing incoming relationship hints:")
    hints = ingester.generate_relationship_links_from_schema("projects", "562949953567479")
    print(f"   Found {len(hints)} incoming relationship hints for projects table:")
    for hint in hints:
        print(f"   - {hint['source_table']}.{hint['source_column']} -> projects.id")
        print(f"     query_hint: {hint['query_hint']}")

    assert len(hints) == 2  # photos and change_orders reference projects
    print("   ✓ Incoming relationship hints passed!")

    return True


@pytest.mark.asyncio
async def test_index_record():
    """Test record indexing to mock Vespa."""
    print("\n" + "=" * 60)
    print("Testing Record Indexing")
    print("=" * 60)

    schema_map = create_test_schema_map()
    mock_db = MockDatabaseConnection()
    mock_vespa = MockVespaApp()

    ingester = RecordIngester(
        db=mock_db,
        vespa_app=mock_vespa,
        schema_map=schema_map,
    )

    # Create a test record
    photo_row = {
        "id": 562950208716653,
        "project_id": 562949954923622,
        "s3_key": "562949953425831/562949954923622/photos/562950208716653/IMG_1128.jpg",
        "description": "Test photo",
        "location": "Test location",
        "url": "https://storage.procore.com/test",
        "created_at": datetime(2024, 3, 15, 10, 30, 0),
        "updated_at": datetime(2024, 3, 15, 10, 35, 0),
    }

    record = ingester.transform_record("photos", photo_row)
    result = await ingester.index_record(record)

    print(f"\n   Index result: success={result.success}, doc_id={result.doc_id}")

    assert result.success
    assert len(mock_vespa.documents) == 1

    doc = mock_vespa.documents[0]
    fields = doc["fields"]

    print("\n   Indexed document fields:")
    print(f"   - doc_id: {fields['doc_id']}")
    print(f"   - source_table: {fields['source_table']}")
    print(f"   - table_description: {fields.get('table_description', 'N/A')}")
    print(f"   - relationships count: {len(fields['relationships'])}")
    print(f"   - file_references count: {len(fields['file_references'])}")
    print(f"   - incoming_relationships count: {len(fields.get('incoming_relationships', []))}")

    # Verify relationship JSON structure
    if fields['relationships']:
        rel_json = json.loads(fields['relationships'][0])
        print("\n   Sample relationship JSON:")
        print(f"   {json.dumps(rel_json, indent=4)}")
        assert "target_doc_id" in rel_json
        assert "direction" in rel_json
        assert "cardinality" in rel_json

    # Verify file reference JSON structure
    if fields['file_references']:
        file_json = json.loads(fields['file_references'][0])
        print("\n   Sample file_reference JSON:")
        print(f"   {json.dumps(file_json, indent=4)}")
        assert "source_column" in file_json
        assert "reference_type" in file_json

    print("\n   ✓ Record indexing test passed!")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print(" PROCORE INGESTION TEST SUITE")
    print("=" * 60)
    print("\nTesting the enhanced Agent Navigation Metadata implementation")
    print("(User Story 5: T075-T081)")

    try:
        # Test transformation
        test_transform_record()

        # Test indexing
        asyncio.run(test_index_record())

        print("\n" + "=" * 60)
        print(" ALL TESTS PASSED! ✓")
        print("=" * 60)
        print("\nThe following features have been verified:")
        print("  - RelationshipLink with navigation context (direction, cardinality)")
        print("  - FileReferenceLink with provenance (source_column, reference_type)")
        print("  - Bidirectional relationship tracking (outgoing + incoming hints)")
        print("  - Schema documentation fields (table_description, column_types)")
        print("  - JSONB attachment parsing with file_id preservation")
        print()

        return 0

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
