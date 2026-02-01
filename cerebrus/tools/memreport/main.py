
import argparse
from pathlib import Path
from typing import Dict, Any, List

from .tabs.device_info import DeviceInfoTab
from .tabs.memory_stats import MemoryStatsTab
from .tabs.obj_summary import ObjectSummaryTab
from .tabs.detailed_lists import DetailedListsTab
from .template import HTML_TEMPLATE
from .utils import format_seconds_to_hms

def parse_memreport(file_path: Path) -> Dict[str, Any]:
    context = {"metadata": {}}
    
    # Tabs that handle parsing
    tabs = [
        MemoryStatsTab(),
        ObjectSummaryTab(),
        DetailedListsTab()
    ]
    
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
        
    line_idx = 0
    total_lines = len(lines)
    
    # 1. Parse Header/Metadata (until empty line)
    # This logic remains in main because it's global file structure, not valid for generic tabs
    while line_idx < total_lines:
        line = lines[line_idx].strip()
        line_idx += 1
        if not line:
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

    # 2. Main Parsing Loop
    current_tab = None
    
    while line_idx < total_lines:
        line = lines[line_idx].rstrip()
        line_idx += 1
        
        # Check for tab switch
        # Check "MemReport: Begin" or specific headers
        # We check all tabs to see if anyone claims this line
        params = None
        new_tab = None
        
        for tab in tabs:
            if tab.should_handle(line):
                new_tab = tab
                break
        
        if new_tab:
            current_tab = new_tab
            # Let the tab handle the very first line too (e.g. to set state)
            current_tab.parse(line, context)
            continue
            
        if line.startswith("MemReport: End command"):
            current_tab = None
            continue
            
        # Delegate
        if current_tab:
            current_tab.parse(line, context)
            
    return context

def generate_html_report(context: Dict[str, Any], output_path: Path):
    # Assemble Tabs
    # DeviceInfo is always first
    all_tabs = [DeviceInfoTab(), MemoryStatsTab(), ObjectSummaryTab(), DetailedListsTab()]
    
    # Re-instantiate tabs? No, we used instances in parse.
    # Actually, DetailedListsTab holds state (current_class) during parsing but stores data in context.
    # So new instances for rendering is fine if they pull from context.
    # BUT DetailedListsTab.get_buttons needs to see the data in context.
    
    tab_buttons_html = ""
    tab_contents_html = ""
    
    for i, tab in enumerate(all_tabs):
        # Delegate to render and get_buttons
        btns = tab.get_buttons(context)
        # Device Info (index 0) is active by default
        content = tab.render(context, is_active=(i == 0))
        
        tab_buttons_html += btns
        tab_contents_html += content
        
    html = HTML_TEMPLATE.format(
        title=f"MemReport - {context['metadata'].get('Device Name', 'Unknown')}",
        report_title="Memory Report",
        tab_buttons=tab_buttons_html,
        tab_contents=tab_contents_html
    )
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
        
    print(f"Report generated: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Convert UE .memreport to HTML (Modular)")
    parser.add_argument("input_file", type=Path, help="Path to .memreport file")
    parser.add_argument("output_file", type=Path, help="Path to output .html file")
    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"Error: File not found {args.input_file}")
        return

    print("Parsing memreport...")
    context = parse_memreport(args.input_file)
    
    print("Generating HTML...")
    args.output_file.parent.mkdir(parents=True, exist_ok=True)
    generate_html_report(context, args.output_file)

if __name__ == "__main__":
    main()
