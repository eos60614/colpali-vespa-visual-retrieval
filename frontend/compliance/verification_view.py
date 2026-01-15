"""
Verification view UI components for displaying verification results with evidence.
"""

from fasthtml.components import Div, H2, H3, P, Span, Img
from fasthtml.xtend import A
from lucide_fasthtml import Lucide
from shad4fast import Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Progress


def VerificationView(session_id: str, status: dict = None, results: list = None):
    """
    Component for displaying verification results with visual evidence.
    """
    if status is None:
        status = {"status": "PENDING", "total_requirements": 0, "verified_count": 0, "progress_percent": 0}

    return Div(
        H2("Verification Results", cls="text-xl font-bold mb-4"),
        VerificationProgress(session_id, status),
        Div(
            ResultsList(session_id, results or []),
            cls="mt-6",
        ),
        id="verification-view",
    )


def VerificationProgress(session_id: str, status: dict):
    """Progress indicator for verification."""
    progress = status.get("progress_percent", 0)
    total = status.get("total_requirements", 0)
    verified = status.get("verified_count", 0)
    status_text = status.get("status", "PENDING")

    status_colors = {
        "PENDING": "text-gray-500",
        "IN_PROGRESS": "text-blue-500",
        "COMPLETE": "text-green-500",
        "FAILED": "text-red-500",
    }

    return Card(
        CardContent(
            Div(
                Div(
                    Span("Verification Progress", cls="font-medium"),
                    Badge(status_text, cls=status_colors.get(status_text, "")),
                    cls="flex justify-between items-center mb-2",
                ),
                Progress(value=int(progress), cls="h-2"),
                Div(
                    Span(f"{verified} of {total} requirements verified", cls="text-sm text-muted-foreground"),
                    Span(f"{progress:.0f}%", cls="text-sm font-medium"),
                    cls="flex justify-between mt-2",
                ),
                cls="py-4",
            ),
            Div(
                Button(
                    Lucide("play", cls="w-4 h-4 mr-2"),
                    "Start Verification",
                    variant="default",
                    hx_post=f"/api/compliance/sessions/{session_id}/verify",
                    hx_target="#verification-view",
                    hx_swap="outerHTML",
                )
                if status_text == "PENDING"
                else None,
                Button(
                    Lucide("refresh-cw", cls="w-4 h-4 mr-2"),
                    "Refresh Status",
                    variant="outline",
                    hx_get=f"/api/compliance/sessions/{session_id}/verify/status",
                    hx_target="#verification-view",
                    hx_swap="outerHTML",
                )
                if status_text == "IN_PROGRESS"
                else None,
                cls="flex gap-2",
            ),
        ),
    )


def ResultsList(session_id: str, results: list):
    """List of verification results."""
    if not results:
        return Div(
            P("No verification results yet. Start verification to check requirements.", cls="text-muted-foreground text-center py-8"),
        )

    # Group by outcome
    passed = [r for r in results if r.get("outcome") == "PASS"]
    failed = [r for r in results if r.get("outcome") == "FAIL"]
    not_found = [r for r in results if r.get("outcome") == "NOT_FOUND"]
    needs_review = [r for r in results if r.get("outcome") == "NEEDS_REVIEW"]

    return Div(
        ResultsSummary(passed, failed, not_found, needs_review),
        Div(
            *[ComplianceResultCard(session_id, r) for r in results],
            cls="space-y-4 mt-6",
        ),
    )


def ResultsSummary(passed: list, failed: list, not_found: list, needs_review: list):
    """Summary of verification results."""
    return Div(
        Div(
            Badge(f"{len(passed)} Passed", cls="bg-green-100 text-green-800"),
            Badge(f"{len(failed)} Failed", cls="bg-red-100 text-red-800"),
            Badge(f"{len(not_found)} Not Found", cls="bg-gray-100 text-gray-600"),
            Badge(f"{len(needs_review)} Needs Review", cls="bg-yellow-100 text-yellow-800"),
            cls="flex flex-wrap gap-2",
        ),
    )


def ComplianceResultCard(session_id: str, result: dict):
    """Individual compliance result card with evidence and bounding box overlays."""
    result_id = result.get("id", "")
    outcome = result.get("outcome", "PENDING")
    confidence = result.get("confidence", 0)
    value_found = result.get("value_found")
    submittal_page = result.get("submittal_page")
    submittal_location = result.get("submittal_location")
    human_confirmed = result.get("human_confirmed", False)
    requirement = result.get("requirement", {})
    spec_location = requirement.get("source_location")

    outcome_styles = {
        "PASS": {"bg": "bg-green-50", "border": "border-l-green-500", "badge": "bg-green-100 text-green-800"},
        "FAIL": {"bg": "bg-red-50", "border": "border-l-red-500", "badge": "bg-red-100 text-red-800"},
        "NOT_FOUND": {"bg": "bg-gray-50", "border": "border-l-gray-400", "badge": "bg-gray-100 text-gray-600"},
        "NEEDS_REVIEW": {"bg": "bg-yellow-50", "border": "border-l-yellow-500", "badge": "bg-yellow-100 text-yellow-800"},
    }
    styles = outcome_styles.get(outcome, outcome_styles["NEEDS_REVIEW"])

    return Div(
        Div(
            Div(
                Badge(outcome, cls=styles["badge"]),
                ConfidenceIndicator(confidence),
                Badge("Confirmed", variant="outline", cls="text-green-600") if human_confirmed else None,
                cls="flex gap-2 items-center",
            ),
            P(requirement.get("text", "Unknown requirement"), cls="font-medium mt-2"),
            Div(
                Span(f"Target: {requirement.get('target_value', 'N/A')}", cls="text-sm"),
                Span(f"Found: {value_found or 'Not found'}", cls="text-sm ml-4"),
                Span(f"Page: {submittal_page or 'N/A'}", cls="text-sm text-muted-foreground ml-4"),
                cls="mt-2",
            ),
            cls="mb-4",
        ),
        EvidenceViewer(
            session_id=session_id,
            requirement_id=result.get("requirement_id", ""),
            spec_location=spec_location,
            submittal_location=submittal_location,
        ),
        Div(
            Button(
                Lucide("check", cls="w-4 h-4 mr-2"),
                "Confirm",
                variant="outline",
                size="sm",
                hx_post=f"/api/compliance/sessions/{session_id}/results/{result_id}/confirm",
                hx_target=f"#result-{result_id}",
                hx_swap="outerHTML",
            )
            if not human_confirmed
            else None,
            Button(
                Lucide("edit", cls="w-4 h-4 mr-2"),
                "Override",
                variant="outline",
                size="sm",
            ),
            cls="flex gap-2 mt-4",
        ),
        cls=f"p-4 rounded-lg border-l-4 {styles['border']} {styles['bg']}",
        id=f"result-{result_id}",
    )


def ConfidenceIndicator(confidence: float):
    """Visual indicator for confidence score."""
    if confidence >= 0.9:
        color = "text-green-600"
        label = "High"
    elif confidence >= 0.7:
        color = "text-yellow-600"
        label = "Medium"
    else:
        color = "text-red-600"
        label = "Low"

    return Span(
        f"{confidence:.0%} ({label})",
        cls=f"text-sm font-medium {color}",
    )


def BoundingBoxOverlay(bounding_box: dict = None, color: str = "blue"):
    """
    Overlay component that highlights a region with a bounding box.
    Uses CSS positioning with normalized coordinates (0-1).
    """
    if not bounding_box:
        return None

    # Get CSS positioning from bounding box (coordinates are 0-1 normalized)
    left = f"{bounding_box.get('x', 0) * 100}%"
    top = f"{bounding_box.get('y', 0) * 100}%"
    width = f"{bounding_box.get('width', 0) * 100}%"
    height = f"{bounding_box.get('height', 0) * 100}%"

    color_classes = {
        "blue": "border-blue-500 bg-blue-500/20",
        "green": "border-green-500 bg-green-500/20",
        "red": "border-red-500 bg-red-500/20",
        "yellow": "border-yellow-500 bg-yellow-500/20",
    }
    colors = color_classes.get(color, color_classes["blue"])

    label = bounding_box.get("label")
    confidence = bounding_box.get("confidence")

    return Div(
        Span(
            f"{label}" if label else "",
            Span(f" ({confidence:.0%})" if confidence else "", cls="text-xs"),
            cls="absolute -top-5 left-0 text-xs font-medium whitespace-nowrap",
        ) if label or confidence else None,
        cls=f"absolute border-2 rounded {colors} pointer-events-none",
        style=f"left: {left}; top: {top}; width: {width}; height: {height};",
    )


def EvidenceViewer(session_id: str, requirement_id: str, spec_location: dict = None, submittal_location: dict = None):
    """
    Side-by-side evidence image viewer with bounding box overlays.

    Args:
        session_id: The review session ID
        requirement_id: The requirement ID
        spec_location: BoundingBox dict for spec requirement location
        submittal_location: BoundingBox dict for submittal match location
    """
    return Div(
        H3("Visual Evidence", cls="text-sm font-medium mb-2"),
        Div(
            Div(
                P("Spec Requirement", cls="text-xs text-muted-foreground mb-1"),
                Div(
                    Img(
                        src=f"/api/compliance/evidence/{session_id}/{requirement_id}/spec",
                        alt="Spec context",
                        cls="w-full h-auto border rounded",
                        loading="lazy",
                    ),
                    BoundingBoxOverlay(spec_location, color="blue"),
                    cls="bg-gray-100 p-2 rounded min-h-[100px] flex items-center justify-center relative",
                ),
                cls="flex-1",
            ),
            Div(
                P("Submittal Evidence", cls="text-xs text-muted-foreground mb-1"),
                Div(
                    Img(
                        src=f"/api/compliance/evidence/{session_id}/{requirement_id}/submittal",
                        alt="Submittal region",
                        cls="w-full h-auto border rounded",
                        loading="lazy",
                    ),
                    BoundingBoxOverlay(submittal_location, color="green"),
                    cls="bg-gray-100 p-2 rounded min-h-[100px] flex items-center justify-center relative",
                ),
                cls="flex-1",
            ),
            cls="grid grid-cols-2 gap-4",
        ),
    )


def VerificationLoading():
    """Loading state for verification."""
    return Div(
        Div(
            Lucide("loader-2", cls="w-12 h-12 animate-spin text-blue-500"),
            P("Verifying requirements against submittal...", cls="mt-4 text-muted-foreground"),
            P("This may take a few moments", cls="text-sm text-muted-foreground"),
            cls="flex flex-col items-center py-12",
        ),
        id="verification-view",
    )
