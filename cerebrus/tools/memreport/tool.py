import argparse
from pathlib import Path
from typing import Any, Dict, List
import sys

import click

from .tabs.detailed_lists import DetailedListsTab
from .tabs.device_info import DeviceInfoTab
from .tabs.memory_stats import MemoryStatsTab
from .tabs.obj_summary import ObjectSummaryTab
from .tabs.rhi_stats import RhiMemoryTab, RhiResourceMemoryTab
from .template import HTML_TEMPLATE
from .utils import format_seconds_to_hms


# --- Generic Tab Handler for Unclaimed Commands ---
class GenericTableTab:
    def __init__(self, command_name: str):
        self.command_name = command_name
        self.id = "gen-" + command_name.replace(" ", "-").replace(".", "-").replace("=", "-").lower()
        self.headers = []
        self.rows = []
        self.raw_lines = [] # For empty/unparseable content
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
            if len(cols) >= len(self.headers) - 2: # Allow some leniency
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
             <div class="alert alert-warning" style="display: flex; align-items: center; gap: 20px;">
                <div class="alert-icon">⚠️</div>
                <div class="alert-content">
                    <strong><u>WARNING</u></strong>: This section ({self.command_name}) contains no data in the report.
                </div>
             </div>
             """
        # Case 2: No rows but have raw lines (Unparsed)
        elif not self.rows and self.raw_lines:
             warning_html = f"""
             <div class="alert alert-warning" style="display: flex; align-items: center; gap: 20px; margin-bottom: 10px;">
                <div class="alert-icon">⚠️</div>
                <div class="alert-content">
                    <strong><u>WARNING</u></strong>: This section ({self.command_name}) could not be parsed into a table.
                </div>
             </div>
             <div class="alert alert-feedback" style="display: flex; align-items: center; gap: 20px;">
                <div class="alert-icon">🛑</div>
                <div class="alert-content" style="font-weight: 600;">
                    <strong><u>FATAL</u></strong> :- Please Provide Feedback to the Tech & Tools team to request a parsing update for this section with a copy of this HTML file or a new raw .memreport file using the Cerebrus Help -> Provide Feedback in the top Menu toolbar
                </div>
             </div>
             """
             body_html = f'<hr class="section-divider"><h4>Raw Data</h4><div class="table-container"><pre style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 8px; overflow-x: auto;">{"\n".join(self.raw_lines)}</pre></div>'
        # Case 3: Parsed Rows
        else:
             thead = "<thead><tr>" + "".join([f"<th>{h}</th>" for h in self.headers]) + "</tr></thead>"
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
             thead = "<thead><tr>" + "".join([f"<th>{h}</th>" for h in self.headers]) + "</tr></thead>"
             tbody = "<tbody>"
             for row in self.rows:
                 tbody += "<tr>" + "".join([f"<td>{c}</td>" for c in row]) + "</tr>"
             tbody += "</tbody>"
             content = f'<table id="tbl-{self.id}">{thead}{tbody}</table>'
        elif not self.rows and self.raw_lines:
             content = warning + "<pre>" + "\n".join(self.raw_lines) + "</pre>"

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
        "generic_tabs": {}, # command_name -> GenericTableTab
        "command_order": [], # List of command names in order
        "raw_memreport": ""
    }

    # Tabs that handle parsing
    # Order matters!
    tabs = [DeviceInfoTab(), MemoryStatsTab(), RhiMemoryTab(), RhiResourceMemoryTab(), DetailedListsTab(), ObjectSummaryTab()]

    # 1. Read File with Robust Encoding
    content = ""
    try:
        content = file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            content = file_path.read_text(encoding="utf-16")
        except UnicodeDecodeError:
            # Fallback to binary replace
             with open(file_path, 'rb') as f:
                 content = f.read().decode('utf-8', errors='replace')

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
        raw_line = lines[line_idx] # Keep indentation
        
        # 1. Check for Tab Switch (Specialized Tabs Priority)
        # Check if any specialized tab wants to handle this line (Start Trigger)
        new_tab = None
        for tab in tabs:
            if tab.should_handle(line):
                new_tab = tab
                break
        
        if new_tab:
            current_tab = new_tab
            generic_tab = None # Clear generic
            context.setdefault("active_tabs", set()).add(current_tab.id)
            
            # Allow tab to parse the trigger line itself (e.g. to extracting params)
            current_tab.parse(raw_line, context)
            
            # If this trigger IS a "Begin command", we should also record it in command_order?
            # Existing tabs logic didn't explicitly do this, but for consistency:
            if line.startswith("MemReport: Begin command"):
                cmd_name = line.split('"')[1] if '"' in line else line.replace("MemReport: Begin command", "").strip()
                if cmd_name not in context["command_order"]:
                    context["command_order"].append(cmd_name)
            
            line_idx += 1
            continue

        # 2. Check for Generic Command Start (MemReport: Begin ...)
        # Only if NOT claimed by a specialized tab above
        if line.startswith("MemReport: Begin command"):
            # Extract Name
            cmd_name = line.split('"')[1] if '"' in line else line.replace("MemReport: Begin command", "").strip()
            
            # Skip "Mem FromReport" as it's redundant (covered by Memory Stats)
            if cmd_name == "Mem FromReport":
                context["command_order"].append(cmd_name) # Keep in order or not? 
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
            current_tab = None # Clear specialized
            
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
    all_tabs = [
        DeviceInfoTab(),
        MemoryStatsTab(),
        RhiMemoryTab(),
        RhiResourceMemoryTab(),
        ObjectSummaryTab(),
        DetailedListsTab(),
    ]

    tab_buttons_html = ""
    tab_contents_html = ""

    # 1. Render Fixed Tabs
    for i, tab in enumerate(all_tabs):
        btns = tab.get_buttons(context)
        content = tab.render(context, is_active=(i == 0))
        
        tab_buttons_html += btns
        tab_contents_html += content

    # 2. Render Generic Tabs
    gen_tabs = context.get("generic_tabs", {})
    ordered_cmds = context.get("command_order", [])
    
    for cmd in ordered_cmds:
        if cmd in gen_tabs:
            tab = gen_tabs[cmd]
            if tab.is_empty:
                continue 
            
            # Render
            t_content = tab.render(context)
            t_btn = f'<button class="tab-btn" onclick="openTab(event, \'{tab.id}\')">{cmd}</button>'
            
            tab_buttons_html += t_btn
            tab_contents_html += t_content

    # 3. Render Raw Mem Report Tab
    import html
    raw_content_escaped = html.escape(context.get("raw_memreport", "No Raw Data"))
    raw_tab_id = "raw-mem-report"
    tab_buttons_html += f'<button class="tab-btn" onclick="openTab(event, \'{raw_tab_id}\')">Raw Mem Report</button>'
    tab_contents_html += f"""
    <div id="{raw_tab_id}" class="tab-content">
        <h3>Raw Mem Report</h3>
        <div class="table-container">
            <pre style="background: #1e1e1e; color: #d4d4d4; padding: 15px; border-radius: 8px; overflow-x: auto; font-family: monospace; font-size: 12px;">{raw_content_escaped}</pre>
        </div>
    </div>
    """

    html = HTML_TEMPLATE.format(
        title=f"MemReport - {context['metadata'].get('Device Name', 'Unknown')}",
        report_title="Memory Report",
        tab_buttons=tab_buttons_html,
        tab_contents=tab_contents_html,
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Report generated: {output_path}")


@click.command(name="memreport_to_html")
@click.argument("input_path", type=click.Path(exists=True))
@click.option(
    "--output-dir", "-o", default="MemReports", help="Output directory for HTML reports"
)
@click.option(
    "--open-report/--no-open-report",
    default=True,
    help="Open the report in browser after generation",
)
@click.option(
    "--use-as-prefix-only", is_flag=True, help="Use the input filename as a prefix only"
)
@click.pass_context
def generate_html(
    context: click.Context,
    input_path: str,
    output_dir: str,
    open_report: bool,
    use_as_prefix_only: bool,
):
    input_file = Path(input_path)

    if not input_file.exists():
        print(f"Error: File not found {input_file}")
        return

    print("Parsing memreport...")
    report_context = parse_memreport(input_file)

    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    if use_as_prefix_only:
        output_filename = f"{input_file.stem}.html"
    else:
        output_filename = f"{input_file.name}.html"

    output_file = output_dir_path / output_filename
    
    # Versioning Logic: Check if file exists and append v1, v2, etc.
    # Current behavior overwrites.
    # New behavior: always fresh file if collision? Or explicit versioning?
    # User asked: "generate a new report each time with addition of versoin as v1, v2"
    if output_file.exists():
        version = 1
        while True:
            # Insert version before suffix
            candidate_name = f"{output_file.stem}_v{version}{output_file.suffix}"
            candidate_file = output_dir_path / candidate_name
            if not candidate_file.exists():
                output_file = candidate_file
                break
            version += 1

    print(f"Generating HTML {output_file.name}...")
    generate_html_report(report_context, output_file)

    if open_report:
        import webbrowser

        webbrowser.open(f"file://{output_file.resolve()}")


if __name__ == "__main__":
    generate_html()
