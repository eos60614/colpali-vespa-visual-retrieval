"""
Verification service for automated compliance checking.
"""

import uuid
from datetime import datetime
from typing import Optional

from backend.models.database import get_connection
from backend.models.enums import LaneType, ComplianceOutcome, SessionStatus
from backend.models.compliance import ComplianceResult
from backend.models.bounding_box import BoundingBox


class VerificationService:
    """Service for verifying requirements against submittal documents."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    def verify_requirement(
        self, requirement_id: str, submittal_id: str
    ) -> ComplianceResult:
        """
        Verify a single requirement against a submittal.

        This is a stub implementation that returns mock results.
        In the future, this will use Vision LLM via OpenRouter/Ollama.

        Args:
            requirement_id: The requirement to verify
            submittal_id: The submittal document ID

        Returns:
            ComplianceResult with verification outcome
        """
        import random

        now = datetime.utcnow()

        # Stub implementation - return mock result with bounding box
        outcomes = [
            ComplianceOutcome.PASS,
            ComplianceOutcome.PASS,
            ComplianceOutcome.PASS,
            ComplianceOutcome.FAIL,
            ComplianceOutcome.NEEDS_REVIEW,
        ]
        outcome = random.choice(outcomes)

        confidence = random.uniform(0.7, 0.98)
        if outcome == ComplianceOutcome.NEEDS_REVIEW:
            confidence = random.uniform(0.5, 0.7)

        # Generate mock bounding box for the submittal location
        submittal_location = BoundingBox(
            x=round(random.uniform(0.1, 0.3), 2),
            y=round(random.uniform(0.2, 0.6), 2),
            width=round(random.uniform(0.3, 0.6), 2),
            height=round(random.uniform(0.04, 0.1), 2),
            confidence=round(confidence, 2),
            label="matched_value",
        ) if outcome != ComplianceOutcome.NOT_FOUND else None

        return ComplianceResult(
            id=str(uuid.uuid4()),
            requirement_id=requirement_id,
            outcome=outcome,
            value_found="Mock Value Found" if outcome != ComplianceOutcome.NOT_FOUND else None,
            confidence=confidence,
            submittal_page=random.randint(1, 10),
            submittal_location=submittal_location,
            reasoning="This is a stub verification result for testing purposes.",
            human_confirmed=False,
            created_at=now,
        )

    def run_verification(self, session_id: str) -> list[ComplianceResult]:
        """
        Run verification for all AUTO_CHECK requirements in a session.

        Args:
            session_id: The review session ID

        Returns:
            List of ComplianceResult objects
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # Get session to find submittal_id
        cursor.execute("SELECT submittal_id FROM review_session WHERE id = ?", (session_id,))
        session_row = cursor.fetchone()
        if not session_row:
            conn.close()
            return []

        submittal_id = session_row["submittal_id"]

        # Get AUTO_CHECK requirements
        cursor.execute(
            "SELECT id FROM requirement WHERE session_id = ? AND lane = ?",
            (session_id, LaneType.AUTO_CHECK.value),
        )
        requirements = cursor.fetchall()
        conn.close()

        results = []
        for req in requirements:
            result = self.verify_requirement(req["id"], submittal_id)
            self.save_compliance_result(result)
            results.append(result)

        # Update session status to VERIFYING -> REVIEWING
        self._update_session_status(session_id, SessionStatus.REVIEWING)

        return results

    def save_compliance_result(self, result: ComplianceResult) -> ComplianceResult:
        """
        Save a compliance result to the database.

        Args:
            result: The ComplianceResult to save

        Returns:
            The saved ComplianceResult
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # Serialize BoundingBox to JSON for storage
        submittal_location_json = result.submittal_location.model_dump_json() if result.submittal_location else None

        cursor.execute(
            """
            INSERT INTO compliance_result (id, requirement_id, outcome, value_found, confidence,
                                          submittal_page, submittal_location, evidence_path,
                                          reasoning, human_confirmed, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.id,
                result.requirement_id,
                result.outcome.value,
                result.value_found,
                result.confidence,
                result.submittal_page,
                submittal_location_json,
                result.evidence_path,
                result.reasoning,
                result.human_confirmed,
                result.created_at,
            ),
        )
        conn.commit()
        conn.close()

        return result

    def get_verification_status(self, session_id: str) -> dict:
        """
        Get the current verification progress for a session.

        Args:
            session_id: The review session ID

        Returns:
            Dict with status, total, verified_count, progress_percent
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # Count total AUTO_CHECK requirements
        cursor.execute(
            "SELECT COUNT(*) FROM requirement WHERE session_id = ? AND lane = ?",
            (session_id, LaneType.AUTO_CHECK.value),
        )
        total = cursor.fetchone()[0]

        # Count verified
        cursor.execute(
            """
            SELECT COUNT(*) FROM compliance_result cr
            JOIN requirement r ON cr.requirement_id = r.id
            WHERE r.session_id = ?
            """,
            (session_id,),
        )
        verified = cursor.fetchone()[0]
        conn.close()

        progress = (verified / total * 100) if total > 0 else 0

        return {
            "status": "COMPLETE" if verified >= total else "IN_PROGRESS" if verified > 0 else "PENDING",
            "total_requirements": total,
            "verified_count": verified,
            "progress_percent": progress,
        }

    def get_results(
        self, session_id: str, outcome: Optional[ComplianceOutcome] = None
    ) -> list[ComplianceResult]:
        """
        Get all compliance results for a session.

        Args:
            session_id: The review session ID
            outcome: Optional filter by outcome

        Returns:
            List of ComplianceResult objects
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        query = """
            SELECT cr.* FROM compliance_result cr
            JOIN requirement r ON cr.requirement_id = r.id
            WHERE r.session_id = ?
        """
        params = [session_id]

        if outcome:
            query += " AND cr.outcome = ?"
            params.append(outcome.value)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_result(row) for row in rows]

    def get_result(self, result_id: str) -> Optional[ComplianceResult]:
        """Get a single compliance result by ID."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM compliance_result WHERE id = ?", (result_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_result(row)

    def _row_to_result(self, row) -> ComplianceResult:
        """Convert a database row to a ComplianceResult object."""
        # Deserialize BoundingBox from JSON
        submittal_location = None
        if row["submittal_location"]:
            submittal_location = BoundingBox.model_validate_json(row["submittal_location"])

        return ComplianceResult(
            id=row["id"],
            requirement_id=row["requirement_id"],
            outcome=ComplianceOutcome(row["outcome"]),
            value_found=row["value_found"],
            confidence=row["confidence"],
            submittal_page=row["submittal_page"],
            submittal_location=submittal_location,
            evidence_path=row["evidence_path"],
            reasoning=row["reasoning"],
            human_confirmed=bool(row["human_confirmed"]),
            created_at=row["created_at"],
        )

    def _update_session_status(self, session_id: str, status: SessionStatus):
        """Update session status."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE review_session SET status = ?, updated_at = ? WHERE id = ?",
            (status.value, datetime.utcnow(), session_id),
        )
        conn.commit()
        conn.close()
