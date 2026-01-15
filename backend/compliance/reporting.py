"""
Reporting service for generating compliance reports.
"""

from datetime import datetime
from typing import Optional

from backend.models.database import get_connection
from backend.models.enums import SessionStatus, ComplianceOutcome


class ReportService:
    """Service for generating compliance reports."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path

    def generate_report(self, session_id: str) -> dict:
        """
        Generate a compliance report for a completed session.

        Args:
            session_id: The session ID

        Returns:
            Dict containing the full report data
        """
        conn = get_connection(self.db_path)
        cursor = conn.cursor()

        # Get session
        cursor.execute("SELECT * FROM review_session WHERE id = ?", (session_id,))
        session = cursor.fetchone()

        if not session:
            conn.close()
            raise ValueError(f"Session {session_id} not found")

        if session["status"] != SessionStatus.COMPLETED.value:
            conn.close()
            raise ValueError("Review not yet complete")

        # Get all requirements with results
        cursor.execute(
            """
            SELECT r.*, cr.outcome, cr.value_found, cr.submittal_page, cr.confidence,
                   (SELECT COUNT(*) FROM correction WHERE result_id = cr.id) as correction_count
            FROM requirement r
            LEFT JOIN compliance_result cr ON r.id = cr.requirement_id
            WHERE r.session_id = ?
            ORDER BY r.source_page, r.created_at
            """,
            (session_id,),
        )
        requirements = cursor.fetchall()

        # Count corrections
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
        summary = self.calculate_summary(requirements)
        results = self._build_results_list(requirements)

        return {
            "session_id": session_id,
            "submittal_id": session["submittal_id"],
            "spec_section_id": session["spec_section_id"],
            "project_id": session["project_id"],
            "overall_result": session["overall_result"],
            "reviewer_id": session["reviewer_id"],
            "completed_at": session["completed_at"],
            "generated_at": datetime.utcnow().isoformat(),
            "summary": summary,
            "results": results,
            "corrections_made": total_corrections,
        }

    def calculate_summary(self, requirements: list) -> dict:
        """
        Calculate summary statistics from requirements.

        Args:
            requirements: List of requirement rows with outcomes

        Returns:
            Dict with counts by category
        """
        summary = {
            "total_requirements": len(requirements),
            "passed": 0,
            "failed": 0,
            "not_applicable": 0,
            "not_found": 0,
        }

        for r in requirements:
            outcome = r["outcome"]
            status = r["status"]

            if status == "NOT_APPLICABLE":
                summary["not_applicable"] += 1
            elif outcome == "PASS":
                summary["passed"] += 1
            elif outcome == "FAIL":
                summary["failed"] += 1
            elif outcome == "NOT_FOUND":
                summary["not_found"] += 1

        return summary

    def format_report_json(self, report: dict) -> dict:
        """Format report as JSON."""
        return report

    def format_report_html(self, report: dict) -> str:
        """
        Format report as HTML.

        Args:
            report: The report data

        Returns:
            HTML string
        """
        summary = report.get("summary", {})
        results = report.get("results", [])
        overall = report.get("overall_result", "UNKNOWN")

        overall_color = {
            "PASS": "#22c55e",
            "FAIL": "#ef4444",
            "NEEDS_REVIEW": "#f59e0b",
        }.get(overall, "#6b7280")

        results_html = ""
        for r in results:
            outcome = r.get("outcome", "UNKNOWN")
            outcome_color = {
                "PASS": "#22c55e",
                "FAIL": "#ef4444",
                "NOT_FOUND": "#6b7280",
                "NEEDS_REVIEW": "#f59e0b",
            }.get(outcome, "#6b7280")

            results_html += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{r.get('requirement_text', '')[:80]}...</td>
                <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{r.get('target_value', 'N/A')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{r.get('value_found', 'N/A')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #e5e7eb; color: {outcome_color}; font-weight: bold;">{outcome}</td>
                <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{r.get('source_page', 'N/A')}</td>
                <td style="padding: 8px; border-bottom: 1px solid #e5e7eb;">{'Yes' if r.get('was_corrected') else 'No'}</td>
            </tr>
            """

        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Compliance Report - {report.get('session_id', 'Unknown')}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 40px; color: #374151; }}
        h1 {{ color: #111827; }}
        .header {{ border-bottom: 2px solid #e5e7eb; padding-bottom: 20px; margin-bottom: 20px; }}
        .overall {{ display: inline-block; padding: 8px 16px; border-radius: 8px; font-weight: bold; font-size: 24px; color: white; background-color: {overall_color}; }}
        .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin: 20px 0; }}
        .summary-item {{ background: #f9fafb; padding: 16px; border-radius: 8px; text-align: center; }}
        .summary-item h3 {{ margin: 0 0 8px 0; color: #6b7280; font-size: 14px; }}
        .summary-item p {{ margin: 0; font-size: 24px; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin-top: 20px; }}
        th {{ text-align: left; padding: 12px 8px; background: #f3f4f6; border-bottom: 2px solid #e5e7eb; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #e5e7eb; color: #6b7280; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Compliance Report</h1>
        <p><strong>Session:</strong> {report.get('session_id', 'Unknown')}</p>
        <p><strong>Submittal:</strong> {report.get('submittal_id', 'Unknown')}</p>
        <p><strong>Generated:</strong> {report.get('generated_at', 'Unknown')}</p>
    </div>

    <h2>Overall Result</h2>
    <div class="overall">{overall}</div>

    <h2>Summary</h2>
    <div class="summary">
        <div class="summary-item">
            <h3>Total Requirements</h3>
            <p>{summary.get('total_requirements', 0)}</p>
        </div>
        <div class="summary-item">
            <h3>Passed</h3>
            <p style="color: #22c55e;">{summary.get('passed', 0)}</p>
        </div>
        <div class="summary-item">
            <h3>Failed</h3>
            <p style="color: #ef4444;">{summary.get('failed', 0)}</p>
        </div>
        <div class="summary-item">
            <h3>Not Found</h3>
            <p style="color: #6b7280;">{summary.get('not_found', 0)}</p>
        </div>
    </div>

    <h2>Detailed Results</h2>
    <table>
        <thead>
            <tr>
                <th>Requirement</th>
                <th>Target Value</th>
                <th>Found Value</th>
                <th>Outcome</th>
                <th>Spec Page</th>
                <th>Corrected</th>
            </tr>
        </thead>
        <tbody>
            {results_html}
        </tbody>
    </table>

    <div class="footer">
        <p>Report generated by Submittal Compliance Checking System</p>
        <p>Corrections made: {report.get('corrections_made', 0)}</p>
    </div>
</body>
</html>
        """

    def _build_results_list(self, requirements: list) -> list[dict]:
        """Build list of result items for the report."""
        results = []
        for r in requirements:
            results.append({
                "requirement_text": r["text"],
                "target_value": r["target_value"],
                "value_found": r["value_found"],
                "outcome": r["outcome"] or "NOT_VERIFIED",
                "source_page": r["source_page"],
                "submittal_page": r["submittal_page"],
                "was_corrected": r["correction_count"] > 0,
            })
        return results
