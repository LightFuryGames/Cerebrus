from __future__ import annotations

from cerebrus.core.plugins import TabPlugin
from cerebrus.ui.components.panels.profiling.profiling_panel import _build_profiling_tab
from cerebrus.ui.state import UIState


class ProfilingPlugin(TabPlugin):
    @property
    def id(self) -> str:
        return "profiling"

    @property
    def name(self) -> str:
        return "Profiling"

    @property
    def version(self) -> str:
        return "1.0.0"

    def build_tab(self, state: UIState) -> None:
        _build_profiling_tab(state)
