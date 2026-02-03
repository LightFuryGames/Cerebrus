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
                # Fallback for generic lists (e.g. -resourcesizesort)
                # Use the flags as the "Class" name or a generic name?
                # User mentioned "tabs missing such as skeletal mesh". 
                # If we parse the generic list, we might want to name it "All Objects"
                self.current_class = "All Objects"
            
            # Extract Variant (flags)
            flags = [p for p in parts if p.startswith("-")]
            self.current_variant = " ".join(flags) if flags else "default"
            
            return True
            
        elif line.startswith('MemReport: Begin command "ListTextures"'):
            self.current_class = "Textures"
            # Check flags? Usually ListTextures has variants like 'ListTextures nonvt'
            content = line.split('"')[1]
            flags = content.replace("ListTextures", "").strip()
            self.current_variant = flags if flags else "default"
            return True
            
        elif line.startswith('MemReport: Begin command "ListParticleSystems'):
            self.current_class = "ParticleSystems"
            content = line.split('"')[1]
            flags = content.replace("ListParticleSystems", "").strip()
            self.current_variant = flags if flags else "default"
            return True

        return False

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        context_data = context
        if "detailed_lists" not in context_data:
            context_data["detailed_lists"] = {} # Just for context passing, we use self.data_store mostly
            
        # Helper to get current view
        if not self.current_class:
            return
            
        if self.current_class not in self.data_store:
            self.data_store[self.current_class] = {"subviews": {}}
            
        if self.current_variant not in self.data_store[self.current_class]["subviews"]:
             self.data_store[self.current_class]["subviews"][self.current_variant] = {
                 "headers": [], "rows": [], "summary": []
             }
             
        view = self.data_store[self.current_class]["subviews"][self.current_variant]

        # 1. Parsing Logic for Textures
        if self.current_class == "Textures":
            if not line.strip():
                return
            if "Listing all textures" in line:
                return
            if "MemReport: Begin" in line or "MemReport: End" in line:
                return 

            if "Cooked/OnDisk:" in line:
                view["headers"] = [
                    "Cooked Res", "Cooked Size", "InMem Res", "InMem Size",
                    "Format", "Group", "Name", "Streaming", "VT", "Usage", "Mips", "Uncompressed"
                ]
            elif view["headers"]:
                parts = line.split(", ")
                if len(parts) >= 11:
                    row = []
                    # ... [Texture Parsing logic remains same] ...
                    # Simplified for brevity, assume previous logic is good but needs applying here
                    # Actually standardizing texture parsing:
                    p0 = parts[0]
                    res_match = re.search(r"(\d+x\d+)", p0)
                    size_match = re.search(r"\((\d+)\s*KB", p0)
                    row.append(res_match.group(1) if res_match else "?")
                    row.append(format_memory_size(float(size_match.group(1))) if size_match else "?")
                    
                    p1 = parts[1]
                    res_match = re.match(r"(\d+x\d+)", p1)
                    size_match = re.search(r"\((\d+)\s*KB", p1)
                    row.append(res_match.group(1) if res_match else "?")
                    row.append(format_memory_size(float(size_match.group(1))) if size_match else "?")
                    
                    row.append(parts[2])  # Format
                    row.append(parts[3])  # Group
                    row.append(parts[4])  # Name
                    row.extend(parts[5:])
                    view["rows"].append(row)

        # 2. Parsing Logic for Generic Classes (Obj List)
        else:
            if not line.strip():
                return
            if "Obj List:" in line or "Objects:" in line:
                return
            if "MemReport: Begin" in line or "MemReport: End" in line:
                return

            # Header Detection
            if "Object" in line and ("NumKB" in line or "Cooked" in line):
                # Avoid resetting if we already have headers (duplication check)
                if not view["headers"]:
                    headers = re.split(r"\s+", line.strip())
                    # Remove "Class" column if present, unless we are viewing All Objects summary
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
                
                # Check for Summary Line (Last lines)
                # Heuristic: First column is a number (count) OR keyword like "Total"
                is_summary = False
                matches_num = re.match(r"^\d+$", cols[0])
                if matches_num and len(cols) < len(view["headers"]): # Likely "20 Objects (Total: ...)"
                     is_summary = True
                
                # Or simply if column count is drastically different
                # But sometimes valid rows have spaces in names. 
                # Strict check: if line starts with ClassName, it's likely a row?
                # User said: "last 4 lines... give aggregate values"
                # And "after Skeletal or Static Mesh which is the class the Object is mentioned"
                
                if is_summary:
                     view["summary"].append(line)
                     return

                # Normal Row Parsing
                # User wants "Class" column removed.
                if self.class_col_idx != -1 and len(cols) > self.class_col_idx:
                     cols.pop(self.class_col_idx)

                # Validate row length vs headers
                # If too short, might be summary?
                if len(cols) < len(view["headers"]) - 2:
                     view["summary"].append(line)
                     return

                formatted = [try_format_cell_value(h, c) for h, c in zip(view["headers"], cols)]
                # Add remaining cols if any
                if len(cols) > len(view["headers"]):
                     formatted.extend(cols[len(view["headers"]):])
                
                view["rows"].append(formatted)


    def get_buttons(self, context: Dict[str, Any]) -> str:
        buttons = ""
        # context doesn't have self.data_store fully populated if we use instance var
        # We should rely on instance var or populate context at end. 
        # Using instance var is fine since tool.py instantiates us once.
        
        for class_name, data in self.data_store.items():
            # Only creating button for the Class
            tab_id = f"list-{class_name}"
            buttons += f'<button class="tab-btn" onclick="openTab(event, \'{tab_id}\')">{class_name}</button>'
        return buttons

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        html = ""
        
        for class_name, data in self.data_store.items():
            tab_id = f"list-{class_name}"
            
            # Sub-Tab Navigation (Variants)
            sub_nav = '<div class="sub-tabs" style="margin-bottom: 15px;">'
            views_html = ""
            
            first_variant = True
            
            for variant, view in data["subviews"].items():
                if not view["rows"]:
                    continue
                    
                vid = f"{tab_id}-{variant.replace(' ', '-')}"
                display_style = "block" if first_variant else "none"
                active_cls = " active-sub" if first_variant else ""
                
                # Button
                sub_nav += f"""
                <button class="tab-btn sub-btn{active_cls}" onclick="openSubTab(event, '{vid}', '{tab_id}')" 
                        style="font-size: 12px; padding: 5px 15px; border-radius: 15px; margin-right: 5px; background-color: #333;">
                    {variant if variant != 'default' else 'Default'}
                </button>
                """
                
                # Table Content
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
                
                # Summary Block
                summary_html = ""
                if view["summary"]:
                     summary_html = '<div class="table-summary" style="margin-top: 10px; padding: 10px; background: rgba(255,255,255,0.05); font-family: monospace;">'
                     for s in view["summary"]:
                         summary_html += f"<div>{s}</div>"
                     summary_html += "</div>"
                
                views_html += f"""
                <div id="{vid}" class="sub-tab-content" style="display: {display_style};">
                    {summary_html}
                    <div class="search-container">
                        <input type="text" placeholder="Filter {class_name} ({variant})..." onkeyup="filterTable('tbl-{vid}', 0, this.value)">
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
            
            sub_nav += "</div>"
            
            html += f"""
            <div id="{tab_id}" class="tab-content">
                 <h3>{class_name}</h3>
                 {sub_nav}
                 {views_html}
            </div>
            """
            
        return html
