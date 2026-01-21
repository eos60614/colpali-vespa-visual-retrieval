#!/usr/bin/env python3
"""
End-to-end integration test: Database file reference -> Download -> Ingest -> Verify in Vespa.

This test:
1. Connects to the Procore database
2. Finds a PDF file reference
3. Downloads it from S3
4. Ingests it using PDFProcessor
5. Verifies the document exists in Vespa with embeddings
"""

import asyncio
import os
import sys
import tempfile
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()


@pytest.fixture
def db_url():
    """Get database URL from environment."""
    url = os.environ.get("PROCORE_DATABASE_URL")
    if not url:
        pytest.skip("PROCORE_DATABASE_URL not set")
    return url


@pytest.fixture
def vespa_url():
    """Get Vespa URL from environment."""
    url = os.environ.get("VESPA_LOCAL_URL")
    if not url:
        pytest.skip("VESPA_LOCAL_URL not set")
    return url


@pytest.fixture
def s3_config():
    """Get S3 configuration from environment."""
    config = {
        "AWS_ACCESS_KEY_ID": os.environ.get("AWS_ACCESS_KEY_ID"),
        "AWS_SECRET_ACCESS_KEY": os.environ.get("AWS_SECRET_ACCESS_KEY"),
        "AWS_REGION": os.environ.get("AWS_REGION", "us-east-1"),
        "S3_BUCKET": os.environ.get("S3_BUCKET", "procore-integration-files"),
    }
    if not config["AWS_ACCESS_KEY_ID"] or not config["AWS_SECRET_ACCESS_KEY"]:
        pytest.skip("AWS credentials not set")
    return config


@pytest.mark.asyncio
async def test_e2e_file_ingestion(db_url, vespa_url, s3_config):
    """Test full pipeline: DB -> Download -> Ingest -> Verify in Vespa."""
    import asyncpg
    import logging
    from vespa.application import Vespa
    from backend.ingestion.file_detector import DetectedFile
    from backend.ingestion.file_downloader import FileDownloader, DownloadStrategy
    from backend.ingestion.pdf_processor import PDFProcessor

    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Step 1: Connect to database and find a PDF file reference
    logger.info("Step 1: Connecting to database to find PDF file...")
    conn = await asyncpg.connect(db_url)

    try:
        # Look for a table with s3_key column that contains PDF
        # Try drawing_revisions first (most likely to have PDFs)
        pdf_record = await conn.fetchrow("""
            SELECT
                id,
                s3_key,
                NULL as url,
                'drawing_revisions' as source_table
            FROM drawing_revisions
            WHERE s3_key IS NOT NULL
              AND s3_key LIKE '%.pdf'
            LIMIT 1
        """)

        if not pdf_record:
            # Try specification_section_revisions
            pdf_record = await conn.fetchrow("""
                SELECT
                    id,
                    s3_key,
                    NULL as url,
                    'specification_section_revisions' as source_table
                FROM specification_section_revisions
                WHERE s3_key IS NOT NULL
                  AND s3_key LIKE '%.pdf'
                LIMIT 1
            """)

        if not pdf_record:
            # Try submittal_attachments
            pdf_record = await conn.fetchrow("""
                SELECT
                    id,
                    s3_key,
                    NULL as url,
                    'submittal_attachments' as source_table
                FROM submittal_attachments
                WHERE s3_key IS NOT NULL
                  AND s3_key LIKE '%.pdf'
                LIMIT 1
            """)

        if not pdf_record:
            # Try change_orders with JSONB attachments
            pdf_record = await conn.fetchrow("""
                SELECT
                    id,
                    NULL as s3_key,
                    NULL as url,
                    'change_orders' as source_table,
                    attachment_s3_keys
                FROM change_orders
                WHERE attachment_s3_keys IS NOT NULL
                  AND jsonb_typeof(attachment_s3_keys) = 'object'
                LIMIT 1
            """)

        if not pdf_record:
            pytest.skip("No PDF file references found in database")

        logger.info(f"Found PDF in {pdf_record['source_table']}: id={pdf_record['id']}")

        # Extract S3 key
        s3_key = pdf_record.get("s3_key")
        if not s3_key and pdf_record.get("attachment_s3_keys"):
            # Get first key from JSONB map
            attachments = pdf_record["attachment_s3_keys"]
            if isinstance(attachments, dict):
                s3_key = next(iter(attachments.values()), None)

        if not s3_key:
            pytest.skip("Could not extract S3 key from record")

        logger.info(f"S3 key: {s3_key}")

    finally:
        await conn.close()

    # Step 2: Create DetectedFile and download
    logger.info("Step 2: Downloading file from S3...")

    detected_file = DetectedFile(
        s3_key=s3_key,
        source_table=pdf_record["source_table"],
        source_record_id=str(pdf_record["id"]),
        source_column="s3_key",
        filename=Path(s3_key).name if s3_key else None,
        file_size=None,
        url=pdf_record.get("url"),
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        downloader = FileDownloader(
            download_dir=Path(tmpdir),
            strategy=DownloadStrategy.DIRECT_S3,
            aws_config=s3_config,
            logger=logger,
        )

        result = await downloader.download(detected_file)

        if not result.success:
            pytest.fail(f"Download failed: {result.error}")

        logger.info(f"Downloaded to: {result.local_path} ({result.file_size} bytes)")

        # Step 3: Connect to Vespa and ingest
        logger.info("Step 3: Ingesting PDF to Vespa...")

        vespa_app = Vespa(url=vespa_url)
        vespa_app.wait_for_application_up()

        pdf_processor = PDFProcessor(
            vespa_app=vespa_app,
            logger=logger,
            batch_size=2,  # Small batch for testing
        )

        process_result = pdf_processor.process_pdf(detected_file, result.local_path)

        if not process_result.success:
            pytest.fail(f"PDF processing failed: {process_result.error}")

        logger.info(f"Indexed {process_result.pages_indexed} pages")

        # Step 4: Verify documents exist in Vespa
        logger.info("Step 4: Verifying documents in Vespa...")

        # Query for documents with matching source metadata
        # The document ID should contain the filename stem
        from vespa.io import VespaQueryResponse

        filename_stem = Path(detected_file.filename).stem if detected_file.filename else ""

        async with vespa_app.asyncio(connections=1) as session:
            response: VespaQueryResponse = await session.query(
                body={
                    "yql": f'select id, title, page_number, tags from pdf_page where url contains "{detected_file.filename}" limit 10',
                    "ranking": "unranked",
                }
            )

            assert response.is_successful(), f"Vespa query failed: {response.json}"

            results = response.json.get("root", {}).get("children", [])
            logger.info(f"Found {len(results)} documents in Vespa")

            # Verify we got at least one result
            assert len(results) > 0, "No documents found in Vespa after ingestion"

            # Verify the results have expected fields
            for doc in results:
                fields = doc.get("fields", {})
                assert "id" in fields, "Document missing id field"
                assert "page_number" in fields, "Document missing page_number field"
                logger.info(f"  - {fields['id']}: page {fields.get('page_number')}")

                # Verify tags include source metadata
                tags = fields.get("tags", [])
                assert detected_file.source_table in tags, f"Source table not in tags: {tags}"

        logger.info("SUCCESS: Full E2E pipeline verified!")


@pytest.mark.asyncio
async def test_vespa_document_has_embeddings(vespa_url):
    """Verify that ingested documents have embeddings."""
    from vespa.application import Vespa
    from vespa.io import VespaQueryResponse

    vespa_app = Vespa(url=vespa_url)
    vespa_app.wait_for_application_up()

    async with vespa_app.asyncio(connections=1) as session:
        # Query for any document with embeddings
        response: VespaQueryResponse = await session.query(
            body={
                "yql": "select id, embedding from pdf_page where true limit 1",
                "ranking": "unranked",
            }
        )

        assert response.is_successful(), f"Vespa query failed: {response.json}"

        results = response.json.get("root", {}).get("children", [])

        if not results:
            pytest.skip("No documents in Vespa to verify embeddings")

        # Check that embedding field exists and is non-empty
        doc = results[0]
        fields = doc.get("fields", {})
        embedding = fields.get("embedding")

        assert embedding is not None, "Document has no embedding"
        assert "blocks" in embedding or len(embedding) > 0, "Embedding is empty"

        print(f"Verified document {fields.get('id')} has embeddings")


if __name__ == "__main__":
    # Run as standalone script
    print("\n" + "=" * 60)
    print("E2E FILE INGESTION TEST")
    print("=" * 60)
    print("\nThis test requires:")
    print("  - PROCORE_DATABASE_URL: Connection to Procore database")
    print("  - VESPA_LOCAL_URL: Local Vespa instance (e.g., http://localhost:8080)")
    print("  - AWS credentials for S3 access")
    print()

    # Run with pytest
    sys.exit(pytest.main([__file__, "-v", "-s"]))
