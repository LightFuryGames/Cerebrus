from typing import Any, Dict, List


class ReportTab:
    """Base class for a MemReport Tab."""

    def __init__(self, name: str, tab_id: str):
        self.name = name
        self.id = tab_id

    def should_handle(self, line: str) -> bool:
        """Return True if this line marks the start of this tab's section."""
        return False

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        """Parse a line of text into the shared context."""
        pass

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        """Return the HTML content for this tab."""
        return ""

    def get_buttons(self, context: Dict[str, Any]) -> str:
        """Return HTML for the tab button(s)."""
        return f'<button class="tab-btn" onclick="openTab(event, \'{self.id}\')">{self.name}</button>'


from .rhi_stats import RhiMemoryTab
