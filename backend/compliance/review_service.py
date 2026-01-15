"""
Service for human review and override functionality.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from backend.models.database import get_connection
from backend.models.enums import SessionStatus, ComplianceOutcome, CorrectionType
from backend.models.compliance import ComplianceResult
from backend.models.correction import Correction


class ReviewService:
    """Service for managing human review and corrections."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    def confirm_result(self, result_id: str) -> Optional[ComplianceResult]:
        """
        Mark a compliance result as human confirmed.

        Args:
            result_id: The result ID to confirm

        Returns:
            Updated ComplianceResult or None if not found
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            "UPDATE compliance_result SET human_confirmed = 1 WHERE id = ?",
            (result_id,),
        )
        conn.commit()

        cursor.execute("SELECT * FROM compliance_result WHERE id = ?", (result_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_result(row)

    def correct_result(
        self,
        result_id: str,
        correction_type: CorrectionType,
        corrected_outcome: Optional[ComplianceOutcome] = None,
        corrected_value: Optional[str] = None,
        user_id: str = "system",
        reason: Optional[str] = None,
    ) -> tuple[ComplianceResult, Correction]:
        """
        Create a correction for a compliance result.

        Args:
            result_id: The result ID to correct
            correction_type: Type of correction
            corrected_outcome: New outcome (if correcting status)
            corrected_value: New value found (if correcting value)
            user_id: User making the correction
            reason: Optional explanation

        Returns:
            Tuple of (updated ComplianceResult, Correction)
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # Get original result
        cursor.execute("SELECT * FROM compliance_result WHERE id = ?", (result_id,))
        row = cursor.fetchone()
        if not row:
            conn.close()
            raise ValueError(f"Result {result_id} not found")

        # Create correction record
        correction_id = str(uuid.uuid4())
        now = datetime.utcnow()

        original_value = json.dumps({
            "outcome": row["outcome"],
            "value_found": row["value_found"],
        })
        corrected_value_json = json.dumps({
            "outcome": corrected_outcome.value if corrected_outcome else row["outcome"],
            "value_found": corrected_value or row["value_found"],
        })

        cursor.execute(
            """
            INSERT INTO correction (id, result_id, correction_type, original_value,
                                   corrected_value, user_id, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                correction_id,
                result_id,
                correction_type.value,
                original_value,
                corrected_value_json,
                user_id,
                reason,
                now,
            ),
        )

        # Update the result
        if corrected_outcome:
            cursor.execute(
                "UPDATE compliance_result SET outcome = ?, human_confirmed = 1 WHERE id = ?",
                (corrected_outcome.value, result_id),
            )
        if corrected_value:
            cursor.execute(
                "UPDATE compliance_result SET value_found = ?, human_confirmed = 1 WHERE id = ?",
                (corrected_value, result_id),
            )

        conn.commit()

        # Fetch updated result
        cursor.execute("SELECT * FROM compliance_result WHERE id = ?", (result_id,))
        updated_row = cursor.fetchone()

        cursor.execute("SELECT * FROM correction WHERE id = ?", (correction_id,))
        correction_row = cursor.fetchone()
        conn.close()

        result = self._row_to_result(updated_row)
        correction = Correction(
            id=correction_row["id"],
            result_id=correction_row["result_id"],
            correction_type=CorrectionType(correction_row["correction_type"]),
            original_value=correction_row["original_value"],
            corrected_value=correction_row["corrected_value"],
            user_id=correction_row["user_id"],
            reason=correction_row["reason"],
            created_at=correction_row["created_at"],
        )

        return result, correction

    def get_corrections(self, result_id: str) -> list[Correction]:
        """
        Get correction history for a result.

        Args:
            result_id: The result ID

        Returns:
            List of Correction objects ordered by date descending
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM correction WHERE result_id = ? ORDER BY created_at DESC",
            (result_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            Correction(
                id=row["id"],
                result_id=row["result_id"],
                correction_type=CorrectionType(row["correction_type"]),
                original_value=row["original_value"],
                corrected_value=row["corrected_value"],
                user_id=row["user_id"],
                reason=row["reason"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    def complete_review(self, session_id: str) -> tuple[bool, str]:
        """
        Complete a review session if all results are confirmed.

        Args:
            session_id: The session ID

        Returns:
            Tuple of (success, message)
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # Check for unconfirmed results
        cursor.execute(
            """
            SELECT COUNT(*) FROM compliance_result cr
            JOIN requirement r ON cr.requirement_id = r.id
            WHERE r.session_id = ? AND cr.human_confirmed = 0
            """,
            (session_id,),
        )
        unconfirmed = cursor.fetchone()[0]

        if unconfirmed > 0:
            conn.close()
            return False, f"{unconfirmed} results need to be confirmed before completing"

        # Calculate overall result
        overall_result = self._calculate_overall_result(cursor, session_id)

        # Update session
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

        return True, f"Review completed with result: {overall_result.value}"

    def get_review_status(self, session_id: str) -> dict:
        """
        Get review status for a session.

        Args:
            session_id: The session ID

        Returns:
            Dict with confirmed/total counts and completion readiness
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(cr.human_confirmed) as confirmed
            FROM compliance_result cr
            JOIN requirement r ON cr.requirement_id = r.id
            WHERE r.session_id = ?
            """,
            (session_id,),
        )
        row = cursor.fetchone()
        conn.close()

        total = row["total"] or 0
        confirmed = row["confirmed"] or 0

        return {
            "total": total,
            "confirmed": confirmed,
            "unconfirmed": total - confirmed,
            "ready_to_complete": total > 0 and confirmed == total,
        }

    def _calculate_overall_result(
        self, cursor, session_id: str
    ) -> ComplianceOutcome:
        """Calculate overall result based on individual outcomes."""
        cursor.execute(
            """
            SELECT cr.outcome, COUNT(*) as count FROM compliance_result cr
            JOIN requirement r ON cr.requirement_id = r.id
            WHERE r.session_id = ?
            GROUP BY cr.outcome
            """,
            (session_id,),
        )
        outcomes = {row["outcome"]: row["count"] for row in cursor.fetchall()}

        if outcomes.get("FAIL", 0) > 0:
            return ComplianceOutcome.FAIL
        elif outcomes.get("NEEDS_REVIEW", 0) > 0:
            return ComplianceOutcome.NEEDS_REVIEW
        else:
            return ComplianceOutcome.PASS

    def _row_to_result(self, row) -> ComplianceResult:
        """Convert a database row to a ComplianceResult object."""
        return ComplianceResult(
            id=row["id"],
            requirement_id=row["requirement_id"],
            outcome=ComplianceOutcome(row["outcome"]),
            value_found=row["value_found"],
            confidence=row["confidence"],
            submittal_page=row["submittal_page"],
            submittal_location=row["submittal_location"],
            evidence_path=row["evidence_path"],
            reasoning=row["reasoning"],
            human_confirmed=bool(row["human_confirmed"]),
            created_at=row["created_at"],
        )
