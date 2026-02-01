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
                # Child of last index
                # Line: Pool[ 10]:    0.00KB allocatable, 184.00KB overhead
                clean_line = re.sub(r"\s+", " ", line).strip()
                clean_line = re.sub(
                    r"(\d)(MB|KB)", r"\1 \2", clean_line, flags=re.IGNORECASE
                )

                alloc_root["children"][-1]["children"].append(
                    {"name": clean_line, "value": "", "children": []}
                )
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
                match = re.search(r"([\d\.]+)\s*(MB|KB|mb|kb)", v, re.IGNORECASE)
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
            if len(parts) == 2:
                # Treat as General Stat
                k = parts[0].strip()
                v = parts[1].strip()
                gen_node = next((x for x in tree if x["name"] == "General Stats"), None)
                if not gen_node:
                    gen_node = {"name": "General Stats", "value": "", "children": []}
                    tree.insert(0, gen_node)
                gen_node["children"].append({"name": k, "value": v, "children": []})

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        active_cls = " active" if is_active else ""
        html = f"""
        <div id="{self.id}" class="tab-content{active_cls}">
             <div class="search-container">
                <input type="text" placeholder="Search stats..." onkeyup="filterTree('mem-stats-tree', this.value)">
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
        children = node["children"]

        has_children = len(children) > 0
        indent = level * 20

        html = ""

        if has_children:
            html += f"""
            <details class="tree-node" style="margin-left: {indent}px">
                <summary class="tree-summary">
                    <span>{name}</span>
                    <span>{value}</span>
                </summary>
                <div class="tree-content">
            """
            for child in children:
                html += self._render_tree_node(child, 0)  # Nesting handled by recursion
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
