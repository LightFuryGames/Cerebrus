import re
from typing import Any, Dict

from ..utils import try_format_cell_value
from . import ReportTab

class ObjectSummaryTab(ReportTab):
    def __init__(self):
        super().__init__("Object Summary Stats", "object-summary")

    def should_handle(self, line: str) -> bool:
        return line.startswith('MemReport: Begin command "obj list -resourcesizesort"')

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        data = context
        if "obj_summary" not in data:
            data["obj_summary"] = {"headers": [], "rows": [], "total": None}
        summary = data["obj_summary"]
        if not line.strip(): return
        if "Objects:" in line and "Total:" not in line: return

        if "Objects (Total:" in line:
            match = re.search(r"(\d+)\s+Objects\s+\(Total:\s+([\d\.]+M?)\s+/\s+Max:\s+([\d\.]+M?)\s+/\s+Res:\s+([\d\.]+M?)\s+\|\s+ResDedSys:\s+([\d\.]+M?)\s+/\s+ResDedVid:\s+([\d\.]+M?)\s+/\s+ResUnknown:\s+([\d\.]+M?)\)", line)
            if match:
                groups = match.groups()
                def fmt_unit(v):
                    v = v.strip()
                    if v.endswith("M"): return v[:-1] + " MB"
                    return v
                summary["total"] = ["TOTAL", groups[0], fmt_unit(groups[1]), fmt_unit(groups[2]), fmt_unit(groups[3]), fmt_unit(groups[4]), fmt_unit(groups[5]), fmt_unit(groups[6])]
            return

        if "Class" in line and "Count" in line:
            summary["headers"] = re.split(r"\s+", line.strip())
        elif len(summary["headers"]) > 0:
            cols = re.split(r"\s+", line.strip())
            if len(cols) == len(summary["headers"]):
                formatted_cols = []
                for i, val in enumerate(cols):
                    header = summary["headers"][i]
                    if i > 0 and re.search(r"\d[a-zA-Z]+$", val):
                         val = re.sub(r"(\d)([a-zA-Z]+)$", r"\1 \2", val)
                    formatted_cols.append(try_format_cell_value(header, val))
                summary["rows"].append(formatted_cols)

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        data = context.get("obj_summary", {"headers": [], "rows": [], "total": None})
        headers, rows, total_row = data["headers"], data["rows"], data["total"]
        active_cls = " active" if is_active else ""
        if not rows: return f'<div id="{self.id}" class="tab-content{active_cls}"><div class="loading">No Object Summary Data</div></div>'

        head_html = "<tr>" + "".join([f'<th {"class=\'numeric\'" if "KB" in h or "Count" in h or "MB" in h else ""}>{h}</th>' for h in headers]) + "</tr>"
        total_html = ""
        if total_row:
            total_html = '<tr data-pinned="true" style="background-color: rgba(59, 130, 246, 0.2); font-weight: bold; position: sticky; top: 40px; z-index: 10;">'
            total_html += "".join([f'<td class="numeric">{cell}</td>' for cell in total_row]) + "</tr>"

        rows_html = ""
        for row in rows:
            rows_html += "<tr>" + "".join([f'<td {"class=\'numeric\'" if i>0 else ""}>{c}</td>' for i, c in enumerate(row)]) + "</tr>"

        return f"""
        <div id="{self.id}" class="tab-content{active_cls}">
            <h3>Object Summary Statistics</h3>
             <div class="search-container" data-no-reset="true">
                <input type="text" placeholder="Filter classes..." onkeyup="filterTable('obj-summary-table', 0, this.value)">
                <span style="font-size: 10px; color: #666; font-weight: 600; text-transform: uppercase;">Sort By:</span>
                <button class="action-btn active-sub" onclick="(function(btn){{
                    const container = btn.closest('.search-container');
                    container.querySelectorAll('.action-btn').forEach(b => b.classList.remove('active-sub'));
                    btn.classList.add('active-sub');

                    const table = document.getElementById('obj-summary-table');
                    const tbody = table.querySelector('tbody');
                    const rows = Array.from(tbody.querySelectorAll('tr'));
                    rows.sort((a, b) => a.getAttribute('data-original-index') - b.getAttribute('data-original-index'));
                    rows.forEach(r => tbody.appendChild(r));
                    table.querySelectorAll('th').forEach(th => {{ th.classList.remove('sort-asc', 'sort-desc'); th.removeAttribute('data-asc'); }});
                }})(this)">Resource Size</button>
            </div>
            <div class="table-container">
                <table id="obj-summary-table">
                    <thead>{head_html}</thead>
                    <tbody>{total_html}{rows_html}</tbody>
                </table>
            </div>
        </div>
        """
