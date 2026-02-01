
import re
from typing import Dict, Any
from . import ReportTab
from ..utils import try_format_cell_value

class ObjectSummaryTab(ReportTab):
    def __init__(self):
        super().__init__("Object Summary", "object-summary")
        
    def should_handle(self, line: str) -> bool:
        return line.startswith('MemReport: Begin command "obj list -resourcesizesort"')
        
    def parse(self, line: str, context: Dict[str, Any]) -> None:
        data = context
        if "obj_summary" not in data:
            data["obj_summary"] = {"headers": [], "rows": []}
            
        summary = data["obj_summary"]
        
        if not line.strip(): return
        if "Objects:" in line: return
        
        # Check for header
        if "Class" in line and "Count" in line:
            headers = re.split(r'\s+', line.strip())
            summary["headers"] = headers
        elif len(summary["headers"]) > 0:
             # Parse row
             cols = re.split(r'\s+', line.strip())
             if len(cols) == len(summary["headers"]):
                 formatted_cols = []
                 for i, val in enumerate(cols):
                     header = summary["headers"][i]
                     formatted_cols.append(try_format_cell_value(header, val))
                 summary["rows"].append(formatted_cols)
    
    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        data = context.get("obj_summary", {"headers": [], "rows": []})
        headers = data["headers"]
        rows = data["rows"]
        active_cls = " active" if is_active else ""
        
        wrapper_start = f'<div id="{self.id}" class="tab-content{active_cls}">'
        
        if not rows:
            return f'{wrapper_start}<div class="loading">No Object Summary Data</div></div>'
            
        # Headers HTML
        head_html = "<tr>"
        for h in headers:
            is_num = "KB" in h or "Count" in h or "MB" in h
            cls = 'class="numeric"' if is_num else ''
            head_html += f'<th {cls}>{h}</th>'
        head_html += "</tr>"
        
        # Rows HTML
        rows_html = ""
        for row in rows:
            rows_html += "<tr>"
            for i, cell in enumerate(row):
                is_num = i > 0 
                cls = 'class="numeric"' if is_num else ''
                rows_html += f'<td {cls}>{cell}</td>'
            rows_html += "</tr>"
            
        return f"""
            {wrapper_start}
             <div class="search-container">
                <input type="text" placeholder="Filter classes..." onkeyup="filterTable('obj-summary-table', 0, this.value)">
            </div>
            <div class="table-container">
                <table id="obj-summary-table">
                    <thead>{head_html}</thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </div>
            </div>
        """
