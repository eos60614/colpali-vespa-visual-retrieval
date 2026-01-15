"""
SQLite database setup and table creation for the compliance checking system.
Uses fastlite for database operations.
"""

import os
import sqlite3
from pathlib import Path
from datetime import datetime


def get_db_path() -> str:
    """Get the database path from environment or use default."""
    return os.environ.get("COMPLIANCE_DB_PATH", "data/compliance.db")


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Get a SQLite connection with row factory enabled."""
    path = db_path or get_db_path()
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | None = None) -> None:
    """Initialize all database tables."""
    conn = get_connection(db_path)
    cursor = conn.cursor()

    create_review_session_table(cursor)
    create_spec_match_suggestion_table(cursor)
    create_requirement_table(cursor)
    create_compliance_result_table(cursor)
    create_correction_table(cursor)
    create_indexes(cursor)

    conn.commit()
    conn.close()


def create_review_session_table(cursor: sqlite3.Cursor) -> None:
    """Create the review_session table for tracking compliance review workflows."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS review_session (
            id TEXT PRIMARY KEY,
            submittal_id TEXT NOT NULL,
            spec_section_id TEXT,
            project_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'MATCHING',
            reviewer_id TEXT,
            overall_result TEXT,
            created_at DATETIME NOT NULL,
            updated_at DATETIME NOT NULL,
            completed_at DATETIME,
            CHECK (status IN ('MATCHING', 'EXTRACTING', 'VERIFYING', 'REVIEWING', 'COMPLETED')),
            CHECK (overall_result IS NULL OR overall_result IN ('PASS', 'FAIL', 'NEEDS_REVIEW'))
        )
    """)


def create_spec_match_suggestion_table(cursor: sqlite3.Cursor) -> None:
    """Create the spec_match_suggestion table for storing spec section suggestions."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spec_match_suggestion (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            spec_section_id TEXT NOT NULL,
            similarity_score REAL NOT NULL,
            rank INTEGER NOT NULL,
            selected BOOLEAN NOT NULL DEFAULT FALSE,
            FOREIGN KEY (session_id) REFERENCES review_session(id)
        )
    """)


def create_requirement_table(cursor: sqlite3.Cursor) -> None:
    """Create the requirement table for storing extracted requirements."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requirement (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            text TEXT NOT NULL,
            lane TEXT NOT NULL,
            source_page INTEGER NOT NULL,
            source_location TEXT,
            attribute_type TEXT,
            target_value TEXT,
            status TEXT NOT NULL DEFAULT 'PENDING',
            created_at DATETIME NOT NULL,
            CHECK (lane IN ('AUTO_CHECK', 'NEEDS_SCOPING', 'INFORMATIONAL')),
            CHECK (status IN ('PENDING', 'VERIFIED', 'SCOPED', 'NOT_APPLICABLE')),
            FOREIGN KEY (session_id) REFERENCES review_session(id)
        )
    """)


def create_compliance_result_table(cursor: sqlite3.Cursor) -> None:
    """Create the compliance_result table for storing verification results."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS compliance_result (
            id TEXT PRIMARY KEY,
            requirement_id TEXT NOT NULL,
            outcome TEXT NOT NULL,
            value_found TEXT,
            confidence REAL NOT NULL,
            submittal_page INTEGER,
            submittal_location TEXT,
            evidence_path TEXT,
            reasoning TEXT,
            human_confirmed BOOLEAN NOT NULL DEFAULT FALSE,
            created_at DATETIME NOT NULL,
            CHECK (outcome IN ('PASS', 'FAIL', 'NOT_FOUND', 'NEEDS_REVIEW')),
            CHECK (confidence >= 0 AND confidence <= 1),
            FOREIGN KEY (requirement_id) REFERENCES requirement(id)
        )
    """)


def create_correction_table(cursor: sqlite3.Cursor) -> None:
    """Create the correction table for storing human overrides."""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS correction (
            id TEXT PRIMARY KEY,
            result_id TEXT NOT NULL,
            correction_type TEXT NOT NULL,
            original_value TEXT NOT NULL,
            corrected_value TEXT NOT NULL,
            user_id TEXT NOT NULL,
            reason TEXT,
            created_at DATETIME NOT NULL,
            CHECK (correction_type IN ('value', 'status', 'lane', 'na')),
            FOREIGN KEY (result_id) REFERENCES compliance_result(id)
        )
    """)


def create_indexes(cursor: sqlite3.Cursor) -> None:
    """Create all indexes for efficient querying."""
    # review_session indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_project ON review_session(project_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_status ON review_session(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_submittal ON review_session(submittal_id)")

    # requirement indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_req_session ON requirement(session_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_req_lane ON requirement(lane)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_req_status ON requirement(status)")

    # compliance_result indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_result_req ON compliance_result(requirement_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_result_outcome ON compliance_result(outcome)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_result_confidence ON compliance_result(confidence)")

    # correction indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_correction_result ON correction(result_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_correction_type ON correction(correction_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_correction_user ON correction(user_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_correction_date ON correction(created_at)")
