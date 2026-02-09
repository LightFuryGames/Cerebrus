import re
from typing import Any, Dict, List, Optional

from ..utils import try_format_cell_value
from . import ReportTab


class ClassStatsTab(ReportTab):
    def _parse_total_line(self, line: str) -> Optional[Dict[str, Any]]:
        # Count is usually at the start
        count_match = re.search(r"(\d+)\s+Objects", line)
        count = int(count_match.group(1)) if count_match else 0

        # Use a helper to extract values with unit awareness
        def get_val(key: str) -> float:
            # Matches "Key: 123.45M" or "Key: 123.45"
            m = re.search(rf"{key}:\s+([\d\.]+)\s*(M|K|G)?", line, re.IGNORECASE)
            if m:
                val = float(m.group(1))
                unit = (m.group(2) or "").upper()
                if unit == "M":
                    return val
                if unit == "K":
                    return val / 1024.0
                if unit == "G":
                    return val * 1024.0
                return val  # Default to MB if possible? Unreal usually uses MB for these totals.
            return 0.0

        return {
            "count": count,
            "total": get_val("Total"),
            "max": get_val("Max"),
            "res": get_val("Res"),
        }

    def __init__(self) -> None:
        super().__init__("Class Memory Stats", "class-stats-generic")
        self.current_class: Optional[str] = None
        self.current_sort: Optional[str] = None
        self.parsing_summary = False
        self.detected_classes: set[str] = set()

    def should_handle(self, line: str) -> bool:
        return line.startswith('MemReport: Begin command "obj list class=')

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        if "class_stats" not in context:
            context["class_stats"] = {}

        if line.startswith('MemReport: Begin command "obj list class='):
            match = re.search(r"class=([^\s]+)\s+(-[a-z]+)", line)
            if match:
                cls_name = match.group(1)
                sort_switch = match.group(2)

                self.current_class = cls_name
                self.detected_classes.add(cls_name)
                self.parsing_summary = False

                if sort_switch == "-resourcesizesort":
                    self.current_sort = "resource_size"
                elif sort_switch == "-alphasort":
                    self.current_sort = "alpha_sort"
                else:
                    self.current_sort = "unknown"

                if cls_name not in context["class_stats"]:
                    context["class_stats"][cls_name] = {
                        "resource_size": None,
                        "alpha_sort": None,
                        "summary": None,
                        "overall_total": None,
                    }

                context["class_stats"][cls_name][self.current_sort] = {
                    "headers": [],
                    "rows": [],
                }
            return

        if not self.current_class or not self.current_sort:
            return

        stats = context["class_stats"][self.current_class]
        current_data = stats[self.current_sort]

        stripped = line.strip()
        if not stripped:
            return

        if stripped.startswith("Obj List:") or stripped == "Objects:":
            return

        # Summary Detection
        if "Class" in line and "Count" in line and "NumKB" in line:
            self.parsing_summary = True
            if stats["summary"] is None:
                stats["summary"] = {
                    "headers": [
                        h.strip() for h in re.split(r"\s+", stripped) if h.strip()
                    ],
                    "rows": [],
                }
            return

        # Overall Total Detection
        if "Objects (Total:" in line:
            stats["overall_total"] = stripped
            stats["total_data"] = self._parse_total_line(stripped)
            return

        if self.parsing_summary:
            cols = [c.strip() for c in re.split(r"\s+", stripped) if c.strip()]
            if stats["summary"] and len(cols) == len(stats["summary"]["headers"]):
                fmt_row = [
                    try_format_cell_value(stats["summary"]["headers"][i], c)
                    for i, c in enumerate(cols)
                ]

                # Deduplicate by class name (first column)
                existing_classes = [r[0] for r in stats["summary"]["rows"]]
                if fmt_row[0] not in existing_classes:
                    stats["summary"]["rows"].append(fmt_row)
            return

        # Main Table Header Detection
        if "Object" in line and "NumKB" in line:
            headers = [h.strip() for h in re.split(r"\s+", stripped) if h.strip()]
            if "Class" not in headers:
                headers.insert(0, "Class")
            current_data["headers"] = headers
            return

        # Main Table Row Parsing
        if current_data["headers"]:
            cols = [c.strip() for c in re.split(r"\s+", stripped) if c.strip()]
            if len(cols) == len(current_data["headers"]):
                fmt_row = [
                    try_format_cell_value(current_data["headers"][i], c)
                    for i, c in enumerate(cols)
                ]
                current_data["rows"].append(fmt_row)

    def get_buttons(self, context: Dict[str, Any]) -> str:
        buttons_html = ""
        class_stats = context.get("class_stats", {})
        sorted_classes = sorted(class_stats.keys())
        for cls_name in sorted_classes:
            tab_id = f"class-{cls_name}"
            buttons_html += f'<button class="tab-btn" onclick="openTab(event, \'{tab_id}\')">{cls_name} Memory Stats</button>'
        return buttons_html

    def get_tab_info(self) -> List[Dict[str, str]]:
        tabs = []
        for cls_name in sorted(list(self.detected_classes)):
            tabs.append(
                {"id": f"class-{cls_name}", "name": f"{cls_name} Memory Statistics"}
            )
        return tabs

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        html_out = ""
        class_stats = context.get("class_stats", {})
        sorted_classes = sorted(class_stats.keys())

        # Consistent Reset JS
        reset_js = """
            const table = document.getElementById(tableId);
            if(table) {
                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));
                rows.sort((a, b) => {
                   const ai = a.getAttribute('data-index') || 0;
                   const bi = b.getAttribute('data-index') || 0;
                   return ai - bi;
                });
                rows.forEach(r => tbody.appendChild(r));
                table.querySelectorAll('th').forEach(th => {
                    th.classList.remove('sort-asc', 'sort-desc');
                    th.removeAttribute('data-asc');
                });
            }
        """

        for idx, cls_name in enumerate(sorted_classes):
            stats = class_stats[cls_name]
            tab_id = f"class-{cls_name}"
            total_data = stats.get("total_data")

            has_res = stats.get("resource_size") is not None
            has_alpha = stats.get("alpha_sort") is not None

            # Count Mismatch Warning
            warning_html = ""
            if total_data:
                # Sum the count from the primary view
                check_view = stats.get("resource_size") or stats.get("alpha_sort")
                if check_view:
                    sum_count = len(check_view["rows"])
                    if sum_count != total_data["count"]:
                        diff = total_data["count"] - sum_count
                        warning_html = f"""
                        <div class="alert alert-warning" style="margin-top: 15px;">
                            <div class="alert-icon">⚠️</div>
                            <div class="alert-content">
                                <strong>WARNING: Count Mismatch:</strong> Unreal's summary reports <b>{total_data['count']:,}</b> {cls_name} instances, but the detailed list contains only <b>{sum_count:,}</b> entries. Stats for <b>{abs(diff):,}</b> {cls_name}s are missing from the detailed data dump.
                            </div>
                        </div>
                        """

            header_html = f"<h3>{cls_name} Memory Statistics</h3>"

            # Dashboard Section
            reported_total_card = ""
            if total_data:
                reported_total_card = f"""
                <div class="analytics-card" style="flex: 1; min-width: 250px; background: var(--header-bg); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color); text-align: center;">
                    <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">
                        Reported Total<br>
                        <span class="unreal-red" style="font-size: 0.85em;">(UNREAL REPORTED)</span>
                    </h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; font-size: 0.85em; text-align: left; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px;">
                        <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Reported Count:</span></div><div style="color: #ce9178; text-align: right;"><b>{total_data['count']:,}</b></div>
                        <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Reported NumKB:</span></div><div style="color: #ce9178; text-align: right;"><b>{total_data['total']:.2f} MB</b></div>
                        <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Reported MaxKB:</span></div><div style="color: #ce9178; text-align: right;"><b>{total_data['max']:.2f} MB</b></div>
                        <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Reported ResExcKB:</span></div><div style="color: #ce9178; text-align: right;"><b>{total_data['res']:.2f} MB</b></div>
                    </div>
                </div>
                """

            calculated_total_card = f"""
            <div class="analytics-card" style="flex: 1; min-width: 250px; background: var(--header-bg); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color); text-align: center;">
                <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated Total</h4>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; font-size: 0.85em; text-align: left; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px;">
                    <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated Count:</span></div><div style="color: #4ec9b0; text-align: right;"><b id="calc-count-{tab_id}">0</b></div>
                    <div id="calc-box-numkb-{tab_id}"><div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated NumKB:</span></div></div><div style="color: #4ec9b0; text-align: right;"><b id="calc-numkb-{tab_id}">0.00 MB</b></div>
                    <div id="calc-box-maxkb-{tab_id}"><div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated MaxKB:</span></div></div><div style="color: #4ec9b0; text-align: right;"><b id="calc-maxkb-{tab_id}">0.00 MB</b></div>
                    <div id="calc-box-reskb-{tab_id}"><div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated ResExcKB:</span></div></div><div style="color: #4ec9b0; text-align: right;"><b id="calc-reskb-{tab_id}">0.00 MB</b></div>
                </div>
            </div>
            """

            filtered_stats_card = f"""
            <div class="analytics-card" title-id="{tab_id}" style="flex: 1; min-width: 250px; background: rgba(59, 130, 246, 0.08); padding: 15px; border-radius: 6px; border: 1px solid var(--accent-color); text-align: center;">
                <h4 style="margin: 0 0 10px 0; color: var(--accent-color); font-size: 0.8em; text-transform: uppercase;">Filtered Statistics</h4>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 4px 10px; font-size: 0.85em; text-align: left; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px;">
                    <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Filtered Count:</span></div><div style="color: var(--accent-color); text-align: right;"><b id="filt-count-{tab_id}">0</b></div>
                    <div id="filt-box-numkb-{tab_id}"><div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Filtered NumKB:</span></div></div><div style="color: var(--accent-color); text-align: right;"><b id="filt-numkb-{tab_id}">0.00 MB</b></div>
                    <div id="filt-box-maxkb-{tab_id}"><div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Filtered MaxKB:</span></div></div><div style="color: var(--accent-color); text-align: right;"><b id="filt-maxkb-{tab_id}">0.00 MB</b></div>
                    <div id="filt-box-reskb-{tab_id}"><div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Filtered ResExcKB:</span></div></div><div style="color: var(--accent-color); text-align: right;"><b id="filt-reskb-{tab_id}">0.00 MB</b></div>
                </div>
            </div>
            """

            summary_html = f"""
            <div class="analytics-wrapper" style="background: var(--row-even); padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid var(--border-color);">
                <div class="analytics-row" style="display: flex; gap: 20px; flex-wrap: wrap;">
                    {reported_total_card}
                    {calculated_total_card}
                    {filtered_stats_card}
                </div>
                {warning_html}
            </div>
            """

            def render_view_content(view_key, view_suffix, is_visible):
                view_data = stats.get(view_key)
                if not view_data:
                    return ""

                v_headers = [
                    h if h != "Count" else "Instance Count"
                    for h in view_data["headers"]
                ]
                v_rows = view_data["rows"]
                view_id = f"{tab_id}-{view_suffix}"
                display_style = "block" if is_visible else "none"

                th_html = (
                    "<thead><tr>"
                    + "".join(
                        [
                            f'<th {"class=\\'numeric\\'" if i>1 else ""}>{h}</th>'
                            for i, h in enumerate(v_headers)
                        ]
                    )
                    + "</tr></thead>"
                )
                tr_html = "<tbody>"
                for r_idx, r in enumerate(v_rows):
                    tr_html += (
                        f'<tr data-index="{r_idx}">'
                        + "".join(
                            [
                                f'<td {"class=\\'numeric\\'" if i>1 else ""}>{c}</td>'
                                for i, c in enumerate(r)
                            ]
                        )
                        + "</tr>"
                    )
                tr_html += "</tbody>"

                # Detect columns for aggregation
                idx_numkb = -1
                idx_maxkb = -1
                idx_reskb = -1
                for i, h in enumerate(v_headers):
                    h_lower = h.lower()
                    if ("numkb" in h_lower or "size" in h_lower) and idx_numkb == -1:
                        idx_numkb = i
                    elif "maxkb" in h_lower and idx_maxkb == -1:
                        idx_maxkb = i
                    elif "res" in h_lower and idx_reskb == -1:
                        idx_reskb = i

                # Check for counter/index column added by template?
                # (Actually ClassStatsTab headers are raw from file, but template might auto-inject one if not present)
                # We'll assume the JS will handle the actual index passed.

                return f"""
                <div id="{view_id}" class="sub-tab-content class-view" style="display: {display_style};"
                     data-idx-numkb="{idx_numkb}" data-idx-maxkb="{idx_maxkb}" data-idx-reskb="{idx_reskb}">
                    <div class="table-container">
                        <table id="tbl-{view_id}">
                            {th_html}
                            {tr_html}
                        </table>
                    </div>
                </div>
                """

            # Sort Category Buttons
            sort_btns_html = ""

            def make_btn(label, vid, is_active):
                active_cls = " active-sub" if is_active else ""
                onclick = f"openSubTab(event, '{vid}', '{tab_id}'); (function(tableId){{{reset_js}}})('tbl-{vid}');"
                return f'<button class="action-btn sub-btn{active_cls}" onclick="{onclick}">{label}</button>'

            if has_res:
                sort_btns_html += make_btn("Resource Size", f"{tab_id}-res", True)
            if has_alpha:
                sort_btns_html += make_btn(
                    "Alpha Order", f"{tab_id}-alpha", not has_res
                )

            search_row_html = f"""
            <div class="search-container" data-no-reset="true">
                <input type="text" placeholder="Search objects..." onkeyup="filterClassTable('{tab_id}', this.value)">
                <span style="font-size: 10px; color: #666; font-weight: 600; text-transform: uppercase; margin-left: 10px;">Sort By:</span>
                {sort_btns_html}
            </div>
            """

            content_html = ""
            if has_res and has_alpha:
                content_html += render_view_content("resource_size", "res", True)
                content_html += render_view_content("alpha_sort", "alpha", False)
            elif has_res:
                content_html += render_view_content("resource_size", "res", True)
            elif has_alpha:
                content_html += render_view_content("alpha_sort", "alpha", True)

            html_out += f"""
            <div id="{tab_id}" class="tab-content">
                {header_html}
                {summary_html}
                {search_row_html}
                {content_html}
            </div>
            """

        # Global Script for Class Stats
        script_html = """
        <script>
            function parseClassSize(val) {
                val = val.replace(/,/g, '').toLowerCase().trim();
                let num = parseFloat(val) || 0;
                if (val.includes('mb')) return num;
                if (val.includes('kb')) return num / 1024.0;
                if (val.includes('gb')) return num * 1024.0;
                return num / 1024.0; // Default to KB like Unreal NumKB
            }

            function updateClassAggregates(tabId) {
                const activeSub = document.querySelector(`#${tabId} .sub-tab-content[style*="block"]`);
                if (!activeSub) return;
                
                const table = activeSub.querySelector('table');
                if (!table) return;

                const idxNumKB = parseInt(activeSub.getAttribute('data-idx-numkb'));
                const idxMaxKB = parseInt(activeSub.getAttribute('data-idx-maxkb'));
                const idxResKB = parseInt(activeSub.getAttribute('data-idx-reskb'));

                const rows = Array.from(table.tBodies[0].rows);
                let calcCount = 0, filtCount = 0;
                let calcSumNum = 0, filtSumNum = 0;
                let calcSumMax = 0, filtSumMax = 0;
                let calcSumRes = 0, filtSumRes = 0;

                rows.forEach(row => {
                    const isVisible = row.style.display !== 'none';
                    calcCount++;
                    if (idxNumKB !== -1 && row.cells[idxNumKB]) calcSumNum += parseClassSize(row.cells[idxNumKB].innerText);
                    if (idxMaxKB !== -1 && row.cells[idxMaxKB]) calcSumMax += parseClassSize(row.cells[idxMaxKB].innerText);
                    if (idxResKB !== -1 && row.cells[idxResKB]) calcSumRes += parseClassSize(row.cells[idxResKB].innerText);
                    
                    if (isVisible) {
                        filtCount++;
                        if (idxNumKB !== -1 && row.cells[idxNumKB]) filtSumNum += parseClassSize(row.cells[idxNumKB].innerText);
                        if (idxMaxKB !== -1 && row.cells[idxMaxKB]) filtSumMax += parseClassSize(row.cells[idxMaxKB].innerText);
                        if (idxResKB !== -1 && row.cells[idxResKB]) filtSumRes += parseClassSize(row.cells[idxResKB].innerText);
                    }
                });

                const setDisplay = (id, val) => {
                    const el = document.getElementById(id);
                    if (el) el.innerText = val.toFixed(2) + " MB";
                };

                const toggleBox = (id, show) => {
                    const el = document.getElementById(id);
                    if (el) el.style.display = show ? 'contents' : 'none';
                };

                document.getElementById('calc-count-' + tabId).innerText = calcCount;
                setDisplay('calc-numkb-' + tabId, calcSumNum);
                setDisplay('calc-maxkb-' + tabId, calcSumMax);
                setDisplay('calc-reskb-' + tabId, calcSumRes);
                
                toggleBox('calc-box-numkb-' + tabId, idxNumKB !== -1);
                toggleBox('calc-box-maxkb-' + tabId, idxMaxKB !== -1);
                toggleBox('calc-box-reskb-' + tabId, idxResKB !== -1);

                document.getElementById('filt-count-' + tabId).innerText = filtCount;
                setDisplay('filt-numkb-' + tabId, filtSumNum);
                setDisplay('filt-maxkb-' + tabId, filtSumMax);
                setDisplay('filt-reskb-' + tabId, filtSumRes);
                
                toggleBox('filt-box-numkb-' + tabId, idxNumKB !== -1);
                toggleBox('filt-box-maxkb-' + tabId, idxMaxKB !== -1);
                toggleBox('filt-box-reskb-' + tabId, idxResKB !== -1);
            }

            function filterClassTable(tabId, term) {
                const activeSub = document.querySelector(`#${tabId} .sub-tab-content[style*="block"]`);
                if (activeSub) {
                    filterTable(activeSub.querySelector('table').id, -1, term);
                    updateClassAggregates(tabId);
                }
            }

            // Hook into sub-tab changes
            const originalOpenSubTab = window.openSubTab;
            window.openSubTab = function(evt, subId, tabId) {
                if (originalOpenSubTab) originalOpenSubTab(evt, subId, tabId);
                setTimeout(() => updateClassAggregates(tabId), 50);
            };

            document.addEventListener('DOMContentLoaded', () => {
                document.querySelectorAll('.tab-content[id^="class-"]').forEach(tc => {
                    updateClassAggregates(tc.id);
                    tc.querySelectorAll('th').forEach(th => {
                        th.addEventListener('click', () => {
                            setTimeout(() => updateClassAggregates(tc.id), 20);
                        });
                    });
                });
            });
        </script>
        """

        return html_out + script_html
