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
                <!-- Reported Total (N/A for level stats as summary isn't provided by Unreal) -->
                <div class="analytics-card" style="flex: 1; min-width: 250px; background: var(--header-bg); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color); text-align: center;">
                    <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">
                        Reported Total<br>
                        <span class="unreal-red" style="font-size: 0.85em;">(UNREAL REPORTED)</span>
                    </h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; font-size: 0.85em; text-align: left; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px;">
                        <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Reported Count:</span></div><div style="color: #ce9178; text-align: right;"><b>N/A</b></div>
                        <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Reported Time to Load:</span></div><div style="color: #ce9178; text-align: right;"><b>N/A</b></div>
                    </div>
                </div>

                <!-- Calculated Total -->
                <div class="analytics-card" style="flex: 1; min-width: 250px; background: var(--header-bg); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color); text-align: center;">
                    <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated Total</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; font-size: 0.85em; text-align: left; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px;">
                        <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated Count:</span></div><div style="color: #4ec9b0; text-align: right;"><b id="lvl-calc-count">0</b></div>
                        <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated Time to Load:</span></div><div style="color: #4ec9b0; text-align: right;"><b id="lvl-calc-time">0.00 sec</b></div>
                    </div>
                </div>

                <!-- Filtered Statistics -->
                <div class="analytics-card" style="flex: 1; min-width: 250px; background: rgba(59, 130, 246, 0.08); padding: 15px; border-radius: 6px; border: 1px solid var(--accent-color); text-align: center;">
                    <h4 style="margin: 0 0 10px 0; color: var(--accent-color); font-size: 0.8em; text-transform: uppercase;">Filtered Statistics</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; font-size: 0.85em; text-align: left; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px;">
                        <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Filtered Count:</span></div><div style="color: var(--accent-color); text-align: right;"><b id="lvl-filt-count">0</b></div>
                        <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Filtered Time to Load:</span></div><div style="color: var(--accent-color); text-align: right;"><b id="lvl-filt-time">0.00 sec</b></div>
                    </div>
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
                    
                    let calcCount = 0, filtCount = 0;
                    let calcTime = 0, filtTime = 0;
                    
                    rows.forEach(row => {{
                        const isVisible = row.style.display !== 'none';
                        const timeStr = row.cells[1].innerText.trim();
                        const timeVal = parseFloat(timeStr) || 0;
                        
                        calcCount++;
                        calcTime += timeVal;
                        
                        if (isVisible) {{
                            filtCount++;
                            filtTime += timeVal;
                        }}
                    }});
                    
                    document.getElementById('lvl-calc-count').innerText = calcCount;
                    document.getElementById('lvl-calc-time').innerText = calcTime.toFixed(2) + " sec";
                    document.getElementById('lvl-filt-count').innerText = filtCount;
                    document.getElementById('lvl-filt-time').innerText = filtTime.toFixed(2) + " sec";
                }}
                function filterLvlTable(term) {{
                    filterTable('tbl-{self.id}', -1, term);
                    updateLvlAggregates();
                }}
                document.addEventListener('DOMContentLoaded', updateLvlAggregates);
            </script>
        </div>
        """
