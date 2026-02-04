import re
from typing import Any, Dict, List
from ..utils import format_memory_size, try_format_cell_value
from . import ReportTab


class TextureStatsTab(ReportTab):
    def __init__(self):
        super().__init__("Texture Stats", "texture-stats")

    def should_handle(self, line: str) -> bool:
        # Capture "ListTextures", "listtextures nonvt", "listtextures uncompressed"
        # Using simple string check is more robust than regex sometimes
        return line.lower().startswith('memreport: begin command "listtextures')

    def _parse_size_in_mb(self, size_str: str) -> float:
        """Helper to convert size string like '1047.81 MB' or '1024 KB' to MB float."""
        match = re.search(r"([\d\.]+)\s*(MB|KB|B)", size_str, re.IGNORECASE)
        if not match:
            return 0.0
        val = float(match.group(1))
        unit = match.group(2).upper()
        if unit == "KB":
            return val / 1024.0
        if unit == "B":
            return val / (1024.0 * 1024.0)
        return val

    def _format_size_smart(self, size_kb: float) -> str:
        """Formats KB to MB if > 1024."""
        if size_kb >= 1024:
            return f"{size_kb / 1024.0:.2f} MB"
        return f"{size_kb:.2f} KB"

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        raw_line = line.strip()
        
        # Initialize context storage if missing
        if "texture_stats" not in context:
            context["texture_stats"] = {
                "textures": {},
                "summary": {
                    "total_in_mem": 0.0,
                    "total_on_disk": 0.0,
                    "total_count": 0,
                    "formats": {},
                    "groups": {},
                    "errors": []
                },
                "parsing_summary": False
            }
        
        store = context["texture_stats"]

        # Reset state on new Begin command
        if self.should_handle(raw_line):
            store["parsing_summary"] = False
            # Only reset summary if it's the main 'listtextures' command
            # Subsets like 'nonvt' shouldn't overwrite a full summary if it exists
            if raw_line.lower().strip() == 'memreport: begin command "listtextures"':
                store["summary"] = {
                    "total_in_mem": 0.0,
                    "total_on_disk": 0.0,
                    "total_count": 0,
                    "formats": {},
                    "groups": {},
                    "errors": []
                }
            return

        if not raw_line or "MemReport:" in raw_line or "Listing all textures" in raw_line or "Listing NONVT" in raw_line:
            return
            
        # Skip header lines
        if "Cooked/OnDisk:" in raw_line or "LODGroup" in raw_line or "Authored Bias" in raw_line:
            return

        # 1. Detect Summary Section
        if raw_line.startswith("Total size:") or (raw_line.startswith("Total ") and "size:" in raw_line):
            store["parsing_summary"] = True
            
            if raw_line.startswith("Total size:"):
                in_mem_match = re.search(r"InMem=\s*([\d\.]+\s*(?:MB|KB))", raw_line, re.I)
                on_disk_match = re.search(r"OnDisk=\s*([\d\.]+\s*(?:MB|KB))", raw_line, re.I)
                count_match = re.search(r"Count=(\d+)", raw_line, re.I)
                if in_mem_match:
                    val = self._parse_size_in_mb(in_mem_match.group(1))
                    if val > store["summary"]["total_in_mem"]: store["summary"]["total_in_mem"] = val
                if on_disk_match:
                    val = self._parse_size_in_mb(on_disk_match.group(1))
                    if val > store["summary"]["total_on_disk"]: store["summary"]["total_on_disk"] = val
                if count_match:
                    val = int(count_match.group(1))
                    if val > store["summary"]["total_count"]: store["summary"]["total_count"] = val
            else:
                match = re.search(r"Total (PF_|TEXTUREGROUP_)(.*) size: InMem=\s*([\d\.]+\s*(?:MB|KB))\s*OnDisk=\s*([\d\.]+\s*(?:MB|KB))", raw_line, re.I)
                if match:
                    prefix = match.group(1).upper()
                    name = match.group(2)
                    in_mem = self._parse_size_in_mb(match.group(3))
                    on_disk = self._parse_size_in_mb(match.group(4))
                    
                    if prefix == "PF_":
                        if name not in store["summary"]["formats"] or in_mem > store["summary"]["formats"][name]["in_mem"]:
                            store["summary"]["formats"][name] = {"in_mem": in_mem, "on_disk": on_disk}
                    else:
                        if name not in store["summary"]["groups"] or in_mem > store["summary"]["groups"][name]["in_mem"]:
                            store["summary"]["groups"][name] = {"in_mem": in_mem, "on_disk": on_disk}
            return

        if store["parsing_summary"]: 
            return

        # 2. Parse Texture Row
        # Use balanced parentheses split to avoid breaking on bias like (Size, Bias)
        raw_parts = [p.strip() for p in raw_line.split(",")]
        parts = []
        temp = ""
        for p in raw_parts:
            if temp:
                temp += ", " + p
            else:
                temp = p
            if temp.count("(") == temp.count(")"):
                parts.append(temp)
                temp = ""
        
        if len(parts) < 8:
            return

        # Group 1: On Disk (Cooked)
        p_disk = parts[0]
        disk_res = re.search(r"(\d+)x(\d+)", p_disk)
        disk_size_match = re.search(r"\((\d+)\s*KB", p_disk)
        bias_match = re.search(r",\s*([^)]+)\)", p_disk)
        
        disk_w = int(disk_res.group(1)) if disk_res else 0
        disk_h = int(disk_res.group(2)) if disk_res else 0
        disk_kb = float(disk_size_match.group(1)) if disk_size_match else 0.0
        bias = bias_match.group(1) if bias_match else ""

        # Group 2: On RAM (InMem)
        p_ram = parts[1]
        ram_res = re.search(r"(\d+)x(\d+)", p_ram)
        ram_size_match = re.search(r"\((\d+)\s*KB", p_ram)
        
        ram_w = int(ram_res.group(1)) if ram_res else 0
        ram_h = int(ram_res.group(2)) if ram_res else 0
        ram_kb = float(ram_size_match.group(1)) if ram_size_match else 0.0

        # Name cleaning
        full_name = parts[4]
        if "." in full_name:
            base_name_part = full_name.split(":")[0]
            if "." in base_name_part:
                path, leaf = base_name_part.rsplit(".", 1)
                if "/" in path:
                    name_only = path.split("/")[-1]
                    if name_only == leaf:
                        full_name = path + (":" + full_name.split(":")[1] if ":" in full_name else "")

        key = full_name 
        store["textures"][key] = {
            "ram_w": ram_w, "ram_h": ram_h, "ram_kb": ram_kb, "bias": bias,
            "disk_w": disk_w, "disk_h": disk_h, "disk_kb": disk_kb,
            "format": parts[2],
            "group": parts[3],
            "name": full_name,
            "streaming": parts[5],
            "unknown_ref": parts[6],
            "vt": parts[7],
            "usage": parts[8],
            "mips": parts[9],
            "uncompressed": parts[10] if len(parts) > 10 else "NO"
        }

    def _validate_stats(self, store):
        summary = store["summary"]
        if summary["total_in_mem"] == 0 and not summary["formats"]:
            return

        sum_f_in = sum(f["in_mem"] for f in summary["formats"].values())
        sum_g_in = sum(g["in_mem"] for g in summary["groups"].values())
        sum_f_disk = sum(f["on_disk"] for f in summary["formats"].values())
        sum_g_disk = sum(g["on_disk"] for g in summary["groups"].values())

        errors = []
        EPS = 0.5 
        
        if abs(summary["total_in_mem"] - sum_f_in) > EPS:
            errors.append(f"InMem Total ({summary['total_in_mem']:.2f} MB) != Sum of Formats ({sum_f_in:.2f} MB)")
        if abs(summary["total_on_disk"] - sum_f_disk) > EPS:
            errors.append(f"OnDisk Total ({summary['total_on_disk']:.2f} MB) != Sum of Formats ({sum_f_disk:.2f} MB)")

        summary["errors"] = errors

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        store = context.get("texture_stats", {
            "textures": {}, 
            "summary": {"total_in_mem": 0.0, "total_on_disk": 0.0, "total_count": 0, "formats": {}, "groups": {}, "errors": []}
        })
        
        self._validate_stats(store)
        summary = store["summary"]
        textures = list(store["textures"].values())
        
        # Validation Alerts
        error_html = ""
        if summary["errors"]:
            error_html = f"""
            <div class="alert alert-danger" style="margin-top: 15px;">
                <div class="alert-icon">🛑</div>
                <div class="alert-content">
                    <strong>Statistics Mismatch:</strong> The reported texture totals do not match the sum of individual formats/groups.
                    <ul style="margin: 10px 0 0 0; padding-left: 20px; font-size: 0.9em;">
                        {"".join([f"<li>{e}</li>" for e in summary['errors']])}
                    </ul>
                </div>
            </div>
            """

        warning_html = ""
        textures_list_count = len(store["textures"])
        if summary["total_count"] > 0 and summary["total_count"] != textures_list_count:
            diff = summary["total_count"] - textures_list_count
            warning_html = f"""
            <div class="alert alert-warning" style="margin-top: 15px;">
                <div class="alert-icon">⚠️</div>
                <div class="alert-content">
                    <strong>Count Mismatch:</strong> Unreal's summary reports <b>{summary['total_count']:,}</b> textures, but the detailed list contains only <b>{textures_list_count:,}</b> entries. Stats for <b>{abs(diff):,}</b> textures are missing from the detailed data dump.
                </div>
            </div>
            """

        overall_stats = f"""
        <div class="analytics-card" style="flex: 1; min-width: 250px; background: var(--header-bg); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color); text-align: center;">
            <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">
                Overall Totals<br>
                <span class="unreal-red" style="font-size: 0.85em;">(UNREAL REPORTED)</span>
            </h4>
            <div style="display: grid; grid-template-columns: 1fr; gap: 5px; font-size: 1.1em; text-align: left;">
                <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">InMem:</span> <b style="color: #ce9178;">{summary['total_in_mem']:.2f} MB</b></div>
                <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">OnDisk:</span> <b style="color: #ce9178;">{summary['total_on_disk']:.2f} MB</b></div>
                <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Count:</span> <b style="color: #ce9178;">{summary['total_count']:,}</b></div>
            </div>
        </div>
        """

        filtered_stats = f"""
        <div class="analytics-card" style="flex: 1; min-width: 250px; background: rgba(59, 130, 246, 0.05); padding: 15px; border-radius: 6px; border: 1px solid var(--accent-color); text-align: center;">
            <h4 style="margin: 0 0 10px 0; color: var(--accent-color); font-size: 0.8em; text-transform: uppercase;">Filtered Statistics</h4>
            <div style="display: grid; grid-template-columns: 1fr; gap: 5px; font-size: 1.1em; text-align: left;">
                <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">InMem:</span> <b id="tex-filtered-inmem" style="color: var(--accent-color);">0.00 MB</b></div>
                <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">OnDisk:</span> <b id="tex-filtered-ondisk" style="color: var(--accent-color);">0.00 MB</b></div>
                <div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Count:</span> <b id="tex-filtered-count" style="color: var(--accent-color);">0</b></div>
            </div>
        </div>
        """

        distribution_stats = f"""
        <div class="analytics-card" style="flex: 2; min-width: 500px; background: rgba(255, 255, 255, 0.02); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color);">
            <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Texture Distribution</h4>
            <div style="display: flex; gap: 20px; align-items: flex-start;">
                <div style="flex: 1;">
                    <div style="color: var(--accent-color); font-size: 0.8em; font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px;">▼ BY FORMAT ({len(summary['formats'])})</div>
                    <div style="padding-right: 5px;">
                        <table style="width: 100%; border-collapse: collapse; font-size: 0.85em;">
                            {"".join([f"<tr><td style='border:none; padding:2px; color: var(--text-muted); white-space: nowrap;'>{f}</td><td style='text-align:right; border:none; padding:2px; white-space: nowrap;'><b>{d['in_mem']:.2f} MB</b></td></tr>" for f, d in sorted(summary['formats'].items(), key=lambda x: x[1]['in_mem'], reverse=True)])}
                        </table>
                    </div>
                </div>
                <div style="flex: 1;">
                    <div style="color: var(--accent-color); font-size: 0.8em; font-weight: bold; margin-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px;">▼ BY GROUP ({len(summary['groups'])})</div>
                    <div style="padding-right: 5px;">
                        <table style="width: 100%; border-collapse: collapse; font-size: 0.85em;">
                            {"".join([f"<tr><td style='border:none; padding:2px; color: var(--text-muted); white-space: normal; word-break: break-all; width: 120px;'>{g}</td><td style='text-align:right; border:none; padding:2px; white-space: nowrap; vertical-align: top;'><b>{d['in_mem']:.2f} MB</b></td></tr>" for g, d in sorted(summary['groups'].items(), key=lambda x: x[1]['in_mem'], reverse=True)])}
                        </table>
                    </div>
                </div>
            </div>
        </div>
        """

        summary_html = f"""
        <div class="analytics-wrapper" style="background: var(--row-even); padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid var(--border-color);">
            <div class="analytics-row" style="display: flex; gap: 20px; flex-wrap: wrap;">
                {overall_stats}
                {filtered_stats}
                {distribution_stats}
            </div>
            {error_html}
            {warning_html}
        </div>
        """

        # Table Headers
        has_bias = any(t["bias"] and any(c.isdigit() for c in t["bias"]) for t in textures)
        headers = [
            ("#", "count-header"),
            ("On RAM<br>(Cooked)<br>Width", "numeric"), 
            ("On RAM<br>(Cooked)<br>Height", "numeric"), 
            ("On RAM<br>(Cooked)<br>Size", "numeric")
        ]
        if has_bias: headers.append(("Authored Bias", ""))
        headers.extend([
            ("On Disk<br>(Cooked)<br>Width", "numeric"), 
            ("On Disk<br>(Cooked)<br>Height", "numeric"), 
            ("On Disk<br>(Cooked)<br>Size", "numeric"), 
            ("Format", ""), ("Group", ""), ("Name", ""), 
            ("Streaming", ""), ("UnknownRef", ""), ("VT", ""), 
            ("Usage", "numeric"), ("Mips", "numeric"), ("Uncompressed", "")
        ])
        
        # Calculate indices (Offset by 1 due to '#' column)
        offset = 5 if has_bias else 4
        idx_ram_size = 3
        idx_disk_size = offset + 2
        idx_format = offset + 3
        idx_group = offset + 4
        idx_streaming = offset + 6
        idx_unkref = offset + 7
        idx_vt = offset + 8
        idx_usage = offset + 9
        idx_mips = offset + 10
        idx_uncomp = offset + 11
        
        # Unique values for filters
        unique_formats = sorted(set(t["format"] for t in textures))
        unique_groups = sorted(set(t["group"] for t in textures))

        # Filter Buttons Helper
        def make_filter_row(label, items, col_idx):
            btns = ""
            for item in items:
                btns += f'<button class="action-btn filter-btn" data-col="{col_idx}" data-val="{item}" onclick="toggleTextureFilter(this)">{item}</button>'
            return f"""
            <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 5px; margin-bottom: 5px;">
                <span style="font-size: 10px; color: #666; font-weight: 600; text-transform: uppercase; width: 80px; flex-shrink: 0;">{label}:</span>
                <div style="flex-grow: 1; display: flex; flex-wrap: wrap; gap: 5px;">{btns}</div>
            </div>
            """

        filter_html = '<div style="background: rgba(0,0,0,0.2); padding: 10px; border-radius: 6px; margin-bottom: 20px;">'
        
        # 1. Flags
        flags_btns = f"""
        <button class="action-btn filter-btn" data-col="{idx_streaming}" data-val="YES" onclick="toggleTextureFilter(this)">Streaming</button>
        <button class="action-btn filter-btn" data-col="{idx_vt}" data-val="YES" onclick="toggleTextureFilter(this)">VT</button>
        <button class="action-btn filter-btn" data-col="{idx_unkref}" data-val="YES" onclick="toggleTextureFilter(this)">Unknown Ref</button>
        <button class="action-btn filter-btn" data-col="{idx_uncomp}" data-val="YES" onclick="toggleTextureFilter(this)">Uncompressed</button>
        <button class="action-btn filter-btn" data-special="size-mismatch" onclick="toggleTextureSpecial(this)">Size Mismatch</button>
        """
        filter_html += f"""
        <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 5px; margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.05);">
            <span style="font-size: 10px; color: #666; font-weight: 600; text-transform: uppercase; width: 80px; flex-shrink: 0;">Flags:</span>
            <div style="flex-grow: 1; display: flex; flex-wrap: wrap; gap: 5px;">{flags_btns}</div>
        </div>
        """
        
        # 2. Formats
        if unique_formats:
            filter_html += make_filter_row("Formats", unique_formats, idx_format)
            
        # 3. Groups
        if unique_groups:
             filter_html += make_filter_row("Groups", unique_groups, idx_group)
             
        filter_html += "</div>"

            # Table Body
        thead = "<tr>" + "".join([f"<th class='{h[1]}'>{h[0]}</th>" for h in headers]) + "</tr>"
        tbody = ""
        for t in textures:
            def get_color_style(v_ram, v_disk):
                if v_ram > v_disk: return 'style="color: #ff4444; font-weight: bold;"'
                if v_ram < v_disk: return 'style="color: #00c851; font-weight: bold;"'
                return ""

            ram_w_style = get_color_style(t["ram_w"], t["disk_w"])
            disk_w_style = get_color_style(t["disk_w"], t["ram_w"])
            ram_h_style = get_color_style(t["ram_h"], t["disk_h"])
            disk_h_style = get_color_style(t["disk_h"], t["ram_h"])
            ram_sz_style = get_color_style(t["ram_kb"], t["disk_kb"])
            disk_sz_style = get_color_style(t["disk_kb"], t["ram_kb"])

            row_class = ""
            # If usage count is 0 and texture is non Streaming then mark the Entire row with a Red outline
            try:
                usage_val = int(t["usage"])
            except:
                usage_val = 0
            if usage_val == 0 and t["streaming"] == "NO":
                row_class = "highlight-red-row"

            row_html = f"<tr class='{row_class}'>"
            row_html += f"<td class='count-cell'></td>"
            row_html += f"<td {ram_w_style}>{t['ram_w']}</td><td {ram_h_style}>{t['ram_h']}</td><td {ram_sz_style}>{self._format_size_smart(t['ram_kb'])}</td>"
            if has_bias: row_html += f"<td>{t['bias']}</td>"
            row_html += f"<td {disk_w_style}>{t['disk_w']}</td><td {disk_h_style}>{t['disk_h']}</td><td {disk_sz_style}>{self._format_size_smart(t['disk_kb'])}</td>"
            row_html += f"<td class='format-cell'>{t['format']}</td><td class='group-cell'>{t['group']}</td>"
            row_html += f"<td title='{t['name']}' class='name-cell'>{t['name']}</td>"
            # Boolean columns
            for col in ["streaming", "unknown_ref", "vt"]:
                val = t[col]
                if col == "streaming":
                    if val == "NO":
                        style = 'style="color: #ff4444; font-weight: bold;"'
                    else:
                        style = 'style="color: #00c851;"' # Good state, no bold
                elif col == "unknown_ref":
                    if val == "YES":
                        style = 'style="color: #ff4444; font-weight: bold;"'
                    else:
                        style = 'style="color: #00c851;"' # Good state, no bold
                else:
                    if val == "YES":
                        style = 'style="color: #00c851; font-weight: bold;"'
                    else:
                        style = 'style="color: var(--text-muted);"'
                row_html += f"<td {style} class='boolean-cell'>{val}</td>"
            row_html += f"<td class='numeric'>{t['usage']}</td><td class='numeric'>{t['mips']}</td>"
            uncomp_style = 'style="color: #ff4444; font-weight: bold;"' if t["uncompressed"] == "YES" else 'style="color: var(--text-muted);"'
            row_html += f"<td {uncomp_style} class='boolean-cell'>{t['uncompressed']}</td></tr>"
            tbody += row_html

        display_style = "block" if is_active else "none"
        
        # Javascript for this specific tab
        script = """
        <script>
            // Store active filters: { colIndex: [val1, val2] }
            var textureFilters = {};
            var textureSpecialFilters = {};
            const IDX_RAM_SIZE = """ + str(idx_ram_size) + """;
            const IDX_DISK_SIZE = """ + str(idx_disk_size) + """;
            const IDX_RAM_W = 1;
            const IDX_DISK_W = """ + str(offset) + """;

            function toggleTextureFilter(btn) {
                const col = btn.getAttribute('data-col');
                const val = btn.getAttribute('data-val');
                
                if (!textureFilters[col]) textureFilters[col] = [];
                
                const idx = textureFilters[col].indexOf(val);
                if (idx > -1) {
                    textureFilters[col].splice(idx, 1);
                    btn.classList.remove('active-sub');
                } else {
                    textureFilters[col].push(val);
                    btn.classList.add('active-sub');
                }
                
                if (textureFilters[col].length === 0) delete textureFilters[col];
                
                applyTextureFilters();
            }
            
            function toggleTextureSpecial(btn) {
                const key = btn.getAttribute('data-special');
                if (textureSpecialFilters[key]) delete textureSpecialFilters[key];
                else textureSpecialFilters[key] = true;
                btn.classList.toggle('active-sub');
                applyTextureFilters();
            }
            
            function clearTextureFilters() {
                textureFilters = {};
                textureSpecialFilters = {};
                // Clear buttons in the tab
                const tab = document.getElementById('""" + self.id + """');
                if(tab) {
                     tab.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active-sub'));
                     const searchInput = tab.querySelector('input');
                     if(searchInput) searchInput.value = '';
                }
                applyTextureFilters();
            }

            function resetTextureView() {
                // 1. Clear all tactical filters and search
                clearTextureFilters();
                
                // 2. Clear sorting visual state from headers
                const table = document.getElementById('tbl-""" + self.id + """');
                if(!table) return;
                table.querySelectorAll('th').forEach(h => {
                     h.classList.remove('sort-asc', 'sort-desc');
                     h.removeAttribute('data-asc');
                });

                // 3. Restore original row order
                const tbody = table.querySelector('tbody');
                const rows = Array.from(tbody.querySelectorAll('tr'));
                rows.sort((a, b) => {
                    return parseInt(a.getAttribute('data-original-index')) - parseInt(b.getAttribute('data-original-index'));
                });
                rows.forEach(r => tbody.appendChild(r));

                // 4. Reset Default View button active state
                const defaultBtn = document.getElementById('btn-default-view-tex');
                if(defaultBtn) {
                    const container = defaultBtn.closest('.search-container');
                    if(container) {
                        container.querySelectorAll('.action-btn').forEach(b => b.classList.remove('active-sub'));
                    }
                    defaultBtn.classList.add('active-sub');
                }
            }

            function parseSizeToMB(szStr) {
                const parts = szStr.split(' ');
                if (parts.length < 2) return 0;
                let val = parseFloat(parts[0]);
                const unit = parts[1].toUpperCase();
                if (unit === 'KB') return val / 1024;
                if (unit === 'GB') return val * 1024;
                if (unit === 'B') return val / (1024 * 1024);
                return val;
            }

            function formatMB(mb) {
                return mb.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' MB';
            }
            
            function applyTextureFilters() {{
                 const table = document.getElementById('tbl-""" + self.id + """');
                 if(!table) return;
                 const rows = table.querySelectorAll('tbody tr');
                 
                 let totalInMem = 0;
                 let totalOnDisk = 0;
                 let visibleCount = 0;

                 rows.forEach(row => {{
                     let visible = true;
                     const getCell = (c) => row.children[c] ? row.children[c].innerText.trim() : "";
                     
                     for (const [col, requiredVals] of Object.entries(textureFilters)) {{
                         if (requiredVals.length > 0) {{
                             const cellText = getCell(col);
                             if (!requiredVals.includes(cellText)) {{
                                 visible = false;
                                 break;
                             }}
                         }}
                     }}
                     
                     // Combined with search term manually to get correct totals
                     const searchInput = document.querySelector('#""" + self.id + """ input');
                     const searchTerm = searchInput ? searchInput.value.toLowerCase() : "";
                     if (visible && searchTerm) {{
                         if (!row.innerText.toLowerCase().includes(searchTerm)) {{
                             visible = false;
                         }}
                     }}

                      // Special Filters: Size Mismatch
                      if (visible && textureSpecialFilters['size-mismatch']) {{
                          const ramMB = parseSizeToMB(getCell(IDX_RAM_SIZE));
                          const diskMB = parseSizeToMB(getCell(IDX_DISK_SIZE));
                          const ramW = parseInt(getCell(IDX_RAM_W)) || 0;
                          const diskW = parseInt(getCell(IDX_DISK_W)) || 0;
                          
                          // Mismatch if either sizes (MB) or dimensions (Width) differ
                          if (Math.abs(ramMB - diskMB) < 0.01 && ramW === diskW) {{
                              visible = false;
                          }}
                      }}

                     row.style.display = visible ? '' : 'none';
                     
                     if (visible) {{
                         visibleCount++;
                         // Update counter cell (first column)
                         row.children[0].innerText = visibleCount;
                         
                         totalInMem += parseSizeToMB(getCell(IDX_RAM_SIZE));
                         totalOnDisk += parseSizeToMB(getCell(IDX_DISK_SIZE));
                     }}
                 }});

                 document.getElementById('tex-filtered-inmem').innerText = formatMB(totalInMem);
                 document.getElementById('tex-filtered-ondisk').innerText = formatMB(totalOnDisk);
                 document.getElementById('tex-filtered-count').innerText = visibleCount;
            }}

            // Add event listener for table sorting to refresh counters
            document.addEventListener('DOMContentLoaded', () => {
                const table = document.getElementById('tbl-""" + self.id + """');
                if(table) {
                    table.querySelectorAll('th').forEach(th => {
                        th.addEventListener('click', () => {
                            // Wait for sorting to finish (it's synchronous but let's be safe)
                            setTimeout(applyTextureFilters, 10);
                        });
                    });
                }
                applyTextureFilters();
            });

            // Initial calculation
            document.addEventListener('DOMContentLoaded', () => applyTextureFilters());
        </script>
        """

        return f"""
        <style>
            #tbl-{self.id} {{
                min-width: 1400px;
                font-size: 13px; /* Standardize with other tabs */
                table-layout: auto;
                border-spacing: 0;
            }}
            #tbl-{self.id} th {{
                white-space: nowrap !important;
                vertical-align: bottom;
                padding: 6px 4px;
                background-color: var(--header-bg);
                word-break: normal !important;
                overflow-wrap: normal !important;
            }}
            #tbl-{self.id} td {{
                padding: 6px 4px;
                vertical-align: middle;
            }}
            .name-cell {{
                min-width: 500px;
                word-break: break-all;
                white-space: normal;
            }}
            .format-cell {{
                white-space: nowrap !important;
                min-width: 80px;
            }}
            .group-cell {{
                white-space: normal !important;
                word-break: break-all !important;
                min-width: 100px;
                max-width: 120px;
                line-height: 1.1;
                font-size: 0.95em;
            }}
            .boolean-cell {{
                min-width: 100px;
                text-align: center;
                white-space: nowrap !important;
            }}
            .numeric {{
                min-width: 85px;
                white-space: nowrap !important;
            }}
            .count-cell, .count-header {{
                min-width: 50px;
                text-align: center;
                color: var(--text-muted);
                font-weight: bold;
                background: rgba(0,0,0,0.1);
            }}
            .highlight-red-row td {{
                border-top: 2px solid #ff4444 !important;
                border-bottom: 2px solid #ff4444 !important;
                background: rgba(255, 68, 68, 0.05) !important;
            }}
            .highlight-red-row td:first-child {{
                border-left: 2px solid #ff4444 !important;
            }}
            .highlight-red-row td:last-child {{
                border-right: 2px solid #ff4444 !important;
            }}
        </style>
        <div id="{self.id}" class="tab-content" style="display: {display_style}; width: 100%;">
            <h3 style="margin-bottom: 20px;">Texture Statistics</h3>
            {summary_html}
            
            <div class="search-container" data-no-reset="true">
                <input type="text" placeholder="Search textures..." onkeyup="applyTextureFilters()">
                
                <button class="action-btn" onclick="clearTextureFilters()" style="margin-left: 10px;">Clear Filters</button>
                <button class="action-btn active-sub" id="btn-default-view-tex" onclick="resetTextureView()" style="margin-left: 10px;">Default View</button>
            </div>
            
            {filter_html}
            
            <div class="table-container">
                <table id="tbl-{self.id}">
                    <thead>{thead}</thead>
                    <tbody>{tbody}</tbody>
                </table>
            </div>
            {script}
        </div>
        """
