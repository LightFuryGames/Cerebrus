import re
from typing import Any, Dict

from ..utils import try_format_cell_value
from . import ReportTab


class ObjectSummaryTab(ReportTab):
    def __init__(self):
        super().__init__("Object Summary", "object-summary")

    def should_handle(self, line: str) -> bool:
        return line.startswith('MemReport: Begin command "obj list -resourcesizesort"')

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        data = context
        if "obj_summary" not in data:
            data["obj_summary"] = {"headers": [], "rows": [], "total": None}

        summary = data["obj_summary"]

        if not line.strip():
            return
        if "Objects:" in line and "Total:" not in line:
            return

        # Check for summary total line: "40199 Objects (Total: 220.811M / Max: 224.660M ...)"
        if "Objects (Total:" in line:
            # Extract values using regex
            # Example: 40199 Objects (Total: 220.811M / Max: 224.660M / Res: 1110.933M | ResDedSys: 11.712M / ResDedVid: 1038.184M / ResUnknown: 61.038M)
            match = re.search(r"(\d+)\s+Objects\s+\(Total:\s+([\d\.]+M?)\s+/\s+Max:\s+([\d\.]+M?)\s+/\s+Res:\s+([\d\.]+M?)\s+\|\s+ResDedSys:\s+([\d\.]+M?)\s+/\s+ResDedVid:\s+([\d\.]+M?)\s+/\s+ResUnknown:\s+([\d\.]+M?)\)", line)
            if match:
                groups = match.groups()
                
                def fmt_unit(v):
                    v = v.strip()
                    if v.endswith("M"):
                        return v[:-1] + " MB"
                    return v

                summary["total"] = [
                    "TOTAL",
                    groups[0], # Count
                    fmt_unit(groups[1]), # Total (NumKB)
                    fmt_unit(groups[2]), # Max
                    fmt_unit(groups[3]), # Res
                    fmt_unit(groups[4]), # ResDedSys
                    fmt_unit(groups[5]), # ResDedVid
                    fmt_unit(groups[6])  # ResUnk
                ]
            return

        # Check for header
        if "Class" in line and "Count" in line:
            headers = re.split(r"\s+", line.strip())
            summary["headers"] = headers
        elif len(summary["headers"]) > 0:
            # Parse row
            cols = re.split(r"\s+", line.strip())
            if len(cols) == len(summary["headers"]):
                formatted_cols = []
                for i, val in enumerate(cols):
                    header = summary["headers"][i]
                    # Ensure space between num and unit if unit is at end
                    # Skip the first column (Class/Object name) to avoid splitting things like Texture2D
                    if i > 0 and re.search(r"\d[a-zA-Z]+$", val):
                         val = re.sub(r"(\d)([a-zA-Z]+)$", r"\1 \2", val)
                    
                    formatted_cols.append(try_format_cell_value(header, val))
                summary["rows"].append(formatted_cols)

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        data = context.get("obj_summary", {"headers": [], "rows": [], "total": None})
        headers = data["headers"]
        rows = data["rows"]
        total_row = data.get("total")
        active_cls = " active" if is_active else ""

        wrapper_start = f'<div id="{self.id}" class="tab-content{active_cls}">'

        if not rows:
            return f'{wrapper_start}<div class="loading">No Object Summary Data</div></div>'

        # Headers HTML
        head_html = "<tr>"
        for h in headers:
            is_num = "KB" in h or "Count" in h or "MB" in h
            cls = 'class="numeric"' if is_num else ""
            head_html += f"<th {cls}>{h}</th>"
        head_html += "</tr>"

        # Total Row (Pinned)
        total_html = ""
        if total_row:
            total_html = '<tr data-pinned="true" style="background-color: rgba(59, 130, 246, 0.2); font-weight: bold; position: sticky; top: 40px; z-index: 10;">'
            for cell in total_row:
                total_html += f'<td class="numeric">{cell}</td>'
            total_html += "</tr>"

        # Rows HTML
        rows_html = ""
        for row in rows:
            rows_html += "<tr>"
            for i, cell in enumerate(row):
                is_num = i > 0
                cls = 'class="numeric"' if is_num else ""
                rows_html += f"<td {cls}>{cell}</td>"
            rows_html += "</tr>"

        return f"""
            {wrapper_start}
            <h3>{self.name}</h3>
             <div class="search-container">
                <input type="text" placeholder="Filter classes..." onkeyup="filterTable('obj-summary-table', 0, this.value)">
            </div>
            <div class="table-container">
                <table id="obj-summary-table">
                    <thead>{head_html}</thead>
                    <tbody>
                        {total_html}
                        {rows_html}
                    </tbody>
                </table>
            </div>
            </div>
        """
