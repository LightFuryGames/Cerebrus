import re
from typing import Any, Dict, List

from ..utils import format_memory_size
from . import ReportTab


class MemoryStatsTab(ReportTab):
    def __init__(self):
        super().__init__("Memory Stats", "memory-stats")

    def should_handle(self, line: str) -> bool:
        return line.startswith("Platform Memory Stats")

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        if "memory_tree" not in context:
            context["memory_tree"] = []

        data = context
        tree = data["memory_tree"]

        # 1. Allocators (PooledVirtualMemoryAllocator)
        if "PooledVirtualMemoryAllocator" in line:
            # Ensure Top-Level Allocator Node exists
            alloc_root = next(
                (x for x in tree if x["name"] == "Pooled Virtual Memory Allocator"),
                None,
            )
            if not alloc_root:
                alloc_root = {
                    "name": "Pooled Virtual Memory Allocator",
                    "value": "",
                    "children": [],
                }
                tree.append(alloc_root)

            # Add specific index as child of Root
            # Line: PooledVirtualMemoryAllocator Index: 0, SizeClass: 64.00KB
            clean_name = line.strip().replace("PooledVirtualMemoryAllocator ", "")

            # Enforce spacing
            clean_name = re.sub(
                r"(\d)(MB|KB)", r"\1 \2", clean_name, flags=re.IGNORECASE
            )

            alloc_root["children"].append(
                {"name": clean_name, "value": "", "children": []}
            )
            return

        if "Pool[" in line:
            # Child of last Allocator Index
            alloc_root = next(
                (x for x in tree if x["name"] == "Pooled Virtual Memory Allocator"),
                None,
            )
            if alloc_root and alloc_root["children"]:
                # Child of last index (which represents a SizeClass/Group)
                current_group = alloc_root["children"][-1]
                
                # Ensure it has a table structure initialized
                if "table_rows" not in current_group:
                    current_group["table_rows"] = []
                    current_group["table_headers"] = ["Index", "Allocatable Memory", "Overhead"]
                    # Clear children if we are switching to table view? 
                    # Probably yes, to avoid double rendering if mixed.
                    current_group["children"] = []

                # Line: Pool[ 10]:    0.00KB allocatable, 184.00KB overhead
                # Extract Index
                idx_match = re.search(r"Pool\[\s*(\d+)\]", line)
                pool_idx = idx_match.group(1) if idx_match else "?"
                
                # Extract Allocatable
                alloc_match = re.search(r":\s*([\d\.]+\s*(?:KB|MB|GB))\s*allocatable", line, re.IGNORECASE)
                alloc_val = format_memory_size(float(re.search(r"[\d\.]+", alloc_match.group(1)).group(0))) if alloc_match else "?"
                # Fix unit spacing consistency
                if alloc_match:
                     # Re-parse to ensure uniform format with our utils
                     raw = alloc_match.group(1)
                     val_num = float(re.search(r"([\d\.]+)", raw).group(1))
                     # Determine unit
                     unit_match = re.search(r"(KB|MB|GB)", raw, re.IGNORECASE)
                     unit = unit_match.group(1).upper() if unit_match else "KB"
                     if unit == "KB":
                         alloc_val = format_memory_size(val_num)
                     elif unit == "MB":
                         alloc_val = f"{val_num:.2f} MB"
                
                # Extract Overhead
                over_match = re.search(r",\s*([\d\.]+\s*(?:KB|MB|GB))\s*overhead", line, re.IGNORECASE)
                over_val = "?"
                if over_match:
                     raw = over_match.group(1)
                     val_num = float(re.search(r"([\d\.]+)", raw).group(1))
                     unit_match = re.search(r"(KB|MB|GB)", raw, re.IGNORECASE)
                     unit = unit_match.group(1).upper() if unit_match else "KB"
                     if unit == "KB":
                         over_val = format_memory_size(val_num)
                     elif unit == "MB":
                         over_val = f"{val_num:.2f} MB"

                current_group["table_rows"].append([pool_idx, alloc_val, over_val])
            return

        # 2. STAT Lines
        # Format: Value - Name - StatName - Group - Category
        if " - STAT_" in line:
            parts = line.split(" - ")
            if len(parts) >= 3:
                val_str = parts[0].strip()
                name = parts[1].strip()

                group = "General"
                category = "Misc"

                for p in parts[2:]:
                    if p.startswith("STATGROUP_"):
                        group = p.replace("STATGROUP_", "")
                    elif p.startswith("STATCAT_"):
                        category = p.replace("STATCAT_", "")

                # Format Value
                match = re.search(r"([\d\.]+)(MB|KB|mb|kb)", val_str, re.IGNORECASE)
                if match:
                    val_num = float(match.group(1))
                    unit = match.group(2).upper()
                    if unit == "KB":
                        val_str = format_memory_size(val_num)
                    elif unit == "MB":
                        val_str = f"{val_num:.2f} MB"

                # Add to Tree path: Category -> Group -> Name
                cat_node = next((x for x in tree if x["name"] == category), None)
                if not cat_node:
                    cat_node = {"name": category, "value": "", "children": []}
                    tree.append(cat_node)

                group_node = next(
                    (x for x in cat_node["children"] if x["name"] == group), None
                )
                if not group_node:
                    group_node = {"name": group, "value": "", "children": []}
                    cat_node["children"].append(group_node)

                group_node["children"].append(
                    {"name": name, "value": val_str, "children": []}
                )
            return

        # 3. Memory Stats Header
        if "Memory Stats:" in line or "Platform Memory Stats" in line:
            return

        # 4. Fallback: Key-Value pairs
        if "=" in line:
            parts = line.split("=")
            if len(parts) == 2:
                k = parts[0].strip()
                v = parts[1].strip()
                # Format value
                match = re.search(r"([\d\.]+)\s*(MB|KB|GB)", v, re.IGNORECASE)
                if match:
                    val_num = float(match.group(1))
                    unit = match.group(2).upper()
                    v = f"{val_num:.2f} {unit}"

                gen_node = next((x for x in tree if x["name"] == "General Stats"), None)
                if not gen_node:
                    gen_node = {"name": "General Stats", "value": "", "children": []}
                    tree.insert(0, gen_node)

                gen_node["children"].append({"name": k, "value": v, "children": []})
            return

        # 5. Fallback: Colon separated (Platform Memory Stats: ...)
        if ":" in line and "Pool" not in line and "Alloc" not in line:
            parts = line.split(":", 1)
            
            # Special Handling for "Process Physical Memory" lines which are long strings
            # User wants a table view.
            # Example: "Process Physical Memory 1201.54 MB used, 1201.54 MB peak"
            # It already has a colon? No, the example image shows it might not.
            # Wait, the fallback loop (lines 51-53 in original) handles lines without colons?
            # actually this loop logic is inside parse() which is called line by line.
            
            if len(parts) == 2:
                # Treat as General Stat
                k = parts[0].strip()
                v = parts[1].strip()
                
                # Check if Value is empty (meaning the line was just "Name:")
                if not v:
                     # Check if line itself contains data like "Process Physical Memory 1201 MB..."
                     # actually if split by colon gave empty v, it was "Name:".
                     pass
                     
                # Format spacing: 123MB -> 123 MB
                fmt_match = re.search(r"^([\d\.]+)\s*(MB|KB|GB|mb|kb|gb)(.*)$", v, re.IGNORECASE)
                if fmt_match:
                    val_num = fmt_match.group(1)
                    unit = fmt_match.group(2).upper()
                    rest = fmt_match.group(3)
                    v = f"{val_num} {unit}{rest}"

                gen_node = next((x for x in tree if x["name"] == "General Stats"), None)
                if not gen_node:
                     gen_node = {"name": "General Stats", "value": "", "children": []}
                     tree.insert(0, gen_node)
                gen_node["children"].append({"name": k, "value": v, "children": []})
            return
            
        # 6. Fallback for lines like "Process Physical Memory..." that might not have separators
        # but belong to General Stats if we are in that 'state'.
        # However, parse() is stateless per line unless we track it.
        # But we can try to extract number patterns.
        match_stat = re.search(r"^(.*?)\s+([\d\.,]+\s*(?:MB|KB|GB).*)$", line, re.IGNORECASE)
        if match_stat:
             k = match_stat.group(1).strip()
             v = match_stat.group(2).strip()
             
             # Format spacing: 123MB -> 123 MB
             # Also normalize casing? User just said "have a space"
             fmt_match = re.search(r"^([\d\.]+)\s*(MB|KB|GB|mb|kb|gb)(.*)$", v, re.IGNORECASE)
             if fmt_match:
                 val_num = fmt_match.group(1)
                 unit = fmt_match.group(2).upper() # Normalize to upper KB/MB/GB
                 rest = fmt_match.group(3)
                 v = f"{val_num} {unit}{rest}"

             gen_node = next((x for x in tree if x["name"] == "General Stats"), None)
             if not gen_node:
                     gen_node = {"name": "General Stats", "value": "", "children": []}
                     tree.insert(0, gen_node)
             gen_node["children"].append({"name": k, "value": v, "children": []})


    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        active_cls = " active" if is_active else ""
        html = f"""
        <div id="{self.id}" class="tab-content{active_cls}">
            <h3>{self.name}</h3>
             <div class="search-container" data-no-reset="true">
                <input type="text" placeholder="Search stats..." onkeyup="filterTree('mem-stats-tree', this.value)">
                <div style="margin-top: 8px;">
                    <button class="tab-btn" onclick="expandAll('mem-stats-tree')" style="font-size: 12px; padding: 4px 10px;">Expand All</button>
                    <button class="tab-btn" onclick="collapseAll('mem-stats-tree')" style="font-size: 12px; padding: 4px 10px;">Collapse All</button>
                </div>
            </div>
            <div id="mem-stats-tree">
        """

        tree = context.get("memory_tree", [])
        for node in tree:
            html += self._render_tree_node(node)

        html += "</div></div>"
        return html

    def _render_tree_node(self, node, level=0):
        name = node["name"]
        value = node["value"]
        children = node.get("children", [])
        table_rows = node.get("table_rows", [])
        
        has_children = len(children) > 0
        has_table = len(table_rows) > 0
        
        indent = level * 20

        html = ""

        if has_children or has_table:
            html += f"""
            <details class="tree-node" style="margin-left: {indent}px">
                <summary class="tree-summary">
                    <span>{name}</span>
                    <span>{value}</span>
                </summary>
                <div class="tree-content">
            """
            # Render Children First
            for child in children:
                html += self._render_tree_node(child, 0)  # Nesting handled by recursion
            
            # Render Table if present (e.g. Pooled Allocator Leaf)
            if has_table:
                 headers = node.get("table_headers", [])
                 # Create unique ID for sorting
                 # We need a fairly unique ID. Use hash or random?
                 # Since this is static gen, we can use a counter or just random string
                 import uuid
                 tbl_id = f"tbl-{uuid.uuid4().hex[:8]}"
                 
                 th_html = "<tr>"
                 for h in headers:
                     # Check if numeric column for auto-class?
                     # Index (0), Alloc (1), Overhead (2) -> 1 and 2 are numeric size
                     th_html += f"<th>{h}</th>"
                 th_html += "</tr>"
                 
                 tr_html = ""
                 for r_idx, row in enumerate(table_rows):
                     tr_html += "<tr>"
                     # Force first column to be local index
                     tr_html += f"<td>{r_idx}</td>"
                     # Skip first col from data (original index), render rest
                     for val in row[1:]:
                         tr_html += f"<td>{val}</td>"
                     tr_html += "</tr>"
                 
                 html += f"""
                 <div class="table-container" style="margin-top: 10px;">
                    <table id="{tbl_id}" style="width: 100%; border: 1px solid rgba(255,255,255,0.1);">
                        <thead>{th_html}</thead>
                        <tbody>{tr_html}</tbody>
                    </table>
                 </div>
                 """

            html += """
                </div>
            </details>
            """
        else:
            html += f"""
            <div class="tree-child" style="display:flex; justify-content:space-between;">
                <span>{name}</span>
                <span class="numeric">{value}</span>
            </div>
            """
        return html
