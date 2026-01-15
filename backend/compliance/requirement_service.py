"""
Service for extracting and managing requirements.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from backend.models.database import get_connection
from backend.models.enums import LaneType, RequirementStatus
from backend.models.requirement import Requirement
from backend.models.bounding_box import BoundingBox


class RequirementService:
    """Service for extracting and managing requirements from spec sections."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    def extract_requirements(
        self, session_id: str, spec_section_id: str
    ) -> list[Requirement]:
        """
        Extract requirements from a spec section.

        This is a stub implementation that returns mock requirements.
        In the future, this will use Vision LLM via OpenRouter/Ollama.

        Args:
            session_id: The review session ID
            spec_section_id: The spec section to extract from

        Returns:
            List of extracted Requirement objects
        """
        now = datetime.utcnow()

        # Stub implementation - return mock requirements with bounding boxes
        mock_requirements = [
            Requirement(
                id=str(uuid.uuid4()),
                session_id=session_id,
                text="Provide cooling capacity of 10 tons minimum",
                lane=LaneType.AUTO_CHECK,
                source_page=1,
                source_location=BoundingBox(x=0.1, y=0.25, width=0.8, height=0.05, confidence=0.95, label="cooling_capacity"),
                attribute_type="cooling_capacity",
                target_value="10 tons",
                status=RequirementStatus.PENDING,
                created_at=now,
            ),
            Requirement(
                id=str(uuid.uuid4()),
                session_id=session_id,
                text="Voltage rating shall be 208V",
                lane=LaneType.AUTO_CHECK,
                source_page=1,
                source_location=BoundingBox(x=0.1, y=0.35, width=0.6, height=0.04, confidence=0.92, label="voltage"),
                attribute_type="voltage",
                target_value="208V",
                status=RequirementStatus.PENDING,
                created_at=now,
            ),
            Requirement(
                id=str(uuid.uuid4()),
                session_id=session_id,
                text="Refrigerant type as scheduled on drawings",
                lane=LaneType.NEEDS_SCOPING,
                source_page=2,
                source_location=BoundingBox(x=0.15, y=0.45, width=0.7, height=0.04, confidence=0.88, label="refrigerant"),
                attribute_type="refrigerant",
                target_value=None,
                status=RequirementStatus.PENDING,
                created_at=now,
            ),
            Requirement(
                id=str(uuid.uuid4()),
                session_id=session_id,
                text="Unit shall be UL listed",
                lane=LaneType.AUTO_CHECK,
                source_page=2,
                source_location=BoundingBox(x=0.1, y=0.55, width=0.5, height=0.04, confidence=0.97, label="certification"),
                attribute_type="certification",
                target_value="UL listed",
                status=RequirementStatus.PENDING,
                created_at=now,
            ),
            Requirement(
                id=str(uuid.uuid4()),
                session_id=session_id,
                text="Install in accordance with manufacturer recommendations",
                lane=LaneType.INFORMATIONAL,
                source_page=3,
                source_location=BoundingBox(x=0.1, y=0.2, width=0.8, height=0.06, confidence=0.85, label="installation"),
                attribute_type=None,
                target_value=None,
                status=RequirementStatus.PENDING,
                created_at=now,
            ),
        ]

        return mock_requirements

    def save_requirements(self, requirements: list[Requirement]) -> list[Requirement]:
        """
        Save extracted requirements to the database.

        Args:
            requirements: List of requirements to save

        Returns:
            List of saved requirements
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        for req in requirements:
            # Serialize BoundingBox to JSON for storage
            source_location_json = req.source_location.model_dump_json() if req.source_location else None
            cursor.execute(
                """
                INSERT INTO requirement (id, session_id, text, lane, source_page, source_location,
                                         attribute_type, target_value, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    req.id,
                    req.session_id,
                    req.text,
                    req.lane.value,
                    req.source_page,
                    source_location_json,
                    req.attribute_type,
                    req.target_value,
                    req.status.value,
                    req.created_at,
                ),
            )

        conn.commit()
        conn.close()

        return requirements

    def get_requirements_by_session(
        self, session_id: str, lane: Optional[LaneType] = None
    ) -> dict[str, list[Requirement]]:
        """
        Get requirements for a session, grouped by lane.

        Args:
            session_id: The review session ID
            lane: Optional lane filter

        Returns:
            Dict with keys 'auto_check', 'needs_scoping', 'informational'
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM requirement WHERE session_id = ?"
        params = [session_id]

        if lane:
            query += " AND lane = ?"
            params.append(lane.value)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        requirements = [self._row_to_requirement(row) for row in rows]

        return {
            "auto_check": [r for r in requirements if r.lane == LaneType.AUTO_CHECK],
            "needs_scoping": [r for r in requirements if r.lane == LaneType.NEEDS_SCOPING],
            "informational": [r for r in requirements if r.lane == LaneType.INFORMATIONAL],
        }

    def get_requirement(self, requirement_id: str) -> Optional[Requirement]:
        """Get a single requirement by ID."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM requirement WHERE id = ?", (requirement_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return self._row_to_requirement(row)

    def update_requirement(
        self,
        requirement_id: str,
        lane: Optional[LaneType] = None,
        target_value: Optional[str] = None,
        status: Optional[RequirementStatus] = None,
    ) -> Optional[Requirement]:
        """
        Update a requirement's lane, target_value, or status.

        Args:
            requirement_id: The requirement ID
            lane: New lane classification
            target_value: New target value (for NEEDS_SCOPING requirements)
            status: New status

        Returns:
            Updated Requirement or None if not found
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        updates = []
        params = []

        if lane:
            updates.append("lane = ?")
            params.append(lane.value)
        if target_value:
            updates.append("target_value = ?")
            params.append(target_value)
        if status:
            updates.append("status = ?")
            params.append(status.value)

        if not updates:
            return self.get_requirement(requirement_id)

        params.append(requirement_id)
        cursor.execute(
            f"UPDATE requirement SET {', '.join(updates)} WHERE id = ?",
            params,
        )
        conn.commit()
        conn.close()

        return self.get_requirement(requirement_id)

    def _row_to_requirement(self, row) -> Requirement:
        """Convert a database row to a Requirement object."""
        # Deserialize BoundingBox from JSON
        source_location = None
        if row["source_location"]:
            source_location = BoundingBox.model_validate_json(row["source_location"])

        return Requirement(
            id=row["id"],
            session_id=row["session_id"],
            text=row["text"],
            lane=LaneType(row["lane"]),
            source_page=row["source_page"],
            source_location=source_location,
            attribute_type=row["attribute_type"],
            target_value=row["target_value"],
            status=RequirementStatus(row["status"]),
            created_at=row["created_at"],
        )
