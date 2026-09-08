"""Battery Thermal tab for the memreport HTML report.

Unlike the other tabs, this one's data doesn't come from parsing the
`.memreport` text - it comes from a separate `*_battery_thermal.csv`
capture taken alongside the profiling session (see
`cerebrus.tools.thermal_capture.BatteryThermalSampler`). The caller is
responsible for loading the samples and constructing this tab; if no
thermal capture exists for the session, this tab is simply never added
to `context["tabs"]`.
"""

from __future__ import annotations

from typing import Any, Dict, List

from cerebrus.tools.thermal_to_html import (
    HOT_THRESHOLD_C,
    WARM_THRESHOLD_C,
    ThermalSample,
    _build_svg_chart,
    _status_for_temp,
)

from . import ReportTab


class BatteryThermalTab(ReportTab):
    def __init__(self, samples: List[ThermalSample]):
        super().__init__("Battery Thermal", "battery-thermal")
        self.samples = samples

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        active_cls = " active" if is_active else ""

        if not self.samples:
            return (
                f'<div id="{self.id}" class="tab-content{active_cls}">'
                f'<div class="loading">No battery thermal capture was recorded '
                f"for this session.</div></div>"
            )

        temps = [s.temp_c for s in self.samples]
        min_temp, max_temp = min(temps), max(temps)
        avg_temp = sum(temps) / len(temps)
        duration = self.samples[-1].elapsed_seconds
        peak_label, peak_color = _status_for_temp(max_temp)

        stats_html = f"""
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Peak Temp</div>
                <div class="stat-value" style="color:{peak_color}">{max_temp:.1f}&#176;C ({peak_label})</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Min Temp</div>
                <div class="stat-value">{min_temp:.1f}&#176;C</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Average Temp</div>
                <div class="stat-value">{avg_temp:.1f}&#176;C</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Duration</div>
                <div class="stat-value">{duration:.0f}s</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Samples</div>
                <div class="stat-value">{len(self.samples)}</div>
            </div>
        </div>
        """

        chart_svg = _build_svg_chart(self.samples)

        return f"""
        <div id="{self.id}" class="tab-content{active_cls}">
            {stats_html}
            <div class="table-container" style="padding: 20px;">
                {chart_svg}
            </div>
        </div>
        """
