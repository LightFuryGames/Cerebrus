import re
from typing import Any, Dict, Optional

from ..utils import format_memory_size, try_format_cell_value
from . import ReportTab


class DetailedListsTab(ReportTab):
    def __init__(self):
        super().__init__("Detailed Lists", "detailed-lists")
        # Structure: { 
        #   "ClassName": {
        #       "subviews": { 
        #           "default": { "headers": [], "rows": [], "summary": [], "total_data": None },
        #           "alphasort": { ... } 
        #       }
        #   } 
        # }
        self.data_store = {} 
        self.current_class = None
        self.current_variant = "default"
        self.class_col_idx = -1

    def should_handle(self, line: str) -> bool:
        if line.startswith('MemReport: Begin command "obj list') and "-resourcesizesort" not in line:
            # Format: obj list class=SkeletalMesh -alphasort OR obj list -resourcesizesort
            parts = line.split('"')
            if len(parts) < 2: return False
            content = parts[1]
            
            # Extract Class
            if "class=" in content:
                cls_match = re.search(r"class=([^\s]+)", content) 
                self.current_class = cls_match.group(1) if cls_match else "Unknown"
            else:
                self.current_class = "All Objects"
            
            # Extract Variant (flags)
            flag_parts = content.split(" ")
            flags = [p for p in flag_parts if p.startswith("-")]
            self.current_variant = " ".join(flags) if flags else "default"
            
            return True
        elif line.startswith('MemReport: Begin command "ListParticleSystems'):
            self.current_class = "ParticleSystems"
            content = line.split('"')[1]
            flags = content.replace("ListParticleSystems", "").strip()
            self.current_variant = flags if flags else "default"
            return True

        return False

    def _parse_total_line(self, line: str) -> Optional[Dict[str, Any]]:
        # Example: 40199 Objects (Total: 220.81 MB / Max: 224.66 MB / Res: 1110.93 MB)
        match = re.search(r"(\d+)\s+Objects\s+\(Total:\s+([\d\.]+M?)\s+/\s+Max:\s+([\d\.]+M?)\s+/\s+Res:\s+([\d\.]+M?)\)", line)
        if match:
             groups = match.groups()
             def fmt_v(v):
                 v = v.strip()
                 if v.endswith("M"): return float(v[:-1])
                 return float(v)
             return {
                 "count": int(groups[0]),
                 "total": fmt_v(groups[1]),
                 "max": fmt_v(groups[2]),
                 "res": fmt_v(groups[3])
             }
        return None

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        if not self.current_class:
            return
            
        if self.current_class not in self.data_store:
            self.data_store[self.current_class] = {"subviews": {}}
            
        if self.current_variant not in self.data_store[self.current_class]["subviews"]:
             self.data_store[self.current_class]["subviews"][self.current_variant] = {
                 "headers": [], "rows": [], "summary": [], "total_data": None
             }
             
        view = self.data_store[self.current_class]["subviews"][self.current_variant]

        if not line.strip():
            return
        if "Obj List:" in line or "Listing" in line:
            return
        if "MemReport: Begin" in line or "MemReport: End" in line:
            return

        # Special check for total data
        if "Objects (Total:" in line:
            total_data = self._parse_total_line(line)
            if total_data:
                view["total_data"] = total_data
            return

        # Header Detection
        if "Object" in line and ("NumKB" in line or "Cooked" in line):
            if not view["headers"]:
                headers = re.split(r"\s+", line.strip())
                if "Class" in headers and self.current_class != "All Objects":
                     try:
                          self.class_col_idx = headers.index("Class")
                          headers.pop(self.class_col_idx)
                     except ValueError:
                          self.class_col_idx = -1
                else:
                     self.class_col_idx = -1
                view["headers"] = headers
            return

        # Row Detection
        if view["headers"]:
            cols = re.split(r"\s+", line.strip())
            
            # Simple heuristic for summary line if not already caught
            if len(cols) < len(view["headers"]) - 2:
                 view["summary"].append(line)
                 return

            if self.class_col_idx != -1 and len(cols) > self.class_col_idx:
                 cols.pop(self.class_col_idx)

            formatted = [try_format_cell_value(h, c) for h, c in zip(view["headers"], cols)]
            if len(cols) > len(view["headers"]):
                 formatted.extend(cols[len(view["headers"]):])
            
            view["rows"].append(formatted)

    def get_buttons(self, context: Dict[str, Any]) -> str:
        buttons = ""
        # Sort classes to keep tab order stable
        sorted_classes = sorted(self.data_store.keys())
        for class_name in sorted_classes:
            tab_id = f"list-{class_name}"
            # Clean up tab name for display
            display_name = f"{class_name} Memory Stats" if class_name != "All Objects" else "Object List"
            buttons += f'<button class="tab-btn" onclick="openTab(event, \'{tab_id}\')">{display_name}</button>'
        return buttons

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        html = ""
        # Sort classes for consistent rendering
        sorted_classes = sorted(self.data_store.keys())
        for class_name in sorted_classes:
            data = self.data_store[class_name]
            tab_id = f"list-{class_name}"
            variant_btns = ""
            views_html = ""
            first_variant = True
            
            # Determine common column indices for aggregation
            # We look for NumKB, MaxKB, ResKB, or just general size columns
            
            for variant, view in data["subviews"].items():
                if not view["rows"]:
                    continue
                    
                vid = f"{tab_id}-{variant.replace(' ', '-').replace('-', '_')}"
                display_style = "block" if first_variant else "none"
                active_cls = " active-sub" if first_variant else ""
                
                variant_btns += f"""
                <button class="action-btn sub-btn{active_cls}" onclick="openSubTab(event, '{vid}', '{tab_id}'); updateDetailedAggregates('{vid}')">
                    {variant if variant != 'default' else 'Default'}
                </button>
                """
                
                headers = view["headers"]
                # Identify numeric columns for the dashboard
                idx_numkb = -1
                idx_maxkb = -1
                idx_reskb = -1
                
                for i, h in enumerate(headers):
                    h_lower = h.lower()
                    if "numkb" in h_lower or "size" in h_lower: idx_numkb = i + 1 # +1 for injected counter
                    elif "maxkb" in h_lower: idx_maxkb = i + 1
                    elif "reskb" in h_lower or "resident" in h_lower: idx_reskb = i + 1

                tbl_head = "<tr>"
                for i, h in enumerate(headers):
                    cls = ' class="numeric"' if i > 0 else ""
                    tbl_head += f"<th{cls}>{h}</th>"
                tbl_head += "</tr>"

                tbl_rows = ""
                for row in view["rows"]:
                    tbl_rows += "<tr>"
                    for i, val in enumerate(row):
                         cls = ' class="numeric"' if i > 0 else ""
                         tbl_rows += f"<td{cls}>{val}</td>"
                    tbl_rows += "</tr>"
                
                summary_html = ""
                if view["summary"]:
                     summary_html = '<div class="table-summary" style="margin-top: 10px; padding: 10px; background: rgba(59, 130, 246, 0.05); font-family: monospace; border-left: 3px solid var(--accent-color); font-size: 11px; margin-bottom: 10px;">'
                     for s in view["summary"]:
                         summary_html += f"<div>{s}</div>"
                     summary_html += "</div>"
                
                total_data = view.get("total_data")
                reported_total_html = ""
                if total_data:
                    reported_total_html = f"""
                    <div class="analytics-card" style="flex: 1; min-width: 250px; background: var(--header-bg); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color);">
                        <h4 style="margin: 0 0 10px 0; color: var(--accent-color); font-size: 0.8em; text-transform: uppercase;">Reported Total</h4>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9em;">
                            <div><span style="color: var(--text-muted);">Count:</span> <b>{total_data['count']}</b></div>
                            <div><span style="color: var(--text-muted);">Total:</span> <b>{total_data['total']:.2f} MB</b></div>
                            <div><span style="color: var(--text-muted);">Max:</span> <b>{total_data['max']:.2f} MB</b></div>
                            <div><span style="color: var(--text-muted);">Res:</span> <b>{total_data['res']:.2f} MB</b></div>
                        </div>
                    </div>
                    """
                
                filtered_stats_html = f"""
                <div class="analytics-card" style="flex: 1; min-width: 250px; background: rgba(59, 130, 246, 0.05); padding: 15px; border-radius: 6px; border: 1px solid var(--accent-color);">
                    <h4 style="margin: 0 0 10px 0; color: var(--accent-color); font-size: 0.8em; text-transform: uppercase;">Filtered Statistics</h4>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9em;">
                        <div><span style="color: var(--text-muted);">Visible Count:</span> <b id="filt-count-{vid}">0</b></div>
                        <div id="filt-box-numkb-{vid}"><span style="color: var(--text-muted);">Total Size:</span> <b id="filt-numkb-{vid}">0.00 MB</b></div>
                        <div id="filt-box-maxkb-{vid}"><span style="color: var(--text-muted);">Total Max:</span> <b id="filt-maxkb-{vid}">0.00 MB</b></div>
                        <div id="filt-box-reskb-{vid}"><span style="color: var(--text-muted);">Total Res:</span> <b id="filt-reskb-{vid}">0.00 MB</b></div>
                    </div>
                </div>
                """

                views_html += f"""
                <div id="{vid}" class="sub-tab-content detail-view" style="display: {display_style};" 
                     data-idx-numkb="{idx_numkb}" data-idx-maxkb="{idx_maxkb}" data-idx-reskb="{idx_reskb}">
                    
                    <div class="analytics-row" style="display: flex; gap: 20px; margin-bottom: 20px; flex-wrap: wrap;">
                        {reported_total_html}
                        {filtered_stats_html}
                    </div>

                    <div class="search-container">
                        <input type="text" placeholder="Filter {class_name}..." onkeyup="filterDetailedTable('{vid}', this.value)">
                        <span style="font-size: 10px; color: #666; font-weight: 600; text-transform: uppercase; margin-left: 10px;">Variant:</span>
                        {variant_btns}
                    </div>
                    {summary_html}
                    <div class="table-container">
                        <table id="tbl-{vid}">
                            <thead>{tbl_head}</thead>
                            <tbody>{tbl_rows}</tbody>
                        </table>
                    </div>
                </div>
                """
                first_variant = False
            
            html += f"""
            <div id="{tab_id}" class="tab-content">
                 <h3 style="margin-bottom: 20px;">{class_name} Memory Statistics</h3>
                 {views_html}
            </div>
            """
        
        # Add Global JS for detailed lists
        script = """
        <script>
            function parseDetailedSize(val) {
                val = val.replace(/,/g, '').toLowerCase().trim();
                let num = parseFloat(val) || 0;
                if (val.includes('mb')) return num;
                if (val.includes('kb')) return num / 1024.0;
                if (val.includes('gb')) return num * 1024.0;
                return num / 1024.0;
            }

            function updateDetailedAggregates(vid) {
                const viewDiv = document.getElementById(vid);
                if (!viewDiv) return;
                
                const table = document.getElementById('tbl-' + vid);
                if (!table) return;

                const idxNumKB = parseInt(viewDiv.getAttribute('data-idx-numkb'));
                const idxMaxKB = parseInt(viewDiv.getAttribute('data-idx-maxkb'));
                const idxResKB = parseInt(viewDiv.getAttribute('data-idx-reskb'));

                const rows = Array.from(table.tBodies[0].rows);
                let count = 0;
                let sumNum = 0, sumMax = 0, sumRes = 0;

                rows.forEach(row => {
                    if (row.style.display !== 'none') {
                        count++;
                        if (idxNumKB !== -1 && row.cells[idxNumKB]) sumNum += parseDetailedSize(row.cells[idxNumKB].innerText);
                        if (idxMaxKB !== -1 && row.cells[idxMaxKB]) sumMax += parseDetailedSize(row.cells[idxMaxKB].innerText);
                        if (idxResKB !== -1 && row.cells[idxResKB]) sumRes += parseDetailedSize(row.cells[idxResKB].innerText);
                    }
                });

                document.getElementById('filt-count-' + vid).innerText = count;
                
                const setVal = (id, boxId, val, idx) => {
                    const el = document.getElementById(id);
                    const box = document.getElementById(boxId);
                    if (idx === -1) {
                        if (box) box.style.display = 'none';
                    } else {
                        if (box) box.style.display = '';
                        if (el) el.innerText = val.toFixed(2) + " MB";
                    }
                };

                setVal('filt-numkb-' + vid, 'filt-box-numkb-' + vid, sumNum, idxNumKB);
                setVal('filt-maxkb-' + vid, 'filt-box-maxkb-' + vid, sumMax, idxMaxKB);
                setVal('filt-reskb-' + vid, 'filt-box-reskb-' + vid, sumRes, idxResKB);
            }

            function filterDetailedTable(vid, term) {
                filterTable('tbl-' + vid, -1, term);
                updateDetailedAggregates(vid);
            }

            document.addEventListener('DOMContentLoaded', () => {
                document.querySelectorAll('.detail-view').forEach(view => {
                    updateDetailedAggregates(view.id);
                    const table = document.getElementById('tbl-' + view.id);
                    if (table) {
                        table.querySelectorAll('th').forEach(th => {
                            th.addEventListener('click', () => {
                                setTimeout(() => updateDetailedAggregates(view.id), 20);
                            });
                        });
                    }
                });
            });
        </script>
        """
        
        return html + script
