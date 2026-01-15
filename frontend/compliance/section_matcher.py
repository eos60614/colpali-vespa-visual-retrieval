"""
Section matcher UI components for matching submittals to spec sections.
"""

from fasthtml.components import Div, H2, H3, P, Span
from fasthtml.xtend import A
from lucide_fasthtml import Lucide
from shad4fast import Badge, Button, Card, CardContent, CardDescription, CardHeader, CardTitle, Select, SelectContent, SelectItem, SelectTrigger, SelectValue


def SectionMatcher(session_id: str, suggestions: list = None):
    """
    Component for matching a submittal to a spec section.

    Shows ranked suggestions from ColPali similarity search and allows
    human confirmation or manual override.
    """
    return Div(
        Card(
            CardHeader(
                CardTitle("Match Spec Section"),
                CardDescription(
                    "Select the specification section that corresponds to this submittal"
                ),
            ),
            CardContent(
                Div(
                    H3("Suggested Sections", cls="text-lg font-medium mb-3"),
                    P(
                        "Based on visual similarity analysis, these spec sections best match your submittal:",
                        cls="text-muted-foreground text-sm mb-4",
                    ),
                    SuggestionList(session_id, suggestions or []),
                    cls="mb-6",
                ),
                Div(
                    H3("Manual Selection", cls="text-lg font-medium mb-3"),
                    P(
                        "If none of the suggestions are correct, select a section manually:",
                        cls="text-muted-foreground text-sm mb-4",
                    ),
                    ManualSectionSelect(session_id),
                    cls="border-t pt-6",
                ),
            ),
        ),
        id="section-matcher",
    )


def SuggestionList(session_id: str, suggestions: list):
    """List of spec section suggestions with similarity scores."""
    if not suggestions:
        return Div(
            P("No suggestions available yet.", cls="text-muted-foreground italic"),
            Button(
                Lucide("search", cls="w-4 h-4 mr-2"),
                "Find Matching Sections",
                variant="outline",
                hx_post=f"/api/compliance/sessions/{session_id}/match",
                hx_target="#section-matcher",
                hx_swap="outerHTML",
            ),
            cls="space-y-4",
        )

    return Div(
        *[SuggestionCard(session_id, s, idx) for idx, s in enumerate(suggestions)],
        cls="space-y-3",
    )


def SuggestionCard(session_id: str, suggestion: dict, index: int):
    """Card displaying a single spec section suggestion."""
    spec_section = suggestion.get("spec_section", {})
    similarity = suggestion.get("similarity_score", 0)
    rank = suggestion.get("rank", index + 1)

    # Color-code by similarity score
    if similarity >= 0.8:
        score_cls = "text-green-600"
        score_badge = "default"
    elif similarity >= 0.6:
        score_cls = "text-yellow-600"
        score_badge = "secondary"
    else:
        score_cls = "text-red-600"
        score_badge = "destructive"

    return Div(
        Div(
            Div(
                Badge(f"#{rank}", variant="outline", cls="mr-2"),
                Span(
                    spec_section.get("section_number", "N/A"),
                    cls="font-mono font-medium",
                ),
                cls="flex items-center",
            ),
            Badge(
                f"{similarity:.0%}",
                variant=score_badge,
                cls=score_cls,
            ),
            cls="flex justify-between items-center mb-2",
        ),
        Div(
            P(
                spec_section.get("section_title", "Untitled Section"),
                cls="font-medium",
            ),
            P(
                f"Pages: {', '.join(map(str, spec_section.get('page_numbers', [])))}",
                cls="text-sm text-muted-foreground",
            ),
            cls="mb-3",
        ),
        Button(
            Lucide("check", cls="w-4 h-4 mr-2"),
            "Select This Section",
            variant="default" if rank == 1 else "outline",
            cls="w-full",
            hx_post=f"/api/compliance/sessions/{session_id}/match/confirm",
            hx_vals=f'{{"spec_section_id": "{spec_section.get("id", "")}"}}',
            hx_target="#main-content",
        ),
        cls="p-4 border rounded-lg hover:bg-accent/50 transition-colors",
    )


def ManualSectionSelect(session_id: str):
    """Manual section selection dropdown."""
    from fasthtml.components import Form, Input, Label

    return Form(
        Div(
            Label("Spec Section ID", htmlFor="manual_section_id"),
            Input(
                type="text",
                name="spec_section_id",
                id="manual_section_id",
                placeholder="Enter spec section ID",
                cls="mt-1 w-full",
            ),
            cls="mb-4",
        ),
        Button(
            "Confirm Manual Selection",
            type="submit",
            variant="outline",
        ),
        hx_post=f"/api/compliance/sessions/{session_id}/match/confirm",
        hx_target="#main-content",
    )


def SectionMatcherLoading():
    """Loading state for section matcher."""
    return Div(
        Div(
            Lucide("loader-2", cls="w-8 h-8 animate-spin text-muted-foreground"),
            P("Analyzing submittal and finding matching sections...", cls="mt-2 text-muted-foreground"),
            cls="flex flex-col items-center py-12",
        ),
        id="section-matcher",
    )


def SectionConfirmed(session_id: str, section: dict):
    """Confirmation message after section is selected."""
    return Div(
        Card(
            CardContent(
                Div(
                    Lucide("check-circle", cls="w-12 h-12 text-green-500 mx-auto"),
                    H2("Section Confirmed", cls="text-xl font-bold text-center mt-4"),
                    P(
                        f"Spec section {section.get('section_number', 'N/A')}: {section.get('section_title', 'Untitled')}",
                        cls="text-center text-muted-foreground mt-2",
                    ),
                    Div(
                        Button(
                            "Continue to Requirements",
                            variant="default",
                            hx_get=f"/compliance/session/{session_id}/requirements",
                            hx_target="#main-content",
                        ),
                        cls="flex justify-center mt-6",
                    ),
                    cls="py-6",
                ),
            ),
        ),
        id="section-matcher",
    )
