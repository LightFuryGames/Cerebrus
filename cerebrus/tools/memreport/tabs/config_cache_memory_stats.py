from typing import Any, Dict, List

from . import ReportTab


class ConfigCacheMemoryStatsTab(ReportTab):
    def __init__(self):
        super().__init__("Config Cache Memory Statistics", "config-cache-memory-stats")
        self.headers = ["#", "File Name", "Current Size", "Max Size"]

    def should_handle(self, line: str) -> bool:
        return 'command "ConfigMem"' in line

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        if "config_mem_data" not in context:
            context["config_mem_data"] = []
            context["config_mem_known"] = None
            context["config_mem_reported_total"] = None

        if (
            "MemReport: Begin command" in line
            or "Config cache memory usage:" in line
            or ("FileName" in line and "NumBytes" in line)
        ):
            return

        parts = line.split()
        if len(parts) >= 3:
            try:
                max_bytes = int(parts[-1])
                num_bytes = int(parts[-2])
                file_name = " ".join(parts[:-2]).strip()

                if file_name == "KnownFiles":
                    context["config_mem_known"] = {
                        "NumBytes": num_bytes,
                        "MaxBytes": max_bytes,
                    }
                elif file_name == "Total":
                    context["config_mem_reported_total"] = {
                        "NumBytes": num_bytes,
                        "MaxBytes": max_bytes,
                    }
                else:
                    context["config_mem_data"].append(
                        {
                            "FileName": file_name,
                            "NumBytes": num_bytes,
                            "MaxBytes": max_bytes,
                        }
                    )
            except ValueError:
                pass

    def _format_size(self, size_bytes: int) -> str:
        kb_val = size_bytes / 1024.0
        if kb_val >= 1024:
            mb_val = kb_val / 1024.0
            return f"{mb_val:.2f} MB"
        return f"{kb_val:.2f} KB"

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        data = context.get("config_mem_data", [])
        if not data:
            return ""

        active_cls = " active" if is_active else ""

        # Aggregates
        calc_num_bytes = sum(item["NumBytes"] for item in data)
        calc_max_bytes = sum(item["MaxBytes"] for item in data)

        known = context.get("config_mem_known")
        reported = context.get("config_mem_reported_total")

        known_html = f"""
            <div class="analytics-card" style="flex: 1; min-width: 240px; background: var(--header-bg); padding: 15px; border-radius: 6px; text-align: center; border: 1px solid var(--border-color);">
                <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">
                    Known Aggregate<br>
                    <span class="unreal-red" style="font-size: 0.85em;">(UNREAL REPORTED)</span>
                </h4>
                <div class="value" style="font-size: 1.15em; font-weight: bold; color: var(--accent-color);">{self._format_size(known['NumBytes']) if known else "N/A"}</div>
                <div style="font-size: 0.8em; color: var(--text-muted);">Max: {self._format_size(known['MaxBytes']) if known else "N/A"}</div>
            </div>
        """

        reported_html = f"""
            <div class="analytics-card" style="flex: 1; min-width: 240px; background: var(--header-bg); padding: 15px; border-radius: 6px; text-align: center; border: 1px solid var(--border-color);">
                <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">
                    Reported Total<br>
                    <span class="unreal-red" style="font-size: 0.85em;">(UNREAL REPORTED)</span>
                </h4>
                <div class="value" style="font-size: 1.15em; font-weight: bold; color: #ce9178;">{self._format_size(reported['NumBytes']) if reported else "N/A"}</div>
                <div style="font-size: 0.8em; color: var(--text-muted);">Max: {self._format_size(reported['MaxBytes']) if reported else "N/A"}</div>
            </div>
        """

        calc_html = f"""
            <div class="analytics-card" style="flex: 1; min-width: 250px; background: var(--header-bg); padding: 15px; border-radius: 6px; text-align: center; border: 1px solid var(--border-color);">
                <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated Total</h4>
                <div class="value" style="font-size: 1.25em; font-weight: bold; color: #4ec9b0;">{self._format_size(calc_num_bytes)}</div>
                <div style="font-size: 0.8em; color: var(--text-muted);">Sum of {len(data)} individual files</div>
            </div>
        """

        filtered_html = f"""
            <div class="analytics-card" style="flex: 1; min-width: 250px; background: rgba(59, 130, 246, 0.05); padding: 15px; border-radius: 6px; text-align: center; border: 1px solid var(--accent-color);">
                <h4 style="margin: 0 0 10px 0; color: var(--accent-color); font-size: 0.8em; text-transform: uppercase;">Filtered Total</h4>
                <div class="value" style="font-size: 1.25em; font-weight: bold; color: var(--accent-color);" id="config-filt-val">0.00 KB</div>
                <div style="font-size: 0.8em; color: var(--text-muted);">Visible Files: <b id="config-filt-count">0</b></div>
            </div>
        """

        # Warning logic
        warning_html = ""
        if reported and abs(calc_num_bytes - reported["NumBytes"]) > 1024:
            diff = calc_num_bytes - reported["NumBytes"]
            diff_str = self._format_size(abs(diff))
            direction = "exceeds" if diff > 0 else "is less than"
            warning_html = f"""
            <div class="alert alert-warning" style="margin-top: 15px;">
                <div class="alert-icon">⚠️</div>
                <div class="alert-content">
                    <strong>WARNING: Total Mismatch Detected:</strong> The calculated sum of individual config files ({self._format_size(calc_num_bytes)}) {direction} the engine's reported total ({self._format_size(reported['NumBytes'])}) by {diff_str}. 
                    This discrepancy often occurs because the engine's summary excludes certain dynamically loaded, plugin-specific, or saved configuration files that are nonetheless present in memory.
                </div>
            </div>
            """

        rows_html = ""
        for idx, item in enumerate(data, 1):
            rows_html += f"""
            <tr>
                <td>{idx}</td>
                <td>{item['FileName']}</td>
                <td class="numeric" data-val="{item['NumBytes']}">{self._format_size(item['NumBytes'])}</td>
                <td class="numeric" data-val="{item['MaxBytes']}">{self._format_size(item['MaxBytes'])}</td>
            </tr>
            """

        headers_html = ""
        for i, h in enumerate(self.headers):
            cls = ' class="numeric"' if i == 0 or i > 2 else ""
            headers_html += f"<th{cls}>{h}</th>"

        return f"""
        <div id="{self.id}" class="tab-content{active_cls}">
            <h2>Config Cache Memory Statistics</h2>
            
            <div class="analytics-wrapper" style="background: var(--row-even); padding: 20px; border-radius: 8px; margin-bottom: 15px; border: 1px solid var(--border-color);">
                <h3 style="margin-top: 0; margin-bottom: 15px; border-bottom: 1px solid var(--border-color); padding-bottom: 10px; color: var(--text-color);">Config Cache Memory Aggregate Statistics</h3>
                <div class="analytics-row" style="display: flex; gap: 20px; justify-content: flex-start; flex-wrap: wrap;">
                    {known_html}
                    {reported_html}
                    {calc_html}
                    {filtered_html}
                </div>
                {warning_html}
            </div>

            <div class="search-container">
                <input type="text" placeholder="Search config files..." onkeyup="filterConfigTable(this.value)">
            </div>

            <div class="table-container">
                <table id="tbl-{self.id}">
                    <thead>
                        <tr>{headers_html}</tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>

            <script>
                function formatConfigSize(bytes) {{
                    let kb = bytes / 1024.0;
                    if (kb >= 1024) return (kb / 1024.0).toFixed(2) + " MB";
                    return kb.toFixed(2) + " KB";
                }}

                function updateConfigAggregates() {{
                    const table = document.getElementById('tbl-{self.id}');
                    const rows = Array.from(table.tBodies[0].rows);
                    let count = 0;
                    let sumBytes = 0;
                    
                    rows.forEach(row => {{
                        if (row.style.display !== 'none') {{
                            count++;
                            const val = parseInt(row.cells[2].getAttribute('data-val')) || 0;
                            sumBytes += val;
                        }}
                    }});

                    document.getElementById('config-filt-count').innerText = count;
                    document.getElementById('config-filt-val').innerText = formatConfigSize(sumBytes);
                }}

                function filterConfigTable(term) {{
                    filterTable('tbl-{self.id}', -1, term);
                    updateConfigAggregates();
                }}
                
                document.addEventListener('DOMContentLoaded', updateConfigAggregates);
            </script>
        </div>
        """
