"""
Review panel UI components for human review and override workflow.
"""

from fasthtml.components import Div, H2, H3, P, Span, Form, Input, Label, Textarea
from fasthtml.xtend import A
from lucide_fasthtml import Lucide
from shad4fast import Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Select, SelectContent, SelectItem, SelectTrigger, SelectValue, Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger


def ReviewPanel(session_id: str, review_status: dict = None):
    """
    Main review panel for confirming and correcting verification results.
    """
    if review_status is None:
        review_status = {"total": 0, "confirmed": 0, "unconfirmed": 0, "ready_to_complete": False}

    return Div(
        H2("Human Review", cls="text-xl font-bold mb-4"),
        ReviewProgress(session_id, review_status),
        Div(
            P(
                "Review each verification result below. Confirm accurate results or override incorrect ones.",
                cls="text-muted-foreground",
            ),
            cls="mt-4 mb-6",
        ),
        id="review-panel",
    )


def ReviewProgress(session_id: str, status: dict):
    """Review progress indicator with completion button."""
    total = status.get("total", 0)
    confirmed = status.get("confirmed", 0)
    unconfirmed = status.get("unconfirmed", 0)
    ready = status.get("ready_to_complete", False)

    progress = (confirmed / total * 100) if total > 0 else 0

    return Card(
        CardContent(
            Div(
                Div(
                    Span("Review Progress", cls="font-medium"),
                    Badge(f"{confirmed}/{total} confirmed", variant="outline"),
                    cls="flex justify-between items-center mb-4",
                ),
                Div(
                    Div(
                        cls=f"h-2 bg-green-500 rounded",
                        style=f"width: {progress}%",
                    ),
                    cls="h-2 bg-gray-200 rounded w-full",
                ),
                Div(
                    Badge(f"{unconfirmed} remaining", cls="bg-yellow-100 text-yellow-800")
                    if unconfirmed > 0
                    else Badge("All confirmed", cls="bg-green-100 text-green-800"),
                    cls="mt-2",
                ),
                cls="py-4",
            ),
            Div(
                Button(
                    Lucide("check-circle", cls="w-4 h-4 mr-2"),
                    "Complete Review",
                    variant="default",
                    disabled=not ready,
                    hx_post=f"/api/compliance/sessions/{session_id}/complete",
                    hx_target="#main-content",
                )
                if ready
                else Button(
                    "Complete Review",
                    variant="outline",
                    disabled=True,
                    title=f"{unconfirmed} results need to be confirmed",
                ),
                cls="flex gap-2",
            ),
        ),
    )


def ConfirmButton(session_id: str, result_id: str):
    """Confirm button for a result."""
    return Button(
        Lucide("check", cls="w-4 h-4 mr-2"),
        "Confirm",
        variant="outline",
        size="sm",
        hx_post=f"/api/compliance/sessions/{session_id}/results/{result_id}/confirm",
        hx_target=f"#result-{result_id}",
        hx_swap="outerHTML",
    )


def OverrideButton(session_id: str, result_id: str, current_outcome: str):
    """Override button that opens correction modal."""
    return Dialog(
        DialogTrigger(
            Button(
                Lucide("edit", cls="w-4 h-4 mr-2"),
                "Override",
                variant="outline",
                size="sm",
            ),
        ),
        CorrectionModal(session_id, result_id, current_outcome),
    )


def CorrectionModal(session_id: str, result_id: str, current_outcome: str):
    """Modal for entering correction details."""
    return DialogContent(
        DialogHeader(
            DialogTitle("Override Result"),
            DialogDescription("Provide the correct outcome and reason for override"),
        ),
        Form(
            Div(
                Label("New Outcome", htmlFor="corrected_outcome"),
                Select(
                    SelectTrigger(
                        SelectValue(placeholder="Select outcome"),
                        cls="w-full",
                    ),
                    SelectContent(
                        SelectItem("PASS", value="PASS"),
                        SelectItem("FAIL", value="FAIL"),
                        SelectItem("NOT_FOUND", value="NOT_FOUND"),
                    ),
                    name="corrected_outcome",
                    cls="mt-1",
                ),
                cls="mb-4",
            ),
            Div(
                Label("Correct Value (optional)", htmlFor="corrected_value"),
                Input(
                    type="text",
                    name="corrected_value",
                    id="corrected_value",
                    placeholder="Enter the actual value found",
                    cls="mt-1",
                ),
                cls="mb-4",
            ),
            Div(
                Label("Reason for Override", htmlFor="reason"),
                Textarea(
                    name="reason",
                    id="reason",
                    placeholder="Explain why this correction is needed",
                    cls="mt-1",
                    rows="3",
                ),
                cls="mb-4",
            ),
            Div(
                Input(type="hidden", name="correction_type", value="status"),
                Button(
                    "Save Correction",
                    type="submit",
                    variant="default",
                ),
                Button(
                    "Cancel",
                    type="button",
                    variant="outline",
                    cls="ml-2",
                ),
                cls="flex gap-2",
            ),
            hx_post=f"/api/compliance/sessions/{session_id}/results/{result_id}/correct",
            hx_target=f"#result-{result_id}",
            hx_swap="outerHTML",
        ),
        cls="max-w-md",
    )


def CorrectionHistory(corrections: list):
    """Display correction history for a result."""
    if not corrections:
        return None

    return Div(
        H3("Correction History", cls="text-sm font-medium mt-4 mb-2"),
        Div(
            *[CorrectionItem(c) for c in corrections],
            cls="space-y-2",
        ),
    )


def CorrectionItem(correction: dict):
    """Single correction history item."""
    return Div(
        Div(
            Badge(correction.get("correction_type", "unknown"), variant="outline", cls="text-xs"),
            Span(correction.get("created_at", "")[:10], cls="text-xs text-muted-foreground ml-2"),
            cls="flex items-center",
        ),
        P(correction.get("reason", "No reason provided"), cls="text-sm mt-1"),
        Span(f"By: {correction.get('user_id', 'unknown')}", cls="text-xs text-muted-foreground"),
        cls="p-2 bg-gray-50 rounded text-sm",
    )


def ReviewCompleteMessage(session_id: str, overall_result: str):
    """Message displayed after review is completed."""
    result_styles = {
        "PASS": {"bg": "bg-green-50", "text": "text-green-700", "icon": "check-circle"},
        "FAIL": {"bg": "bg-red-50", "text": "text-red-700", "icon": "x-circle"},
        "NEEDS_REVIEW": {"bg": "bg-yellow-50", "text": "text-yellow-700", "icon": "alert-circle"},
    }
    styles = result_styles.get(overall_result, result_styles["NEEDS_REVIEW"])

    return Card(
        CardContent(
            Div(
                Lucide(styles["icon"], cls=f"w-16 h-16 mx-auto {styles['text']}"),
                H2("Review Completed", cls="text-2xl font-bold text-center mt-4"),
                P(
                    f"Overall Result: {overall_result}",
                    cls=f"text-center text-lg font-medium mt-2 {styles['text']}",
                ),
                Div(
                    Button(
                        Lucide("file-text", cls="w-4 h-4 mr-2"),
                        "View Report",
                        variant="default",
                        hx_get=f"/compliance/session/{session_id}/report",
                        hx_target="#main-content",
                    ),
                    Button(
                        "Back to Dashboard",
                        variant="outline",
                        hx_get="/compliance",
                        hx_target="#main-content",
                    ),
                    cls="flex justify-center gap-4 mt-6",
                ),
                cls=f"py-8 {styles['bg']} rounded-lg",
            ),
        ),
    )
