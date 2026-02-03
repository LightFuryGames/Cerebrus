import re
from typing import Any, Dict, List
from . import ReportTab
from ..utils import try_format_cell_value

class RhiMemoryTab(ReportTab):
    def __init__(self):
        super().__init__("RHI Memory stats", "rhi-memory-stats")
        self.headers = ["RHI resource Category", "STAT Category (STATGROUP_RHI)", "Size"]

    def should_handle(self, line: str) -> bool:
        return 'command "rhi.DumpMemory"' in line

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        if "rhi_memory_data" not in context:
            context["rhi_memory_data"] = []
        
        # Format:          0.000MB  -  Bindless Resource Heap - STAT_BindlessResourceHeapMemory - STATGROUP_RHI - STATCAT_Advanced
        # Regex to capture parts while ignoring STATGROUP_RHI and STATCAT_Advanced
        match = re.search(r"^\s*([\d\.]+\s*[KMGM]?B)\s*-\s*(.*?)\s*-\s*(STAT_.*?)\s*-\s*STATGROUP_RHI", line, re.IGNORECASE)
        if match:
            size_raw = match.group(1).strip()
            category = match.group(2).strip()
            stat_category = match.group(3).strip()
            
            # Format size to ensure space (e.g. 0.000MB -> 0.00 MB)
            size = try_format_cell_value("Size", size_raw)
            
            context["rhi_memory_data"].append([category, stat_category, size])
            return

        # Handle total line: 62686.836MB total
        total_match = re.search(r"^\s*([\d\.]+\s*[KMGM]?B)\s*total", line, re.IGNORECASE)
        if total_match:
            size_raw = total_match.group(1).strip()
            context["rhi_memory_total_val"] = try_format_cell_value("Size", size_raw)

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        data = context.get("rhi_memory_data", [])
        total_val = context.get("rhi_memory_total_val", "")
        
        if not data and not total_val:
            return ""

        active_cls = " active" if is_active else ""
        
        thead = "<thead><tr>" + "".join([f"<th>{h}</th>" for h in self.headers]) + "</tr></thead>"
        tbody = "<tbody>"
        
        # Add pinned TOTAL row
        if total_val:
            tbody += f'<tr data-pinned="true" style="background-color: rgba(59, 130, 246, 0.2); font-weight: bold; position: sticky; top: 40px; z-index: 10;">'
            tbody += f'<td>TOTAL</td><td></td><td class="numeric">{total_val}</td></tr>'

        for row in data:
            tbody += "<tr>"
            tbody += f"<td>{row[0]}</td>"
            tbody += f"<td>{row[1]}</td>"
            tbody += f'<td class="numeric">{row[2]}</td>'
            tbody += "</tr>"
        tbody += "</tbody>"
        
        html = f"""
        <div id="{self.id}" class="tab-content{active_cls}">
            <h3>{self.name}</h3>
            <div class="search-container">
                <input type="text" placeholder="Search {self.name}..." onkeyup="filterTable('tbl-{self.id}', 0, this.value)">
            </div>
            <div class="table-container">
                <table id="tbl-{self.id}">
                    {thead}
                    {tbody}
                </table>
            </div>
        </div>
        """
        return html

class RhiResourceMemoryTab(ReportTab):
    def __init__(self):
        super().__init__("RHI Resource Memory", "rhi-resource-memory")
        self.headers = ["Metric", "Total with info", "Total tracked"]

    def should_handle(self, line: str) -> bool:
        return 'command "rhi.DumpResourceMemory"' in line

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        if "rhi_resource_memory_data" not in context:
            context["rhi_resource_memory_data"] = {
                "metrics": [],
                "raw_lines": [],
                "has_large_content": False
            }
        
        # Parse: Tracked RHIResources (0 total with info, 17414 total tracked)
        match1 = re.search(r"Tracked RHIResources \((\d+) total with info, (\d+) total tracked\)", line, re.IGNORECASE)
        if match1:
            total_with_info = match1.group(1)
            total_tracked = match1.group(2)
            context["rhi_resource_memory_data"]["metrics"].append(["Tracked RHI Resources", total_with_info, total_tracked])
            return

        # Parse: Total tracked resource size: 0.000000000 MB
        match2 = re.search(r"Total tracked resource size:\s*([\d\.]+\s*[KMGM]?B)", line, re.IGNORECASE)
        if match2:
            size_raw = match2.group(1).strip()
            size = try_format_cell_value("Size", size_raw)
            # The user requested: total tracked resource Size, 0.000000000 MB, 0.000000000 MB
            # We use the same size for both if we don't have separate info
            context["rhi_resource_memory_data"]["metrics"].append(["total tracked resource Size", size, size])
            
            # Check if size > 0
            size_num_match = re.search(r"([\d\.]+)", size_raw)
            if size_num_match:
                try:
                    size_val = float(size_num_match.group(1))
                    if size_val > 0.0:
                        context["rhi_resource_memory_data"]["has_large_content"] = True
                except ValueError:
                    pass
            return

        # If it's not a begin/end command line and not matched above, store as raw if it's not empty
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
        
        thead = "<thead><tr>" + "".join([f"<th>{h}</th>" for h in self.headers]) + "</tr></thead>"
        tbody = "<tbody>"
        
        for row in metrics:
            tbody += "<tr>"
            tbody += f"<td>{row[0]}</td>"
            tbody += f'<td class="numeric">{row[1]}</td>'
            tbody += f'<td class="numeric">{row[2]}</td>'
            tbody += "</tr>"
        tbody += "</tbody>"
        
        warning_html = ""
        if has_large_content:
            warning_html = f"""
            <div class="alert alert-warning" style="display: flex; align-items: center; gap: 20px; margin-bottom: 10px;">
                <div class="alert-icon">⚠️</div>
                <div class="alert-content">
                    <strong><u>WARNING</u></strong>: Large resource tracking detected. Detailed info is currently unparsed.
                </div>
            </div>
            <div class="alert alert-feedback" style="display: flex; align-items: center; gap: 20px;">
                <div class="alert-icon">🛑</div>
                <div class="alert-content" style="font-weight: 600;">
                    <strong><u>FATAL</u></strong> :- Please Provide Feedback to the Tech & Tools team to request a parsing update for this section with a copy of this HTML file or a new raw .memreport file using the Cerebrus Help -> Provide Feedback in the top Menu toolbar
                </div>
            </div>
            """

        content = f"""
        {warning_html}
        <div class="search-container">
            <input type="text" placeholder="Search RHI Resource Memory..." onkeyup="filterTable('tbl-{self.id}', 0, this.value)">
        </div>
        <div class="table-container">
            <table id="tbl-{self.id}">
                {thead}
                {tbody}
            </table>
        </div>
        """
        
        if has_large_content:
            content += f"""
            <hr class="section-divider">
            <h4>Raw Trace Data</h4>
            <div class="table-container">
                <pre style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 8px; overflow-x: auto;">{"\n".join(raw_lines)}</pre>
            </div>
            """
        
        html = f"""
        <div id="{self.id}" class="tab-content{active_cls}">
            <h3>{self.name}</h3>
            {content}
        </div>
        """
        return html
