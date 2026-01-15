"""
Service for managing review sessions.
"""

import uuid
from datetime import datetime
from typing import Optional

from backend.models.database import get_connection
from backend.models.enums import SessionStatus, ComplianceOutcome
from backend.models.compliance import ReviewSession


class ReviewSessionService:
    """Service for managing compliance review sessions."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    def create_session(
        self, submittal_id: str, project_id: str, reviewer_id: Optional[str] = None
    ) -> ReviewSession:
        """Create a new review session."""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()

        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO review_session (id, submittal_id, project_id, status, reviewer_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, submittal_id, project_id, SessionStatus.MATCHING.value, reviewer_id, now, now),
        )
        conn.commit()
        conn.close()

        return ReviewSession(
            id=session_id,
            submittal_id=submittal_id,
            project_id=project_id,
            status=SessionStatus.MATCHING,
            reviewer_id=reviewer_id,
            created_at=now,
            updated_at=now,
        )

    def get_session(self, session_id: str) -> Optional[ReviewSession]:
        """Get a session by ID."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM review_session WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return ReviewSession(
            id=row["id"],
            submittal_id=row["submittal_id"],
            spec_section_id=row["spec_section_id"],
            project_id=row["project_id"],
            status=SessionStatus(row["status"]),
            reviewer_id=row["reviewer_id"],
            overall_result=ComplianceOutcome(row["overall_result"]) if row["overall_result"] else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
        )

    def list_sessions(
        self,
        project_id: Optional[str] = None,
        status: Optional[SessionStatus] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[ReviewSession], int]:
        """List sessions with optional filtering and pagination."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM review_session WHERE 1=1"
        params = []

        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        if status:
            query += " AND status = ?"
            params.append(status.value)

        # Count total
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

        # Get paginated results
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        sessions = [
            ReviewSession(
                id=row["id"],
                submittal_id=row["submittal_id"],
                spec_section_id=row["spec_section_id"],
                project_id=row["project_id"],
                status=SessionStatus(row["status"]),
                reviewer_id=row["reviewer_id"],
                overall_result=ComplianceOutcome(row["overall_result"]) if row["overall_result"] else None,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                completed_at=row["completed_at"],
            )
            for row in rows
        ]

        return sessions, total

    def update_status(self, session_id: str, status: SessionStatus) -> Optional[ReviewSession]:
        """Update session status."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        now = datetime.utcnow()
        cursor.execute(
            "UPDATE review_session SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, now, session_id),
        )
        conn.commit()
        conn.close()

        return self.get_session(session_id)

    def set_spec_section(self, session_id: str, spec_section_id: str) -> Optional[ReviewSession]:
        """Set the spec section for a session and transition to EXTRACTING."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        now = datetime.utcnow()
        cursor.execute(
            """
            UPDATE review_session
            SET spec_section_id = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (spec_section_id, SessionStatus.EXTRACTING.value, now, session_id),
        )
        conn.commit()
        conn.close()

        return self.get_session(session_id)

    def complete_session(
        self, session_id: str, overall_result: ComplianceOutcome
    ) -> Optional[ReviewSession]:
        """Mark a session as complete with overall result."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        now = datetime.utcnow()
        cursor.execute(
            """
            UPDATE review_session
            SET status = ?, overall_result = ?, completed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (SessionStatus.COMPLETED.value, overall_result.value, now, now, session_id),
        )
        conn.commit()
        conn.close()

        return self.get_session(session_id)
