import re
from typing import Any, Dict, List, Optional
from . import ReportTab

class LevelLoadingStatsTab(ReportTab):
    def __init__(self):
        super().__init__("Level Loading Stats", "level-loading-stats")
        self.parsing = False
        self.headers = ["Level", "Time to Load", "Streaming Status", "Visibility Status"]

    def should_handle(self, line: str) -> bool:
        return line.startswith('MemReport: Begin command "LogOutStatLevels"')

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        if "level_stats" not in context:
            context["level_stats"] = {
                "rows": [],
                "persistent_count": 0
            }

        if line.startswith('MemReport: Begin command "LogOutStatLevels"'):
            self.parsing = True
            return

        if not self.parsing:
            return

        stripped = line.strip()
        if not stripped or stripped == "Levels:":
            return

        is_persistent = False
        level_text = stripped
        if stripped.startswith("->"):
            is_persistent = True
            level_text = stripped[2:].strip()
        
        match = re.search(r"^(.*?)\s*-\s*([\d\.]+\s*sec)\s+(.*?)\s+(.*?)$", level_text)
        
        if match:
            level = match.group(1).strip()
            time_to_load = match.group(2).strip()
            streaming = match.group(3).strip()
            visibility = match.group(4).strip()
        else:
            level = level_text
            time_to_load = ""
            streaming = ""
            visibility = ""
            is_persistent = True

        if is_persistent:
            context["level_stats"]["persistent_count"] += 1

        context["level_stats"]["rows"].append([level, time_to_load, streaming, visibility])

    def get_buttons(self, context: Dict[str, Any]) -> str:
        if "level_stats" in context and context["level_stats"]["rows"]:
            return f'<button class="tab-btn" onclick="openTab(event, \'{self.id}\')">Level Loading Stats</button>'
        return ""

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        if "level_stats" not in context or not context["level_stats"]["rows"]:
            return ""

        stats = context["level_stats"]
        rows = stats["rows"]
        persistent_count = stats["persistent_count"]
        active_class = " active" if is_active else ""

        warning_html = ""
        if persistent_count >= 2:
            warning_html = f"""
            <div class="alert alert-warning" style="margin-top: 15px;">
                <div class="alert-icon">⚠️</div>
                <div class="alert-content">
                    <strong>WARNING:</strong> More than 1 persistent level detected ({persistent_count}). Please check if they are sub-levels, as only 1 persistent primary level can be loaded at all times.
                </div>
            </div>
            """

        thead = "<thead><tr>" + "".join([f"<th>{h}</th>" for h in self.headers]) + "</tr></thead>"
        tbody = "<tbody>"
        for row in rows:
            row_style = ""
            if not row[1]: 
                row_style = ' style="background-color: rgba(59, 130, 246, 0.1); font-weight: 600;"'
            tbody += f"<tr{row_style}>" + "".join([f"<td>{c}</td>" for c in row]) + "</tr>"
        tbody += "</tbody>"

        dashboard_html = f"""
        <div class="analytics-wrapper" style="background: var(--row-even); padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid var(--border-color);">
            <div class="analytics-row" style="display: flex; gap: 20px; flex-wrap: wrap;">
                <div class="analytics-card" style="flex: 1; max-width: 300px; background: rgba(59, 130, 246, 0.05); padding: 15px; border-radius: 6px; border: 1px solid var(--accent-color); text-align: center;">
                     <h4 style="margin: 0 0 10px 0; color: var(--accent-color); font-size: 0.8em; text-transform: uppercase;">Filtered Statistics</h4>
                     <div style="font-size: 0.9em; text-align: left;"><span style="color: var(--text-muted); font-size: 0.85em; text-transform: uppercase;">Levels:</span> <b id="lvl-filt-count" style="color: var(--accent-color);">0</b></div>
                </div>
            </div>
            {warning_html}
        </div>
        """

        return f"""
        <div id="{self.id}" class="tab-content{active_class}">
            <h3 id="level-loading-statistics">Level Loading Statistics</h3>
            {dashboard_html}
            <div class="search-container">
                <input type="text" placeholder="Search levels..." onkeyup="filterLvlTable(this.value)">
            </div>
            <div class="table-container">
                <table id="tbl-{self.id}">
                    {thead}
                    {tbody}
                </table>
            </div>
            <script>
                function updateLvlAggregates() {{
                    const table = document.getElementById('tbl-{self.id}');
                    const rows = Array.from(table.tBodies[0].rows);
                    let count = 0;
                    rows.forEach(row => {{
                        if (row.style.display !== 'none') count++;
                    }});
                    document.getElementById('lvl-filt-count').innerText = count;
                }}
                function filterLvlTable(term) {{
                    filterTable('tbl-{self.id}', -1, term);
                    updateLvlAggregates();
                }}
                document.addEventListener('DOMContentLoaded', updateLvlAggregates);
            </script>
        </div>
        """
