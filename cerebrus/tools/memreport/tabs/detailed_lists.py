import re
from typing import Any, Dict

from ..utils import format_memory_size, try_format_cell_value
from . import ReportTab


class DetailedListsTab(ReportTab):
    def __init__(self):
        super().__init__("Detailed Lists", "detailed-lists")
        self.current_class = None

    def should_handle(self, line: str) -> bool:
        if line.startswith('MemReport: Begin command "obj list class='):
            match = re.search(r"class=([^\s]+)", line)
            if match:
                self.current_class = match.group(1)
                return True
        elif line.startswith('MemReport: Begin command "ListTextures"'):
            self.current_class = "Textures"
            return True
        return False

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        data = context
        if "detailed_lists" not in data:
            data["detailed_lists"] = {}

        if not self.current_class:
            return

        # Ensure list init
        if self.current_class not in data["detailed_lists"]:
            data["detailed_lists"][self.current_class] = {"headers": [], "rows": []}

        target_list = data["detailed_lists"][self.current_class]

        # 1. Parsing Logic for Textures
        if self.current_class == "Textures":
            if not line.strip():
                return
            if "Listing all textures" in line:
                return
            if "MemReport: Begin" in line:
                return  # Skip start line

            if "Cooked/OnDisk:" in line:
                target_list["headers"] = [
                    "Cooked Res",
                    "Cooked Size",
                    "InMem Res",
                    "InMem Size",
                    "Format",
                    "Group",
                    "Name",
                    "Streaming",
                    "VT",
                    "Usage",
                    "Mips",
                    "Uncompressed",
                ]
            elif target_list["headers"]:
                parts = line.split(", ")
                if len(parts) >= 11:
                    row = []
                    # 1. Param parsing (Cooked)
                    p0 = parts[0]
                    res_match = re.match(r"(\d+x\d+)", p0)
                    size_match = re.search(r"\((\d+)\s*KB", p0)
                    row.append(res_match.group(1) if res_match else "?")
                    row.append(
                        format_memory_size(float(size_match.group(1)))
                        if size_match
                        else "?"
                    )

                    # 2. Param parsing (InMem)
                    p1 = parts[1]
                    res_match = re.match(r"(\d+x\d+)", p1)
                    size_match = re.search(r"\((\d+)\s*KB", p1)
                    row.append(res_match.group(1) if res_match else "?")
                    row.append(
                        format_memory_size(float(size_match.group(1)))
                        if size_match
                        else "?"
                    )

                    row.append(parts[2])  # Format
                    row.append(parts[3])  # Group
                    row.append(parts[4])  # Name
                    row.extend(parts[5:])
                    target_list["rows"].append(row)

        # 2. Parsing Logic for Generic Classes
        else:
            if not line.strip():
                return
            if "Obj List:" in line or "Objects:" in line:
                return
            if "MemReport: Begin" in line:
                return

            if "Object" in line and ("NumKB" in line or "Cooked" in line):
                headers = re.split(r"\s+", line.strip())
                target_list["headers"] = headers
            elif len(target_list["headers"]) > 0:
                cols = re.split(r"\s+", line.strip())
                if len(cols) >= len(target_list["headers"]):
                    formatted_cols = []
                    for i, val in enumerate(cols):
                        if i < len(target_list["headers"]):
                            header = target_list["headers"][i]
                            formatted_cols.append(try_format_cell_value(header, val))
                        else:
                            formatted_cols.append(val)
                    target_list["rows"].append(formatted_cols)

    def get_buttons(self, context: Dict[str, Any]) -> str:
        data = context.get("detailed_lists", {})
        buttons = ""
        for class_name, content in data.items():
            if not content["rows"]:
                continue
            tab_id = f"list-{class_name}"
            buttons += f'<button class="tab-btn" onclick="openTab(event, \'{tab_id}\')">{class_name}</button>'
        return buttons

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        # Detailed Lists ignores is_active for now (sub-tabs are rarely default active)
        data = context.get("detailed_lists", {})
        html = ""

        for class_name, content in data.items():
            if not content["rows"]:
                continue

            tab_id = f"list-{class_name}"

            # Headers
            headers = content["headers"]
            tbl_head = "<tr>"
            for h in headers:
                is_num = "KB" in h or "Size" in h
                cls = 'class="numeric"' if is_num else ""
                tbl_head += f"<th {cls}>{h}</th>"
            tbl_head += "</tr>"

            # Rows
            tbl_rows = ""
            for row in content["rows"]:
                tbl_rows += "<tr>"
                for i in range(len(headers)):
                    val = row[i] if i < len(row) else ""
                    is_num = i > 0
                    cls = 'class="numeric"' if is_num else ""
                    tbl_rows += f"<td {cls}>{val}</td>"
                tbl_rows += "</tr>"

            html += f"""
            <div id="{tab_id}" class="tab-content">
                 <div class="search-container">
                    <input type="text" placeholder="Filter {class_name}..." onkeyup="filterTable('tbl-{tab_id}', 0, this.value)">
                </div>
                <div class="table-container">
                    <table id="tbl-{tab_id}">
                        <thead>{tbl_head}</thead>
                        <tbody>{tbl_rows}</tbody>
                    </table>
                </div>
            </div>
            """
        return html
