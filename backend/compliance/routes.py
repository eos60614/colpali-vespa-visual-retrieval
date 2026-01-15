"""
Compliance API routes for the submittal compliance checking system.
"""

import json
import uuid
from datetime import datetime
from typing import Optional

from fasthtml.common import JSONResponse

from backend.models.database import get_connection
from backend.models.enums import (
    SessionStatus,
    LaneType,
    RequirementStatus,
    ComplianceOutcome,
    CorrectionType,
)
from backend.models.schemas import (
    CreateSessionRequest,
    ConfirmSpecSectionRequest,
    UpdateRequirementRequest,
    CorrectionRequest,
    ReviewSessionResponse,
    ReviewSessionDetailResponse,
    SessionListResponse,
    SpecSectionSuggestionsResponse,
    SpecSectionSuggestionResponse,
    SpecSectionResponse,
    RequirementResponse,
    RequirementDetailResponse,
    RequirementListResponse,
    ComplianceResultResponse,
    ComplianceResultDetailResponse,
    ComplianceResultListResponse,
    VerificationStatusResponse,
    ComplianceReportResponse,
    ReportSummaryResponse,
    ReportResultItemResponse,
    ErrorResponse,
    RequirementsSummary,
    ResultsSummary,
)


def error_response(status_code: int, error: str, message: str, details: dict = None):
    """Create a standardized error response."""
    return JSONResponse(
        ErrorResponse(error=error, message=message, details=details).model_dump(),
        status_code=status_code,
    )


def register_compliance_routes(app, rt):
    """Register all compliance API routes with the FastHTML app."""

    # ============== SESSION MANAGEMENT ==============

    @rt("/api/compliance/sessions")
    def post_create_session(request):
        """Create a new review session."""
        try:
            data = request.json()
            req = CreateSessionRequest(**data)
        except Exception as e:
            return error_response(400, "validation_error", str(e))

        session_id = str(uuid.uuid4())
        now = datetime.utcnow()

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO review_session (id, submittal_id, project_id, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (session_id, req.submittal_id, req.project_id, SessionStatus.MATCHING.value, now, now),
        )
        conn.commit()
        conn.close()

        return JSONResponse(
            ReviewSessionResponse(
                id=session_id,
                submittal_id=req.submittal_id,
                project_id=req.project_id,
                status=SessionStatus.MATCHING,
                created_at=now,
                updated_at=now,
            ).model_dump(mode="json"),
            status_code=201,
        )

    @rt("/api/compliance/sessions")
    def get_list_sessions(
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ):
        """List review sessions with optional filtering."""
        conn = get_connection()
        cursor = conn.cursor()

        query = "SELECT * FROM review_session WHERE 1=1"
        params = []

        if project_id:
            query += " AND project_id = ?"
            params.append(project_id)
        if status:
            query += " AND status = ?"
            params.append(status)

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

        items = [
            ReviewSessionResponse(
                id=row["id"],
                submittal_id=row["submittal_id"],
                spec_section_id=row["spec_section_id"],
                project_id=row["project_id"],
                status=SessionStatus(row["status"]),
                overall_result=ComplianceOutcome(row["overall_result"]) if row["overall_result"] else None,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

        return JSONResponse(
            SessionListResponse(items=items, total=total, limit=limit, offset=offset).model_dump(
                mode="json"
            )
        )

    @rt("/api/compliance/sessions/{session_id}")
    def get_session(session_id: str):
        """Get session details."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM review_session WHERE id = ?", (session_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return error_response(404, "not_found", "Session not found")

        # Get requirements summary
        cursor.execute(
            "SELECT lane, COUNT(*) as count FROM requirement WHERE session_id = ? GROUP BY lane",
            (session_id,),
        )
        lane_counts = {r["lane"]: r["count"] for r in cursor.fetchall()}

        # Get results summary
        cursor.execute(
            """
            SELECT cr.outcome, COUNT(*) as count, SUM(cr.human_confirmed) as confirmed
            FROM compliance_result cr
            JOIN requirement r ON cr.requirement_id = r.id
            WHERE r.session_id = ?
            GROUP BY cr.outcome
            """,
            (session_id,),
        )
        result_rows = cursor.fetchall()
        conn.close()

        results_summary = ResultsSummary(
            total=sum(r["count"] for r in result_rows),
            confirmed=sum(r["confirmed"] or 0 for r in result_rows),
            unconfirmed=sum(r["count"] - (r["confirmed"] or 0) for r in result_rows),
            **{r["outcome"].lower(): r["count"] for r in result_rows if r["outcome"]},
        )

        return JSONResponse(
            ReviewSessionDetailResponse(
                id=row["id"],
                submittal_id=row["submittal_id"],
                spec_section_id=row["spec_section_id"],
                project_id=row["project_id"],
                status=SessionStatus(row["status"]),
                overall_result=ComplianceOutcome(row["overall_result"]) if row["overall_result"] else None,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                requirements_summary=RequirementsSummary(
                    total=sum(lane_counts.values()),
                    by_lane=lane_counts,
                ),
                results_summary=results_summary,
            ).model_dump(mode="json")
        )

    # ============== SPEC SECTION MATCHING ==============

    @rt("/api/compliance/sessions/{session_id}/match")
    def post_find_spec_sections(session_id: str):
        """Find matching spec sections (stub - returns mock suggestions)."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM review_session WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return error_response(404, "not_found", "Session not found")

        # Stub implementation - return mock suggestions
        suggestions = [
            SpecSectionSuggestionResponse(
                spec_section=SpecSectionResponse(
                    id="mock-spec-001",
                    section_number="23 05 00",
                    section_title="Common Work Results for HVAC",
                    page_numbers=[1, 2, 3],
                ),
                similarity_score=0.85,
                rank=1,
            ),
            SpecSectionSuggestionResponse(
                spec_section=SpecSectionResponse(
                    id="mock-spec-002",
                    section_number="23 23 00",
                    section_title="Refrigerant Piping",
                    page_numbers=[4, 5],
                ),
                similarity_score=0.72,
                rank=2,
            ),
        ]

        return JSONResponse(
            SpecSectionSuggestionsResponse(suggestions=suggestions).model_dump(mode="json")
        )

    @rt("/api/compliance/sessions/{session_id}/match/confirm")
    def post_confirm_spec_section(session_id: str, request):
        """Confirm spec section selection."""
        try:
            data = request.json()
            req = ConfirmSpecSectionRequest(**data)
        except Exception as e:
            return error_response(400, "validation_error", str(e))

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM review_session WHERE id = ?", (session_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return error_response(404, "not_found", "Session not found")

        now = datetime.utcnow()
        cursor.execute(
            """
            UPDATE review_session
            SET spec_section_id = ?, status = ?, updated_at = ?
            WHERE id = ?
            """,
            (req.spec_section_id, SessionStatus.EXTRACTING.value, now, session_id),
        )
        conn.commit()

        cursor.execute("SELECT * FROM review_session WHERE id = ?", (session_id,))
        updated_row = cursor.fetchone()
        conn.close()

        return JSONResponse(
            ReviewSessionResponse(
                id=updated_row["id"],
                submittal_id=updated_row["submittal_id"],
                spec_section_id=updated_row["spec_section_id"],
                project_id=updated_row["project_id"],
                status=SessionStatus(updated_row["status"]),
                created_at=updated_row["created_at"],
                updated_at=updated_row["updated_at"],
            ).model_dump(mode="json")
        )

    # ============== REQUIREMENT MANAGEMENT ==============

    @rt("/api/compliance/sessions/{session_id}/requirements")
    def get_list_requirements(
        session_id: str,
        lane: Optional[str] = None,
        status: Optional[str] = None,
    ):
        """List extracted requirements."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM review_session WHERE id = ?", (session_id,))
        if not cursor.fetchone():
            conn.close()
            return error_response(404, "not_found", "Session not found")

        query = "SELECT * FROM requirement WHERE session_id = ?"
        params = [session_id]

        if lane:
            query += " AND lane = ?"
            params.append(lane)
        if status:
            query += " AND status = ?"
            params.append(status)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        requirements = [
            RequirementResponse(
                id=r["id"],
                session_id=r["session_id"],
                text=r["text"],
                lane=LaneType(r["lane"]),
                source_page=r["source_page"],
                source_location=r["source_location"],
                attribute_type=r["attribute_type"],
                target_value=r["target_value"],
                status=RequirementStatus(r["status"]),
            )
            for r in rows
        ]

        grouped = {
            "auto_check": [r for r in requirements if r.lane == LaneType.AUTO_CHECK],
            "needs_scoping": [r for r in requirements if r.lane == LaneType.NEEDS_SCOPING],
            "informational": [r for r in requirements if r.lane == LaneType.INFORMATIONAL],
        }

        return JSONResponse(RequirementListResponse(**grouped).model_dump(mode="json"))

    @rt("/api/compliance/sessions/{session_id}/requirements/{requirement_id}")
    def get_requirement(session_id: str, requirement_id: str):
        """Get requirement details."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM requirement WHERE id = ? AND session_id = ?",
            (requirement_id, session_id),
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return error_response(404, "not_found", "Requirement not found")

        # Get compliance result if exists
        cursor.execute(
            "SELECT * FROM compliance_result WHERE requirement_id = ?", (requirement_id,)
        )
        result_row = cursor.fetchone()
        conn.close()

        compliance_result = None
        if result_row:
            compliance_result = ComplianceResultResponse(
                id=result_row["id"],
                requirement_id=result_row["requirement_id"],
                outcome=ComplianceOutcome(result_row["outcome"]),
                value_found=result_row["value_found"],
                confidence=result_row["confidence"],
                submittal_page=result_row["submittal_page"],
                human_confirmed=result_row["human_confirmed"],
                created_at=result_row["created_at"],
            )

        return JSONResponse(
            RequirementDetailResponse(
                id=row["id"],
                session_id=row["session_id"],
                text=row["text"],
                lane=LaneType(row["lane"]),
                source_page=row["source_page"],
                source_location=row["source_location"],
                attribute_type=row["attribute_type"],
                target_value=row["target_value"],
                status=RequirementStatus(row["status"]),
                compliance_result=compliance_result,
            ).model_dump(mode="json")
        )

    @rt("/api/compliance/sessions/{session_id}/requirements/{requirement_id}")
    def patch_requirement(session_id: str, requirement_id: str, request):
        """Update requirement (lane, target_value, status)."""
        try:
            data = request.json()
            req = UpdateRequirementRequest(**data)
        except Exception as e:
            return error_response(400, "validation_error", str(e))

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM requirement WHERE id = ? AND session_id = ?",
            (requirement_id, session_id),
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return error_response(404, "not_found", "Requirement not found")

        updates = []
        params = []

        if req.lane:
            updates.append("lane = ?")
            params.append(req.lane.value)
        if req.target_value:
            updates.append("target_value = ?")
            params.append(req.target_value)
        if req.status:
            updates.append("status = ?")
            params.append(req.status.value)

        if updates:
            params.append(requirement_id)
            cursor.execute(
                f"UPDATE requirement SET {', '.join(updates)} WHERE id = ?", params
            )
            conn.commit()

        cursor.execute("SELECT * FROM requirement WHERE id = ?", (requirement_id,))
        updated_row = cursor.fetchone()
        conn.close()

        return JSONResponse(
            RequirementResponse(
                id=updated_row["id"],
                session_id=updated_row["session_id"],
                text=updated_row["text"],
                lane=LaneType(updated_row["lane"]),
                source_page=updated_row["source_page"],
                source_location=updated_row["source_location"],
                attribute_type=updated_row["attribute_type"],
                target_value=updated_row["target_value"],
                status=RequirementStatus(updated_row["status"]),
            ).model_dump(mode="json")
        )

    # ============== COMPLIANCE VERIFICATION ==============

    @rt("/api/compliance/sessions/{session_id}/verify")
    def post_run_verification(session_id: str):
        """Run verification (stub - returns mock status)."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM review_session WHERE id = ?", (session_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return error_response(404, "not_found", "Session not found")

        # Check if there are requirements to verify
        cursor.execute(
            "SELECT COUNT(*) FROM requirement WHERE session_id = ? AND lane = ?",
            (session_id, LaneType.AUTO_CHECK.value),
        )
        count = cursor.fetchone()[0]
        conn.close()

        if count == 0:
            return error_response(400, "no_requirements", "No auto-check requirements to verify")

        # Stub: Return pending status
        return JSONResponse(
            VerificationStatusResponse(
                status="PENDING",
                total_requirements=count,
                verified_count=0,
                progress_percent=0.0,
            ).model_dump(mode="json"),
            status_code=202,
        )

    @rt("/api/compliance/sessions/{session_id}/verify/status")
    def get_verification_status(session_id: str):
        """Get verification progress."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM review_session WHERE id = ?", (session_id,))
        if not cursor.fetchone():
            conn.close()
            return error_response(404, "not_found", "Session not found")

        cursor.execute(
            "SELECT COUNT(*) FROM requirement WHERE session_id = ? AND lane = ?",
            (session_id, LaneType.AUTO_CHECK.value),
        )
        total = cursor.fetchone()[0]

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

        return JSONResponse(
            VerificationStatusResponse(
                status="COMPLETE" if verified >= total else "IN_PROGRESS",
                total_requirements=total,
                verified_count=verified,
                progress_percent=progress,
            ).model_dump(mode="json")
        )

    @rt("/api/compliance/sessions/{session_id}/results")
    def get_list_results(
        session_id: str,
        outcome: Optional[str] = None,
        needs_review: Optional[bool] = None,
    ):
        """List compliance results."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM review_session WHERE id = ?", (session_id,))
        if not cursor.fetchone():
            conn.close()
            return error_response(404, "not_found", "Session not found")

        query = """
            SELECT cr.* FROM compliance_result cr
            JOIN requirement r ON cr.requirement_id = r.id
            WHERE r.session_id = ?
        """
        params = [session_id]

        if outcome:
            query += " AND cr.outcome = ?"
            params.append(outcome)
        if needs_review is not None:
            if needs_review:
                query += " AND cr.human_confirmed = 0"
            else:
                query += " AND cr.human_confirmed = 1"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        items = [
            ComplianceResultResponse(
                id=r["id"],
                requirement_id=r["requirement_id"],
                outcome=ComplianceOutcome(r["outcome"]),
                value_found=r["value_found"],
                confidence=r["confidence"],
                submittal_page=r["submittal_page"],
                human_confirmed=r["human_confirmed"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

        return JSONResponse(
            ComplianceResultListResponse(items=items, total=len(items)).model_dump(mode="json")
        )

    @rt("/api/compliance/sessions/{session_id}/results/{result_id}")
    def get_result(session_id: str, result_id: str):
        """Get result details with evidence."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT cr.*, r.* FROM compliance_result cr
            JOIN requirement r ON cr.requirement_id = r.id
            WHERE r.session_id = ? AND cr.id = ?
            """,
            (session_id, result_id),
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return error_response(404, "not_found", "Result not found")

        # Get corrections
        cursor.execute(
            "SELECT * FROM correction WHERE result_id = ? ORDER BY created_at DESC", (result_id,)
        )
        corrections = cursor.fetchall()
        conn.close()

        return JSONResponse(
            ComplianceResultDetailResponse(
                id=row["id"],
                requirement_id=row["requirement_id"],
                outcome=ComplianceOutcome(row["outcome"]),
                value_found=row["value_found"],
                confidence=row["confidence"],
                submittal_page=row["submittal_page"],
                human_confirmed=row["human_confirmed"],
                created_at=row["created_at"],
                reasoning=row["reasoning"],
                requirement=RequirementResponse(
                    id=row["requirement_id"],
                    session_id=session_id,
                    text=row["text"],
                    lane=LaneType(row["lane"]),
                    source_page=row["source_page"],
                    source_location=row["source_location"],
                    attribute_type=row["attribute_type"],
                    target_value=row["target_value"],
                    status=RequirementStatus(row["status"]),
                ),
            ).model_dump(mode="json")
        )

    # ============== HUMAN REVIEW ==============

    @rt("/api/compliance/sessions/{session_id}/results/{result_id}/confirm")
    def post_confirm_result(session_id: str, result_id: str):
        """Confirm a verification result."""
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT cr.* FROM compliance_result cr
            JOIN requirement r ON cr.requirement_id = r.id
            WHERE r.session_id = ? AND cr.id = ?
            """,
            (session_id, result_id),
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return error_response(404, "not_found", "Result not found")

        cursor.execute(
            "UPDATE compliance_result SET human_confirmed = 1 WHERE id = ?", (result_id,)
        )
        conn.commit()

        cursor.execute("SELECT * FROM compliance_result WHERE id = ?", (result_id,))
        updated = cursor.fetchone()
        conn.close()

        return JSONResponse(
            ComplianceResultResponse(
                id=updated["id"],
                requirement_id=updated["requirement_id"],
                outcome=ComplianceOutcome(updated["outcome"]),
                value_found=updated["value_found"],
                confidence=updated["confidence"],
                submittal_page=updated["submittal_page"],
                human_confirmed=updated["human_confirmed"],
                created_at=updated["created_at"],
            ).model_dump(mode="json")
        )

    @rt("/api/compliance/sessions/{session_id}/results/{result_id}/correct")
    def post_correct_result(session_id: str, result_id: str, request):
        """Correct a verification result."""
        try:
            data = request.json()
            req = CorrectionRequest(**data)
        except Exception as e:
            return error_response(400, "validation_error", str(e))

        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT cr.* FROM compliance_result cr
            JOIN requirement r ON cr.requirement_id = r.id
            WHERE r.session_id = ? AND cr.id = ?
            """,
            (session_id, result_id),
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return error_response(404, "not_found", "Result not found")

        correction_id = str(uuid.uuid4())
        now = datetime.utcnow()

        original_value = json.dumps({
            "outcome": row["outcome"],
            "value_found": row["value_found"],
        })
        corrected_value = json.dumps({
            "outcome": req.corrected_outcome.value if req.corrected_outcome else row["outcome"],
            "value_found": req.corrected_value or row["value_found"],
        })

        cursor.execute(
            """
            INSERT INTO correction (id, result_id, correction_type, original_value, corrected_value, user_id, reason, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (correction_id, result_id, req.correction_type.value, original_value, corrected_value, "system", req.reason, now),
        )

        # Update the result
        if req.corrected_outcome:
            cursor.execute(
                "UPDATE compliance_result SET outcome = ?, human_confirmed = 1 WHERE id = ?",
                (req.corrected_outcome.value, result_id),
            )
        if req.corrected_value:
            cursor.execute(
                "UPDATE compliance_result SET value_found = ?, human_confirmed = 1 WHERE id = ?",
                (req.corrected_value, result_id),
            )

        conn.commit()

        cursor.execute("SELECT * FROM compliance_result WHERE id = ?", (result_id,))
        updated = cursor.fetchone()
        conn.close()

        return JSONResponse(
            ComplianceResultResponse(
                id=updated["id"],
                requirement_id=updated["requirement_id"],
                outcome=ComplianceOutcome(updated["outcome"]),
                value_found=updated["value_found"],
                confidence=updated["confidence"],
                submittal_page=updated["submittal_page"],
                human_confirmed=updated["human_confirmed"],
                created_at=updated["created_at"],
            ).model_dump(mode="json")
        )

    @rt("/api/compliance/sessions/{session_id}/complete")
    def post_complete_review(session_id: str):
        """Complete the review session."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM review_session WHERE id = ?", (session_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return error_response(404, "not_found", "Session not found")

        # Check all results are confirmed
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
            return error_response(
                400, "unconfirmed_results", f"{unconfirmed} results need to be confirmed"
            )

        # Determine overall result
        cursor.execute(
            """
            SELECT cr.outcome, COUNT(*) as count FROM compliance_result cr
            JOIN requirement r ON cr.requirement_id = r.id
            WHERE r.session_id = ?
            GROUP BY cr.outcome
            """,
            (session_id,),
        )
        outcomes = {r["outcome"]: r["count"] for r in cursor.fetchall()}

        if outcomes.get("FAIL", 0) > 0:
            overall = ComplianceOutcome.FAIL
        elif outcomes.get("NEEDS_REVIEW", 0) > 0:
            overall = ComplianceOutcome.NEEDS_REVIEW
        else:
            overall = ComplianceOutcome.PASS

        now = datetime.utcnow()
        cursor.execute(
            """
            UPDATE review_session
            SET status = ?, overall_result = ?, completed_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (SessionStatus.COMPLETED.value, overall.value, now, now, session_id),
        )
        conn.commit()

        cursor.execute("SELECT * FROM review_session WHERE id = ?", (session_id,))
        updated = cursor.fetchone()
        conn.close()

        return JSONResponse(
            ReviewSessionResponse(
                id=updated["id"],
                submittal_id=updated["submittal_id"],
                spec_section_id=updated["spec_section_id"],
                project_id=updated["project_id"],
                status=SessionStatus(updated["status"]),
                overall_result=ComplianceOutcome(updated["overall_result"]) if updated["overall_result"] else None,
                created_at=updated["created_at"],
                updated_at=updated["updated_at"],
            ).model_dump(mode="json")
        )

    # ============== REPORTING ==============

    @rt("/api/compliance/sessions/{session_id}/report")
    def get_report(session_id: str, format: str = "json"):
        """Get compliance report."""
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM review_session WHERE id = ?", (session_id,))
        session_row = cursor.fetchone()

        if not session_row:
            conn.close()
            return error_response(404, "not_found", "Session not found")

        if session_row["status"] != SessionStatus.COMPLETED.value:
            conn.close()
            return error_response(400, "not_complete", "Review not yet complete")

        # Get all results with requirements
        cursor.execute(
            """
            SELECT r.*, cr.outcome, cr.value_found, cr.submittal_page,
                   (SELECT COUNT(*) FROM correction WHERE result_id = cr.id) as correction_count
            FROM requirement r
            LEFT JOIN compliance_result cr ON r.id = cr.requirement_id
            WHERE r.session_id = ?
            """,
            (session_id,),
        )
        result_rows = cursor.fetchall()

        # Get total corrections
        cursor.execute(
            """
            SELECT COUNT(*) FROM correction c
            JOIN compliance_result cr ON c.result_id = cr.id
            JOIN requirement r ON cr.requirement_id = r.id
            WHERE r.session_id = ?
            """,
            (session_id,),
        )
        total_corrections = cursor.fetchone()[0]
        conn.close()

        # Build report
        results = []
        summary = {
            "total_requirements": len(result_rows),
            "passed": 0,
            "failed": 0,
            "not_applicable": 0,
            "not_found": 0,
        }

        for r in result_rows:
            outcome = r["outcome"]
            if outcome == "PASS":
                summary["passed"] += 1
            elif outcome == "FAIL":
                summary["failed"] += 1
            elif outcome == "NOT_FOUND":
                summary["not_found"] += 1
            if r["status"] == "NOT_APPLICABLE":
                summary["not_applicable"] += 1

            results.append(
                ReportResultItemResponse(
                    requirement_text=r["text"],
                    target_value=r["target_value"],
                    value_found=r["value_found"],
                    outcome=ComplianceOutcome(outcome) if outcome else ComplianceOutcome.NOT_FOUND,
                    source_page=r["source_page"],
                    submittal_page=r["submittal_page"],
                    was_corrected=r["correction_count"] > 0,
                )
            )

        report = ComplianceReportResponse(
            session_id=session_id,
            submittal_id=session_row["submittal_id"],
            overall_result=ComplianceOutcome(session_row["overall_result"]) if session_row["overall_result"] else None,
            generated_at=datetime.utcnow(),
            reviewer_id=session_row["reviewer_id"],
            summary=ReportSummaryResponse(**summary),
            results=results,
            corrections_made=total_corrections,
        )

        if format == "html":
            # Return HTML format
            html = f"""
            <html>
            <head><title>Compliance Report - {session_id}</title></head>
            <body>
            <h1>Compliance Report</h1>
            <p>Session: {session_id}</p>
            <p>Overall Result: {report.overall_result}</p>
            <h2>Summary</h2>
            <ul>
                <li>Total Requirements: {summary['total_requirements']}</li>
                <li>Passed: {summary['passed']}</li>
                <li>Failed: {summary['failed']}</li>
                <li>Not Found: {summary['not_found']}</li>
            </ul>
            </body>
            </html>
            """
            return html

        return JSONResponse(report.model_dump(mode="json"))

    # ============== EVIDENCE ==============

    @rt("/api/compliance/evidence/{session_id}/{requirement_id}/spec")
    def get_spec_evidence(session_id: str, requirement_id: str):
        """Get spec evidence image."""
        import os
        from pathlib import Path
        from fasthtml.common import FileResponse

        evidence_path = Path(f"static/compliance/evidence/{session_id}/{requirement_id}/spec_context.jpg")
        if not evidence_path.exists():
            return error_response(404, "not_found", "Spec evidence not found")

        return FileResponse(evidence_path)

    @rt("/api/compliance/evidence/{session_id}/{requirement_id}/submittal")
    def get_submittal_evidence(session_id: str, requirement_id: str):
        """Get submittal evidence image."""
        from pathlib import Path
        from fasthtml.common import FileResponse

        evidence_path = Path(f"static/compliance/evidence/{session_id}/{requirement_id}/submittal_region.jpg")
        if not evidence_path.exists():
            return error_response(404, "not_found", "Submittal evidence not found")

        return FileResponse(evidence_path)
