import re
from typing import Any, Dict, List
from ..utils import format_memory_size
from . import ReportTab

class RenderTargetPoolTab(ReportTab):
    def __init__(self):
        super().__init__("Pooled Render Target Stats", "render-target-pool")

    def should_handle(self, line: str) -> bool:
        return line.lower().strip().startswith('memreport: begin command "r.dumprendertargetpoolmemory')

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        raw_line = line.strip()

        if "render_target_pool" not in context:
            context["render_target_pool"] = {
                "pooled": [],
                "deferred": [],
                "summary": {
                    "pooled_total_mb": 0.0,
                    "pooled_used_mb": 0.0,
                    "pooled_unused_mb": 0.0,
                    "pooled_count": 0,
                    "deferred_mb": 0.0
                },
                "parsing_mode": None 
            }

        store = context["render_target_pool"]

        if self.should_handle(raw_line):
           store["parsing_mode"] = None
           return

        if "Pooled Render Targets:" in raw_line:
            store["parsing_mode"] = "pooled"
            return
        if "Deferred Render Targets:" in raw_line:
            store["parsing_mode"] = "deferred"
            return
        
        # Pooled Summary Line: "60.806MB total, 13.762MB used, 20.695MB unused, 25 render targets"
        if "MB total," in raw_line and "MB used," in raw_line and "render targets" in raw_line:
            match = re.search(r"([\d\.]+)MB total,\s*([\d\.]+)MB used,\s*([\d\.]+)MB unused,\s*(\d+)", raw_line)
            if match:
                store["summary"]["pooled_total_mb"] = float(match.group(1))
                store["summary"]["pooled_used_mb"] = float(match.group(2))
                store["summary"]["pooled_unused_mb"] = float(match.group(3))
                store["summary"]["pooled_count"] = int(match.group(4))
            return

        # Deferred Summary Line: "0.000MB Deferred total"
        if "Deferred total" in raw_line:
            match = re.search(r"([\d\.]+)MB Deferred total", raw_line)
            if match:
                 store["summary"]["deferred_mb"] = float(match.group(1))
            return

        if not store["parsing_mode"]:
            return

        # Refined Regex to handle Depth (x 4) and Array Size ([ 1])
        match = re.search(r"^\s*([\d\.]+)MB\s+(\d+)x\s*(\d+)(?:\s*x\s*(\d+))?(?:\s*\[\s*(\d+)\])?\s+(\d+)mip\(s\)\s+(.*)$", raw_line)
        if match:
            size_mb = float(match.group(1))
            width = int(match.group(2))
            height = int(match.group(3))
            depth = match.group(4) 
            array_size_str = match.group(5) 
            mips = int(match.group(6))
            remainder = match.group(7)
            
            unused_frames = 0
            if "Unused frames:" in remainder:
                parts = remainder.rsplit("Unused frames:", 1)
                remainder = parts[0].strip()
                try:
                    unused_frames = int(parts[1].strip())
                except:
                    pass
            
            fmt = "Unknown"
            name = remainder
            fmt_match = re.search(r"\((PF_[^)]+)\)$", remainder)
            if not fmt_match:
                 fmt_match = re.search(r"\(([^)]+)\)$", remainder)
            
            if fmt_match:
                fmt = fmt_match.group(1)
                name = remainder[:fmt_match.start()].strip()
            
            # Logic for Is Array and Array Size
            is_array = "No"
            display_array_size = ""
            if array_size_str:
                val = int(array_size_str)
                display_array_size = str(val)
                if val >= 1:
                    is_array = "Yes"
            
            depth_val = int(depth) if depth else 1
            is_volumetric = "Yes" if depth_val > 1 else "No"
            
            entry = {
                "size_mb": size_mb,
                "width": width,
                "height": height,
                "depth": depth_val,
                "is_volumetric": is_volumetric,
                "is_array": is_array,
                "array_size": display_array_size,
                "mips": mips,
                "name": name,
                "format": fmt,
                "unused_frames": unused_frames
            }
            
            if store["parsing_mode"] == "pooled":
                store["pooled"].append(entry)
            else:
                store["deferred"].append(entry)

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        store = context.get("render_target_pool", {
            "pooled": [], "deferred": [],
            "summary": {"pooled_total_mb": 0, "pooled_used_mb": 0, "pooled_unused_mb": 0, "pooled_count": 0, "deferred_mb": 0}
        })
        
        summary = store["summary"]
        pooled = store["pooled"]
        deferred = store["deferred"]
        
        display_class = " active" if is_active else ""
        display_style = "block" if is_active else "none"

        calc_pooled_mb = sum(x['size_mb'] for x in pooled)
        calc_deferred_mb = sum(x['size_mb'] for x in deferred)

        # Prepare Shared Warning logic (Used in both Pooled and Deferred sections)
        reported_sum = summary['pooled_used_mb'] + summary['pooled_unused_mb']
        has_pooled_mismatch = abs(summary['pooled_total_mb'] - reported_sum) > 0.001 and summary['pooled_total_mb'] > 0
        
        debug_name_note = f"<b>Note:</b> Render Targets use generic labels rather than unique names. If the same name appears multiple times, each entry represents a <b>separate and unique memory allocation</b> (these are not accidental duplicate records)."
        
        if has_pooled_mismatch:
            mismatch_note = f"<br><b>This discrepancy often occurs due to internal alignment overhead, driver-reserved memory, or hidden base allocations within the pool that aren't categorized as active or inactive.</b>"
            shared_warning = f"""
                <div class="alert alert-warning" style="margin-top: 15px;">
                    <div class="alert-icon">⚠️</div>
                    <div class="alert-content">
                        <strong>Total Mismatch Detected:</strong> The reported total ({summary['pooled_total_mb']:.3f} MB) does not equal the sum of used and unused memory ({reported_sum:.3f} MB).
                        {mismatch_note}
                        <br>{debug_name_note}
                    </div>
                </div>
                """
        else:
            shared_warning = f"""
                <div class="alert alert-warning" style="margin-top: 15px;">
                    <div class="alert-icon">⚠️</div>
                    <div class="alert-content">
                        {debug_name_note}
                    </div>
                </div>
                """

        def render_metric_card(title, subtext, total_mb, used_mb, unused_mb, count, prefix, card_type):
            used_str = f"{used_mb:.3f} MB" if used_mb is not None else "Cannot COMPUTE (See ⚠️)"
            unused_str = f"{unused_mb:.3f} MB" if unused_mb is not None else "Cannot COMPUTE (See ⚠️)"
            
            subtext_html = f'<div style="font-size: 0.65em; color: var(--unreal-red-color, #f43f5e); text-transform: uppercase; margin-bottom: 5px;">{subtext}</div>' if subtext else ""
            
            count_label = "Targets"
            val_color = "var(--accent-color)"
            card_style = "background: var(--header-bg); border: 1px solid var(--border-color);"
            
            if card_type == "reported":
                count_label = "Render Target Count reported"
                val_color = "#ce9178"
            elif card_type == "calculated":
                count_label = "Render Target Count Calculated"
                val_color = "#4ec9b0"
            elif card_type == "filtered":
                count_label = "Render Target Count Filtered"
                card_style = "background: rgba(59, 130, 246, 0.05); border: 1px solid var(--accent-color);"

            return f"""
            <div class="analytics-card" style="flex: 1; min-width: 250px; padding: 15px; border-radius: 8px; {card_style} text-align: center; display: flex; flex-direction: column; justify-content: space-between;">
                <div>
                    <h4 style="margin: 0 0 5px 0; color: {val_color if card_type == 'filtered' else 'var(--text-muted)'}; font-size: 0.8em; text-transform: uppercase; letter-spacing: 1px;">{title}</h4>
                    {subtext_html}
                    <div id="stat-total-{prefix}" style="font-size: 1.5em; font-weight: bold; color: {val_color}; margin: 10px 0;">{total_mb:.3f} MB</div>
                </div>
                <div style="font-size: 0.85em; color: var(--text-secondary); border-top: 1px solid var(--border-color); padding-top: 10px; margin-top: 5px; text-align: left; display: grid; grid-template-columns: 1fr 1fr; gap: 5px 10px;">
                    <div><span style="color: var(--text-muted);">Used:</span> <span id="stat-used-{prefix}" style="font-weight: 500;">{used_str}</span></div>
                    <div><span style="color: var(--text-muted);">Unused:</span> <span id="stat-unused-{prefix}" style="font-weight: 500;">{unused_str}</span></div>
                    <div style="grid-column: span 2; border-top: 1px solid rgba(128,128,128,0.1); padding-top: 5px; margin-top: 5px;">
                        <span style="color: var(--text-muted);">{count_label}:</span> <b id="stat-count-{prefix}" style="color: {val_color};">{count}</b>
                    </div>
                </div>
            </div>
            """

        def render_analytics_row(title, prefix, rep_total, rep_used, rep_unused, rep_count, calc_total, calc_count):
            # Merge into 3 main cards: Reported, Calculated, Filtered
            # Reported
            reported_card = render_metric_card(
                "Reported Total", 
                "(UNREAL REPORTED TOTAL)", 
                rep_total, 
                rep_used, 
                rep_unused, 
                rep_count, 
                f"{prefix}-reported",
                "reported"
            )
            # Calculated
            calculated_card = render_metric_card(
                "Calculated Total", 
                None, 
                calc_total, 
                None, 
                None, 
                calc_count, 
                f"{prefix}-calculated",
                "calculated"
            )
            # Filtered
            filtered_card = render_metric_card(
                "Filtered Total", 
                None, 
                calc_total, 
                None, 
                None, 
                calc_count, 
                f"{prefix}-filtered",
                "filtered"
            )

            return f"""
            <div class="analytics-wrapper" style="background: var(--row-even); padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid var(--border-color);">
                <h3 style="margin-top: 0; margin-bottom: 20px; border-bottom: 1px solid var(--border-color); padding-bottom: 15px; color: var(--text-color); font-size: 1.1em; font-weight: 600;">{title} Aggregate Statistics</h3>
                <div class="analytics-row" style="display: flex; gap: 20px; flex-wrap: wrap;">
                    {reported_card}
                    {calculated_card}
                    {filtered_card}
                </div>
                {shared_warning}
                <div style="margin-top: 15px;">
                    {info_box}
                </div>
            </div>
            """

        def render_table(rows, table_id, filtered_id_prefix):
            headers = ["#", "Width", "Height", "Depth", "Size (MB)", "Is Volumetric", "Is Array", "Array Size", "Debug Name", "Format", "Num Mips", "Unused Frames"]
            
            thead = "<tr>" + "".join([f"<th>{h}</th>" for h in headers]) + "</tr>"
            tbody = ""
            for idx, r in enumerate(rows, 1):
                row_class = ""
                if r["unused_frames"] > 60:
                     row_class = 'class="unused-danger"'
                elif r["unused_frames"] > 5:
                     row_class = 'class="unused-warn"'

                # Yes/No styling matching Texture Stats boolean style (Standard Green/Red)
                is_array_class = "status-yes" if r["is_array"] == "Yes" else "status-no"
                is_array_html = f'<span class="{is_array_class}">{r["is_array"]}</span>'

                is_vol_class = "status-yes" if r["is_volumetric"] == "Yes" else "status-no"
                is_vol_html = f'<span class="{is_vol_class}">{r["is_volumetric"]}</span>'

                depth_display = str(r['depth']) if r['depth'] > 1 else ""

                row_html = f"<tr {row_class} data-size='{r['size_mb']}'>"
                row_html += f"<td>{idx}</td>"
                row_html += f"<td>{r['width']}</td>"
                row_html += f"<td>{r['height']}</td>"
                row_html += f"<td>{depth_display}</td>"
                row_html += f"<td>{r['size_mb']:.3f}</td>"
                row_html += f"<td>{is_vol_html}</td>"
                row_html += f"<td>{is_array_html}</td>"
                row_html += f"<td>{r['array_size']}</td>"
                row_html += f"<td class='name-cell'>{r['name']}</td>"
                row_html += f"<td class='format-cell'>{r['format']}</td>"
                row_html += f"<td>{r['mips']}</td>"
                row_html += f"<td>{r['unused_frames']}</td>"
                row_html += "</tr>"
                tbody += row_html
            
            return f"""
            <div class="table-container">
                <table id="{table_id}">
                    <thead>{thead}</thead>
                    <tbody>{tbody}</tbody>
                </table>
            </div>
            """

        script = """
        <script>
            // Store active filters: { tableId: { colIndex: [vals] } }
            var rtFilters = {};

            function toggleRtFilter(btn, tableId, prefix) {
                const col = parseInt(btn.getAttribute('data-col'));
                const val = btn.getAttribute('data-val');
                
                if (!rtFilters[tableId]) rtFilters[tableId] = {};
                if (!rtFilters[tableId][col]) rtFilters[tableId][col] = [];
                
                const idx = rtFilters[tableId][col].indexOf(val);
                if (idx > -1) {
                    rtFilters[tableId][col].splice(idx, 1);
                    btn.classList.remove('active-sub');
                } else {
                    rtFilters[tableId][col].push(val);
                    btn.classList.add('active-sub');
                }
                
                if (rtFilters[tableId][col].length === 0) delete rtFilters[tableId][col];
                
                filterRtTable(tableId, prefix);
            }

            function filterRtTable(tableId, prefix) {
                const tab = document.getElementById('render-target-pool');
                const searchInput = tab ? tab.querySelector(`div:has(> #tbl-${prefix}) .search-container input`) : null;
                // Simplified lookup for search input if previous fails
                const allInputs = document.querySelectorAll('#render-target-pool input');
                let input = null;
                if (prefix === 'pooled') input = allInputs[0];
                else input = allInputs[1];

                const filter = input ? input.value.toUpperCase() : "";
                const table = document.getElementById(tableId);
                const tr = table.getElementsByTagName("tr");
                let visibleSum = 0.0;
                let visibleCount = 0;

                for (let i = 1; i < tr.length; i++) {
                    let visible = true;
                    const tds = tr[i].getElementsByTagName("td");
                    
                    // 1. Check Search Box
                    if (filter) {
                        let rowMatch = false;
                        for (let j = 0; j < tds.length; j++) {
                            if (tds[j].innerText.toUpperCase().indexOf(filter) > -1) {
                                rowMatch = true;
                                break;
                            }
                        }
                        if (!rowMatch) visible = false;
                    }

                    // 2. Check Quick Filters
                    if (visible && rtFilters[tableId]) {
                        for (const [col, vals] of Object.entries(rtFilters[tableId])) {
                            if (vals.length > 0) {
                                let cellVal = tds[col].innerText.trim();
                                if (!vals.includes(cellVal)) {
                                    visible = false;
                                    break;
                                }
                            }
                        }
                    }

                    tr[i].style.display = visible ? "" : "none";
                    
                    if (visible) {
                         visibleCount++;
                         tr[i].children[0].innerText = visibleCount;
                         const sizeVal = parseFloat(tr[i].getAttribute('data-size')) || 0;
                         visibleSum += sizeVal;
                    }
                }
                
                // Update Filtered Card
                const totalEl = document.getElementById('stat-total-' + prefix + '-filtered');
                const countEl = document.getElementById('stat-count-' + prefix + '-filtered');
                
                if(totalEl) totalEl.innerText = visibleSum.toFixed(3) + " MB";
                if(countEl) countEl.innerText = visibleCount;
            }
        </script>
        """

        info_box = """
            <div class="alert alert-info" style="margin-top: 15px;">
                <div class="alert-icon">ℹ️</div>
                <div class="alert-content">
                    <ul style="margin: 0; padding-left: 20px;">
                        <li><strong>Volumetric Render Target:</strong> A 3D texture resource where Depth > 1. Unlike arrays, a volume is treated as a single coordinate space.</li>
                        <li><strong>Understanding Arrays:</strong> Is Array is True only if Array Size is not empty and the value is ≥ 1. A value of 1 implies 2 total elements (indexing 0 and 1).</li>
                        <li><strong>Understanding Comparisons:</strong>
                            <ul style="margin-top: 5px; opacity: 0.9; padding-left: 30px; list-style-type: circle;">
                                <li><strong>Texture 2D:</strong> Standard flat image (W x H).</li>
                                <li><strong>Texture 3D (Volumetric):</strong> Single volume resource (W x H x D). Excellent for SDFs, VDBs or 3D noise.</li>
                                <li><strong>Texture Array:</strong> Stack of 2D images. Similar to a pack of cards; you index a specific "slice".</li>
                                <li><strong>Cube Map:</strong> 6 faces (W x H x 6) forming a cube. Usually for environment maps or reflections.</li>
                                <li><strong>Cube Map Array:</strong> An array where each element is a full 6-face cube map.</li>
                                <li><strong>Array of Texture 3D:</strong> A stack of multiple volumes (W x H x D x ArraySize).</li>
                            </ul>
                        </li>
                        <li><strong>Unused Frames:</strong> Frames elapsed since the target was last used in the frame graph.</li>
                    </ul>
                </div>
            </div>
        """

        def render_filters(rows, table_id, prefix):
            unique_formats = sorted(list(set(r["format"] for r in rows if r["format"] != "Unknown")))
            
            format_btns = "".join([f'<button class="action-btn filter-btn" data-col="9" data-val="{f}" onclick="toggleRtFilter(this, \'{table_id}\', \'{prefix}\')">{f}</button>' for f in unique_formats])
            
            return f"""
            <div style="background: rgba(0,0,0,0.15); padding: 12px; border-radius: 6px; margin-bottom: 20px; border: 1px solid var(--border-color);">
                <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 5px; margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid rgba(255,255,255,0.05);">
                    <span style="font-size: 10px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; width: 100px; flex-shrink: 0;">Flags:</span>
                    <div style="flex-grow: 1; display: flex; flex-wrap: wrap; gap: 5px;">
                        <button class="action-btn filter-btn" data-col="6" data-val="Yes" onclick="toggleRtFilter(this, '{table_id}', '{prefix}')">Arrays</button>
                        <button class="action-btn filter-btn" data-col="5" data-val="Yes" onclick="toggleRtFilter(this, '{table_id}', '{prefix}')">Volumetric</button>
                    </div>
                </div>
                <div style="display: flex; flex-wrap: wrap; align-items: center; gap: 5px;">
                    <span style="font-size: 10px; color: var(--text-muted); font-weight: 600; text-transform: uppercase; width: 100px; flex-shrink: 0;">Formats:</span>
                    <div style="flex-grow: 1; display: flex; flex-wrap: wrap; gap: 5px;">{format_btns}</div>
                </div>
            </div>
            """

        return f"""
        <div id="{self.id}" class="tab-content{display_class}" style="display: {display_style};">
            
            {render_analytics_row("Pooled Render Target", "pooled", summary['pooled_total_mb'], summary['pooled_used_mb'], summary['pooled_unused_mb'], summary['pooled_count'], calc_pooled_mb, len(pooled))}
            
            <div class="search-container">
                <input type="text" placeholder="Search pooled render targets..." onkeyup="filterRtTable('tbl-rt-pooled', 'pooled')">
            </div>
            {render_filters(pooled, "tbl-rt-pooled", "pooled")}
            {render_table(pooled, "tbl-rt-pooled", "pooled")}
            
            <hr class="section-divider">
            
            {render_analytics_row("Deferred Render Target", "deferred", summary['deferred_mb'], None, None, 0, calc_deferred_mb, len(deferred))}
            

            <div class="search-container">
                <input type="text" placeholder="Search deferred render targets..." onkeyup="filterRtTable('tbl-rt-deferred', 'deferred')">
            </div>
            {render_filters(deferred, "tbl-rt-deferred", "deferred")}
            {render_table(deferred, "tbl-rt-deferred", "deferred")}
            
            {script}
        </div>
        """
