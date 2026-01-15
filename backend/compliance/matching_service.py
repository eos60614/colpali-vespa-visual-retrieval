"""
Service for matching submittals to spec sections.
"""

import uuid
from typing import Optional

from backend.models.database import get_connection
from backend.models.compliance import SpecMatchSuggestion, SpecSection


class SpecMatchingService:
    """Service for matching submittals to specification sections."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    def find_matching_sections(
        self, submittal_id: str, limit: int = 5
    ) -> list[tuple[SpecSection, float]]:
        """
        Find spec sections that match the given submittal.

        This is a stub implementation that returns mock suggestions.
        In the future, this will use ColPali similarity search.

        Args:
            submittal_id: The ID of the submittal document
            limit: Maximum number of suggestions to return

        Returns:
            List of (SpecSection, similarity_score) tuples
        """
        # Stub implementation - return mock suggestions
        mock_sections = [
            (
                SpecSection(
                    id="mock-spec-001",
                    project_id="mock-project",
                    section_number="23 05 00",
                    section_title="Common Work Results for HVAC",
                    source_doc_id="mock-doc-001",
                    page_numbers=[1, 2, 3],
                ),
                0.85,
            ),
            (
                SpecSection(
                    id="mock-spec-002",
                    project_id="mock-project",
                    section_number="23 23 00",
                    section_title="Refrigerant Piping",
                    source_doc_id="mock-doc-001",
                    page_numbers=[4, 5],
                ),
                0.72,
            ),
            (
                SpecSection(
                    id="mock-spec-003",
                    project_id="mock-project",
                    section_number="23 81 26",
                    section_title="Split-System Air-Conditioners",
                    source_doc_id="mock-doc-001",
                    page_numbers=[6, 7, 8],
                ),
                0.68,
            ),
        ]

        return mock_sections[:limit]

    def save_suggestions(
        self, session_id: str, suggestions: list[tuple[SpecSection, float]]
    ) -> list[SpecMatchSuggestion]:
        """
        Save spec section suggestions for a session.

        Args:
            session_id: The review session ID
            suggestions: List of (SpecSection, similarity_score) tuples

        Returns:
            List of saved SpecMatchSuggestion objects
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        saved = []
        for rank, (section, score) in enumerate(suggestions, 1):
            suggestion_id = str(uuid.uuid4())
            cursor.execute(
                """
                INSERT INTO spec_match_suggestion (id, session_id, spec_section_id, similarity_score, rank, selected)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (suggestion_id, session_id, section.id, score, rank),
            )
            saved.append(
                SpecMatchSuggestion(
                    id=suggestion_id,
                    session_id=session_id,
                    spec_section_id=section.id,
                    similarity_score=score,
                    rank=rank,
                    selected=False,
                )
            )

        conn.commit()
        conn.close()

        return saved

    def get_suggestions(self, session_id: str) -> list[SpecMatchSuggestion]:
        """Get all suggestions for a session."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM spec_match_suggestion WHERE session_id = ? ORDER BY rank",
            (session_id,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            SpecMatchSuggestion(
                id=row["id"],
                session_id=row["session_id"],
                spec_section_id=row["spec_section_id"],
                similarity_score=row["similarity_score"],
                rank=row["rank"],
                selected=bool(row["selected"]),
            )
            for row in rows
        ]

    def confirm_section(self, session_id: str, spec_section_id: str) -> bool:
        """
        Confirm a spec section selection for a session.

        Args:
            session_id: The review session ID
            spec_section_id: The selected spec section ID

        Returns:
            True if successful
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # Mark all suggestions as not selected
        cursor.execute(
            "UPDATE spec_match_suggestion SET selected = 0 WHERE session_id = ?",
            (session_id,),
        )

        # Mark the selected suggestion
        cursor.execute(
            """
            UPDATE spec_match_suggestion
            SET selected = 1
            WHERE session_id = ? AND spec_section_id = ?
            """,
            (session_id, spec_section_id),
        )

        conn.commit()
        conn.close()

        return True

    def get_selected_section(self, session_id: str) -> Optional[str]:
        """Get the selected spec section ID for a session."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT spec_section_id FROM spec_match_suggestion WHERE session_id = ? AND selected = 1",
            (session_id,),
        )
        row = cursor.fetchone()
        conn.close()

        return row["spec_section_id"] if row else None
