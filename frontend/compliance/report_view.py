"""
Report view UI components for displaying compliance reports.
"""

from fasthtml.components import Div, H1, H2, H3, P, Span, Table, Thead, Tbody, Tr, Th, Td
from fasthtml.xtend import A
from lucide_fasthtml import Lucide
from shad4fast import Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle


def ReportView(session_id: str, report: dict = None):
    """
    Component for displaying a compliance report.
    """
    if report is None:
        return ReportLoading(session_id)

    return Div(
        ReportHeader(report),
        ReportSummary(report.get("summary", {})),
        ResultsBreakdown(report.get("results", [])),
        ReportActions(session_id),
        id="report-view",
    )


def ReportHeader(report: dict):
    """Report header with overall status."""
    overall_result = report.get("overall_result", "UNKNOWN")
    result_styles = {
        "PASS": {"bg": "bg-green-100", "text": "text-green-800", "icon": "check-circle"},
        "FAIL": {"bg": "bg-red-100", "text": "text-red-800", "icon": "x-circle"},
        "NEEDS_REVIEW": {"bg": "bg-yellow-100", "text": "text-yellow-800", "icon": "alert-circle"},
    }
    styles = result_styles.get(overall_result, {"bg": "bg-gray-100", "text": "text-gray-800", "icon": "help-circle"})

    return Div(
        Div(
            H1("Compliance Report", cls="text-2xl font-bold"),
            Div(
                Lucide(styles["icon"], cls=f"w-8 h-8 {styles['text']}"),
                Span(overall_result, cls=f"text-2xl font-bold ml-2 {styles['text']}"),
                cls=f"flex items-center px-4 py-2 rounded-lg {styles['bg']}",
            ),
            cls="flex justify-between items-center",
        ),
        Div(
            Div(
                P("Session:", cls="text-sm text-muted-foreground"),
                P(report.get("session_id", "")[:20] + "...", cls="font-mono text-sm"),
            ),
            Div(
                P("Submittal:", cls="text-sm text-muted-foreground"),
                P(report.get("submittal_id", "N/A"), cls="font-mono text-sm"),
            ),
            Div(
                P("Generated:", cls="text-sm text-muted-foreground"),
                P(report.get("generated_at", "")[:19], cls="text-sm"),
            ),
            Div(
                P("Reviewer:", cls="text-sm text-muted-foreground"),
                P(report.get("reviewer_id", "N/A"), cls="text-sm"),
            ),
            cls="grid grid-cols-4 gap-4 mt-4 py-4 border-b",
        ),
        cls="mb-6",
    )


def ReportSummary(summary: dict):
    """Summary statistics cards."""
    total = summary.get("total_requirements", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    not_found = summary.get("not_found", 0)
    not_applicable = summary.get("not_applicable", 0)

    return Div(
        H2("Summary", cls="text-lg font-bold mb-4"),
        Div(
            SummaryCard("Total Requirements", total, "file-text", "bg-gray-50"),
            SummaryCard("Passed", passed, "check-circle", "bg-green-50", "text-green-600"),
            SummaryCard("Failed", failed, "x-circle", "bg-red-50", "text-red-600"),
            SummaryCard("Not Found", not_found, "help-circle", "bg-gray-50", "text-gray-500"),
            SummaryCard("Not Applicable", not_applicable, "minus-circle", "bg-orange-50", "text-orange-500"),
            cls="grid grid-cols-5 gap-4",
        ),
        cls="mb-8",
    )


def SummaryCard(label: str, count: int, icon: str, bg_cls: str, text_cls: str = ""):
    """Individual summary statistic card."""
    return Card(
        CardContent(
            Div(
                Lucide(icon, cls=f"w-8 h-8 mb-2 {text_cls}"),
                P(str(count), cls=f"text-3xl font-bold {text_cls}"),
                P(label, cls="text-sm text-muted-foreground"),
                cls="text-center py-4",
            ),
        ),
        cls=bg_cls,
    )


def ResultsBreakdown(results: list):
    """Detailed results table."""
    if not results:
        return Div(
            P("No results to display.", cls="text-muted-foreground text-center py-8"),
        )

    return Div(
        Div(
            H2("Detailed Findings", cls="text-lg font-bold"),
            Span(f"{len(results)} items", cls="text-muted-foreground"),
            cls="flex justify-between items-center mb-4",
        ),
        Div(
            Table(
                Thead(
                    Tr(
                        Th("Requirement", cls="text-left py-3"),
                        Th("Target", cls="text-left py-3"),
                        Th("Found", cls="text-left py-3"),
                        Th("Outcome", cls="text-left py-3"),
                        Th("Page", cls="text-left py-3"),
                        Th("Corrected", cls="text-center py-3"),
                    ),
                    cls="bg-gray-50",
                ),
                Tbody(
                    *[ResultRow(r) for r in results],
                ),
                cls="w-full",
            ),
            cls="overflow-x-auto",
        ),
        cls="mb-8",
    )


def ResultRow(result: dict):
    """Single result row in the table."""
    outcome = result.get("outcome", "UNKNOWN")
    outcome_styles = {
        "PASS": "bg-green-100 text-green-800",
        "FAIL": "bg-red-100 text-red-800",
        "NOT_FOUND": "bg-gray-100 text-gray-600",
        "NEEDS_REVIEW": "bg-yellow-100 text-yellow-800",
    }

    text = result.get("requirement_text", "")
    truncated = text[:60] + "..." if len(text) > 60 else text

    return Tr(
        Td(
            Span(truncated, title=text),
            cls="py-3 pr-4",
        ),
        Td(
            Span(result.get("target_value") or "N/A", cls="font-mono text-sm"),
            cls="py-3",
        ),
        Td(
            Span(result.get("value_found") or "Not found", cls="font-mono text-sm"),
            cls="py-3",
        ),
        Td(
            Badge(outcome, cls=outcome_styles.get(outcome, "bg-gray-100")),
            cls="py-3",
        ),
        Td(
            Span(str(result.get("source_page", "?")), cls="text-muted-foreground"),
            cls="py-3",
        ),
        Td(
            Lucide("check", cls="w-4 h-4 text-blue-500 mx-auto") if result.get("was_corrected") else Span("-", cls="text-muted-foreground block text-center"),
            cls="py-3",
        ),
        cls="border-b hover:bg-gray-50",
    )


def ReportActions(session_id: str):
    """Action buttons for report."""
    return Div(
        Button(
            Lucide("download", cls="w-4 h-4 mr-2"),
            "Download JSON",
            variant="outline",
            hx_get=f"/api/compliance/sessions/{session_id}/report?format=json",
            hx_target="_blank",
        ),
        Button(
            Lucide("file-text", cls="w-4 h-4 mr-2"),
            "Download HTML",
            variant="outline",
            hx_get=f"/api/compliance/sessions/{session_id}/report?format=html",
            hx_target="_blank",
        ),
        Button(
            "Back to Dashboard",
            variant="outline",
            hx_get="/compliance",
            hx_target="#main-content",
        ),
        cls="flex gap-4",
    )


def ReportLoading(session_id: str):
    """Loading state for report."""
    return Div(
        Div(
            Lucide("loader-2", cls="w-8 h-8 animate-spin text-muted-foreground"),
            P("Generating report...", cls="mt-2 text-muted-foreground"),
            cls="flex flex-col items-center py-12",
        ),
        hx_get=f"/api/compliance/sessions/{session_id}/report",
        hx_trigger="load",
        hx_target="this",
        hx_swap="outerHTML",
        id="report-view",
    )
