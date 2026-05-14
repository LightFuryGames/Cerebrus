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
        if not line.strip():
            return
        if "Objects:" in line and "Total:" not in line:
            return

        if "Objects (Total:" in line:
            # Objects (Total: 1047.81 MB / Max: 1047.81 MB / Res: 864.63 MB | ResDedSys: 864.55 MB / ResDedVid: 0.00 MB / ResUnknown: 0.08 MB)
            match = re.search(
                r"(\d+)\s+Objects\s+\(Total:\s+([\d\.]+M?)\s+/\s+Max:\s+([\d\.]+M?)\s+/\s+Res:\s+([\d\.]+M?)\s+\|\s+ResDedSys:\s+([\d\.]+M?)\s+/\s+ResDedVid:\s+([\d\.]+M?)\s+/\s+ResUnknown:\s+([\d\.]+M?)\)",
                line,
            )
            if match:
                groups = match.groups()

                def fmt_val(v):
                    v = v.strip()
                    if v.endswith("M"):
                        return float(v[:-1])
                    return float(v)

                summary["total_data"] = {
                    "count": int(groups[0]),
                    "total": fmt_val(groups[1]),
                    "max": fmt_val(groups[2]),
                    "res": fmt_val(groups[3]),
                    "res_ded_sys": fmt_val(groups[4]),
                    "res_ded_vid": fmt_val(groups[5]),
                    "res_unknown": fmt_val(groups[6]),
                }
            return

        if "Class" in line and "Count" in line:
            headers = re.split(r"\s+", line.strip())
            # Rename Count to Instance Count in headers
            self.headers = [h if h != "Count" else "Instance Count" for h in headers]
            summary["headers"] = self.headers
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
        data = context.get(
            "obj_summary", {"headers": [], "rows": [], "total_data": None}
        )
        headers, rows, total_data = (
            data["headers"],
            data["rows"],
            data.get("total_data"),
        )
        active_cls = " active" if is_active else ""
        if not rows:
            return f'<div id="{self.id}" class="tab-content{active_cls}"><div class="loading">No Object Summary Data</div></div>'

        # Headers - index 0 is Class, 1 is Count, 2 is NumKB...
        head_html = (
            "<tr>"
            + "".join(
                [
                    f'<th {"class=\'numeric\'" if i>0 else ""}>{h}</th>'
                    for i, h in enumerate(headers)
                ]
            )
            + "</tr>"
        )

        rows_html = ""
        for row in rows:
            rows_html += (
                "<tr>"
                + "".join(
                    [
                        f'<td {"class=\'numeric\'" if i>0 else ""}>{c}</td>'
                        for i, c in enumerate(row)
                    ]
                )
                + "</tr>"
            )

        overall_stats = ""
        if total_data:
            overall_stats = f"""
            <div class="analytics-card" style="flex: 1; min-width: 250px; background: var(--header-bg); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color); text-align: center;">
                <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">
                    Reported Total<br>
                    <span class="unreal-red" style="font-size: 0.85em;">(UNREAL REPORTED)</span>
                </h4>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; font-size: 0.85em; text-align: left; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px;">
                    <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Reported Instance Count:</span></div><div style="color: #ce9178; text-align: right;"><b>{total_data['count']:,}</b></div>
                    <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Reported NumKB:</span></div><div style="color: #ce9178; text-align: right;"><b>{total_data['total']:.2f} MB</b></div>
                    <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Reported MaxKB:</span></div><div style="color: #ce9178; text-align: right;"><b>{total_data['max']:.2f} MB</b></div>
                    <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Reported ResExcKB:</span></div><div style="color: #ce9178; text-align: right;"><b>{total_data['res']:.2f} MB</b></div>
                </div>
            </div>
            """

        calculated_stats = f"""
        <div class="analytics-card" style="flex: 1; min-width: 250px; background: var(--header-bg); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color); text-align: center;">
            <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated Total</h4>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; font-size: 0.85em; text-align: left; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px;">
                <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated Instance Count:</span></div><div style="color: #4ec9b0; text-align: right;"><b id="obj-calc-instances">0</b></div>
                <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated NumKB:</span></div><div style="color: #4ec9b0; text-align: right;"><b id="obj-calc-numkb">0.00 MB</b></div>
                <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated MaxKB:</span></div><div style="color: #4ec9b0; text-align: right;"><b id="obj-calc-maxkb">0.00 MB</b></div>
                <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated ResExcKB:</span></div><div style="color: #4ec9b0; text-align: right;"><b id="obj-calc-reskb">0.00 MB</b></div>
            </div>
        </div>
        """

        filtered_stats = f"""
        <div class="analytics-card" style="flex: 1; min-width: 250px; background: rgba(59, 130, 246, 0.08); padding: 15px; border-radius: 6px; border: 1px solid var(--accent-color); text-align: center;">
            <h4 style="margin: 0 0 10px 0; color: var(--accent-color); font-size: 0.8em; text-transform: uppercase;">Filtered Statistics</h4>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; font-size: 0.85em; text-align: left; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px;">
                <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Filtered Instance Count:</span></div><div style="color: var(--accent-color); text-align: right;"><b id="obj-filtered-instances">0</b></div>
                <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Filtered NumKB:</span></div><div style="color: var(--accent-color); text-align: right;"><b id="obj-filtered-numkb">0.00 MB</b></div>
                <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Filtered MaxKB:</span></div><div style="color: var(--accent-color); text-align: right;"><b id="obj-filtered-maxkb">0.00 MB</b></div>
                <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Filtered ResExcKB:</span></div><div style="color: var(--accent-color); text-align: right;"><b id="obj-filtered-reskb">0.00 MB</b></div>
            </div>
            <div style="margin-top: 5px; font-size: 0.8em; color: var(--text-muted); border-top: 1px solid rgba(255,255,255,0.05); padding-top: 5px;">
                Classes Visible: <b id="obj-filtered-count" style="color: var(--accent-color);">0</b>
            </div>
        </div>
        """

        # Python-side Count Mismatch check
        warning_html = ""
        if total_data:
            sum_instances = sum(
                int(re.sub(r"[^0-9]", "", str(r[1]))) if len(r) > 1 and r[1] else 0
                for r in data["rows"]
            )
            if sum_instances != total_data["count"]:
                diff = total_data["count"] - sum_instances
                warning_html = f"""
                <div class="alert alert-warning" style="margin-top: 15px;">
                    <div class="alert-icon">⚠️</div>
                    <div class="alert-content">
                        <strong>WARNING: Count Mismatch:</strong> Unreal's summary reports <b>{total_data['count']:,}</b> objects, but the detailed list contains only <b>{sum_instances:,}</b> entries. Stats for <b>{abs(diff):,}</b> objects are missing from the detailed dump.
                    </div>
                </div>
                """

        idx_count = 1
        idx_numkb = 2
        idx_maxkb = 3
        idx_reskb = 4

        return f"""
        <div id="{self.id}" class="tab-content{active_cls}">
            <h3>Object Summary Statistics</h3>
            
            <div class="analytics-wrapper" style="background: var(--row-even); padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid var(--border-color);">
                <div class="analytics-row" style="display: flex; gap: 20px; flex-wrap: wrap;">
                    {overall_stats}
                    {calculated_stats}
                    {filtered_stats}
                </div>
                {warning_html}
            </div>
            
            <div class="search-container" data-no-reset="true">
                <input type="text" placeholder="Filter classes..." onkeyup="filterObjTable(this.value)">
                <span style="font-size: 10px; color: #666; font-weight: 600; text-transform: uppercase;">Sort By:</span>
                <button class="action-btn active-sub" id="btn-default-{self.id}" onclick="resetObjTable()">Resource Size</button>
            </div>
            <div class="table-container">
                <table id="obj-summary-table">
                    <thead>{head_html}</thead>
                    <tbody>{rows_html}</tbody>
                </table>
            </div>

            <script>
                function parseObjSize(val) {{
                    val = val.replace(/,/g, '').toLowerCase();
                    let num = parseFloat(val) || 0;
                    if (val.includes('mb')) return num;
                    if (val.includes('kb')) return num / 1024.0;
                    if (val.includes('gb')) return num * 1024.0;
                    return num / 1024.0; // Assume KB if no unit or unknown
                }}

                function updateObjAggregates() {{
                    const table = document.getElementById('obj-summary-table');
                    if (!table) return;
                    
                    const headerRow = table.querySelector('thead tr');
                    if (!headerRow) return;
                    
                    const headers = Array.from(headerRow.cells).map(th => th.innerText.trim());
                    const idxInst = headers.indexOf('Instance Count');
                    const idxNumKB = headers.indexOf('NumKB');
                    const idxMaxKB = headers.indexOf('MaxKB');
                    const idxResKB = headers.indexOf('ResExcKB');
                    
                    if (idxInst === -1) return; // Wait for headers to be ready or counter to be added if needed
                    
                    const rows = Array.from(table.tBodies[0].rows);
                    let calcInstances = 0, calcNumKB = 0, calcMaxKB = 0, calcResKB = 0;
                    let filtCount = 0, filtInstances = 0, filtNumKB = 0, filtMaxKB = 0, filtResKB = 0;
                    
                    rows.forEach(row => {{
                        const cells = row.cells;
                        if (cells.length <= Math.max(idxInst, idxNumKB, idxMaxKB, idxResKB)) return;
                        
                        const inst = parseInt(cells[idxInst].innerText.replace(/,/g, '')) || 0;
                        const nkb = parseObjSize(cells[idxNumKB].innerText);
                        const mkb = parseObjSize(cells[idxMaxKB].innerText);
                        const rkb = parseObjSize(cells[idxResKB].innerText);

                        calcInstances += inst;
                        calcNumKB += nkb;
                        calcMaxKB += mkb;
                        calcResKB += rkb;

                        if (row.style.display !== 'none') {{
                            filtCount++;
                            filtInstances += inst;
                            filtNumKB += nkb;
                            filtMaxKB += mkb;
                            filtResKB += rkb;
                        }}
                    }});

                    document.getElementById('obj-calc-instances').innerText = calcInstances.toLocaleString();
                    document.getElementById('obj-calc-numkb').innerText = calcNumKB.toFixed(2) + " MB";
                    document.getElementById('obj-calc-maxkb').innerText = calcMaxKB.toFixed(2) + " MB";
                    document.getElementById('obj-calc-reskb').innerText = calcResKB.toFixed(2) + " MB";

                    document.getElementById('obj-filtered-count').innerText = filtCount;
                    document.getElementById('obj-filtered-instances').innerText = filtInstances.toLocaleString();
                    document.getElementById('obj-filtered-numkb').innerText = filtNumKB.toFixed(2) + " MB";
                    document.getElementById('obj-filtered-maxkb').innerText = filtMaxKB.toFixed(2) + " MB";
                    document.getElementById('obj-filtered-reskb').innerText = filtResKB.toFixed(2) + " MB";
                }}

                function filterObjTable(term) {{
                    filterTable('obj-summary-table', 0, term); 
                    updateObjAggregates();
                    const defBtn = document.getElementById('btn-default-{self.id}');
                    if (defBtn) {{
                        defBtn.classList.remove('active-sub');
                        if(!term) defBtn.classList.add('active-sub');
                    }}
                }}

                function resetObjTable() {{
                    const table = document.getElementById('obj-summary-table');
                    const tbody = table.tBodies[0];
                    const rows = Array.from(tbody.rows);
                    rows.sort((a, b) => a.getAttribute('data-original-index') - b.getAttribute('data-original-index'));
                    rows.forEach(r => {{
                        tbody.appendChild(r);
                        r.style.display = '';
                    }});
                    table.querySelectorAll('th').forEach(th => {{ 
                        th.classList.remove('sort-asc', 'sort-desc'); 
                        th.removeAttribute('data-asc'); 
                    }});
                    document.querySelector('.search-container input').value = '';
                    document.getElementById('btn-default-{self.id}').classList.add('active-sub');
                    updateObjAggregates();
                    updateTableCounters(table);
                }}

                document.addEventListener('DOMContentLoaded', () => {{
                    setTimeout(updateObjAggregates, 100);
                    // Hook into sorting
                    const table = document.getElementById('obj-summary-table');
                    if (table) {{
                        table.querySelectorAll('th').forEach(th => {{
                            th.addEventListener('click', () => {{
                                setTimeout(updateObjAggregates, 10);
                                const defBtn = document.getElementById('btn-default-{self.id}');
                                if (defBtn) defBtn.classList.remove('active-sub');
                            }});
                        }});
                    }}
                }});
            </script>
        </div>
        """
