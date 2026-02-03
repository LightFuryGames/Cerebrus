import re
from typing import Any, Dict, List, Optional
from ..utils import try_format_cell_value
from . import ReportTab

class ClassStatsTab(ReportTab):
    def __init__(self):
        super().__init__("Class Memory Stats", "class-stats-generic")
        self.current_class: Optional[str] = None
        self.current_sort: Optional[str] = None
        self.parsing_summary = False

    def should_handle(self, line: str) -> bool:
        return line.startswith('MemReport: Begin command "obj list class=')

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        if "class_stats" not in context:
            context["class_stats"] = {}

        if line.startswith('MemReport: Begin command "obj list class='):
            match = re.search(r'class=([^\s]+)\s+(-[a-z]+)', line)
            if match:
                cls_name = match.group(1)
                sort_switch = match.group(2)
                
                self.current_class = cls_name
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
                        "overall_total": None
                    }
                
                context["class_stats"][cls_name][self.current_sort] = {
                    "headers": [],
                    "rows": []
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
                stats["summary"] = {"headers": [h.strip() for h in re.split(r"\s+", stripped) if h.strip()], "rows": []}
            return

        # Overall Total Detection - redundantly captured but we'll ignore it in render if requested
        if "Objects (Total:" in line:
            stats["overall_total"] = stripped
            return

        if self.parsing_summary:
            cols = [c.strip() for c in re.split(r"\s+", stripped) if c.strip()]
            if stats["summary"] and len(cols) == len(stats["summary"]["headers"]):
                fmt_row = [try_format_cell_value(stats["summary"]["headers"][i], c) for i, c in enumerate(cols)]
                
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
                fmt_row = [try_format_cell_value(current_data["headers"][i], c) for i, c in enumerate(cols)]
                current_data["rows"].append(fmt_row)

    def get_buttons(self, context: Dict[str, Any]) -> str:
        buttons_html = ""
        class_stats = context.get("class_stats", {})
        sorted_classes = sorted(class_stats.keys())
        for cls_name in sorted_classes:
            tab_id = f"class-{cls_name}"
            buttons_html += f'<button class="tab-btn" onclick="openTab(event, \'{tab_id}\')">{cls_name} Memory Stats</button>'
        return buttons_html

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
            
            has_res = stats.get("resource_size") is not None
            has_alpha = stats.get("alpha_sort") is not None
            
            header_html = f'<h3>{cls_name} Memory Statistics</h3>'
            
            # Summary Section
            summary_html = ""
            if stats.get("summary"):
                s_headers = stats["summary"]["headers"]
                s_rows = stats["summary"]["rows"]
                sh_html = "<thead><tr>" + "".join([f'<th class="numeric">{h}</th>' for h in s_headers]) + "</tr></thead>"
                sr_html = "<tbody>"
                for r in s_rows:
                     # Make the summary entry blue background and bold per user request
                     sr_html += '<tr style="background-color: rgba(59, 130, 246, 0.15); font-weight: bold; color: var(--accent-light);">'
                     sr_html += "".join([f'<td class="numeric">{c}</td>' for c in r]) + "</tr>"
                sr_html += "</tbody>"
                
                # Redundant block removed per user request: No blue text line at bottom if table has same data
                # aggregate_text = stats.get("overall_total", "")
                
                summary_html = f"""
                <div class="stat-card" style="margin-bottom: 20px; overflow-x: auto; border-left: 4px solid var(--accent-color);">
                    <h4 style="margin-bottom: 10px; color: var(--accent-color); font-size: 10px; text-transform: uppercase; letter-spacing: 1px;">Class Aggregate Summary</h4>
                    <table>{sh_html}{sr_html}</table>
                </div>
                """

            def render_view_content(view_key, view_suffix, is_visible):
                view_data = stats.get(view_key)
                if not view_data: return ""
                
                v_headers = view_data["headers"]
                v_rows = view_data["rows"]
                view_id = f"{tab_id}-{view_suffix}"
                display_style = "block" if is_visible else "none"
                
                th_html = "<thead><tr>" + "".join([f'<th {"class=\\'numeric\\'" if i>1 else ""}>{h}</th>' for i, h in enumerate(v_headers)]) + "</tr></thead>"
                tr_html = "<tbody>"
                for r_idx, r in enumerate(v_rows):
                     tr_html += f'<tr data-index="{r_idx}">' + "".join([f'<td {"class=\\'numeric\\'" if i>1 else ""}>{c}</td>' for i, c in enumerate(r)]) + "</tr>"
                tr_html += "</tbody>"
                
                return f"""
                <div id="{view_id}" class="sub-tab-content" style="display: {display_style};">
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
                sort_btns_html += make_btn("Alpha Order", f"{tab_id}-alpha", not has_res)

            search_row_html = f"""
            <div class="search-container" data-no-reset="true">
                <input type="text" placeholder="Search objects..." onkeyup="filterTable('tbl-{tab_id}-' + (document.getElementById('{tab_id}-res') && document.getElementById('{tab_id}-res').style.display !== 'none' ? 'res' : 'alpha'), 0, this.value)">
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
            
        return html_out
