import re
from typing import Any, Dict, List

from ..utils import parse_memory_size_to_mb, try_format_cell_value
from . import ReportTab


class RhiMemoryTab(ReportTab):
    def __init__(self):
        super().__init__("RHI Memory Stats", "rhi-memory-stats")
        self.headers = [
            "RHI resource Category",
            "STAT Category (STATGROUP_RHI)",
            "Size",
        ]

    def should_handle(self, line: str) -> bool:
        return 'command "rhi.DumpMemory"' in line

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        if "rhi_memory_data" not in context:
            context["rhi_memory_data"] = []

        match = re.search(
            r"^\s*([\d\.]+\s*[KMGM]?B)\s*-\s*(.*?)\s*-\s*(STAT_.*?)\s*-\s*STATGROUP_RHI",
            line,
            re.IGNORECASE,
        )
        if match:
            size_raw = match.group(1).strip()
            category = match.group(2).strip()
            stat_category = match.group(3).strip()
            size = try_format_cell_value("Size", size_raw)
            context["rhi_memory_data"].append([category, stat_category, size])
            return

        total_match = re.search(
            r"^\s*([\d\.]+\s*[KMGM]?B)\s*total", line, re.IGNORECASE
        )
        if total_match:
            size_raw = total_match.group(1).strip()
            context["rhi_memory_total_val"] = try_format_cell_value("Size", size_raw)

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        data = context.get("rhi_memory_data", [])
        total_val = context.get("rhi_memory_total_val", "")
        if not data and not total_val:
            return ""

        active_cls = " active" if is_active else ""
        thead = (
            "<thead><tr>"
            + "".join([f"<th>{h}</th>" for h in self.headers])
            + "</tr></thead>"
        )
        tbody = "<tbody>"

        # Track total size for warning comparison
        calc_total_mb = 0.0
        for r_idx, row in enumerate(data):
            # Convert to GB if needed for better readability
            size_val = row[2]
            size_mb = parse_memory_size_to_mb(size_val)
            calc_total_mb += size_mb

            display_size = size_val
            if size_mb >= 1024:
                display_size = f"{size_mb/1024.0:.2f} GB"

            tbody += f'<tr data-index="{r_idx}"><td>{row[0]}</td><td>{row[1]}</td><td class="numeric">{display_size}</td></tr>'
        tbody += "</tbody>"

        # Warning Logic
        phys_peak_mb = context.get("platform_phys_mem_peak_mb", 0)
        warning_html = ""
        # If RHI reported > Peak Phys Mem, it's a likely reporting error
        if phys_peak_mb > 0 and calc_total_mb > phys_peak_mb:
            warning_html = f"""
            <div class="alert alert-warning" style="margin-bottom: 20px;">
                <div class="alert-icon">⚠️</div>
                <div class="alert-content">
                    <strong>Report Warning:</strong> Calculated RHI Memory (<b>{calc_total_mb/1024.0:.2f} GB</b>) exceeds reported Peak Process Physical Memory (<b>{phys_peak_mb/1024.0:.2f} GB</b>). 
                    Unreal may be over-reporting tracked RHI resources or double-counting overlapping allocations.
                </div>
            </div>
            """

        dashboard_html = ""
        dashboard_html = f"""
        <div class="analytics-wrapper" style="background: var(--row-even); padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid var(--border-color);">
            <div class="analytics-row" style="display: flex; gap: 20px; flex-wrap: wrap;">
                <!-- Reported Total -->
                <div class="analytics-card" style="flex: 1; min-width: 250px; background: var(--header-bg); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color); text-align: center;">
                    <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">
                        Reported Total<br>
                        <span class="unreal-red" style="font-size: 0.85em;">(UNREAL REPORTED)</span>
                    </h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; font-size: 0.85em; text-align: left; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px;">
                        <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Reported Size:</span></div>
                        <div style="color: #ce9178; text-align: right;"><b>{f"{parse_memory_size_to_mb(total_val)/1024.0:.2f} GB" if parse_memory_size_to_mb(total_val) >= 1024 else total_val}</b></div>
                    </div>
                </div>

                <!-- Calculated Total -->
                <div class="analytics-card" style="flex: 1; min-width: 250px; background: var(--header-bg); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color); text-align: center;">
                    <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated Total</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; font-size: 0.85em; text-align: left; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px;">
                        <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated Count:</span></div><div style="color: #4ec9b0; text-align: right;"><b id="rhi-calc-count">0</b></div>
                        <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated Size:</span></div><div style="color: #4ec9b0; text-align: right;"><b id="rhi-calc-size">{f"{calc_total_mb/1024.0:.2f} GB" if calc_total_mb >= 1024 else f"{calc_total_mb:.2f} MB"}</b></div>
                    </div>
                </div>

                <!-- Filtered Statistics -->
                <div class="analytics-card" style="flex: 1; min-width: 250px; background: rgba(59, 130, 246, 0.08); padding: 15px; border-radius: 6px; border: 1px solid var(--accent-color); text-align: center;">
                    <h4 style="margin: 0 0 10px 0; color: var(--accent-color); font-size: 0.8em; text-transform: uppercase;">Filtered Statistics</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; font-size: 0.85em; text-align: left; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px;">
                        <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Filtered Count:</span></div><div style="color: var(--accent-color); text-align: right;"><b id="rhi-filt-count">0</b></div>
                        <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Filtered Size:</span></div><div style="color: var(--accent-color); text-align: right;"><b id="rhi-filt-sum">{f"{calc_total_mb/1024.0:.2f} GB" if calc_total_mb >= 1024 else f"{calc_total_mb:.2f} MB"}</b></div>
                    </div>
                </div>
            </div>
        </div>
        """

        return f"""
        <div id="{self.id}" class="tab-content{active_cls}">
            <h3>RHI Memory Statistics</h3>
            {dashboard_html}
            {warning_html}
            <div class="search-container" data-no-reset="true">
                <input type="text" placeholder="Search RHI Memory Statistics..." onkeyup="filterRhiTable(this.value)">
                <span style="font-size: 10px; color: #666; font-weight: 600; text-transform: uppercase; margin-left: 10px;">Sort By:</span>
                <button class="action-btn active-sub" id="btn-default-{self.id}" onclick="resetRhiView()">Default View</button>
            </div>
            <div class="table-container">
                <table id="tbl-{self.id}">{thead}{tbody}</table>
            </div>
            <script>
                function updateRhiAggregates() {{
                    const table = document.getElementById('tbl-{self.id}');
                    const rows = Array.from(table.tBodies[0].rows);
                    let calcCount = 0, filtCount = 0;
                    let calcSum = 0, filtSum = 0;
                    
                    rows.forEach(row => {{
                        const isVisible = row.style.display !== 'none' && row.getAttribute('data-pinned') !== 'true';
                        const size = _parseSizeToMb(row.cells[row.cells.length-1].innerText);
                        
                        calcCount++;
                        calcSum += size;
                        
                        if (isVisible) {{
                            filtCount++;
                            filtSum += size;
                        }}
                    }});
                    
                    document.getElementById('rhi-calc-count').innerText = calcCount;
                    document.getElementById('rhi-calc-size').innerText = calcSum >= 1024 ? (calcSum/1024).toFixed(2) + " GB" : calcSum.toFixed(2) + " MB";
                    document.getElementById('rhi-filt-count').innerText = filtCount;
                    document.getElementById('rhi-filt-sum').innerText = filtSum >= 1024 ? (filtSum/1024).toFixed(2) + " GB" : filtSum.toFixed(2) + " MB";
                }}

                function filterRhiTable(term) {{
                    filterTable('tbl-{self.id}', -1, term);
                    updateRhiAggregates();
                    
                    const defBtn = document.getElementById('btn-default-{self.id}');
                    if (defBtn) {{
                        if (term) defBtn.classList.remove('active-sub');
                        else defBtn.classList.add('active-sub');
                    }}
                }}

                function resetRhiView() {{
                    const searchInput = document.querySelector('#{self.id} .search-container input');
                    if (searchInput) {{
                        searchInput.value = '';
                    }}
                    filterRhiTable('');

                    const defBtn = document.getElementById('btn-default-{self.id}');
                    if (defBtn) defBtn.classList.add('active-sub');

                    // Reset Table Sorting
                    const table = document.getElementById('tbl-{self.id}');
                    if (table) {{
                        const tbody = table.querySelector('tbody');
                        const rows = Array.from(tbody.querySelectorAll('tr'));
                        rows.sort((a, b) => {{
                           const ai = parseInt(a.getAttribute('data-index')) || 0;
                           const bi = parseInt(b.getAttribute('data-index')) || 0;
                           return ai - bi;
                        }});
                        rows.forEach(r => tbody.appendChild(r));
                        
                        table.querySelectorAll('th').forEach(th => {{
                            th.classList.remove('sort-asc', 'sort-desc');
                            th.removeAttribute('data-asc');
                        }});
                    }}
                }}

                function _parseSizeToMb(val) {{
                    val = val.replace(/,/g, '').toLowerCase();
                    let num = parseFloat(val) || 0;
                    if (val.includes('gb')) return num * 1024.0;
                    if (val.includes('mb')) return num;
                    if (val.includes('kb')) return num / 1024.0;
                    return num / 1024.0;
                }}

                document.addEventListener('DOMContentLoaded', updateRhiAggregates);
            </script>
        </div>
        """


class RhiResourceMemoryTab(ReportTab):
    def __init__(self):
        super().__init__("RHI Resource Memory Stats", "rhi-resource-memory")
        self.headers = ["Metric", "Total with info", "Total tracked"]

    def should_handle(self, line: str) -> bool:
        return 'command "rhi.DumpResourceMemory"' in line

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        if "rhi_resource_memory_data" not in context:
            context["rhi_resource_memory_data"] = {
                "metrics": [],
                "raw_lines": [],
                "has_large_content": False,
            }

        match1 = re.search(
            r"Tracked RHIResources \((\d+) total with info, (\d+) total tracked\)",
            line,
            re.IGNORECASE,
        )
        if match1:
            context["rhi_resource_memory_data"]["metrics"].append(
                ["Tracked RHI Resources", match1.group(1), match1.group(2)]
            )
            return

        match2 = re.search(
            r"Total tracked resource size:\s*([\d\.]+\s*[KMGM]?B)", line, re.IGNORECASE
        )
        if match2:
            size_str = match2.group(1).strip()
            size = try_format_cell_value("Size", size_str)
            context["rhi_resource_memory_data"]["metrics"].append(
                ["total tracked resource Size", size, size]
            )
            # Store raw MB for threshold check
            m = re.search(r"([\d\.]+)", size_str)
            if m:
                num_val = float(m.group(1))
                if num_val > 0:
                    context["rhi_resource_memory_data"]["has_large_content"] = True
            return

        if "MemReport:" not in line and line.strip():
            context["rhi_resource_memory_data"]["raw_lines"].append(line)

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        data = context.get("rhi_resource_memory_data", {})
        metrics = data.get("metrics", [])
        raw_lines = data.get("raw_lines", [])
        has_large_content = data.get("has_large_content", False)
        if not metrics and not raw_lines:
            return ""

        active_cls = " active" if is_active else ""
        thead = (
            "<thead><tr>"
            + "".join([f"<th>{h}</th>" for h in self.headers])
            + "</tr></thead>"
        )
        tbody = "<tbody>"
        for row in metrics:
            tbody += f'<tr><td>{row[0]}</td><td class="numeric">{row[1]}</td><td class="numeric">{row[2]}</td></tr>'
        tbody += "</tbody>"

        warning_html = ""
        if has_large_content:
            warning_html = """
            <div class="analytics-wrapper" style="background: var(--row-even); padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid var(--border-color);">
                <div class="alert alert-warning">
                    <div class="alert-icon">⚠️</div>
                    <div class="alert-content"><strong>WARNING:</strong> Large resource tracking detected. Detailed info is currently unparsed.</div>
                </div>
                <div class="alert alert-danger" style="margin-top: 15px;">
                    <div class="alert-icon">🛑</div>
                    <div class="alert-content"><strong>FATAL:</strong> Please Provide Feedback...</div>
                </div>
            </div>
            """

        raw_trace_html = ""
        if has_large_content:
            raw_trace_html = f"""
            <hr class="section-divider">
            <h4>Raw Trace Data</h4>
            <pre style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 8px; overflow-x: auto; font-size: 11px;">{"\n".join(raw_lines)}</pre>
            """

        return f"""
        <div id="{self.id}" class="tab-content{active_cls}">
            <h3>RHI Resource Memory Statistics</h3>
            {warning_html}
            <div class="search-container">
                <input type="text" placeholder="Search RHI Resource Memory Statistics..." onkeyup="filterTable('tbl-{self.id}', -1, this.value)">
            </div>
            <div class="table-container">
                <table id="tbl-{self.id}">{thead}{tbody}</table>
            </div>
            {raw_trace_html}
        </div>
        """
