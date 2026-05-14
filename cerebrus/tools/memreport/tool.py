import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import click

from .tabs.class_stats import ClassStatsTab
from .tabs.config_cache_memory_stats import ConfigCacheMemoryStatsTab
from .tabs.detailed_lists import DetailedListsTab
from .tabs.device_info import DeviceInfoTab
from .tabs.level_stats import LevelLoadingStatsTab
from .tabs.memory_stats import MemoryStatsTab
from .tabs.obj_summary import ObjectSummaryTab
from .tabs.particle_stats import ParticleSystemsTab
from .tabs.persistent_actors_stats import PersistentActorsStatsTab
from .tabs.render_target_pool import RenderTargetPoolTab
from .tabs.rhi_stats import RhiMemoryTab, RhiResourceMemoryTab
from .tabs.texture_stats import TextureStatsTab
from .template import HTML_TEMPLATE
from .utils import format_seconds_to_hms


# --- Generic Tab Handler for Unclaimed Commands ---
class GenericTableTab:
    def __init__(self, command_name: str):
        self.command_name = command_name
        self.id = (
            "gen-"
            + command_name.replace(" ", "-").replace(".", "-").replace("=", "-").lower()
        )
        self.headers: List[str] = []
        self.rows: List[List[str]] = []
        self.raw_lines: List[str] = []  # For empty/unparseable content
        self.is_empty = False

    def parse(self, line: str):
        if not line.strip():
            return

        # Heuristic: Check for Header Line (Caps, spaced)
        # e.g. "Class    Count    NumKB"
        if not self.headers and not self.rows:
            # Assume first non-empty line is header if it looks like one?
            # Or just store as raw first?
            # Let's try to detect headers:
            if "    " in line or "\t" in line:
                self.headers = [x.strip() for x in line.split("  ") if x.strip()]
                return

        if self.headers:
            # Parse row
            # Split by 2+ spaces
            cols = [x.strip() for x in line.split("  ") if x.strip()]
            # If cols count mismatches significantly, might not be a table row?
            # Basic fallback
            if len(cols) >= len(self.headers) - 2:  # Allow some leniency
                self.rows.append(cols)
            else:
                self.raw_lines.append(line)
        else:
            self.raw_lines.append(line)

    def render(self, context: Dict[str, Any], is_active: bool = False) -> str:
        # If marked empty
        if self.is_empty:
            return ""

        warning_html = ""
        body_html = ""

        # Case 1: Purely Empty
        if not self.rows and not self.raw_lines:
            warning_html = f"""
             <div class="analytics-wrapper" style="background: var(--row-even); padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid var(--border-color);">
                 <div class="alert alert-warning">
                    <div class="alert-icon">⚠️</div>
                    <div class="alert-content">
                        <strong>WARNING:</strong> This section ({self.command_name}) contains no data in the report.
                    </div>
                 </div>
             </div>
             """
        # Case 2: No rows but have raw lines (Unparsed)
        elif not self.rows and self.raw_lines:
            warning_html = f"""
             <div class="analytics-wrapper" style="background: var(--row-even); padding: 20px; border-radius: 8px; margin-bottom: 20px; border: 1px solid var(--border-color);">
                <div class="alert alert-warning">
                    <div class="alert-icon">⚠️</div>
                    <div class="alert-content">
                        <strong>WARNING:</strong> This section ({self.command_name}) could not be parsed into a table.
                    </div>
                </div>
                <div class="alert alert-danger" style="margin-top: 15px;">
                    <div class="alert-icon">🛑</div>
                    <div class="alert-content">
                        <strong>FATAL:</strong> Please Provide Feedback to the Tech & Tools team to request a parsing update for this section with a copy of this HTML file or a new raw .memreport file using the Cerebrus Help -> Provide Feedback in the top Menu toolbar.
                    </div>
                </div>
             </div>
             """
            raw_content = "\n".join(self.raw_lines)
            body_html = f'<hr class="section-divider"><h4>Raw Data</h4><div class="table-container"><pre style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 8px; overflow-x: auto;">{raw_content}</pre></div>'
        # Case 3: Parsed Rows
        else:
            thead = (
                "<thead><tr>"
                + "".join([f"<th>{h}</th>" for h in self.headers])
                + "</tr></thead>"
            )
            tbody = "<tbody>"
            for row in self.rows:
                tbody += "<tr>" + "".join([f"<td>{c}</td>" for c in row]) + "</tr>"
            tbody += "</tbody>"
            body_html = f"""
             <div class="table-container">
                <table id="tbl-{self.id}">
                    {thead}
                    {tbody}
                </table>
             </div>
             """

        return f"""
        <div id="{self.id}" class="tab-content">
             <h3>{self.command_name}</h3>
             {warning_html}
             <div class="search-container">
                <input type="text" placeholder="Search {self.command_name}..." onkeyup="filterTable('tbl-{self.id}', 0, this.value)">
            </div>
            {body_html}
        </div>
        """
        # Note: Reduced logic above to fit generic table structure simpler.
        # Correct logic:
        if self.rows:
            thead = (
                "<thead><tr>"
                + "".join([f"<th>{h}</th>" for h in self.headers])
                + "</tr></thead>"
            )
            tbody = "<tbody>"
            for row in self.rows:
                tbody += "<tr>" + "".join([f"<td>{c}</td>" for c in row]) + "</tr>"
            tbody += "</tbody>"
            content = f'<table id="tbl-{self.id}">{thead}{tbody}</table>'
        elif not self.rows and self.raw_lines:
            content = warning_html + "<pre>" + "\n".join(self.raw_lines) + "</pre>"

        return f"""
        <div id="{self.id}" class="tab-content">
             <h3>{self.command_name}</h3>
             <div class="search-container">
                <input type="text" placeholder="Search {self.command_name}..." onkeyup="filterTable('tbl-{self.id}', 0, this.value)">
            </div>
             <div class="table-container">
             {content}
             </div>
        </div>
        """


def parse_memreport(file_path: Path) -> Dict[str, Any]:
    context: Dict[str, Any] = {
        "metadata": {},
        "generic_tabs": {},  # command_name -> GenericTableTab
        "command_order": [],  # List of command names in order
        "raw_memreport": "",
    }

    # Tabs that handle parsing
    # Order matters!
    # Order matters!
    tabs = [
        DeviceInfoTab(),
        MemoryStatsTab(),
        RhiMemoryTab(),
        RhiResourceMemoryTab(),
        TextureStatsTab(),
        ParticleSystemsTab(),
        LevelLoadingStatsTab(),
        PersistentActorsStatsTab(),
        ClassStatsTab(),
        DetailedListsTab(),
        ObjectSummaryTab(),
        RenderTargetPoolTab(),
        ConfigCacheMemoryStatsTab(),
    ]
    context["tabs"] = tabs

    # 1. Read File with Robust Encoding
    content = ""
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            content = file_path.read_text(encoding="utf-16")
        except UnicodeDecodeError:
            # Fallback to binary replace
            with open(file_path, "rb") as f:
                content = f.read().decode("utf-8", errors="replace")

    lines = content.splitlines()
    context["raw_memreport"] = content
    line_idx = 0
    total_lines = len(lines)

    # 2. Parse Header/Metadata (until first Begin command or empty block)
    while line_idx < total_lines:
        line = lines[line_idx].strip()
        if "MemReport: Begin command" in line:
            break

        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()

            if key == "Time Since Boot":
                val = format_seconds_to_hms(val)

            if "PlayerController" in key:
                val = val.replace(" View Location", "<br>View Location")
                val = val.replace(" View Rotation", "<br>View Rotation")

            context["metadata"][key] = val

        line_idx += 1

    # 3. Main Command Loop
    current_tab = None
    generic_tab = None

    while line_idx < total_lines:
        line = lines[line_idx].strip()
        raw_line = lines[line_idx]  # Keep indentation

        # 1. Check for Tab Switch (Specialized Tabs Priority)
        # Check if any specialized tab wants to handle this line (Start Trigger)
        new_tab = None
        for tab in tabs:
            if tab.should_handle(line):
                new_tab = tab
                break

        if new_tab:
            current_tab = new_tab
            generic_tab = None  # Clear generic
            context.setdefault("active_tabs", set()).add(current_tab.id)

            # Allow tab to parse the trigger line itself (e.g. to extracting params)
            current_tab.parse(raw_line, context)

            # If this trigger IS a "Begin command", we should also record it in command_order?
            # Existing tabs logic didn't explicitly do this, but for consistency:
            if line.startswith("MemReport: Begin command"):
                cmd_name = (
                    line.split('"')[1]
                    if '"' in line
                    else line.replace("MemReport: Begin command", "").strip()
                )
                if cmd_name not in context["command_order"]:
                    context["command_order"].append(cmd_name)

            line_idx += 1
            continue

        # 2. Check for Generic Command Start (MemReport: Begin ...)
        # Only if NOT claimed by a specialized tab above
        if line.startswith("MemReport: Begin command"):
            # Extract Name
            cmd_name = (
                line.split('"')[1]
                if '"' in line
                else line.replace("MemReport: Begin command", "").strip()
            )

            # Skip "Mem FromReport" as it's redundant (covered by Memory Stats)
            if cmd_name == "Mem FromReport":
                context["command_order"].append(cmd_name)  # Keep in order or not?
                # User wants to remove the TAB. So we shouldn't create a generic tab.
                # But should we add to command_order? If we do, generating logic looks in context["generic_tabs"]
                # and won't find it, so it won't render. That works.
                # However, cleaner to just skip entirely.
                line_idx += 1
                continue

            context["command_order"].append(cmd_name)

            # Start Generic Tab
            generic_tab = GenericTableTab(cmd_name)
            context["generic_tabs"][cmd_name] = generic_tab
            current_tab = None  # Clear specialized

            line_idx += 1
            continue

        # 3. Check for Command End
        if line.startswith("MemReport: End command"):
            current_tab = None
            if generic_tab:
                # Check if empty
                if not generic_tab.rows and not generic_tab.raw_lines:
                    generic_tab.is_empty = True
                generic_tab = None
            line_idx += 1
            continue

        # 4. Delegate Parsing
        if current_tab:
            current_tab.parse(raw_line, context)
        elif generic_tab:
            generic_tab.parse(raw_line)

        line_idx += 1

    return context


def generate_html_report(context: Dict[str, Any], output_path: Path):
    # Assemble Tabs
    all_tabs = context.get("tabs", [])

    # Grouping Helper
    def get_group(t_id, t_name):
        if t_id in ["device-info", "memory-stats", "level-loading-stats"]:
            return "Overview"

        # RHI Matches
        if t_id in ["rhi-memory-stats", "rhi-resource-memory", "render-target-pool"]:
            return "RHI & Rendering"

        # specified classes move to Objects & Actors
        requested_classes = [
            "Level",
            "SkeletalMesh",
            "SoundWave",
            "StaticMesh",
            "StaticMeshComponent",
        ]
        is_requested = any(c in t_name for c in requested_classes)

        merged_grp = "Assets, Objects & Actors"
        # Assets Matches
        if t_id in ["texture-stats", "particle-systems"]:
            return merged_grp
        if t_id.startswith("list-"):
            if "Object List" in t_name or "All Objects" in t_name or is_requested:
                return merged_grp
            return merged_grp

        # Objects & Actors Matches
        if (
            t_id in ["object-summary", "persistent-actors-stats", "class-stats-generic"]
            or t_id.startswith("class-")
            or is_requested
        ):
            return merged_grp

        if t_id.startswith("config-cache"):
            return "Config"

        # Generics / Raw
        if t_id == "raw-mem-report":
            return "Raw Data"
        lower_name = t_name.lower()
        if "dump" in lower_name or "raw" in lower_name:
            return "Raw Data"

        return "Uncategorized"

    tab_contents_html = ""
    collected_tabs = []  # {id, name, group}

    # 1. Specialized Tabs
    for tab in all_tabs:
        # Render content (inactive by default, JS handles activation)
        content = tab.render(context, is_active=False)
        tab_contents_html += content

        # Collect Definitions
        if hasattr(tab, "get_tab_info"):
            infos = tab.get_tab_info()
            for info in infos:
                grp = get_group(info["id"], info["name"])
                collected_tabs.append(
                    {"id": info["id"], "name": info["name"], "group": grp}
                )
        else:
            # Fallback if get_tab_info missing (shouldn't happen with base class update)
            grp = get_group(tab.id, tab.name)
            collected_tabs.append({"id": tab.id, "name": tab.name, "group": grp})

    # 2. Generic Tabs
    gen_tabs = context.get("generic_tabs", {})
    ordered_cmds = context.get("command_order", [])

    for cmd in ordered_cmds:
        if cmd in gen_tabs:
            tab = gen_tabs[cmd]
            if tab.is_empty:
                continue

            # Render
            t_content = tab.render(context)
            tab_contents_html += t_content

            grp = get_group(tab.id, tab.command_name)
            collected_tabs.append(
                {"id": tab.id, "name": tab.command_name, "group": grp}
            )

    # 3. Raw Mem Report Tab
    import html

    raw_content_escaped = html.escape(context.get("raw_memreport", "No Raw Data"))
    raw_tab_id = "raw-mem-report"
    tab_contents_html += f"""
    <div id="{raw_tab_id}" class="tab-content">
        <h3>Raw Mem Report</h3>
        <div class="table-container">
            <pre style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 8px; overflow-x: auto; font-family: monospace; font-size: 12px;">{raw_content_escaped}</pre>
        </div>
    </div>
    """
    collected_tabs.append(
        {"id": raw_tab_id, "name": "Raw Mem Report", "group": "Raw Data"}
    )

    # Build Grouped Sidebar/Nav
    # Combine Assets and Objects/Actors to save vertical space
    group_order = [
        "Overview",
        "Config",
        "Assets, Objects & Actors",
        "RHI & Rendering",
        "Raw Data",
        "Uncategorized",
    ]
    final_groups: Dict[str, List[Dict[str, str]]] = {k: [] for k in group_order}

    # Bucket tabs
    for t in collected_tabs:
        g = t["group"]
        if g not in final_groups:
            final_groups[g] = []  # Handle unknown groups safely
        final_groups[g].append(t)

    tab_buttons_html = """
    <div class="tabs-grid">
    <style>
        .tabs-grid {
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            width: 100%;
            margin-bottom: 0px;
        }
        .tab-group { 
            display: flex;
            flex-direction: row;
            align-items: stretch;
            flex-wrap: wrap;
            padding: 4px;
            background: rgba(255,255,255,0.03);
            border-radius: 10px;
            border: 1px solid var(--border-color);
            transition: all 0.2s ease;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        body.light-mode .tab-group {
            background: #ffffff;
            border-color: #cbd5e1;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }

        /* Pyramid / Hopskip Logic via Flex Basis */
        .tab-group.size-lg { flex: 1 1 100%; }
        .tab-group.size-md { flex: 1 1 calc(50% - 6px); }
        .tab-group.size-sm { flex: 1 1 calc(33.33% - 8px); }
        
        .tab-group:hover {
            border-color: var(--accent-color);
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
        }

        .group-title { 
            font-size: 10px; 
            text-transform: uppercase; 
            letter-spacing: 1.2px; 
            color: var(--text-muted);
            font-weight: 800;
            margin: 4px 12px 4px 8px;
            padding-right: 12px;
            border-right: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            white-space: nowrap;
        }
        
        .group-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            flex: 1;
            padding: 4px;
        }

        .tab-btn { 
            margin: 0 !important; 
            font-size: 12px !important;
            padding: 6px 14px !important;
            border-radius: 6px !important;
            border: 1px solid transparent !important;
            background: transparent !important;
            color: var(--text-color) !important;
            opacity: 0.8 !important;
            font-weight: 500 !important;
            transition: all 0.2s ease !important;
        }

        .tab-btn:hover {
            opacity: 1 !important;
            background: rgba(255, 255, 255, 0.08) !important;
            border-color: rgba(255, 255, 255, 0.1) !important;
        }

        body.light-mode .tab-btn:hover {
            background: #f1f5f9 !important;
            border-color: #e2e8f0 !important;
        }

        .tab-btn.active {
            opacity: 1 !important;
            background: var(--accent-color) !important;
            color: white !important;
            border-color: var(--accent-color) !important;
            box-shadow: 0 2px 4px rgba(59, 130, 246, 0.4) !important;
            border-bottom: 2px solid var(--accent-color) !important;
        }
        
        /* Specific adjustments for Assets row which can be very busy */
        .tab-group.size-lg .tab-btn {
            font-size: 11px !important;
            padding: 5px 10px !important;
        }
    </style>
    """

    first_tab_id = None

    # Identify non-empty groups and their tab counts
    active_groups: List[Dict[str, Any]] = []
    for g_name in group_order:
        tabs = final_groups.get(g_name, [])
        if tabs:
            active_groups.append({"name": g_name, "tabs": tabs, "count": len(tabs)})

    # Sort by group_order to ensure Assets/Objects are at the bottom
    # We maintain the count but keep the user-defined order
    if active_groups:
        for i, g in enumerate(active_groups):
            # Pyramid: Small items on top, big merged group at the bottom
            if g["name"] == "Assets, Objects & Actors":
                size_class = "size-lg"
            elif i < 2:
                size_class = "size-md"
            else:
                size_class = "size-sm"

            tab_buttons_html += f'<div class="tab-group {size_class}"><div class="group-title">{g["name"]}</div><div class="group-buttons">'
            for t in g["tabs"]:
                if not first_tab_id:
                    first_tab_id = t["id"]
                tab_buttons_html += f'<button class="tab-btn" onclick="openTab(event, \'{t["id"]}\')">{t["name"]}</button>'
            tab_buttons_html += "</div></div>"

    tab_buttons_html += "</div>"  # Close tabs-grid

    # Inject a script to activate the Device Info tab by default
    tab_buttons_html += """
    <script>
        document.addEventListener('DOMContentLoaded', () => {
            // Priority 1: Specifically look for device-info
            let targetBtn = document.querySelector('button[onclick*="device-info"]');
            
            // Priority 2: Fallback to the very first tab button if device-info is missing
            if (!targetBtn) {
                targetBtn = document.querySelector('.tab-btn');
            }
            
            if (targetBtn) targetBtn.click();
        });
    </script>
    """

    metadata = context.get("metadata", {})
    metadata_json = json.dumps(metadata, indent=4)

    report_html = HTML_TEMPLATE.format(
        title=f"MemReport - {metadata.get('Device Name', 'Unknown')}",
        report_title="Memory Report",
        tab_buttons=tab_buttons_html,
        tab_contents=tab_contents_html,
        metadata_json=metadata_json,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_html)

    print(f"Report generated: {output_path}")


def process_memreport(
    input_file: Path,
    output_dir: Path,
    report_context: Dict[str, Any] | None = None,
    use_as_prefix_only: bool = False,
    output_name_prefix: str | None = None,
    open_report: bool = False,
):
    """Core logic for processing a memreport and generating HTML, separated from CLI."""
    if not input_file.exists():
        print(f"Error: File not found {input_file}")
        return None

    if report_context is None:
        print("Parsing memreport...")
        report_context = parse_memreport(input_file)

    output_dir.mkdir(parents=True, exist_ok=True)

    metadata = report_context.get("metadata", {})
    build_config = metadata.get("Build Configuration", "UnknownConfig")
    device_make = metadata.get("Device Make", "UnknownMake")
    device_model = metadata.get("Device Model", "UnknownModel")
    cl_number = metadata.get("Changelist", "UnknownCL")

    # Try to use existing Date from metadata, otherwise use current
    report_date_str = metadata.get("Date")
    if not report_date_str:
        report_date_str = datetime.now().strftime("%Y.%m.%d-%H.%M.%S")

    # Format: <Config>_<Device Make>_<Device Model>_<CL Number>_<Date and time>.html
    # Sanitize for filename
    def sanitize(s):
        return str(s).replace(" ", "").replace("/", "_").replace("\\", "_")

    if use_as_prefix_only:
        output_stem = input_file.stem
        if output_name_prefix:
            output_stem = f"{sanitize(output_name_prefix)}_{output_stem}"
        output_filename = f"{output_stem}.html"
    else:
        output_filename = f"{sanitize(build_config)}_{sanitize(device_make)}_{sanitize(device_model)}_{sanitize(cl_number)}_{sanitize(report_date_str)}.html"

    output_file = output_dir / output_filename

    # Versioning Logic: Check if file exists and append v1, v2, etc.
    if output_file.exists():
        version = 1
        while True:
            candidate_name = f"{output_file.stem}_v{version}{output_file.suffix}"
            candidate_file = output_dir / candidate_name
            if not candidate_file.exists():
                output_file = candidate_file
                break
            version += 1

    print(f"Generating HTML {output_file.name}...")
    generate_html_report(report_context, output_file)

    if open_report:
        import webbrowser

        webbrowser.open(f"file://{output_file.resolve()}")

    return output_file


@click.command(name="memreport_to_html")
@click.argument("input_path", type=click.Path(exists=True))
@click.option(
    "--output-dir", "-o", default="MemReports", help="Output directory for HTML reports"
)
@click.option(
    "--open-report/--no-open-report",
    default=False,
    help="Open the report in browser after generation",
)
@click.option(
    "--use-as-prefix-only", is_flag=True, help="Use the input filename as a prefix only"
)
def generate_html(
    input_path: str,
    output_dir: str,
    open_report: bool,
    use_as_prefix_only: bool,
):
    process_memreport(
        input_file=Path(input_path),
        output_dir=Path(output_dir),
        open_report=open_report,
        use_as_prefix_only=use_as_prefix_only,
    )


if __name__ == "__main__":
    generate_html()
