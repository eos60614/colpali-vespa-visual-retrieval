"""
Evidence service for managing visual evidence files.
"""

import os
from pathlib import Path
from typing import Optional


class EvidenceService:
    """Service for managing visual evidence storage and retrieval."""

    def __init__(self, evidence_base_path: str = "static/compliance/evidence"):
        self.base_path = Path(evidence_base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def get_evidence_dir(self, session_id: str, requirement_id: str) -> Path:
        """Get the evidence directory for a requirement."""
        evidence_dir = self.base_path / session_id / requirement_id
        evidence_dir.mkdir(parents=True, exist_ok=True)
        return evidence_dir

    def save_evidence(
        self,
        session_id: str,
        requirement_id: str,
        spec_image: bytes,
        submittal_image: bytes,
    ) -> dict[str, str]:
        """
        Save evidence images for a requirement.

        Args:
            session_id: The review session ID
            requirement_id: The requirement ID
            spec_image: Spec context image bytes
            submittal_image: Submittal region image bytes

        Returns:
            Dict with paths to saved images
        """
        evidence_dir = self.get_evidence_dir(session_id, requirement_id)

        spec_path = evidence_dir / "spec_context.jpg"
        submittal_path = evidence_dir / "submittal_region.jpg"

        with open(spec_path, "wb") as f:
            f.write(spec_image)

        with open(submittal_path, "wb") as f:
            f.write(submittal_image)

        return {
            "spec_image_path": str(spec_path),
            "submittal_image_path": str(submittal_path),
        }

    def get_evidence_paths(
        self, session_id: str, requirement_id: str
    ) -> Optional[dict[str, str]]:
        """
        Get paths to evidence images for a requirement.

        Args:
            session_id: The review session ID
            requirement_id: The requirement ID

        Returns:
            Dict with paths or None if not found
        """
        evidence_dir = self.base_path / session_id / requirement_id

        spec_path = evidence_dir / "spec_context.jpg"
        submittal_path = evidence_dir / "submittal_region.jpg"

        if not spec_path.exists() or not submittal_path.exists():
            return None

        return {
            "spec_image_path": str(spec_path),
            "submittal_image_path": str(submittal_path),
        }

    def get_evidence_urls(
        self, session_id: str, requirement_id: str
    ) -> Optional[dict[str, str]]:
        """
        Get URLs for evidence images.

        Args:
            session_id: The review session ID
            requirement_id: The requirement ID

        Returns:
            Dict with URLs or None if not found
        """
        paths = self.get_evidence_paths(session_id, requirement_id)
        if not paths:
            return None

        return {
            "spec_image_url": f"/api/compliance/evidence/{session_id}/{requirement_id}/spec",
            "submittal_image_url": f"/api/compliance/evidence/{session_id}/{requirement_id}/submittal",
        }

    def delete_evidence(self, session_id: str, requirement_id: str) -> bool:
        """
        Delete evidence for a requirement.

        Args:
            session_id: The review session ID
            requirement_id: The requirement ID

        Returns:
            True if deleted, False if not found
        """
        evidence_dir = self.base_path / session_id / requirement_id

        if not evidence_dir.exists():
            return False

        import shutil
        shutil.rmtree(evidence_dir)
        return True

    def delete_session_evidence(self, session_id: str) -> bool:
        """
        Delete all evidence for a session.

        Args:
            session_id: The review session ID

        Returns:
            True if deleted, False if not found
        """
        session_dir = self.base_path / session_id

        if not session_dir.exists():
            return False

        import shutil
        shutil.rmtree(session_dir)
        return True
