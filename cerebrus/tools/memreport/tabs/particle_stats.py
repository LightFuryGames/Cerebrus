from typing import Any, Dict, List
from . import ReportTab
from ..utils import format_bytes


class ParticleSystemsTab(ReportTab):
    def __init__(self):
        super().__init__("Particle System Stats", "particle-systems")
        self.headers = [
            "Name",
            "Size",
            "System Size",
            "Module Size",
            "Component Size",
            "ComponentCount",
            "ComponentResourceSize",
            "ComponentTrueResourceSize",
        ]

    def should_handle(self, line: str) -> bool:
        return line.lower().strip().startswith(
            'memreport: begin command "listparticlesystems -alphasort"'
        )

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        if "particle_stats" not in context:
            context["particle_stats"] = []

        raw_line = line.strip()
        if self.should_handle(raw_line) or "MemReport:" in raw_line:
            return

        # Skip empty lines
        if not raw_line:
            return

        parts = [p.strip() for p in raw_line.split(",")]
        if len(parts) >= 8:
            # Original order: Size,Name,PSysSize,ModuleSize,ComponentSize,ComponentCount,CompResSize,CompTrueResSize
            # Corrected order: Name, Size, System Size, Module Size, Component Size, ComponentCount, ComponentResourceSize, ComponentTrueResourceSize
            try:
                # Based on sample: 122658,/Game/VFX/Water/Particles/PS_Water_Splashes.PS_Water_Splashes,432,2376,40734,6,79116,38382
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
                        "ComponentCount": comp_count,
                        "ComponentResourceSize": comp_res_size,
                        "ComponentTrueResourceSize": comp_true_res_size,
                    }
                )
            except (ValueError, IndexError):
                pass

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        stats = context.get("particle_stats", [])
        if not stats:
            return ""

        display_style = "block" if is_active else "none"

        # Pinned Total row
        total_row = None
        other_rows = []
        for s in stats:
            if s["Name"].lower() == "total":
                total_row = s
            else:
                other_rows.append(s)

        # Calculated totals (Python side)
        def get_calc(field):
            return sum(s[field] for s in other_rows)

        calc_stats = {
            "Size": get_calc("Size"),
            "System Size": get_calc("System Size"),
            "Module Size": get_calc("Module Size"),
            "Component Size": get_calc("Component Size"),
            "ComponentCount": get_calc("ComponentCount"),
            "ComponentResourceSize": get_calc("ComponentResourceSize"),
            "ComponentTrueResourceSize": get_calc("ComponentTrueResourceSize"),
        }
        calc_count = len(other_rows)

        thead = (
            "<thead><tr><th class='numeric'>#</th>"
            + "".join([f"<th>{h}</th>" for h in self.headers])
            + "</tr></thead>"
        )

        tbody = "<tbody>"

        # Helper to render a row
        def render_row(s, idx=""):
            row_html = f"<tr data-index='{idx}'>"
            row_html += f"<td class='numeric'>{idx}</td>"
            row_html += f"<td title='{s['Name']}' style='word-break: break-all;'>{s['Name']}</td>"
            row_html += f"<td class='numeric' data-val='{s['Size']}'>{format_bytes(s['Size'])}</td>"
            row_html += f"<td class='numeric' data-val='{s['System Size']}'>{format_bytes(s['System Size'])}</td>"
            row_html += f"<td class='numeric' data-val='{s['Module Size']}'>{format_bytes(s['Module Size'])}</td>"
            row_html += f"<td class='numeric' data-val='{s['Component Size']}'>{format_bytes(s['Component Size'])}</td>"
            row_html += f"<td class='numeric' data-val='{s['ComponentCount']}'>{s['ComponentCount']}</td>"
            row_html += f"<td class='numeric' data-val='{s['ComponentResourceSize']}'>{format_bytes(s['ComponentResourceSize'])}</td>"
            row_html += f"<td class='numeric' data-val='{s['ComponentTrueResourceSize']}'>{format_bytes(s['ComponentTrueResourceSize'])}</td>"
            row_html += "</tr>"
            return row_html

        for i, s in enumerate(other_rows):
            tbody += render_row(s, idx=i + 1)

        tbody += "</tbody>"

        def render_metrics_grid(prefix, data):
            # If data is from total_row or calc_stats
            is_reported = prefix == "Reported"
            color = "#ce9178" if is_reported else "#4ec9b0"
            if prefix == "Filtered": color = "var(--accent-color)"
            
            metrics = [
                ("Size", data.get("Size", 0)),
                ("System Size", data.get("System Size", 0)),
                ("Module Size", data.get("Module Size", 0)),
                ("Component Size", data.get("Component Size", 0)),
                ("ComponentCount", data.get("ComponentCount", 0)),
                ("ComponentResourceSize", data.get("ComponentResourceSize", 0)),
                ("ComponentTrueResourceSize", data.get("ComponentTrueResourceSize", 0)),
            ]
            
            html = f'<div style="display: grid; grid-template-columns: 1fr 1.2fr; gap: 4px 10px; font-size: 0.85em; text-align: left; margin-top: 10px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 10px;">'
            for label, val in metrics:
                display_val = f"<b>{format_bytes(val)}</b>" if label != "ComponentCount" else f"<b>{int(val)}</b>"
                # Add ID for filtered fields to update via JS
                # Convert label to lowercase and remove spaces for ID
                id_label = label.lower().replace(" ", "")
                id_attr = f' id="filt-{id_label}-{self.id}"' if prefix == "Filtered" else ""
                html += f'<div><span style="color: var(--text-muted); font-size: 0.8em; text-transform: uppercase;">{prefix} {label}:</span></div>'
                html += f'<div{id_attr} style="color: {color}; text-align: right;">{display_val}</div>'
            html += "</div>"
            return html

        reported_grid = render_metrics_grid("Reported", total_row if total_row else {})
        calculated_grid = render_metrics_grid("Calculated", calc_stats)
        filtered_grid = render_metrics_grid("Filtered", calc_stats) # Initial state is same as calculated

        return f"""
        <div id="{self.id}" class="tab-content" style="display: {display_style};">
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
                        <div style="font-size: 1.5em; font-weight: bold; color: #4ec9b0;">{format_bytes(calc_stats['Size'])}</div>
                        {calculated_grid}
                    </div>

                    <!-- Card 3: Filtered Total -->
                    <div class="analytics-card" style="flex: 1; min-width: 250px; background: rgba(59, 130, 246, 0.08); padding: 15px; border-radius: 6px; border: 1px solid var(--accent-color); text-align: center;">
                        <h4 style="margin: 0 0 10px 0; color: var(--accent-color); font-size: 0.8em; text-transform: uppercase;">Filtered Total</h4>
                        <div id="filt-main-val-{self.id}" style="font-size: 1.5em; font-weight: bold; color: var(--accent-color);">{format_bytes(calc_stats['Size'])}</div>
                        {filtered_grid}
                        <div style="margin-top: 5px; font-size: 0.8em; color: var(--text-muted); border-top: 1px solid rgba(255,255,255,0.05); padding-top: 5px;">
                            Items Visible: <b id="filt-items-{self.id}" style="color: var(--accent-color);">{calc_count}</b>
                        </div>
                    </div>
                </div>
            </div>

            <div class="search-container" data-no-reset="true">
                <input type="text" id="srch-{self.id}" placeholder="Search particle systems..." onkeyup="filterParticleTable(this.value)">
                <span style="font-size: 10px; color: #666; font-weight: 600; text-transform: uppercase; margin-left: 10px;">Sort By:</span>
                <button class="action-btn active-sub" onclick="resetParticleView()" style="height: 38px;">Alpha Order</button>
            </div>

            <div class="table-container">
                <table id="tbl-{self.id}">
                    {thead}
                    {tbody}
                </table>
            </div>

            <script>
                function formatParticleSize(bytes) {{
                    if (bytes >= 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(2) + " MB";
                    if (bytes >= 1024) return (bytes / 1024.0).toFixed(2) + " KB";
                    return bytes.toFixed(2) + " B";
                }}

                function updateParticleAggregates() {{
                    const table = document.getElementById('tbl-{self.id}');
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

                    document.getElementById('filt-items-{self.id}').innerText = itemsVisible;
                    document.getElementById('filt-main-val-{self.id}').innerText = formatParticleSize(sums.size);
                    
                    document.getElementById('filt-size-{self.id}').innerHTML = "<b>" + formatParticleSize(sums.size) + "</b>";
                    document.getElementById('filt-systemsize-{self.id}').innerHTML = "<b>" + formatParticleSize(sums.systemsize) + "</b>";
                    document.getElementById('filt-modulesize-{self.id}').innerHTML = "<b>" + formatParticleSize(sums.modulesize) + "</b>";
                    document.getElementById('filt-componentsize-{self.id}').innerHTML = "<b>" + formatParticleSize(sums.componentsize) + "</b>";
                    document.getElementById('filt-componentcount-{self.id}').innerHTML = "<b>" + sums.componentcount + "</b>";
                    document.getElementById('filt-componentresourcesize-{self.id}').innerHTML = "<b>" + formatParticleSize(sums.componentresourcesize) + "</b>";
                    document.getElementById('filt-componenttrueresourcesize-{self.id}').innerHTML = "<b>" + formatParticleSize(sums.componenttrueresourcesize) + "</b>";
                }}

                function filterParticleTable(term) {{
                    // Use index 0 because filterTable shifts by 1 if it finds a '#' column. 
                    // '#' is at index 0, so 'Name' is at data index 0 (actual index 1).
                    filterTable('tbl-{self.id}', 0, term);
                    updateParticleAggregates();
                }}
                
                function resetParticleView() {{
                    const searchInput = document.getElementById('srch-{self.id}');
                    if (searchInput) {{
                        searchInput.value = '';
                        filterParticleTable('');
                    }}
                    
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
                        
                        // Clear header arrows
                        table.querySelectorAll('th').forEach(th => {{
                            th.classList.remove('sort-asc', 'sort-desc');
                            th.removeAttribute('data-asc');
                        }});
                    }}
                }}

                // Wait for high-level UI to be ready
                setTimeout(updateParticleAggregates, 100);
            </script>
        </div>
        """


