"""
Procore PostgreSQL-backed project store.
Reads projects and document counts from the readonly Procore database.
"""

import logging
import os
from typing import List, Optional

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


class ProjectStore:
    """Read-only project store backed by the Procore PostgreSQL database."""

    # Document-type tables that have a project_id column
    DOC_TABLES = {
        "drawings": "Drawing",
        "photos": "Photo",
        "submittals": "Submittal",
        "rfis": "RFI",
        "change_orders": "Change Order",
        "specification_sections": "Spec",
    }

    def __init__(self):
        self._db_url = os.getenv("PROCORE_DATABASE_URL")
        if not self._db_url:
            raise ValueError("PROCORE_DATABASE_URL environment variable is required")

    def _conn(self):
        return psycopg2.connect(self._db_url, cursor_factory=psycopg2.extras.RealDictCursor)

    def list_projects(self) -> List[dict]:
        """List all active projects with per-category document counts."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        p.id,
                        p.name,
                        p.display_name,
                        p.project_number,
                        p.address,
                        p.city,
                        p.state_code,
                        p.active,
                        (SELECT count(*) FROM drawings d WHERE d.project_id = p.id) AS drawing_count,
                        (SELECT count(*) FROM photos ph WHERE ph.project_id = p.id) AS photo_count,
                        (SELECT count(*) FROM submittals s WHERE s.project_id = p.id) AS submittal_count,
                        (SELECT count(*) FROM rfis r WHERE r.project_id = p.id) AS rfi_count,
                        (SELECT count(*) FROM change_orders co WHERE co.project_id = p.id) AS change_order_count,
                        (SELECT count(*) FROM specification_sections ss WHERE ss.project_id = p.id) AS spec_count
                    FROM projects p
                    WHERE p.active = true
                    ORDER BY p.name
                """)
                rows = cur.fetchall()

        return [self._format_project(dict(r)) for r in rows]

    def get_project(self, project_id: int) -> Optional[dict]:
        """Get a single project by ID with document counts."""
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        p.id,
                        p.name,
                        p.display_name,
                        p.project_number,
                        p.address,
                        p.city,
                        p.state_code,
                        p.active,
                        (SELECT count(*) FROM drawings d WHERE d.project_id = p.id) AS drawing_count,
                        (SELECT count(*) FROM photos ph WHERE ph.project_id = p.id) AS photo_count,
                        (SELECT count(*) FROM submittals s WHERE s.project_id = p.id) AS submittal_count,
                        (SELECT count(*) FROM rfis r WHERE r.project_id = p.id) AS rfi_count,
                        (SELECT count(*) FROM change_orders co WHERE co.project_id = p.id) AS change_order_count,
                        (SELECT count(*) FROM specification_sections ss WHERE ss.project_id = p.id) AS spec_count
                    FROM projects p
                    WHERE p.id = %s
                """, (project_id,))
                row = cur.fetchone()

        if not row:
            return None
        return self._format_project(dict(row))

    def _format_project(self, row: dict) -> dict:
        """Format a project row into the API response shape."""
        doc_counts = {
            "Drawing": row.get("drawing_count", 0),
            "Photo": row.get("photo_count", 0),
            "Submittal": row.get("submittal_count", 0),
            "RFI": row.get("rfi_count", 0),
            "Change Order": row.get("change_order_count", 0),
            "Spec": row.get("spec_count", 0),
        }
        total = sum(doc_counts.values())

        return {
            "id": str(row["id"]),  # string to avoid JS bigint precision loss
            "name": row["name"],
            "display_name": row.get("display_name") or row["name"],
            "project_number": row.get("project_number") or "",
            "address": row.get("address") or "",
            "city": row.get("city") or "",
            "state_code": row.get("state_code") or "",
            "active": row.get("active", True),
            "document_count": total,
            "document_counts": doc_counts,
        }
