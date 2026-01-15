"""
Triage service for classifying requirements into lanes.
"""

from backend.models.enums import LaneType


# Trigger phrases that indicate NEEDS_SCOPING classification
SCOPING_TRIGGERS = [
    "as scheduled",
    "as indicated",
    "per plans",
    "per drawings",
    "where shown",
    "match drawings",
    "coordinate with",
    "as specified elsewhere",
    "as required by",
    "refer to section",
    "see drawings",
    "per schedule",
    "as shown",
    "per specifications",
    "as detailed",
]

# Patterns that indicate INFORMATIONAL classification
INFORMATIONAL_PATTERNS = [
    "install in accordance with",
    "installation shall",
    "workmanship",
    "warranty",
    "submit",
    "coordinate",
    "provide",
    "furnish and install",
    "general conditions",
    "in accordance with manufacturer",
    "comply with",
]

# Patterns that indicate AUTO_CHECK classification
AUTO_CHECK_PATTERNS = [
    r"\d+\s*(v|volt|voltage)",
    r"\d+\s*(ton|tons)",
    r"\d+\s*(hp|horsepower)",
    r"\d+\s*(kw|kilowatt)",
    r"\d+\s*(cfm|cubic feet)",
    r"\d+\s*(db|decibel)",
    r"\d+\s*(psi)",
    r"\d+\s*(btu)",
    "ul listed",
    "ul certified",
    "astm",
    "ansi",
    "ashrae",
    "nfpa",
    "r-410a",
    "r-32",
    "type x",
    "factory-wired",
    "shall be",
    "minimum",
    "maximum",
]


class TriageService:
    """
    Service for classifying requirements into triage lanes.

    Uses rule-based trigger phrase detection for initial classification.
    LLM fallback will be integrated via OpenRouter/Ollama on a separate branch.
    """

    def __init__(self):
        self.scoping_triggers = [t.lower() for t in SCOPING_TRIGGERS]
        self.informational_patterns = [p.lower() for p in INFORMATIONAL_PATTERNS]

    def classify_lane(self, requirement_text: str) -> LaneType:
        """
        Classify a requirement into one of three lanes.

        This is a stub implementation using rule-based detection.
        LLM fallback will be added via OpenRouter/Ollama integration.

        Args:
            requirement_text: The full text of the requirement

        Returns:
            LaneType enum value
        """
        text_lower = requirement_text.lower()

        # Check for NEEDS_SCOPING triggers first
        for trigger in self.scoping_triggers:
            if trigger in text_lower:
                return LaneType.NEEDS_SCOPING

        # Check for INFORMATIONAL patterns
        for pattern in self.informational_patterns:
            if pattern in text_lower:
                return LaneType.INFORMATIONAL

        # Check for AUTO_CHECK patterns (numeric values, certifications)
        import re
        for pattern in AUTO_CHECK_PATTERNS:
            if re.search(pattern, text_lower):
                return LaneType.AUTO_CHECK

        # Default to INFORMATIONAL if no patterns match
        return LaneType.INFORMATIONAL

    def classify_requirements(
        self, requirements: list[dict]
    ) -> list[tuple[dict, LaneType]]:
        """
        Classify multiple requirements.

        Args:
            requirements: List of requirement dicts with 'text' field

        Returns:
            List of (requirement, lane) tuples
        """
        results = []
        for req in requirements:
            text = req.get("text", "")
            lane = self.classify_lane(text)
            results.append((req, lane))
        return results

    def needs_scoping(self, requirement_text: str) -> bool:
        """Check if a requirement needs scoping."""
        return self.classify_lane(requirement_text) == LaneType.NEEDS_SCOPING

    def is_auto_checkable(self, requirement_text: str) -> bool:
        """Check if a requirement is auto-checkable."""
        return self.classify_lane(requirement_text) == LaneType.AUTO_CHECK

    def is_informational(self, requirement_text: str) -> bool:
        """Check if a requirement is informational only."""
        return self.classify_lane(requirement_text) == LaneType.INFORMATIONAL
