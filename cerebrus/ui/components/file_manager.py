from __future__ import annotations
import os
import re
import subprocess
import sys
import webbrowser
from pathlib import Path
import dearpygui.dearpygui as dpg

from cerebrus.ui.state import UIState
from cerebrus.ui.themes import get_theme_manager
from cerebrus.ui.components.shared import log_message, _auto_save_profile
from cerebrus.tools.adb import AdbClient, AdbError
from cerebrus.tools.log_to_html import convert_log_to_html
from cerebrus.tools.memreport.tool import generate_html_report, parse_memreport


def _handle_output_file_name_change(
    sender: int, app_data: str, user_data: UIState
) -> None:
    user_data.output_file_name = app_data
    _auto_save_profile(user_data)


def _handle_use_prefix_toggle(sender: int, app_data: bool, user_data: UIState) -> None:
    user_data.use_prefix_only = bool(app_data)
    _auto_save_profile(user_data)


def _handle_bulk_action_toggle(
    sender: int, app_data: bool, user_data: tuple[UIState, str]
) -> None:
    state, field_name = user_data
    setattr(state, field_name, app_data)
    _auto_save_profile(state)


def _open_folder_in_explorer(path: Path | str) -> None:
    """Open the folder in the OS file explorer."""
    if isinstance(path, str):
        path = Path(path)

    if not path.exists():
        return

    try:
        if sys.platform == "win32":
            os.startfile(path)
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
    except Exception as e:
        print(f"Failed to open folder: {e}")


def _open_profile_folder(state: UIState) -> None:
    """Open the folder containing the current profile."""
    if state.profile_path and state.profile_path.exists():
        if state.profile_path.is_file():
            _open_folder_in_explorer(state.profile_path.parent)
        else:
            _open_folder_in_explorer(state.profile_path)
    else:
        log_message(state, "WARNING", "Profile path does not exist.")


def _get_unique_output_path(base_path: Path, filename: str, extension: str) -> Path:
    """
    Generate a unique file path by appending a counter if the file already exists.
    """
    # Ensure extension has a leading dot
    if not extension.startswith("."):
        extension = f".{extension}"

    output_path = base_path / f"{filename}{extension}"

    # If file doesn't exist, return it
    if not output_path.exists():
        return output_path

    # File exists, find a unique name by appending counter
    counter = 1
    while True:
        output_path = base_path / f"{filename}_{counter}{extension}"
        if not output_path.exists():
            return output_path
        counter += 1


def _handle_view_html_logs(state: UIState) -> None:
    """Open HTML log files in the default web browser."""
    # Output directory: state.output_path (device-specific folder)
    output_dir = state.output_path
    if not output_dir.exists():
        log_message(state, "ERROR", f"Output directory not found: {output_dir}")
        return

    # Find all HTML files recursively in the output directory and subdirectories
    html_files = list(output_dir.glob("**/*.html"))

    if not html_files:
        log_message(state, "WARNING", f"No HTML files found in {output_dir}")
        log_message(state, "INFO", "Generate colored logs first to create HTML files.")
        return

    # Sort by modification time (newest first)
    html_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    log_message(state, "INFO", f"Found {len(html_files)} HTML file(s) in {output_dir}")

    # Show a dialog to select which HTML file to open
    from cerebrus.ui.components.dialogs.files.file_dialog import _show_html_file_selector
    _show_html_file_selector(state, html_files)


def _open_html_file(state: UIState, html_file: Path) -> None:
    """Open a single HTML file in the default web browser."""
    import webbrowser
    try:
        # Use webbrowser module (part of Python standard library)
        webbrowser.open(f"file:///{html_file.as_posix()}")
        log_message(state, "SUCCESS", f"Opened {html_file.name} in browser")
    except Exception as e:
        log_message(state, "ERROR", f"Failed to open {html_file.name}: {e}")


def _open_all_html_files(state: UIState, html_files: list) -> None:
    """Open all HTML files in the default web browser."""
    import webbrowser
    opened_count = 0
    for html_file in html_files:
        try:
            webbrowser.open(f"file:///{html_file.as_posix()}")
            opened_count += 1
        except Exception as e:
            log_message(state, "ERROR", f"Failed to open {html_file.name}: {e}")

    if opened_count > 0:
        log_message(state, "SUCCESS", f"Opened {opened_count} HTML file(s) in browser")

    # Close the dialog
    if dpg.does_item_exist("html_viewer_dialog"):
        dpg.delete_item("html_viewer_dialog")


def _handle_generate_actions(state: UIState) -> None:
    """Execute selected bulk actions."""
    if state.move_logs_enabled:
        _handle_move_logs(state)
    if state.move_csv_enabled:
        _handle_move_csv(state)
    if state.move_memreport_enabled:
        _handle_move_memreport(state)
    if state.generate_perf_report_enabled:
        _handle_generate_perf_report(state)
    if state.generate_memreport_enabled:
        _handle_generate_mem_report(state)
    if state.generate_colored_logs_enabled:
        _handle_generate_colored_logs(state)


def _handle_move_csv(state: UIState) -> None:
    _move_files_from_device(state, "Profiling/CSV", "CSV")


def _handle_move_memreport(state: UIState) -> None:
    _move_files_from_device(state, "Profiling/MemReports", "MemReports")


def _handle_move_logs(state: UIState) -> None:
    _move_files_from_device(state, "Logs", "Logs")


def _move_files_from_device(
    state: UIState, source_subpath: str, dest_subpath: str
) -> None:
    if not state.selected_device_serial:
        log_message(state, "ERROR", "No device selected.")
        return

    if not state.package_name:
        log_message(state, "ERROR", "Package Name not set.")
        return

    parts = state.package_name.split(".")
    if len(parts) < 3:
        log_message(
            state, "ERROR", "Invalid Package Name format. Cannot derive Project Name."
        )
        return
    project_name = parts[-1]

    # Source: /sdcard/Android/data/{package}/files/UnrealGame/{project}/{project}/Saved/{source_subpath}/
    source_path = f"/sdcard/Android/data/{state.package_name}/files/UnrealGame/{project_name}/{project_name}/Saved/{source_subpath}/"

    # Dest: Use base_output_path (not device-specific) / {dest_subpath}/
    base_path = state.base_output_path if state.base_output_path else state.output_path
    dest_path = base_path / dest_subpath

    if not dest_path.exists():
        dest_path.mkdir(parents=True, exist_ok=True)

    client = AdbClient()
    serial = state.selected_device_serial

    log_message(state, "INFO", f"Moving files from {source_path} to {dest_path}...")

    try:
        # Pull all files from source directory
        client.pull(serial, source_path + ".", str(dest_path))

        # Delete files from source
        client.shell(serial, ["rm", "-rf", source_path + "*"])

        log_message(state, "SUCCESS", f"Moved files to {dest_path}")
    except AdbError as e:
        error_msg = str(e)
        if "does not exist" in error_msg or "No such file or directory" in error_msg:
            file_type = "Logs" if "Logs" in dest_subpath else "CSV Data"
            log_message(state, "ERROR", f"No {file_type} present on device.")
        else:
            log_message(state, "ERROR", f"ADB Error: {e}")
    except Exception as e:
        log_message(state, "ERROR", f"Failed to move files: {e}")


def _handle_generate_perf_report(state: UIState) -> None:
    """Run PerfreportTool on CSV files and delete them on success."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    tool_path = repo_root / "Binaries" / "CsvTools" / "PerfReportTool.exe"

    if not tool_path.exists():
        # Fallback to dev path if deeper nesting (ui/components/files.py -> 3 levels up -> cerebrus. 4 levels? no)
        # files.py is in cerebrus/ui/components/files.py.
        # Parent 1: components
        # Parent 2: ui
        # Parent 3: cerebrus
        # Parent 4: root
        log_message(state, "ERROR", f"PerfreportTool not found at: {tool_path}")
        return

    base_path = state.base_output_path if state.base_output_path else state.output_path
    csv_dir = base_path / "CSV"
    if not csv_dir.exists():
        log_message(state, "ERROR", f"CSV directory not found: {csv_dir}")
        return

    output_dir = state.output_path

    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    csv_files = list(csv_dir.glob("*.csv"))
    if not csv_files:
        log_message(state, "WARNING", f"No CSV files found in {csv_dir}")
        return

    log_message(
        state, "INFO", f"Found {len(csv_files)} CSV files. Starting processing..."
    )

    for csv_file in csv_files:
        if state.use_prefix_only:
            if state.output_file_name:
                output_filename = f"{state.output_file_name}_{csv_file.stem}"
            else:
                output_filename = csv_file.stem
        else:
            output_filename = (
                state.output_file_name if state.output_file_name else csv_file.stem
            )

        report_dir_name = output_filename
        report_dir = output_dir / report_dir_name
        
        counter = 1
        while report_dir.exists():
            report_dir = output_dir / f"{report_dir_name}_{counter}"
            counter += 1

        cmd = [
            str(tool_path),
            "-csv",
            str(csv_file),
            "-reportType",
            "Default60fps",
            "-o",
            str(report_dir),
            "-perfLog",
        ]

        log_message(state, "INFO", f"Processing {csv_file.name}...")

        try:
            startupinfo = None
            if hasattr(subprocess, "STARTUPINFO"):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

            result = subprocess.run(
                cmd, capture_output=True, text=True, startupinfo=startupinfo
            )

            if result.returncode == 0:
                generated_html_path = report_dir / f"{csv_file.stem}.html"
                log_message(state, "SUCCESS", f"Generated report in: {report_dir.name}")
                
                try:
                    _inject_metadata_into_report(state, csv_file, generated_html_path)
                except Exception as e:
                    log_message(state, "WARNING", f"Metadata injection failed: {e}")

                try:
                    _post_process_perf_report(state, generated_html_path)
                except Exception as e:
                    log_message(state, "WARNING", f"Post-processing failed: {e}")

                try:
                    csv_file.unlink()
                    log_message(state, "INFO", f"Deleted {csv_file.name}")
                except Exception as e:
                    log_message(state, "WARNING", f"Failed to delete {csv_file.name}: {e}")

            else:
                log_message(state, "ERROR", f"Failed to process {csv_file.name}")
                log_message(state, "ERROR", f"Tool Output: {result.stdout}")

        except Exception as e:
            log_message(state, "ERROR", f"Exception processing {csv_file.name}: {e}")

    log_message(state, "INFO", "Batch processing completed.")


def _handle_generate_mem_report(state: UIState) -> None:
    """Generate HTML reports from .memreport files."""
    base_path = state.base_output_path if state.base_output_path else state.output_path
    
    # Input defined as where MemReports were moved to: base_path/MemReports
    mem_dir = base_path / "MemReports"
    
    if not mem_dir.exists():
        log_message(state, "ERROR", f"MemReports directory not found: {mem_dir}")
        return

    # Output to current output_path
    dest_dir = state.output_path
    if not dest_dir.exists():
        dest_dir.mkdir(parents=True, exist_ok=True)
        
    report_files = list(mem_dir.glob("**/*.memreport"))
    if not report_files:
        log_message(state, "WARNING", f"No .memreport files found in {mem_dir}")
        return

    log_message(state, "INFO", f"Found {len(report_files)} memreport files. Generating...")

    for report_file in report_files:
        try:
            output_filename = report_file.stem
            if state.use_prefix_only and state.output_file_name:
                output_filename = f"{state.output_file_name}_{report_file.stem}"

            output_filename += ".html"
            output_path = dest_dir / output_filename

            log_message(state, "INFO", f"Parsing {report_file.name}...")
            context = parse_memreport(report_file)

            log_message(state, "INFO", f"Generating HTML: {output_filename}...")
            # Assuming generate_html_report exists and imported
            generate_html_report(context, output_path)

            try:
                report_file.unlink()
                log_message(state, "INFO", f"Deleted source: {report_file.name}")
            except Exception as e:
                log_message(state, "WARNING", f"Failed to delete source: {e}")

            log_message(state, "SUCCESS", f"Report generated: {output_filename}")

        except Exception as e:
            import traceback
            traceback.print_exc()
            log_message(state, "ERROR", f"Failed to process {report_file.name}: {e}")

    log_message(state, "INFO", "MemReport generation completed.")


def _handle_generate_colored_logs(state: UIState) -> None:
    """Convert text logs to colored HTML logs."""
    base_path = state.base_output_path if state.base_output_path else state.output_path
    logs_dir = base_path / "Logs"
    if not logs_dir.exists():
        log_message(state, "ERROR", f"Logs directory not found: {logs_dir}")
        return

    output_dir = state.output_path
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    log_files = list(logs_dir.glob("*.log")) + list(logs_dir.glob("*.txt"))
    if not log_files:
        log_message(state, "WARNING", f"No log files found in {logs_dir}")
        return

    log_message(state, "INFO", f"Found {len(log_files)} log files. Starting conversion...")

    for log_file in log_files:
        if state.use_prefix_only:
            if state.output_file_name:
                output_filename = f"{state.output_file_name}_{log_file.stem}"
            else:
                output_filename = log_file.stem
        else:
            output_filename = state.output_file_name if state.output_file_name else log_file.stem

        output_file_path = _get_unique_output_path(output_dir, output_filename, ".html")

        log_message(state, "INFO", f"Converting {log_file.name}...")

        try:
            convert_log_to_html(log_file, output_file_path)
            log_message(state, "SUCCESS", f"Created {output_file_path.name}")

            try:
                log_file.unlink()
                log_message(state, "INFO", f"Deleted {log_file.name}")
            except Exception as e:
                log_message(state, "WARNING", f"Failed to delete {log_file.name}: {e}")

        except Exception as e:
            log_message(state, "ERROR", f"Exception converting {log_file.name}: {e}")

    log_message(state, "INFO", "Log conversion completed.")


def _log_debug_to_file(msg: str):
    try:
        if getattr(sys, "frozen", False):
            root_path = Path(sys.executable).parent
        else:
            root_path = Path(__file__).resolve().parent.parent.parent.parent

        debug_dir = root_path / "DebugInfo"
        if not debug_dir.exists():
            debug_dir.mkdir(parents=True, exist_ok=True)

        debug_path = debug_dir / "cerebrus_debug.txt"

        with open(debug_path, "a", encoding="utf-8") as f:
            from datetime import datetime
            f.write(f"[{datetime.now()}] {msg}\n")
    except:
        pass


def _read_csv_metadata(csv_path: Path) -> dict:
    metadata = {}
    try:
        with open(csv_path, "rb") as f:
            try:
                f.seek(-16384, 2)
            except OSError:
                f.seek(0)
            tail_bytes = f.read()
            tail = tail_bytes.decode("utf-8", errors="ignore")

        matches = re.findall(r"\[([a-zA-Z0-9_]+)\]\s*([^[\]\r\n]+)", tail)
        for key, value in matches:
            clean_value = value.strip().strip(",").strip()
            metadata[key.lower()] = clean_value

    except Exception as e:
        _log_debug_to_file(f"CSV Read Exception: {e}")

    return metadata


def _inject_metadata_into_report(state: UIState, csv_file: Path, html_file: Path) -> None:
    if not html_file.exists():
        return

    try:
        metadata = _read_csv_metadata(csv_file)
        if not metadata:
            return

        config = metadata.get("config", "Unknown")
        os_name = metadata.get("os", "Unknown")
        cpu = metadata.get("cpu", "Unknown")
        duration = metadata.get("captureduration", "0")
        try:
            duration_val = float(duration)
            duration_str = f"{duration_val:.2f} s"
        except ValueError:
            duration_str = duration

        cmd_line = metadata.get("commandline", "").strip()
        target_fps = metadata.get("targetframerate", "60")

        features_list = []
        if metadata.get("largeworldcoordinates") == "1":
            features_list.append("Large World Coordinates (LWC) Enabled")
            
        pgo = metadata.get("pgoenabled", "0")
        lto = metadata.get("ltoenabled", "0")
        asan = metadata.get("asan", "0")
        if pgo == "0" and lto == "0" and asan == "0":
            features_list.append("PGO/LTO/ASAN Disabled")
        else:
            enabled = []
            if pgo == "1": enabled.append("PGO")
            if lto == "1": enabled.append("LTO")
            if asan == "1": enabled.append("ASAN")
            if enabled:
                features_list.append(f"{'/'.join(enabled)} Enabled")

        features_str = "; ".join(features_list)

        extra_rows = f"""
        <tr><td>Configuration</td><td><b>{config}</b></td></tr>
        <tr><td>OS</td><td><b>{os_name}</b></td></tr>
        <tr><td>CPU/Device</td><td><b>{cpu}</b></td></tr>
        <tr><td>Capture Duration</td><td><b>{duration_str}</b></td></tr>
        <tr><td>Command Line</td><td><b>{cmd_line}</b></td></tr>
        <tr><td>Features</td><td><b>{features_str}</b></td></tr>
        <tr><td>Target Framerate</td><td><b>{target_fps} FPS</b></td></tr>
        """

        content = html_file.read_text(encoding="utf-8")
        pattern = re.compile(r"(<tr[^>]*>.*?Frame\s*count.*?</tr>)", re.IGNORECASE | re.DOTALL)
        match = pattern.search(content)

        if match:
            insertion_point = match.end()
            new_content = content[:insertion_point] + extra_rows + content[insertion_point:]
            html_file.write_text(new_content, encoding="utf-8")
            log_message(state, "SUCCESS", f"Metadata successfully appended to {html_file.name}")
        else:
            log_message(state, "WARNING", f"Metadata injection failed: Could not find 'Frame count' row.")

    except Exception as e:
        log_message(state, "ERROR", f"Failed to inject metadata: {e}")


def _post_process_perf_report(state: UIState, file_path: Path) -> None:
    if not file_path.exists():
        return

    try:
        content = file_path.read_text(encoding="utf-8")
        chart_start_match = re.search(r"FPSChart", content)
        if not chart_start_match: return
        
        table_start_match = re.search(r"<table", content[chart_start_match.end() :])
        if not table_start_match: return
        
        real_table_start_idx = chart_start_match.end() + table_start_match.start()
        table_end_match = re.search(r"</table>", content[real_table_start_idx:])
        if not table_end_match: return
        
        real_table_end_idx = real_table_start_idx + table_end_match.end()
        table_content = content[real_table_start_idx:real_table_end_idx]

        if "Frametime" in table_content:
            header_pattern = re.compile(r"(<th[^>]*>.*?Frametime.*?</th>)", re.IGNORECASE | re.DOTALL)
            if header_pattern.search(table_content):
                table_content = header_pattern.sub(r"\1<th style=\"background-color:#e0e0e0\">FPS Avg</th>", table_content, count=1)

        def row_processor(match):
            row_html = match.group(0)
            if "<th" in row_html: return row_html
            cells_match = list(re.finditer(r"(<td[^>]*>.*?</td>)", row_html, re.IGNORECASE | re.DOTALL))
            if not cells_match: return row_html

            target_idx = 5
            if len(cells_match) > target_idx:
                try:
                    cell_html = cells_match[target_idx].group(0)
                    cell_text = re.sub(r"<[^>]+>", "", cell_html).strip()
                    frametime = float(cell_text)

                    if frametime > 0:
                        fps = 1000.0 / frametime
                        color = "#87d387" if fps >= 59.99 else "#ff6666" if fps <= 30.0 else "#ffedcc"
                        new_cell = f'<td bgcolor="{color}" style="font-weight:bold;">{fps:.2f}</td>'
                        target_end = cells_match[target_idx].end()
                        return row_html[:target_end] + new_cell + row_html[target_end:]
                except ValueError:
                    pass
            return row_html

        new_table_content = re.sub(r"<tr[^>]*>.*?</tr>", row_processor, table_content, flags=re.DOTALL)
        new_content = content[:real_table_start_idx] + new_table_content + content[real_table_end_idx:]
        file_path.write_text(new_content, encoding="utf-8")
        log_message(state, "SUCCESS", "Added FPS Avg column to report.")

    except Exception as e:
        log_message(state, "ERROR", f"Failed to post-process report: {e}")
