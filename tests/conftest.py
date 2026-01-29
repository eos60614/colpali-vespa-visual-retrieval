"""
Shared test fixtures for the colpali-procore test suite.
"""

import asyncio
import os
from pathlib import Path
from typing import Generator
from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create an event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_data_dir(tmp_path: Path) -> Path:
    """Provide a temporary directory for test data."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return data_dir


@pytest.fixture
def mock_db_connection() -> MagicMock:
    """Create a mock database connection."""
    mock = MagicMock()
    mock.connect = AsyncMock()
    mock.close = AsyncMock()
    mock.execute = AsyncMock(return_value=[])
    mock.is_connected = True
    return mock


@pytest.fixture
def mock_vespa_client() -> MagicMock:
    """Create a mock Vespa client."""
    mock = MagicMock()
    mock.feed_data_point = AsyncMock()
    mock.delete_data = AsyncMock()
    mock.query = AsyncMock(return_value={"root": {"children": []}})
    return mock


@pytest.fixture
def sample_table_columns() -> list[dict]:
    """Sample column data for testing schema discovery."""
    return [
        {
            "column_name": "id",
            "data_type": "bigint",
            "is_nullable": "NO",
            "column_default": None,
            "character_maximum_length": None,
        },
        {
            "column_name": "project_id",
            "data_type": "bigint",
            "is_nullable": "YES",
            "column_default": None,
            "character_maximum_length": None,
        },
        {
            "column_name": "name",
            "data_type": "text",
            "is_nullable": "YES",
            "column_default": None,
            "character_maximum_length": None,
        },
        {
            "column_name": "s3_key",
            "data_type": "text",
            "is_nullable": "YES",
            "column_default": None,
            "character_maximum_length": None,
        },
        {
            "column_name": "attachment_s3_keys",
            "data_type": "jsonb",
            "is_nullable": "YES",
            "column_default": None,
            "character_maximum_length": None,
        },
        {
            "column_name": "created_at",
            "data_type": "timestamp without time zone",
            "is_nullable": "YES",
            "column_default": None,
            "character_maximum_length": None,
        },
        {
            "column_name": "updated_at",
            "data_type": "timestamp without time zone",
            "is_nullable": "YES",
            "column_default": None,
            "character_maximum_length": None,
        },
    ]


@pytest.fixture
def sample_record() -> dict:
    """Sample database record for testing transformations."""
    return {
        "id": 562950208716653,
        "project_id": 562949954923622,
        "name": "Test Photo",
        "description": "HVAC unit installation",
        "location": "Building A, Floor 2",
        "s3_key": "562949953425831/562949954923622/photos/562950208716653/IMG_1128.jpg",
        "url": "https://storage.procore.com/api/v5/files/...",
        "created_at": "2024-03-15T10:35:00",
        "updated_at": "2024-03-15T10:35:00",
    }


@pytest.fixture
def sample_jsonb_attachments() -> dict:
    """Sample JSONB attachments for testing file detection."""
    return {
        "562951022152066": "562949953425831/562949954229558/change_orders/562949956208422/EOS_CO11.pdf",
        "562951023918286": "562949953425831/562949954229558/change_orders/562949956208422/another_file.pdf",
    }


@pytest.fixture
def database_url() -> str:
    """Get database URL from environment or return test default."""
    return os.environ.get(
        "PROCORE_DATABASE_URL",
        "postgresql://testuser:testpass@localhost:5432/testdb",
    )


@pytest.fixture
def vespa_url() -> str:
    """Get Vespa URL from environment or return test default."""
    return os.environ.get("VESPA_LOCAL_URL", "http://localhost:8080")
