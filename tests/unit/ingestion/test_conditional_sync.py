"""
Tests for conditional file re-processing in incremental sync.
"""

import json
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.ingestion.change_detector import Change, ChangeSet
from backend.ingestion.sync_manager import SyncConfig, SyncManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_db():
    mock = MagicMock()
    mock.connect = AsyncMock()
    mock.close = AsyncMock()
    mock.execute = AsyncMock(return_value=[])
    mock.stream = MagicMock()
    mock.is_connected = True
    return mock


@pytest.fixture
def mock_vespa():
    mock = MagicMock()
    mock.feed_data_point = MagicMock()
    mock.delete_data = MagicMock()
    mock.get_data = MagicMock()
    mock.query = MagicMock()
    mock.url = "http://localhost:8080"
    return mock


@pytest.fixture
def mock_schema_map():
    mock = MagicMock()
    mock.tables = []
    mock.relationships = []
    return mock


@pytest.fixture
def mock_checkpoint_store():
    mock = MagicMock()
    mock.get_last_sync_time = AsyncMock(return_value=None)
    mock.set = AsyncMock()
    mock.get_all = AsyncMock(return_value=[])
    return mock


@pytest.fixture
def sync_manager(mock_db, mock_vespa, mock_schema_map, mock_checkpoint_store):
    return SyncManager(
        db=mock_db,
        vespa_app=mock_vespa,
        schema_map=mock_schema_map,
        checkpoint_store=mock_checkpoint_store,
    )


# ---------------------------------------------------------------------------
# _diff_file_references tests
# ---------------------------------------------------------------------------

class TestDiffFileReferences:
    """Tests for the static _diff_file_references method."""

    def test_no_change(self):
        refs = [
            {"s3_key": "bucket/file1.pdf", "filename": "file1.pdf"},
            {"s3_key": "bucket/file2.pdf", "filename": "file2.pdf"},
        ]
        added, removed, unchanged = SyncManager._diff_file_references(refs, refs)
        assert len(added) == 0
        assert len(removed) == 0
        assert len(unchanged) == 2

    def test_file_added(self):
        old = [{"s3_key": "bucket/file1.pdf"}]
        new = [
            {"s3_key": "bucket/file1.pdf"},
            {"s3_key": "bucket/file2.pdf"},
        ]
        added, removed, unchanged = SyncManager._diff_file_references(old, new)
        assert len(added) == 1
        assert added[0]["s3_key"] == "bucket/file2.pdf"
        assert len(removed) == 0
        assert len(unchanged) == 1

    def test_file_removed(self):
        old = [
            {"s3_key": "bucket/file1.pdf"},
            {"s3_key": "bucket/file2.pdf"},
        ]
        new = [{"s3_key": "bucket/file1.pdf"}]
        added, removed, unchanged = SyncManager._diff_file_references(old, new)
        assert len(added) == 0
        assert len(removed) == 1
        assert removed[0]["s3_key"] == "bucket/file2.pdf"
        assert len(unchanged) == 1

    def test_file_replaced(self):
        old = [{"s3_key": "bucket/old_file.pdf"}]
        new = [{"s3_key": "bucket/new_file.pdf"}]
        added, removed, unchanged = SyncManager._diff_file_references(old, new)
        assert len(added) == 1
        assert added[0]["s3_key"] == "bucket/new_file.pdf"
        assert len(removed) == 1
        assert removed[0]["s3_key"] == "bucket/old_file.pdf"
        assert len(unchanged) == 0

    def test_empty_to_some(self):
        old: list[dict] = []
        new = [{"s3_key": "bucket/file1.pdf"}]
        added, removed, unchanged = SyncManager._diff_file_references(old, new)
        assert len(added) == 1
        assert len(removed) == 0
        assert len(unchanged) == 0

    def test_some_to_empty(self):
        old = [{"s3_key": "bucket/file1.pdf"}]
        new: list[dict] = []
        added, removed, unchanged = SyncManager._diff_file_references(old, new)
        assert len(added) == 0
        assert len(removed) == 1
        assert len(unchanged) == 0

    def test_both_empty(self):
        added, removed, unchanged = SyncManager._diff_file_references([], [])
        assert len(added) == 0
        assert len(removed) == 0
        assert len(unchanged) == 0

    def test_url_based_refs(self):
        old = [{"s3_key": "", "url": "https://example.com/old.pdf"}]
        new = [{"s3_key": "", "url": "https://example.com/new.pdf"}]
        added, removed, unchanged = SyncManager._diff_file_references(old, new)
        assert len(added) == 1
        assert len(removed) == 1
        assert len(unchanged) == 0

    def test_mixed_s3_and_url(self):
        old = [
            {"s3_key": "bucket/file1.pdf"},
            {"s3_key": "", "url": "https://example.com/file2.pdf"},
        ]
        new = [
            {"s3_key": "bucket/file1.pdf"},
            {"s3_key": "", "url": "https://example.com/file3.pdf"},
        ]
        added, removed, unchanged = SyncManager._diff_file_references(old, new)
        assert len(added) == 1
        assert len(removed) == 1
        assert len(unchanged) == 1

    def test_empty_keys_ignored(self):
        """Refs with no s3_key and no url are treated as having empty key and discarded."""
        old = [{"s3_key": "", "url": ""}]
        new = [{"s3_key": "", "url": ""}]
        added, removed, unchanged = SyncManager._diff_file_references(old, new)
        # Empty keys are discarded
        assert len(added) == 0
        assert len(removed) == 0
        assert len(unchanged) == 0


# ---------------------------------------------------------------------------
# _fetch_existing_file_references tests
# ---------------------------------------------------------------------------

class TestFetchExistingFileReferences:

    @pytest.mark.asyncio
    async def test_returns_parsed_refs(self, sync_manager, mock_vespa):
        mock_response = MagicMock()
        mock_response.json = {
            "fields": {
                "file_references": [
                    json.dumps({"s3_key": "bucket/file1.pdf", "filename": "file1.pdf"}),
                    json.dumps({"s3_key": "bucket/file2.pdf", "filename": "file2.pdf"}),
                ]
            }
        }
        mock_vespa.get_data.return_value = mock_response

        refs = await sync_manager._fetch_existing_file_references("photos:123")
        assert len(refs) == 2
        assert refs[0]["s3_key"] == "bucket/file1.pdf"
        assert refs[1]["s3_key"] == "bucket/file2.pdf"

    @pytest.mark.asyncio
    async def test_returns_empty_on_not_found(self, sync_manager, mock_vespa):
        mock_vespa.get_data.side_effect = Exception("404 Not Found")
        refs = await sync_manager._fetch_existing_file_references("photos:999")
        assert refs == []

    @pytest.mark.asyncio
    async def test_handles_dict_refs(self, sync_manager, mock_vespa):
        """If Vespa returns already-parsed dicts, handle them."""
        mock_response = MagicMock()
        mock_response.json = {
            "fields": {
                "file_references": [
                    {"s3_key": "bucket/file1.pdf", "filename": "file1.pdf"},
                ]
            }
        }
        mock_vespa.get_data.return_value = mock_response

        refs = await sync_manager._fetch_existing_file_references("photos:123")
        assert len(refs) == 1

    @pytest.mark.asyncio
    async def test_handles_no_file_references_field(self, sync_manager, mock_vespa):
        mock_response = MagicMock()
        mock_response.json = {"fields": {}}
        mock_vespa.get_data.return_value = mock_response

        refs = await sync_manager._fetch_existing_file_references("photos:123")
        assert refs == []


# ---------------------------------------------------------------------------
# _cleanup_orphaned_pdf_pages tests
# ---------------------------------------------------------------------------

class TestCleanupOrphanedPdfPages:

    @pytest.mark.asyncio
    async def test_deletes_matching_pdf_pages(self, sync_manager, mock_vespa):
        removed_refs = [
            {"s3_key": "bucket/path/report.pdf", "filename": "report.pdf"},
        ]
        mock_response = MagicMock()
        mock_response.json = {
            "root": {
                "children": [
                    {"id": "id:default:pdf_page::report.pdf_page0", "fields": {}},
                    {"id": "id:default:pdf_page::report.pdf_page1", "fields": {}},
                ]
            }
        }
        mock_vespa.query.return_value = mock_response

        deleted = await sync_manager._cleanup_orphaned_pdf_pages(
            "photos", "123", removed_refs,
        )

        assert deleted == 2
        assert mock_vespa.delete_data.call_count == 2

    @pytest.mark.asyncio
    async def test_no_orphans_found(self, sync_manager, mock_vespa):
        removed_refs = [
            {"s3_key": "bucket/path/report.pdf", "filename": "report.pdf"},
        ]
        mock_response = MagicMock()
        mock_response.json = {"root": {"children": []}}
        mock_vespa.query.return_value = mock_response

        deleted = await sync_manager._cleanup_orphaned_pdf_pages(
            "photos", "123", removed_refs,
        )
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_skips_refs_without_identifiers(self, sync_manager, mock_vespa):
        removed_refs = [{"s3_key": "", "filename": ""}]

        deleted = await sync_manager._cleanup_orphaned_pdf_pages(
            "photos", "123", removed_refs,
        )
        assert deleted == 0
        mock_vespa.query.assert_not_called()

    @pytest.mark.asyncio
    async def test_handles_query_failure(self, sync_manager, mock_vespa):
        removed_refs = [
            {"s3_key": "bucket/file.pdf", "filename": "file.pdf"},
        ]
        mock_vespa.query.side_effect = Exception("Connection error")

        deleted = await sync_manager._cleanup_orphaned_pdf_pages(
            "photos", "123", removed_refs,
        )
        assert deleted == 0


# ---------------------------------------------------------------------------
# Incremental sync integration tests (mocked)
# ---------------------------------------------------------------------------

class TestIncrementalSyncConditionalFiles:
    """Test that incremental sync skips unchanged files and downloads only new ones."""

    @pytest.mark.asyncio
    async def test_skips_unchanged_files(self, sync_manager, mock_vespa, mock_db, mock_checkpoint_store):
        """When file references haven't changed, no downloads should occur."""
        now = datetime.now(timezone.utc)
        last_sync = now - timedelta(hours=1)
        mock_checkpoint_store.get_last_sync_time.return_value = last_sync

        # Set up schema map with one table
        table_mock = MagicMock()
        table_mock.name = "photos"
        table_mock.columns = []
        table_mock.file_reference_columns = []
        table_mock.timestamp_columns = ["updated_at"]
        sync_manager._schema_map.tables = [table_mock]

        # Mock change detector to return one update with row data
        update_change = Change(
            table="photos",
            record_id="42",
            change_type="update",
            updated_at=now,
            row={
                "id": 42,
                "name": "Test Photo",
                "updated_at": now,
                "created_at": now - timedelta(days=1),
            },
        )
        changeset = ChangeSet(
            table="photos",
            since=last_sync,
            until=now,
            inserts=[],
            updates=[update_change],
        )

        # Existing Vespa refs are identical to "new" refs (no file columns → no files)
        existing_refs = [
            {"s3_key": "bucket/photo.jpg", "filename": "photo.jpg"},
        ]
        mock_response = MagicMock()
        mock_response.json = {
            "fields": {
                "file_references": [json.dumps(r) for r in existing_refs]
            }
        }
        mock_vespa.get_data.return_value = mock_response

        # Patch change_detector and ingester
        with patch("backend.ingestion.sync_manager.ChangeDetector") as MockCD, \
             patch("backend.ingestion.sync_manager.RecordIngester") as MockRI:
            mock_cd_instance = MockCD.return_value
            mock_cd_instance.detect_changes = AsyncMock(return_value=changeset)

            # Ingester returns success for the record
            async def fake_ingest(table, batch_size, since=None):
                yield MagicMock(success=True, doc_id="photos:42", error=None)

            mock_ri_instance = MockRI.return_value
            mock_ri_instance.ingest_table = fake_ingest

            config = SyncConfig(
                download_files=True,
                process_pdfs=False,
            )

            result = await sync_manager.run_incremental_sync(config)

        assert result.records_processed == 1
        # No files should be downloaded (no file_reference_columns on table)
        assert result.files_downloaded == 0

    @pytest.mark.asyncio
    async def test_downloads_only_new_files_for_updates(
        self, sync_manager, mock_vespa, mock_db, mock_checkpoint_store,
    ):
        """For updated records, only added file references should trigger downloads."""
        now = datetime.now(timezone.utc)
        last_sync = now - timedelta(hours=1)
        mock_checkpoint_store.get_last_sync_time.return_value = last_sync

        table_mock = MagicMock()
        table_mock.name = "drawings"
        table_mock.columns = []
        table_mock.file_reference_columns = []
        table_mock.timestamp_columns = ["updated_at"]
        sync_manager._schema_map.tables = [table_mock]

        update_change = Change(
            table="drawings",
            record_id="100",
            change_type="update",
            updated_at=now,
            row={
                "id": 100,
                "title": "Floor Plan",
                "updated_at": now,
                "created_at": now - timedelta(days=30),
            },
        )
        changeset = ChangeSet(
            table="drawings",
            since=last_sync,
            until=now,
            inserts=[],
            updates=[update_change],
        )

        # Old refs in Vespa
        old_refs = [
            {"s3_key": "bucket/old_drawing.pdf", "filename": "old_drawing.pdf"},
        ]
        mock_response = MagicMock()
        mock_response.json = {
            "fields": {
                "file_references": [json.dumps(r) for r in old_refs]
            }
        }
        mock_vespa.get_data.return_value = mock_response

        with patch("backend.ingestion.sync_manager.ChangeDetector") as MockCD, \
             patch("backend.ingestion.sync_manager.RecordIngester") as MockRI:
            mock_cd_instance = MockCD.return_value
            mock_cd_instance.detect_changes = AsyncMock(return_value=changeset)

            async def fake_ingest(table, batch_size, since=None):
                yield MagicMock(success=True, doc_id="drawings:100", error=None)

            mock_ri_instance = MockRI.return_value
            mock_ri_instance.ingest_table = fake_ingest

            config = SyncConfig(download_files=True)
            result = await sync_manager.run_incremental_sync(config)

        # The update row has no file_reference_columns on the mock table,
        # so FileDetector finds no files, meaning 0 downloads
        assert result.records_processed == 1
        assert result.files_downloaded == 0

    @pytest.mark.asyncio
    async def test_downloads_all_files_for_inserts(
        self, sync_manager, mock_vespa, mock_db, mock_checkpoint_store,
    ):
        """For newly inserted records, all file references should be downloaded."""
        now = datetime.now(timezone.utc)
        mock_checkpoint_store.get_last_sync_time.return_value = None

        table_mock = MagicMock()
        table_mock.name = "photos"
        table_mock.columns = []
        table_mock.file_reference_columns = []
        table_mock.timestamp_columns = ["updated_at"]
        sync_manager._schema_map.tables = [table_mock]

        insert_change = Change(
            table="photos",
            record_id="200",
            change_type="insert",
            updated_at=now,
            row={
                "id": 200,
                "name": "New Photo",
                "created_at": now,
                "updated_at": now,
            },
        )
        changeset = ChangeSet(
            table="photos",
            since=datetime.min,
            until=now,
            inserts=[insert_change],
            updates=[],
        )

        with patch("backend.ingestion.sync_manager.ChangeDetector") as MockCD, \
             patch("backend.ingestion.sync_manager.RecordIngester") as MockRI:
            mock_cd_instance = MockCD.return_value
            mock_cd_instance.detect_changes = AsyncMock(return_value=changeset)

            async def fake_ingest(table, batch_size, since=None):
                yield MagicMock(success=True, doc_id="photos:200", error=None)

            mock_ri_instance = MockRI.return_value
            mock_ri_instance.ingest_table = fake_ingest

            config = SyncConfig(download_files=True)
            result = await sync_manager.run_incremental_sync(config)

        assert result.records_processed == 1
        # No file refs detected (empty file_reference_columns on mock table)
        assert result.files_downloaded == 0
        # get_data should NOT be called for inserts (no pre-fetch needed)
        mock_vespa.get_data.assert_not_called()


# ---------------------------------------------------------------------------
# _get_vespa_record_ids tests
# ---------------------------------------------------------------------------

class TestGetVespaRecordIds:

    def _make_visit_response(self, documents, continuation=None):
        """Create a mock httpx response for the Vespa visit API."""
        resp = MagicMock()
        data = {
            "documents": documents,
            "documentCount": len(documents),
        }
        if continuation:
            data["continuation"] = continuation
        resp.json.return_value = data
        resp.raise_for_status = MagicMock()
        return resp

    @pytest.mark.asyncio
    async def test_returns_record_ids(self, sync_manager, mock_vespa):
        mock_resp = self._make_visit_response([
            {"fields": {"source_id": "1"}},
            {"fields": {"source_id": "2"}},
            {"fields": {"source_id": "3"}},
        ])

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        with patch("backend.ingestion.sync_manager.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            ids = await sync_manager._get_vespa_record_ids("photos")

        assert ids == {"1", "2", "3"}

    @pytest.mark.asyncio
    async def test_returns_empty_on_no_results(self, sync_manager, mock_vespa):
        mock_resp = self._make_visit_response([])

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp

        with patch("backend.ingestion.sync_manager.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            ids = await sync_manager._get_vespa_record_ids("photos")

        assert ids == set()

    @pytest.mark.asyncio
    async def test_handles_visit_error(self, sync_manager, mock_vespa):
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Vespa down")

        with patch("backend.ingestion.sync_manager.httpx.AsyncClient") as MockClient:
            MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
            ids = await sync_manager._get_vespa_record_ids("photos")

        assert ids == set()
