"""
Compliance dashboard UI components.
"""

from fasthtml.components import Div, H1, H2, H3, P, Span, Table, Thead, Tbody, Tr, Th, Td
from fasthtml.xtend import A
from lucide_fasthtml import Lucide
from shad4fast import Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle


def ComplianceDashboard():
    """Main compliance dashboard page."""
    return Div(
        Div(
            H1("Compliance Review", cls="text-2xl font-bold"),
            Button(
                Lucide("plus", cls="w-4 h-4 mr-2"),
                "New Review",
                variant="default",
                hx_get="/compliance/new",
                hx_target="#main-content",
            ),
            cls="flex justify-between items-center mb-6",
        ),
        Div(
            Card(
                CardHeader(
                    CardTitle("Active Reviews"),
                    CardDescription("Sessions currently in progress"),
                ),
                CardContent(
                    SessionList(),
                ),
                cls="w-full",
            ),
            id="session-list-container",
        ),
        cls="p-6",
        id="main-content",
    )


def SessionList():
    """List of review sessions - fetched via HTMX."""
    return Div(
        Div(
            P("Loading sessions...", cls="text-muted-foreground"),
            cls="flex justify-center py-8",
        ),
        hx_get="/api/compliance/sessions",
        hx_trigger="load",
        hx_target="this",
        hx_swap="innerHTML",
    )


def SessionListTable(sessions: list):
    """Table displaying review sessions."""
    if not sessions:
        return Div(
            P("No review sessions found.", cls="text-muted-foreground text-center py-4"),
        )

    return Table(
        Thead(
            Tr(
                Th("Session ID", cls="text-left"),
                Th("Submittal", cls="text-left"),
                Th("Status", cls="text-left"),
                Th("Created", cls="text-left"),
                Th("Actions", cls="text-right"),
            ),
        ),
        Tbody(
            *[SessionRow(s) for s in sessions],
        ),
        cls="w-full",
    )


def SessionRow(session: dict):
    """Single session row in the table."""
    status_colors = {
        "MATCHING": "bg-blue-100 text-blue-800",
        "EXTRACTING": "bg-yellow-100 text-yellow-800",
        "VERIFYING": "bg-purple-100 text-purple-800",
        "REVIEWING": "bg-orange-100 text-orange-800",
        "COMPLETED": "bg-green-100 text-green-800",
    }

    status = session.get("status", "MATCHING")
    status_cls = status_colors.get(status, "bg-gray-100 text-gray-800")

    return Tr(
        Td(
            Span(session["id"][:8] + "...", cls="font-mono text-sm"),
            cls="py-3",
        ),
        Td(
            Span(session["submittal_id"][:20] + "..." if len(session["submittal_id"]) > 20 else session["submittal_id"]),
            cls="py-3",
        ),
        Td(
            Badge(status, cls=status_cls),
            cls="py-3",
        ),
        Td(
            Span(session["created_at"][:10] if session.get("created_at") else "N/A"),
            cls="py-3 text-muted-foreground",
        ),
        Td(
            A(
                Button("View", variant="outline", size="sm"),
                href=f"/compliance/session/{session['id']}",
            ),
            cls="py-3 text-right",
        ),
        cls="border-b",
    )


def StatusBadge(status: str):
    """Status badge with appropriate color."""
    colors = {
        "MATCHING": "secondary",
        "EXTRACTING": "outline",
        "VERIFYING": "outline",
        "REVIEWING": "destructive",
        "COMPLETED": "default",
    }
    return Badge(status, variant=colors.get(status, "outline"))


def NewSessionForm():
    """Form for creating a new review session."""
    from fasthtml.components import Form, Input, Label

    return Card(
        CardHeader(
            CardTitle("New Compliance Review"),
            CardDescription("Start a new submittal compliance check"),
        ),
        CardContent(
            Form(
                Div(
                    Label("Submittal ID", htmlFor="submittal_id"),
                    Input(
                        type="text",
                        name="submittal_id",
                        id="submittal_id",
                        placeholder="Enter submittal document ID",
                        cls="mt-1",
                    ),
                    cls="mb-4",
                ),
                Div(
                    Label("Project ID", htmlFor="project_id"),
                    Input(
                        type="text",
                        name="project_id",
                        id="project_id",
                        placeholder="Enter project ID",
                        cls="mt-1",
                    ),
                    cls="mb-4",
                ),
                Div(
                    Button(
                        "Start Review",
                        type="submit",
                        variant="default",
                    ),
                    Button(
                        "Cancel",
                        type="button",
                        variant="outline",
                        cls="ml-2",
                        hx_get="/compliance",
                        hx_target="#main-content",
                    ),
                    cls="flex gap-2",
                ),
                hx_post="/api/compliance/sessions",
                hx_target="#main-content",
            ),
        ),
        cls="max-w-lg",
    )
