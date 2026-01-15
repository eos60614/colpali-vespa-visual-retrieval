"""
Pytest configuration and shared fixtures for the compliance testing suite.
"""

import pytest
import os
import tempfile
from pathlib import Path


@pytest.fixture
def temp_db():
    """Create a temporary SQLite database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def temp_evidence_dir():
    """Create a temporary directory for evidence storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_session_data():
    """Sample review session data for testing."""
    return {
        "submittal_id": "test-submittal-001",
        "project_id": "test-project-001",
        "spec_section_id": None,
    }


@pytest.fixture
def sample_requirement_data():
    """Sample requirement data for testing."""
    return {
        "text": "Provide voltage rating of 208V minimum",
        "lane": "AUTO_CHECK",
        "source_page": 1,
        "attribute_type": "voltage",
        "target_value": "208V",
    }


@pytest.fixture
def sample_compliance_result_data():
    """Sample compliance result data for testing."""
    return {
        "outcome": "PASS",
        "value_found": "208V",
        "confidence": 0.95,
        "submittal_page": 3,
    }
