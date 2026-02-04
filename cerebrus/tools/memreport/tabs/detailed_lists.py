import re
from typing import Any, Dict

from ..utils import format_memory_size, try_format_cell_value
from . import ReportTab


class DetailedListsTab(ReportTab):
    def __init__(self):
        super().__init__("Detailed Lists", "detailed-lists")
        # Structure: { 
        #   "ClassName": {
        #       "subviews": { 
        #           "default": { "headers": [], "rows": [], "summary": [] },
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
            content = line.split('"')[1]
            parts = content.split(" ")
            
            # Extract Class
            if "class=" in content:
                cls_match = re.search(r"class=([^\s]+)", content) 
                self.current_class = cls_match.group(1) if cls_match else "Unknown"
            else:
                self.current_class = "All Objects"
            
            # Extract Variant (flags)
            flags = [p for p in parts if p.startswith("-")]
            self.current_variant = " ".join(flags) if flags else "default"
            
            return True
        elif line.startswith('MemReport: Begin command "ListParticleSystems'):
            self.current_class = "ParticleSystems"
            content = line.split('"')[1]
            flags = content.replace("ListParticleSystems", "").strip()
            self.current_variant = flags if flags else "default"
            return True

        return False

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        if not self.current_class:
            return
            
        if self.current_class not in self.data_store:
            self.data_store[self.current_class] = {"subviews": {}}
            
        if self.current_variant not in self.data_store[self.current_class]["subviews"]:
             self.data_store[self.current_class]["subviews"][self.current_variant] = {
                 "headers": [], "rows": [], "summary": []
             }
             
        view = self.data_store[self.current_class]["subviews"][self.current_variant]

        if not line.strip():
            return
        if "Obj List:" in line or "Objects:" in line or "Listing" in line:
            return
        if "MemReport: Begin" in line or "MemReport: End" in line:
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

        # Row / Summary Detection
        if view["headers"]:
            cols = re.split(r"\s+", line.strip())
            
            is_summary = False
            matches_num = re.match(r"^\d+$", cols[0])
            if matches_num and len(cols) < len(view["headers"]):
                 is_summary = True
            
            if is_summary:
                 view["summary"].append(line)
                 return

            if self.class_col_idx != -1 and len(cols) > self.class_col_idx:
                 cols.pop(self.class_col_idx)

            if len(cols) < len(view["headers"]) - 2:
                 view["summary"].append(line)
                 return

            formatted = [try_format_cell_value(h, c) for h, c in zip(view["headers"], cols)]
            if len(cols) > len(view["headers"]):
                 formatted.extend(cols[len(view["headers"]):])
            
            view["rows"].append(formatted)


    def get_buttons(self, context: Dict[str, Any]) -> str:
        buttons = ""
        for class_name, data in self.data_store.items():
            tab_id = f"list-{class_name}"
            buttons += f'<button class="tab-btn" onclick="openTab(event, \'{tab_id}\')">{class_name}</button>'
        return buttons

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        html = ""
        for class_name, data in self.data_store.items():
            tab_id = f"list-{class_name}"
            variant_btns = ""
            views_html = ""
            first_variant = True
            
            for variant, view in data["subviews"].items():
                if not view["rows"]:
                    continue
                    
                vid = f"{tab_id}-{variant.replace(' ', '-')}"
                display_style = "block" if first_variant else "none"
                active_cls = " active-sub" if first_variant else ""
                
                variant_btns += f"""
                <button class="action-btn sub-btn{active_cls}" onclick="openSubTab(event, '{vid}', '{tab_id}')">
                    {variant if variant != 'default' else 'Default'}
                </button>
                """
                
                headers = view["headers"]
                tbl_head = "<tr>"
                for h in headers:
                    tbl_head += f"<th>{h}</th>"
                tbl_head += "</tr>"

                tbl_rows = ""
                for row in view["rows"]:
                    tbl_rows += "<tr>"
                    for val in row:
                        tbl_rows += f"<td>{val}</td>"
                    tbl_rows += "</tr>"
                
                summary_html = ""
                if view["summary"]:
                     summary_html = '<div class="table-summary" style="margin-top: 10px; padding: 10px; background: rgba(255,255,255,0.05); font-family: monospace; border-left: 3px solid var(--accent-color);">'
                     for s in view["summary"]:
                         summary_html += f"<div>{s}</div>"
                     summary_html += "</div>"
                
                views_html += f"""
                <div id="{vid}" class="sub-tab-content" style="display: {display_style};">
                    {summary_html}
                    <div class="search-container">
                        <input type="text" placeholder="Filter {class_name} ({variant})..." onkeyup="filterTable('tbl-{vid}', 0, this.value)">
                        <span style="font-size: 10px; color: #666; font-weight: 600; text-transform: uppercase;">View:</span>
                        {variant_btns}
                    </div>
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
                 <h3>{class_name}</h3>
                 {views_html}
            </div>
            """
        return html
