from typing import Any, Dict, List

from ..utils import format_bytes
from . import ReportTab


class ParticleSystemsTab(ReportTab):
    def __init__(self):
        super().__init__("Particle System Stats", "particle-systems")
        self.headers = [
            "Name",
            "Size",
            "System Size",
            "Module Size",
            "Component Size",
            "Component Count",
            "Component Resource Size",
            "Component True Resource Size",
        ]

    def should_handle(self, line: str) -> bool:
        line_lower = line.lower().strip()
        return line_lower.startswith(
            'memreport: begin command "listparticlesystems -alphasort"'
        ) or line_lower.startswith('memreport: begin command "dumpparticlemem"')

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        if "particle_stats" not in context:
            context["particle_stats"] = []
        if "particle_dynamic_stats" not in context:
            context["particle_dynamic_stats"] = {
                "types": [],
                "summary": {},
                "parsing_mode": None,
            }

        raw_line = line.strip()
        if self.should_handle(raw_line) or "MemReport:" in raw_line:
            # Reset parsing mode on any command boundary
            if "particle_dynamic_stats" in context:
                context["particle_dynamic_stats"]["parsing_mode"] = None
            return

        # Skip empty lines
        if not raw_line:
            return

        # Dynamic Stats Parsing
        dynamic = context["particle_dynamic_stats"]

        # Detect mode
        if (
            "Type,Count,MaxCount,Mem(Bytes),MaxMem(Bytes),GTMem(Bytes),GTMemMax(Bytes)"
            in raw_line
        ):
            dynamic["parsing_mode"] = "types"
            return
        elif "ParticleData,Total(Bytes),FMath::Max(Bytes)" in raw_line:
            dynamic["parsing_mode"] = "summary"
            return
        elif "Max wasted GT," in raw_line:
            dynamic["parsing_mode"] = "misc"

        if dynamic["parsing_mode"] == "types":
            parts = [p.strip() for p in raw_line.split(",")]
            if len(parts) >= 7:
                try:
                    p_type = parts[0]
                    # Label refinement
                    if p_type == "Total PSysComponents":
                        p_type = "Total Particle System Components"
                    elif p_type == "Total DynamicEmitters":
                        p_type = "Total Dynamic Emitters"

                    dynamic["types"].append(
                        {
                            "Type": p_type,
                            "Count": int(parts[1]),
                            "MaxCount": int(parts[2]),
                            "Mem": float(parts[3]),
                            "MaxMem": float(parts[4]),
                            "GTMem": float(parts[5]),
                            "GTMemMax": float(parts[6]),
                        }
                    )
                    return
                except (ValueError, IndexError):
                    pass

        if dynamic["parsing_mode"] == "summary":
            parts = [p.strip() for p in raw_line.split(",")]
            if len(parts) >= 3:
                try:
                    p_key = parts[0]
                    # Abbreviation refinement (GT/RT)
                    p_key = p_key.replace("GameThread", "Game Thread").replace(
                        "RenderThread", "Render Thread"
                    )

                    dynamic["summary"][p_key] = {
                        "Total": float(parts[1]),
                        "Max": float(parts[2]),
                    }
                    return
                except (ValueError, IndexError):
                    pass

        if dynamic["parsing_mode"] == "misc":
            parts = [p.strip() for p in raw_line.split(",")]
            if len(parts) >= 2:
                try:
                    p_key = parts[0]
                    # Abbreviation refinement (GT/RT)
                    p_key = p_key.replace("GT", "Game Thread").replace(
                        "RT", "Render Thread"
                    )

                    dynamic["summary"][p_key] = float(parts[1])
                    return
                except (ValueError, IndexError):
                    pass

        # Original Static Stats Parsing
        parts = [p.strip() for p in raw_line.split(",")]
        if len(parts) >= 8:
            try:
                size = float(parts[0])
                name = parts[1]
                psys_size = float(parts[2])
                module_size = float(parts[3])
                comp_size = float(parts[4])
                comp_count = int(parts[5])
                comp_res_size = float(parts[6])
                comp_true_res_size = float(parts[7])

                context["particle_stats"].append(
                    {
                        "Name": name,
                        "Size": size,
                        "System Size": psys_size,
                        "Module Size": module_size,
                        "Component Size": comp_size,
                        "Component Count": comp_count,
                        "Component Resource Size": comp_res_size,
                        "Component True Resource Size": comp_true_res_size,
                    }
                )
            except (ValueError, IndexError):
                pass

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        stats = context.get("particle_stats", [])
        dynamic_stats = context.get(
            "particle_dynamic_stats", {"types": [], "summary": {}}
        )

        display_style = "block" if is_active else "none"

        # --- Static Spawned Section ---
        static_html = ""
        if stats:
            # Pinned Total row
            total_row = None
            other_rows = []
            for s in stats:
                if s["Name"].lower() == "total":
                    total_row = s
                else:
                    other_rows.append(s)

            # Calculated totals (Python side)
            def get_calc_static(field):
                return sum(s[field] for s in other_rows)

            calc_static_stats = {
                "Size": get_calc_static("Size"),
                "System Size": get_calc_static("System Size"),
                "Module Size": get_calc_static("Module Size"),
                "Component Size": get_calc_static("Component Size"),
                "Component Count": get_calc_static("Component Count"),
                "Component Resource Size": get_calc_static("Component Resource Size"),
                "Component True Resource Size": get_calc_static(
                    "Component True Resource Size"
                ),
            }
            calc_static_count = len(other_rows)

            thead_static = (
                "<thead><tr><th class='numeric'>#</th>"
                + "".join([f"<th>{h}</th>" for h in self.headers])
                + "</tr></thead>"
            )

            tbody_static = "<tbody>"

            def render_static_row(s, idx=""):
                row_html = f"<tr data-index='{idx}'>"
                row_html += f"<td class='numeric'>{idx}</td>"
                row_html += f"<td title='{s['Name']}' style='word-break: break-all;'>{s['Name']}</td>"
                row_html += f"<td class='numeric' data-val='{s['Size']}'>{format_bytes(s['Size'])}</td>"
                row_html += f"<td class='numeric' data-val='{s['System Size']}'>{format_bytes(s['System Size'])}</td>"
                row_html += f"<td class='numeric' data-val='{s['Module Size']}'>{format_bytes(s['Module Size'])}</td>"
                row_html += f"<td class='numeric' data-val='{s['Component Size']}'>{format_bytes(s['Component Size'])}</td>"
                row_html += f"<td class='numeric' data-val='{s['Component Count']}'>{s['Component Count']}</td>"
                row_html += f"<td class='numeric' data-val='{s['Component Resource Size']}'>{format_bytes(s['Component Resource Size'])}</td>"
                row_html += f"<td class='numeric' data-val='{s['Component True Resource Size']}'>{format_bytes(s['Component True Resource Size'])}</td>"
                row_html += "</tr>"
                return row_html

            for i, s in enumerate(other_rows):
                tbody_static += render_static_row(s, idx=i + 1)
            tbody_static += "</tbody>"

            def render_static_metrics_grid(prefix, data):
                is_reported = prefix == "Reported"
                color = "#ce9178" if is_reported else "#4ec9b0"
                if prefix == "Filtered":
                    color = "var(--accent-color)"

                metrics = [
                    ("Size", data.get("Size", 0)),
                    ("System Size", data.get("System Size", 0)),
                    ("Module Size", data.get("Module Size", 0)),
                    ("Component Size", data.get("Component Size", 0)),
                    ("Component Count", data.get("Component Count", 0)),
                    ("Component Resource Size", data.get("Component Resource Size", 0)),
                    (
                        "Component True Resource Size",
                        data.get("Component True Resource Size", 0),
                    ),
                ]

                html = f'<div style="display: grid; grid-template-columns: 1fr 1.2fr; gap: 4px 10px; font-size: 0.85em; text-align: left; margin-top: 10px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px;">'
                for label, val in metrics:
                    display_val = (
                        f"<b>{format_bytes(val)}</b>"
                        if label not in ["Component Count", "ComponentCount"]
                        else f"<b>{int(val)}</b>"
                    )
                    id_label = label.lower().replace(" ", "")
                    id_attr = (
                        f' id="filt-{id_label}-{self.id}"'
                        if prefix == "Filtered"
                        else ""
                    )
                    html += f'<div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">{prefix} {label}:</span></div>'
                    html += f'<div{id_attr} style="color: {color}; text-align: right;">{display_val}</div>'
                html += "</div>"
                return html

            reported_grid = render_static_metrics_grid(
                "Reported", total_row if total_row else {}
            )
            calculated_grid = render_static_metrics_grid(
                "Calculated", calc_static_stats
            )
            filtered_grid = render_static_metrics_grid("Filtered", calc_static_stats)

            static_html = f"""
            <h3 style="margin-bottom: 20px;">Particle System Statistics (Static Spawned)</h3>
            
            <div class="analytics-wrapper" style="background: var(--row-even); padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid var(--border-color);">
                <div class="analytics-row" style="display: flex; gap: 20px; flex-wrap: wrap;">
                    <!-- Card 1: Reported Total -->
                    <div class="analytics-card" style="flex: 1; min-width: 250px; background: var(--header-bg); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color); text-align: center;">
                        <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">
                            Reported Total<br>
                            <span class="unreal-red" style="font-size: 0.85em;">(UNREAL REPORTED)</span>
                        </h4>
                        <div style="font-size: 1.5em; font-weight: bold; color: #ce9178;">{format_bytes(total_row['Size']) if total_row else '0 B'}</div>
                        {reported_grid}
                    </div>
                    
                    <!-- Card 2: Calculated Total -->
                    <div class="analytics-card" style="flex: 1; min-width: 250px; background: var(--header-bg); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color); text-align: center;">
                        <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Calculated Total</h4>
                        <div style="font-size: 1.5em; font-weight: bold; color: #4ec9b0;">{format_bytes(calc_static_stats['Size'])}</div>
                        {calculated_grid}
                    </div>

                    <!-- Card 3: Filtered Total -->
                    <div class="analytics-card" style="flex: 1; min-width: 250px; background: rgba(59, 130, 246, 0.08); padding: 15px; border-radius: 6px; border: 1px solid var(--accent-color); text-align: center;">
                        <h4 style="margin: 0 0 10px 0; color: var(--accent-color); font-size: 0.8em; text-transform: uppercase;">Filtered Total</h4>
                        <div id="filt-main-val-{self.id}" style="font-size: 1.5em; font-weight: bold; color: var(--accent-color);">{format_bytes(calc_static_stats['Size'])}</div>
                        {filtered_grid}
                        <div style="margin-top: 5px; font-size: 0.8em; color: var(--text-muted); border-top: 1px solid rgba(255,255,255,0.05); padding-top: 5px;">
                            Items Visible: <b id="filt-items-{self.id}" style="color: var(--accent-color);">{calc_static_count}</b>
                        </div>
                    </div>
                </div>
            </div>

            <div class="search-container" data-no-reset="true">
                <input type="text" id="srch-{self.id}" placeholder="Search static particle systems..." onkeyup="filterParticleTable(this.value)">
                <span style="font-size: 10px; color: #666; font-weight: 600; text-transform: uppercase; margin-left: 10px;">Sort By:</span>
                <button class="action-btn active-sub" id="btn-default-{self.id}" onclick="resetParticleView()">Alpha Sort</button>
            </div>

            <div class="table-container">
                <table id="tbl-{self.id}">
                    {thead_static}
                    {tbody_static}
                </table>
            </div>
            """

        # --- Dynamic Spawned Section ---
        dynamic_html = ""
        types = dynamic_stats.get("types", [])
        summary = dynamic_stats.get("summary", {})

        if types:
            gt_data = summary.get("Game Thread", {"Total": 0, "Max": 0})
            rt_data = summary.get("Render Thread", {"Total": 0, "Max": 0})
            max_wasted = summary.get("Max wasted Game Thread", 0)
            largest_gt = summary.get("Largest single Game Thread allocation", 0)
            largest_rt = summary.get("Largest single Render Thread allocation", 0)

            thead_dyn = "<thead><tr><th class='numeric'>#</th><th>Type</th><th>Count</th><th>Max Count</th><th>Memory</th><th>Max Memory</th><th>Game Thread Memory</th><th>Game Thread Mem Max</th></tr></thead>"
            tbody_dyn = "<tbody>"
            for i, t in enumerate(types):
                tbody_dyn += f"<tr data-index='{i+1}'><td class='numeric'>{i+1}</td><td>{t['Type']}</td><td class='numeric'>{t['Count']}</td><td class='numeric'>{t['MaxCount']}</td><td class='numeric'>{format_bytes(t['Mem'])}</td><td class='numeric'>{format_bytes(t['MaxMem'])}</td><td class='numeric'>{format_bytes(t['GTMem'])}</td><td class='numeric'>{format_bytes(t['GTMemMax'])}</td></tr>"
            tbody_dyn += "</tbody>"

            dynamic_html = f"""
            <hr class="section-divider">
            <h3 style="margin: 40px 0 20px 0;">Particle System Statistics (Dynamic Spawned)</h3>
            
            <div class="analytics-wrapper" style="background: var(--row-even); padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid var(--border-color);">
                <div class="analytics-row" style="display: flex; gap: 20px; flex-wrap: wrap;">
                    <div class="analytics-card" style="flex: 1; min-width: 200px; background: var(--header-bg); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color); text-align: center;">
                        <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Game Thread Data</h4>
                        <div style="font-size: 1.3em; font-weight: bold; color: #4ec9b0;">{format_bytes(gt_data['Total'])}</div>
                        <div style="font-size: 0.8em; color: var(--text-muted); margin-top: 5px;">Max: {format_bytes(gt_data['Max'])}</div>
                    </div>
                    <div class="analytics-card" style="flex: 1; min-width: 200px; background: var(--header-bg); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color); text-align: center;">
                        <h4 style="margin: 0 0 10px 0; color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">Render Thread Data</h4>
                        <div style="font-size: 1.3em; font-weight: bold; color: #4ec9b0;">{format_bytes(rt_data['Total'])}</div>
                        <div style="font-size: 0.8em; color: var(--text-muted); margin-top: 5px;">Max: {format_bytes(rt_data['Max'])}</div>
                    </div>
                    <div class="analytics-card" style="flex: 1; min-width: 220px; background: var(--header-bg); padding: 15px; border-radius: 6px; border: 1px solid var(--border-color); text-align: center; display: flex; flex-direction: column; justify-content: center; gap: 5px;">
                        <div style="font-size: 0.85em;"><span style="color: var(--text-muted); text-transform: uppercase; font-size: 0.9em;">Max Wasted Game Thread:</span> <b style="color: #f43f5e;">{format_bytes(max_wasted)}</b></div>
                        <div style="font-size: 0.85em;"><span style="color: var(--text-muted); text-transform: uppercase; font-size: 0.9em;">Largest Game Thread:</span> <b style="color: #4ec9b0;">{format_bytes(largest_gt)}</b></div>
                        <div style="font-size: 0.85em;"><span style="color: var(--text-muted); text-transform: uppercase; font-size: 0.9em;">Largest Render Thread:</span> <b style="color: #4ec9b0;">{format_bytes(largest_rt)}</b></div>
                    </div>
                </div>
            </div>

            <div class="search-container" data-no-reset="true" style="margin-top: 20px;">
                <input type="text" id="srch-dynamic-{self.id}" placeholder="Search dynamic types..." onkeyup="filterDynamicParticleTable(this.value)">
                <span style="font-size: 10px; color: #666; font-weight: 600; text-transform: uppercase; margin-left: 10px;">Sort By:</span>
                <button class="action-btn active-sub" id="btn-dyn-default-{self.id}" onclick="resetDynamicParticleView()">Default View</button>
            </div>
            <div class="table-container">
                <table id="tbl-dynamic-{self.id}">
                    {thead_dyn}
                    {tbody_dyn}
                </table>
            </div>
            """

        return f"""
        <div id="{self.id}" class="tab-content" style="display: {display_style};">
            {static_html}
            {dynamic_html}
            
            <script>
                function formatParticleSize(bytes) {{
                    if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(2) + " MB";
                    if (bytes >= 1024) return (bytes / 1024.0).toFixed(2) + " KB";
                    return bytes.toFixed(2) + " B";
                }}

                function updateParticleAggregates() {{
                    const table = document.getElementById('tbl-{self.id}');
                    if (!table) return;
                    const rows = Array.from(table.tBodies[0].rows);
                    let itemsVisible = 0;
                    
                    let sums = {{
                        size: 0,
                        systemsize: 0,
                        modulesize: 0,
                        componentsize: 0,
                        componentcount: 0,
                        componentresourcesize: 0,
                        componenttrueresourcesize: 0
                    }};
                    
                    rows.forEach(row => {{
                        if (row.style.display !== 'none' && !row.classList.contains('total-row')) {{
                            itemsVisible++;
                            sums.size += parseFloat(row.cells[2].getAttribute('data-val')) || 0;
                            sums.systemsize += parseFloat(row.cells[3].getAttribute('data-val')) || 0;
                            sums.modulesize += parseFloat(row.cells[4].getAttribute('data-val')) || 0;
                            sums.componentsize += parseFloat(row.cells[5].getAttribute('data-val')) || 0;
                            sums.componentcount += parseInt(row.cells[6].getAttribute('data-val')) || 0;
                            sums.componentresourcesize += parseFloat(row.cells[7].getAttribute('data-val')) || 0;
                            sums.componenttrueresourcesize += parseFloat(row.cells[8].getAttribute('data-val')) || 0;
                        }}
                    }});

                    const filtItems = document.getElementById('filt-items-{self.id}');
                    if (filtItems) filtItems.innerText = itemsVisible;
                    
                    const mainVal = document.getElementById('filt-main-val-{self.id}');
                    if (mainVal) mainVal.innerText = formatParticleSize(sums.size);
                    
                    const setFilt = (id, val, isCount=false) => {{
                        const el = document.getElementById(id);
                        if (el) el.innerHTML = "<b>" + (isCount ? val : formatParticleSize(val)) + "</b>";
                    }};

                    setFilt('filt-size-{self.id}', sums.size);
                    setFilt('filt-systemsize-{self.id}', sums.systemsize);
                    setFilt('filt-modulesize-{self.id}', sums.modulesize);
                    setFilt('filt-componentsize-{self.id}', sums.componentsize);
                    setFilt('filt-componentcount-{self.id}', sums.componentcount, true);
                    setFilt('filt-componentresourcesize-{self.id}', sums.componentresourcesize);
                    setFilt('filt-componenttrueresourcesize-{self.id}', sums.componenttrueresourcesize);
                }}

                function filterParticleTable(term) {{
                    filterTable('tbl-{self.id}', 0, term);
                    updateParticleAggregates();
                }}

                function filterDynamicParticleTable(term) {{
                    filterTable('tbl-dynamic-{self.id}', 0, term);
                    updateDynamicParticleAggregates();
                }}
                
                function updateDynamicParticleAggregates() {{
                    const table = document.getElementById('tbl-dynamic-{self.id}');
                    if (!table) return;
                    const rows = Array.from(table.tBodies[0].rows);
                    let itemsVisible = 0;
                    // We don't have filtered total cards for dynamic yet, 
                    // but we could add them if needed. For now just filtering.
                }}

                function resetParticleView() {{
                    const searchInput = document.getElementById('srch-{self.id}');
                    if (searchInput) {{
                        searchInput.value = '';
                        filterParticleTable('');
                    }}
                    
                    const defBtn = document.getElementById('btn-default-{self.id}');
                    if (defBtn) defBtn.classList.add('active-sub');

                    // Reset Table Sorting
                    const table = document.getElementById('tbl-{self.id}');
                    if (table) {{
                        const tbody = table.querySelector('tbody');
                        const rows = Array.from(tbody.querySelectorAll('tr'));
                        rows.sort((a, b) => {{
                           const ai = parseInt(a.getAttribute('data-index')) || 0;
                           const bi = parseInt(b.getAttribute('data-index')) || 0;
                           return ai - bi;
                        }});
                        rows.forEach(r => tbody.appendChild(r));
                        
                        table.querySelectorAll('th').forEach(th => {{
                            th.classList.remove('sort-asc', 'sort-desc');
                            th.removeAttribute('data-asc');
                        }});
                    }}
                }}

                function resetDynamicParticleView() {{
                    const searchInput = document.getElementById('srch-dynamic-{self.id}');
                    if (searchInput) {{
                        searchInput.value = '';
                        filterDynamicParticleTable('');
                    }}

                    const defBtn = document.getElementById('btn-dyn-default-{self.id}');
                    if (defBtn) defBtn.classList.add('active-sub');

                    // Reset Table Sorting
                    const table = document.getElementById('tbl-dynamic-{self.id}');
                    if (table) {{
                        const tbody = table.querySelector('tbody');
                        const rows = Array.from(tbody.querySelectorAll('tr'));
                        rows.sort((a, b) => {{
                           const ai = parseInt(a.getAttribute('data-index')) || 0;
                           const bi = parseInt(b.getAttribute('data-index')) || 0;
                           return ai - bi;
                        }});
                        rows.forEach(r => tbody.appendChild(r));
                        
                        table.querySelectorAll('th').forEach(th => {{
                            th.classList.remove('sort-asc', 'sort-desc');
                            th.removeAttribute('data-asc');
                        }});
                    }}
                }}

                // Wait for high-level UI to be ready
                setTimeout(() => {{
                    updateParticleAggregates();
                }}, 100);
            </script>
        </div>
        """
