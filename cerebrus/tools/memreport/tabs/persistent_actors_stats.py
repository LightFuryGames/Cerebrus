import re
import uuid
from typing import Any, Dict, List
from . import ReportTab


class PersistentActorsStatsTab(ReportTab):
    def __init__(self):
        super().__init__("Persistent Level Actors Stats", "persistent-actors-stats")
        self.total_spawned = 0
        self.actors = []
        self.parsing_actors = False

    def should_handle(self, line: str) -> bool:
        return 'MemReport: Begin command "ListSpawnedActors"' in line or "Listing spawned actors in persistent level:" in line

    def parse(self, line: str, context: Dict[str, Any]) -> None:
        # Ensure context storage exists
        if "persistent_actors" not in context:
            context["persistent_actors"] = []
        if "total_persistent_actors" not in context:
            context["total_persistent_actors"] = 0

        raw_line = line.strip()

        if "MemReport: Begin command \"ListSpawnedActors\"" in raw_line:
            self.parsing_actors = True
            return

        if "Listing spawned actors in persistent level:" in raw_line:
            self.parsing_actors = True
            return

        if not self.parsing_actors:
            return

        if raw_line.startswith("Total:"):
            match = re.search(r"Total:\s*(\d+)", raw_line)
            if match:
                self.total_spawned = int(match.group(1))
                context["total_persistent_actors"] = self.total_spawned
            return

        if "TimeUnseen,TimeAlive,Distance,Class,Name,Owner" in raw_line or not raw_line:
            return

        # Check for end of section (another command or header)
        if "MemReport:" in raw_line and "Begin command \"ListSpawnedActors\"" not in raw_line:
            self.parsing_actors = False
            return

        parts = [p.strip() for p in raw_line.split(",")]
        if len(parts) >= 6:
            try:
                # NOTE: Unreal MemReport headers say 'TimeUnseen, TimeAlive' but the data 
                # actually provides 'TimeAlive, TimeUnseen'. We swap them here for correctness.
                actor = {
                    "time_alive": float(parts[0]),
                    "time_unseen": float(parts[1]),
                    "distance": parts[2],
                    "class": parts[3],
                    "name": parts[4],
                    "owner": parts[5]
                }
                context["persistent_actors"].append(actor)
                # Sync local actors as well just in case
                self.actors = context["persistent_actors"]
            except ValueError:
                pass

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        reported_total = context.get("total_persistent_actors", self.total_spawned)
        actors = context.get("persistent_actors", self.actors)
        listed_count = len(actors)
        
        # Calculate unique entities theory
        all_names = {a['name'] for a in actors}
        all_owners = {a['owner'] for a in actors}
        external_owners = {o for o in all_owners if o not in all_names and o.lower() != 'none'}
        actual_total_found = len(all_names) + len(external_owners)

        active_cls = " active" if is_active else ""
        safe_id = self.id.replace("-", "_")
        
        # Table Headers (Unseen and Alive are in Seconds since Level Load)
        headers = ["#", "Class", "Name", "Owner", "Distance", "Time Alive (s)", "Time Unseen (s)", "% Unseen"]
        
        # 1. Flat List Body
        flat_tbody = ""
        for actor in actors:
            unseen = actor['time_unseen']
            alive = actor['time_alive']
            pct = (unseen / alive * 100.0) if alive > 0 else 0
            if pct > 100: pct = 100.0
            
            flat_tbody += f"""
            <tr data-unseen="{unseen}" data-alive="{alive}" data-pct="{pct}">
                <td class="count-cell"></td>
                <td>{actor['class']}</td>
                <td class="name-cell" title="{actor['name']}">{actor['name']}</td>
                <td>{actor['owner']}</td>
                <td class="numeric">{actor['distance']}</td>
                <td class="numeric">{alive:.2f}</td>
                <td class="numeric">{unseen:.2f}</td>
                <td class="numeric">{pct:.1f}%</td>
            </tr>
            """

        # 2. Hierarchy View Body
        name_to_actor = {a['name']: a for a in actors}
        children_map = {}
        roots = []
        for a in actors:
            owner = a['owner']
            if owner in name_to_actor:
                children_map.setdefault(owner, []).append(a)
            else:
                roots.append(a)

        def render_tree_node(actor, depth=0):
            unseen = actor['time_unseen']
            alive = actor['time_alive']
            dist = actor['distance']
            pct = (unseen / alive * 100.0) if alive > 0 else 0
            if pct > 100: pct = 100.0
            
            my_children = children_map.get(actor['name'], [])
            has_children = len(my_children) > 0
            indent = depth * 20
            
            node_html = f"""
            <div class="tree-node-wrapper" {"data-expanded='true'" if has_children else ""}>
                <div class="tree-row" data-unseen="{unseen}" data-alive="{alive}" data-pct="{pct}">
                    <div class="tree-cell name-col">
                        <div style="width: {indent}px; flex-shrink: 0;"></div>
                        <span class="tree-toggle-icon" onclick="toggleTreeNode_{safe_id}(this)">{'▼' if has_children else '•'}</span>
                        <span class="actor-name" title="{actor['name']}">{actor['name']}</span>
                    </div>
                    <div class="tree-cell class-col">{actor['class']}</div>
                    <div class="tree-cell numeric-col">{dist}</div>
                    <div class="tree-cell numeric-col">{alive:.1f}</div>
                    <div class="tree-cell numeric-col">{unseen:.1f}</div>
                    <div class="tree-cell numeric-col">{pct:.1f}%</div>
                </div>
            """
            if has_children:
                node_html += '<div class="tree-children-container">'
                for child in sorted(my_children, key=lambda x: x['name']):
                    node_html += render_tree_node(child, depth + 1)
                node_html += '</div>'
            node_html += '</div>'
            return node_html

        tree_html = ""
        for root in sorted(roots, key=lambda x: (x['owner'], x['name'])):
            tree_html += render_tree_node(root)

        html = f"""
        <style>
            .persistent-actors-analytics {{
                display: flex;
                gap: 12px;
                margin-bottom: 20px;
                flex-wrap: wrap;
            }}
            .analytics-card {{
                background: rgba(255,255,255,0.05);
                padding: 10px;
                border-radius: 8px;
                flex: 1;
                min-width: 150px;
                text-align: center;
                border: 1px solid var(--border-color);
            }}
            .analytics-label {{
                font-size: 10px;
                text-transform: uppercase;
                color: var(--text-muted);
                margin-bottom: 4px;
            }}
            .analytics-value {{
                font-size: 18px;
                font-weight: bold;
                color: var(--accent-color);
            }}
            .view-selector {{
                display: flex;
                gap: 10px;
                margin-bottom: 15px;
                align-items: center;
            }}
            .filter-container {{
                background: rgba(0,0,0,0.2);
                padding: 15px;
                border-radius: 6px;
                margin-bottom: 20px;
                display: flex;
                flex-direction: column;
                gap: 12px;
            }}
            .slider-wrapper {{
                display: flex;
                align-items: center;
                gap: 15px;
            }}
            .slider-wrapper label {{ min-width: 180px; font-size: 13px; }}
            .slider-wrapper input {{ flex: 1; height: 6px; cursor: pointer; }}
            
            .highlight-red-row {{
                background: rgba(255, 68, 68, 0.1) !important;
                box-shadow: inset 0 0 0 1px rgba(255, 68, 68, 0.3) !important;
            }}
            .table-container tbody tr.highlight-red-row td {{
                border-top: 1px solid rgba(255, 68, 68, 0.3) !important;
                border-bottom: 1px solid rgba(255, 68, 68, 0.3) !important;
                background: transparent !important;
            }}

            /* Tree Styles */
            .tree-view-wrapper {{
                background: rgba(0,0,0,0.2);
                border: 1px solid var(--border-color);
                border-radius: 4px;
                font-family: 'Consolas', monospace;
                font-size: 12px;
            }}
            .tree-header-row {{
                display: flex;
                background: var(--header-bg);
                font-weight: bold;
                padding: 10px;
                border-bottom: 1px solid var(--border-color);
            }}
            .tree-row {{
                display: flex;
                padding: 4px 10px;
                border-bottom: 1px solid rgba(255,255,255,0.02);
                align-items: center;
            }}
            .tree-row:hover {{ background: var(--hover-bg); }}
            
            /* Column Alignment */
            .tree-cell {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; padding: 0 5px; }}
            .name-col {{ flex: 1; min-width: 250px; display: flex; align-items: center; }}
            .class-col {{ flex: 0.8; min-width: 150px; color: var(--text-muted); font-size: 11px; }}
            .numeric-col {{ width: 85px; text-align: right; flex-shrink: 0; }}
            
            .tree-toggle-icon {{ width: 20px; color: var(--accent-color); cursor: pointer; display: inline-block; font-size: 12px; text-align: center; }}
            .actor-name {{ color: #4cd137; margin-right: 5px; }}
            
            .child-collapsed .tree-children-container {{ display: none; }}
            
            .info-zone {{ display: flex; flex-direction: column; gap: 8px; margin-bottom: 15px; }}
            .discrepancy-warning, .world-info {{
                font-size: 11px;
                padding: 8px 12px;
                border-radius: 2px;
                border-left: 3px solid;
            }}
            .discrepancy-warning {{
                color: #ffb74d; background: rgba(255, 183, 77, 0.1); border-color: #ffb74d;
            }}
            .world-info {{
                color: #3b82f6; background: rgba(59, 130, 246, 0.1); border-color: #3b82f6;
            }}
        </style>

        <div id="{self.id}" class="tab-content{active_cls}">
            <h2>Persistent Level Actors Statistics</h2>
            
            <div class="persistent-actors-analytics">
                <div class="analytics-card" title="Actor count reported in MemReport summary header">
                    <div class="analytics-label">Unreal Reported Total</div>
                    <div class="analytics-value">{reported_total}</div>
                </div>
                <div class="analytics-card" title="Actual actors found in detailed list + implied unique owners">
                    <div class="analytics-label">Actual Total Found</div>
                    <div class="analytics-value" style="color: #3b82f6;">{actual_total_found}</div>
                </div>
                <div class="analytics-card" title="Actors meeting the current Unseen Threshold">
                    <div class="analytics-label">Threshold Met</div>
                    <div class="analytics-value" style="color: #ff4444;" id="ra-threshold-{self.id}">0</div>
                </div>
                <div class="analytics-card" title="Items currently visible in the active view">
                    <div class="analytics-label">Visible View Items</div>
                    <div class="analytics-value" style="color: #4cd137;" id="ra-visible-{self.id}">0</div>
                </div>
            </div>

            <div class="info-zone">
                <div class="world-info">
                    <b>WorldSettings Context:</b> <code>WorldSettings</code> is an internal actor representing the Persistent Level itself. 
                    It is always present, even in empty levels, as the root of the world state and global level settings.
                </div>
                <div class="discrepancy-warning">
                    <b>Count Mismatch:</b> Unreal's summary reports <b>{reported_total}</b> spawned actors, but the detailed list contains only <b>{listed_count}</b> entries.
                    Even including the <b>{len(external_owners)}</b> implied external owners found during scan (Total: <b>{actual_total_found}</b>), 
                    the detailed data dump is still missing stats for <b>{reported_total - actual_total_found}</b> actors.
                </div>
            </div>

            <div class="filter-container">
                <div class="view-selector">
                    <button class="action-btn active-sub" id="btn-flat-{self.id}" onclick="toggleView_{safe_id}('flat')">Flat List</button>
                    <button class="action-btn" id="btn-tree-{self.id}" onclick="toggleView_{safe_id}('tree')">Hierarchy View</button>
                    
                    <div id="tree-controls-{self.id}" style="display: none; margin-left: auto; gap: 5px;">
                        <button class="action-btn" onclick="expandAllTree_{safe_id}()">Expand All</button>
                        <button class="action-btn" onclick="collapseAllTree_{safe_id}()">Collapse All</button>
                    </div>
                </div>

                <div class="slider-wrapper">
                    <label for="slider-{self.id}">Unseen Threshold (% of Alive Time):</label>
                    <input type="range" id="slider-{self.id}" min="0" max="100" value="70" oninput="updateActors_{safe_id}()">
                    <span class="slider-value" id="val-{self.id}">70%</span>
                </div>

                <div class="search-container" data-no-reset="true" style="margin-top: 0; background: transparent; padding: 0; display: flex; gap: 10px; align-items: center;">
                    <input type="text" id="srch-{self.id}" placeholder="Search actors..." onkeyup="updateActors_{safe_id}()" style="flex: 1;">
                    <button class="action-btn" onclick="resetView_{safe_id}()">Default View</button>
                </div>
            </div>

            <div id="view-flat-{self.id}" class="table-container">
                <table id="tbl-{self.id}">
                    <thead>
                        <tr>{"".join([f"<th class='{'numeric' if 'numeric' in h.lower() or '%' in h else ''}'>{h}</th>" for h in headers])}</tr>
                    </thead>
                    <tbody>
                        {flat_tbody}
                    </tbody>
                </table>
            </div>

            <div id="view-tree-{self.id}" class="tree-view-wrapper" style="display: none;">
                <div class="tree-header-row">
                    <div class="tree-cell name-col">Name / Local Hierarchy</div>
                    <div class="tree-cell class-col">Class</div>
                    <div class="tree-cell numeric-col">Distance</div>
                    <div class="tree-cell numeric-col">Alive (s)</div>
                    <div class="tree-cell numeric-col">Unseen (s)</div>
                    <div class="tree-cell numeric-col">% Unseen</div>
                </div>
                <div class="tree-body-container">
                    {tree_html}
                </div>
            </div>

            <script>
                function toggleTreeNode_{safe_id}(icon) {{
                    const wrapper = icon.closest('.tree-node-wrapper');
                    if (wrapper) {{
                        wrapper.classList.toggle('child-collapsed');
                        icon.innerText = wrapper.classList.contains('child-collapsed') ? '▶' : '▼';
                    }}
                }}

                function expandAllTree_{safe_id}() {{
                    document.querySelectorAll('#{self.id} .tree-node-wrapper').forEach(n => {{
                        n.classList.remove('child-collapsed');
                        const icon = n.querySelector('.tree-toggle-icon');
                        if (icon && icon.innerText !== '•') icon.innerText = '▼';
                    }});
                }}

                function collapseAllTree_{safe_id}() {{
                    document.querySelectorAll('#{self.id} .tree-node-wrapper').forEach(n => {{
                        n.classList.add('child-collapsed');
                        const icon = n.querySelector('.tree-toggle-icon');
                        if (icon && icon.innerText !== '•') icon.innerText = '▶';
                    }});
                }}

                function toggleView_{safe_id}(mode) {{
                    const flat = document.getElementById('view-flat-{self.id}');
                    const tree = document.getElementById('view-tree-{self.id}');
                    const btnFlat = document.getElementById('btn-flat-{self.id}');
                    const btnTree = document.getElementById('btn-tree-{self.id}');
                    const treeCtrls = document.getElementById('tree-controls-{self.id}');

                    if (mode === 'flat') {{
                        flat.style.display = '';
                        tree.style.display = 'none';
                        treeCtrls.style.display = 'none';
                        btnFlat.classList.add('active-sub');
                        btnTree.classList.remove('active-sub');
                    }} else {{
                        flat.style.display = 'none';
                        tree.style.display = 'block';
                        treeCtrls.style.display = 'flex';
                        btnFlat.classList.remove('active-sub');
                        btnTree.classList.add('active-sub');
                    }}
                    updateActors_{safe_id}();
                }}

                function updateActors_{safe_id}() {{
                    const thresholdVal = document.getElementById('slider-{self.id}').value;
                    document.getElementById('val-{self.id}').innerText = thresholdVal + '%';

                    const threshold = parseFloat(thresholdVal) / 100.0;
                    const searchTerm = document.getElementById('srch-{self.id}').value.toLowerCase();
                    
                    const flatActive = document.getElementById('view-flat-{self.id}').style.display !== 'none';
                    const targetSelector = flatActive ? '.table-container tbody tr' : '.tree-row';
                    const items = document.querySelectorAll('#{self.id} ' + targetSelector);
                    
                    let thresholdCount = 0;
                    let visibleCount = 0;
                    let visibleIndex = 1;

                    items.forEach(item => {{
                        const unseen = parseFloat(item.getAttribute('data-unseen')) || 0;
                        const alive = parseFloat(item.getAttribute('data-alive')) || 0;
                        const text = item.innerText.toLowerCase();
                        
                        const isOverThreshold = (threshold === 0) || (alive > 0 && unseen >= (alive * threshold) - 0.001);
                        const matchesSearch = searchTerm === "" || text.includes(searchTerm);
                        
                        if (isOverThreshold) {{
                            item.classList.add('highlight-red-row');
                            thresholdCount++;
                        }} else {{
                            item.classList.remove('highlight-red-row');
                        }}

                        if (matchesSearch && isOverThreshold) {{
                            item.style.display = '';
                            const countCell = item.querySelector('.count-cell');
                            if (countCell) countCell.innerText = visibleIndex++;
                            visibleCount++;
                        }} else {{
                            item.style.display = 'none';
                        }}
                    }});

                    document.getElementById('ra-threshold-{self.id}').innerText = thresholdCount;
                    document.getElementById('ra-visible-{self.id}').innerText = visibleCount;
                }}

                function resetView_{safe_id}() {{
                    document.getElementById('slider-{self.id}').value = 70;
                    document.getElementById('srch-{self.id}').value = '';
                    updateActors_{safe_id}();
                }}

                document.addEventListener('DOMContentLoaded', () => {{
                    updateActors_{safe_id}();
                }});
            </script>
        </div>
        """
        return html
