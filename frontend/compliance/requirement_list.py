"""
Requirement list UI components for displaying requirements organized by lane.
"""

from fasthtml.components import Div, H2, H3, P, Span, Input, Label, Form
from fasthtml.xtend import A
from lucide_fasthtml import Lucide
from shad4fast import Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Select, SelectContent, SelectItem, SelectTrigger, SelectValue


def RequirementList(session_id: str, requirements: dict = None):
    """
    Component displaying requirements organized by 3-lane triage system.

    - AUTO_CHECK (green): Clear, typed requirements for automatic verification
    - NEEDS_SCOPING (yellow): References external docs, needs human scoping
    - INFORMATIONAL (gray): Workmanship/narrative, display only
    """
    if requirements is None:
        requirements = {"auto_check": [], "needs_scoping": [], "informational": []}

    return Div(
        H2("Requirements", cls="text-xl font-bold mb-4"),
        Div(
            LaneSummary(requirements),
            cls="mb-6",
        ),
        Div(
            LaneSection(
                "Auto-Check",
                "auto_check",
                requirements.get("auto_check", []),
                session_id,
                "green",
                "These requirements will be automatically verified against the submittal.",
            ),
            LaneSection(
                "Needs Scoping",
                "needs_scoping",
                requirements.get("needs_scoping", []),
                session_id,
                "yellow",
                "These requirements reference external documents. Please provide the target value.",
            ),
            LaneSection(
                "Informational",
                "informational",
                requirements.get("informational", []),
                session_id,
                "gray",
                "These are workmanship/narrative items displayed for reference only.",
            ),
            cls="space-y-6",
        ),
        id="requirement-list",
    )


def LaneSummary(requirements: dict):
    """Summary badges showing counts per lane."""
    auto_count = len(requirements.get("auto_check", []))
    scoping_count = len(requirements.get("needs_scoping", []))
    info_count = len(requirements.get("informational", []))
    total = auto_count + scoping_count + info_count

    return Div(
        Div(
            Badge(f"{total} Total", variant="outline", cls="mr-2"),
            Badge(f"{auto_count} Auto-Check", cls="bg-green-100 text-green-800 mr-2"),
            Badge(f"{scoping_count} Needs Scoping", cls="bg-yellow-100 text-yellow-800 mr-2"),
            Badge(f"{info_count} Informational", cls="bg-gray-100 text-gray-800"),
            cls="flex flex-wrap gap-2",
        ),
    )


def LaneSection(
    title: str,
    lane_key: str,
    requirements: list,
    session_id: str,
    color: str,
    description: str,
):
    """A section containing requirements of a single lane."""
    color_classes = {
        "green": "border-l-4 border-l-green-500",
        "yellow": "border-l-4 border-l-yellow-500",
        "gray": "border-l-4 border-l-gray-400",
    }

    header_colors = {
        "green": "text-green-700",
        "yellow": "text-yellow-700",
        "gray": "text-gray-600",
    }

    return Card(
        CardHeader(
            Div(
                CardTitle(title, cls=header_colors.get(color, "")),
                Badge(str(len(requirements)), variant="outline"),
                cls="flex justify-between items-center",
            ),
            CardDescription(description),
        ),
        CardContent(
            Div(
                *[
                    RequirementCard(req, session_id, lane_key)
                    for req in requirements
                ],
                cls="space-y-3",
            )
            if requirements
            else P("No requirements in this lane.", cls="text-muted-foreground italic"),
        ),
        cls=f"{color_classes.get(color, '')} pl-4",
    )


def RequirementCard(requirement: dict, session_id: str, lane_key: str):
    """Individual requirement card with actions."""
    req_id = requirement.get("id", "")
    text = requirement.get("text", "")
    source_page = requirement.get("source_page", "?")
    target_value = requirement.get("target_value")
    status = requirement.get("status", "PENDING")

    status_colors = {
        "PENDING": "bg-gray-100 text-gray-600",
        "VERIFIED": "bg-green-100 text-green-600",
        "SCOPED": "bg-blue-100 text-blue-600",
        "NOT_APPLICABLE": "bg-orange-100 text-orange-600",
    }

    return Div(
        Div(
            Div(
                P(text, cls="font-medium"),
                Div(
                    Span(f"Page {source_page}", cls="text-xs text-muted-foreground"),
                    Badge(status, cls=f"text-xs {status_colors.get(status, '')}", variant="outline"),
                    cls="flex gap-2 mt-1",
                ),
                cls="flex-1",
            ),
            cls="flex justify-between items-start",
        ),
        # Show target value or scoping input
        Div(
            TargetValueDisplay(requirement, session_id, lane_key),
            cls="mt-2",
        )
        if lane_key != "informational"
        else None,
        # Action buttons
        Div(
            RequirementActions(requirement, session_id, lane_key),
            cls="mt-3 flex gap-2",
        ),
        cls="p-3 border rounded-lg hover:bg-accent/30 transition-colors",
        id=f"requirement-{req_id}",
    )


def TargetValueDisplay(requirement: dict, session_id: str, lane_key: str):
    """Display or input for target value."""
    req_id = requirement.get("id", "")
    target_value = requirement.get("target_value")

    if lane_key == "auto_check":
        # Show the target value
        return Div(
            Label("Target Value:", cls="text-xs text-muted-foreground"),
            Span(target_value or "Not set", cls="font-mono text-sm ml-2"),
        )
    elif lane_key == "needs_scoping":
        # Show input for scoping
        return ScopingInput(requirement, session_id)

    return None


def ScopingInput(requirement: dict, session_id: str):
    """Input field for scoping NEEDS_SCOPING requirements."""
    req_id = requirement.get("id", "")
    target_value = requirement.get("target_value")

    if target_value:
        return Div(
            Label("Scoped Value:", cls="text-xs text-muted-foreground"),
            Span(target_value, cls="font-mono text-sm ml-2"),
            Button(
                Lucide("edit", cls="w-3 h-3"),
                variant="ghost",
                size="sm",
                cls="ml-2",
            ),
        )

    return Form(
        Div(
            Input(
                type="text",
                name="target_value",
                placeholder="Enter the target value from drawings/schedules",
                cls="text-sm",
            ),
            Button(
                "Scope",
                type="submit",
                variant="secondary",
                size="sm",
                cls="ml-2",
            ),
            cls="flex gap-2",
        ),
        hx_patch=f"/api/compliance/sessions/{session_id}/requirements/{req_id}",
        hx_target=f"#requirement-{req_id}",
        hx_swap="outerHTML",
    )


def RequirementActions(requirement: dict, session_id: str, lane_key: str):
    """Action buttons for a requirement."""
    req_id = requirement.get("id", "")
    status = requirement.get("status", "PENDING")

    actions = []

    # Lane reclassification dropdown
    actions.append(
        LaneReclassificationSelect(requirement, session_id),
    )

    # Mark N/A button
    if status != "NOT_APPLICABLE":
        actions.append(
            Button(
                "Mark N/A",
                variant="outline",
                size="sm",
                hx_patch=f"/api/compliance/sessions/{session_id}/requirements/{req_id}",
                hx_vals='{"status": "NOT_APPLICABLE"}',
                hx_target=f"#requirement-{req_id}",
                hx_swap="outerHTML",
            ),
        )

    return Div(*actions, cls="flex gap-2 flex-wrap")


def LaneReclassificationSelect(requirement: dict, session_id: str):
    """Dropdown for reclassifying requirement lane."""
    req_id = requirement.get("id", "")
    current_lane = requirement.get("lane", "AUTO_CHECK")

    return Div(
        Select(
            SelectTrigger(
                SelectValue(placeholder="Change Lane"),
                cls="w-[140px] h-8 text-xs",
            ),
            SelectContent(
                SelectItem("AUTO_CHECK", value="AUTO_CHECK"),
                SelectItem("NEEDS_SCOPING", value="NEEDS_SCOPING"),
                SelectItem("INFORMATIONAL", value="INFORMATIONAL"),
            ),
            name="lane",
            hx_patch=f"/api/compliance/sessions/{session_id}/requirements/{req_id}",
            hx_target="#requirement-list",
            hx_swap="outerHTML",
        ),
    )


def RequirementListLoading():
    """Loading state for requirement list."""
    return Div(
        Div(
            Lucide("loader-2", cls="w-8 h-8 animate-spin text-muted-foreground"),
            P("Extracting requirements...", cls="mt-2 text-muted-foreground"),
            cls="flex flex-col items-center py-12",
        ),
        id="requirement-list",
    )
