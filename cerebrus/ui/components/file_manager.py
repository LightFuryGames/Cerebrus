from __future__ import annotations

import csv
import html
import json
import math
import os
import re
import subprocess
import sys
import webbrowser
from pathlib import Path

import dearpygui.dearpygui as dpg

from cerebrus.plugins.analytics.core.device_profiles import (
    enrich_with_device_profile_tier,
)
from cerebrus.plugins.analytics.core.normalizer import parse_cpu_device
from cerebrus.tools.adb import AdbClient, AdbError
from cerebrus.tools.log_to_html import convert_log_to_html

from cerebrus.tools.memreport.tool import process_memreport
from cerebrus.ui.components.shared import _auto_save_profile, log_message

from cerebrus.tools.memreport.tabs.battery_thermal import BatteryThermalTab
from cerebrus.tools.memreport.tool import generate_html_report, parse_memreport
from cerebrus.tools.thermal_to_html import (
    _build_svg_chart,
    _read_samples,
    _status_for_temp,
    generate_thermal_html,
)
from cerebrus.ui.components.shared import (
    _auto_save_profile,
    device_label,
    device_output_subfolder_name,
    log_message,
    resolve_profiling_targets,
)

from cerebrus.ui.state import UIState
from cerebrus.ui.themes import get_theme_manager


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
    from .dialogs.files.file_dialog import _show_html_file_selector

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
    if state.generate_thermal_report_enabled:
        _handle_generate_thermal_report(state)


def _handle_generate_thermal_report(state: UIState) -> None:
    """Render an HTML report for any battery-thermal capture CSV(s) found
    in the output folder. Unlike CSV/memreport, thermal CSVs are written
    directly to the output folder by the sampler (there's no on-device
    file to pull), so this just looks for `*_battery_thermal.csv` there.

    Searches recursively: single-device sessions write the CSV directly
    under `base_path`, but multi-device sessions nest it one level down,
    inside a per-device subfolder (`base_path/{make}_{model}_{serial}/`),
    to keep simultaneous captures from colliding.
    """
    base_path = state.base_output_path if state.base_output_path else state.output_path
    if not base_path.exists():
        return

    csv_files = list(base_path.rglob("*_battery_thermal.csv"))
    if not csv_files:
        return

    generated = 0
    for csv_file in csv_files:
        html_path = csv_file.with_suffix(".html")
        if html_path.exists():
            continue
        try:
            generate_thermal_html(csv_file, html_path)
            generated += 1
        except Exception as e:
            log_message(
                state,
                "ERROR",
                f"Failed to generate thermal report for {csv_file.relative_to(base_path)}: {e}",
            )

    if generated:
        log_message(state, "SUCCESS", f"Generated {generated} battery thermal report(s).")


def _handle_move_csv(state: UIState) -> None:
    _move_files_from_device(state, "Profiling/CSV", "CSV")


def _handle_move_memreport(state: UIState) -> None:
    _move_files_from_device(state, "Profiling/MemReports", "MemReports")


def _handle_move_logs(state: UIState) -> None:
    _move_files_from_device(state, "Logs", "Logs")


def _move_files_from_device(
    state: UIState, source_subpath: str, dest_subpath: str
) -> None:
    targets = resolve_profiling_targets(state)
    if not targets:
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

    base_path = state.base_output_path if state.base_output_path else state.output_path
    multi_device = len(targets) > 1
    client = AdbClient()

    for device in targets:
        label = device_label(device) if multi_device else ""

        # Source: /sdcard/Android/data/{package}/files/UnrealGame/{project}/{project}/Saved/{source_subpath}/
        source_path = f"/sdcard/Android/data/{state.package_name}/files/UnrealGame/{project_name}/{project_name}/Saved/{source_subpath}/"

        # Dest: isolate per-device when multiple devices are active, so
        # simultaneous pulls never overwrite each other's files.
        dest_path = base_path / dest_subpath
        if multi_device:
            dest_path = base_path / device_output_subfolder_name(device) / dest_subpath

        if not dest_path.exists():
            dest_path.mkdir(parents=True, exist_ok=True)

        serial = device.serial
        log_message(
            state,
            "INFO",
            f"Moving files{f' from {label}' if label else ''} from {source_path} to {dest_path}...",
        )

        try:
            # Pull all files from source directory
            client.pull(serial, source_path + ".", str(dest_path))

            # Delete files from source
            client.shell(serial, ["rm", "-rf", source_path + "*"])

            log_message(
                state, "SUCCESS", f"Moved files{f' from {label}' if label else ''} to {dest_path}"
            )
        except AdbError as e:
            error_msg = str(e)
            if "does not exist" in error_msg or "No such file or directory" in error_msg:
                file_type = "Logs" if "Logs" in dest_subpath else "CSV Data"
                log_message(
                    state,
                    "ERROR",
                    f"No {file_type} present{f' on {label}' if label else ' on device'}.",
                )
            else:
                log_message(
                    state,
                    "ERROR",
                    f"ADB Error{f' ({label})' if label else ''}: {e}",
                )
        except Exception as e:
            log_message(
                state,
                "ERROR",
                f"Failed to move files{f' from {label}' if label else ''}: {e}",
            )


def _handle_generate_perf_report(state: UIState) -> None:
    """Run PerfreportTool on CSV files and delete them on success."""
    repo_root = Path(__file__).resolve().parent.parent.parent.parent
    tool_path = repo_root / "Binaries" / "CsvTools" / "PerfReportTool.exe"

    if not tool_path.exists():
        log_message(state, "ERROR", f"PerfreportTool not found at: {tool_path}")
        return

    base_path = state.base_output_path if state.base_output_path else state.output_path

    # A CSV directory can live directly under base_path (single-device
    # sessions, unchanged from before) or nested one level down inside a
    # per-device subfolder (multi-device sessions - see
    # `_move_files_from_device`). Collect every CSV dir that actually
    # exists so each device's captures get processed.
    csv_dirs = []
    flat_csv_dir = base_path / "CSV"
    if flat_csv_dir.exists():
        csv_dirs.append(flat_csv_dir)
    csv_dirs.extend(sorted(base_path.glob("*/CSV")))

    if not csv_dirs:
        log_message(state, "ERROR", f"CSV directory not found: {flat_csv_dir}")
        return

    total_processed = 0
    for csv_dir in csv_dirs:
        # Flat (single-device) CSVs keep the original shared Profiling
        # output folder. Per-device CSVs get their own sibling Profiling
        # folder, so each device's generated reports stay together.
        if csv_dir == flat_csv_dir:
            output_dir = state.output_path / "Profiling"
            device_prefix = None
            thermal_search_root = base_path
        else:
            output_dir = csv_dir.parent / "Profiling"
            # Force the report filename to this device's own folder name
            # rather than `state.output_file_name` - that's a single
            # global value (whatever was last typed/auto-filled) with no
            # reliable relation to which device's CSV is being processed
            # here, which is what caused every device's report to be
            # named after whichever device was selected last.
            device_prefix = csv_dir.parent.name
            thermal_search_root = csv_dir.parent

        total_processed += _process_csv_directory(
            state, tool_path, csv_dir, output_dir, device_prefix, thermal_search_root
        )

    log_message(state, "INFO", "Batch processing completed.")


def _process_csv_directory(
    state: UIState,
    tool_path: Path,
    csv_dir: Path,
    output_dir: Path,
    device_prefix: str | None,
    thermal_search_root: Path,
) -> int:
    """Run PerfReportTool on every CSV file in one directory. Returns the
    number of files processed (attempted), regardless of individual
    success/failure - callers use this just for a summary count.
    """
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    csv_files = list(csv_dir.glob("*.csv"))
    if not csv_files:
        log_message(state, "WARNING", f"No CSV files found in {csv_dir}")
        return 0

    log_message(
        state, "INFO", f"Found {len(csv_files)} CSV files in {csv_dir}. Starting processing..."
    )

    thermal_samples = []
    thermal_csv_files = list(thermal_search_root.glob("*_battery_thermal.csv"))
    if thermal_csv_files:
        try:
            thermal_samples = _read_samples(thermal_csv_files[0])
        except Exception as e:
            log_message(state, "WARNING", f"Could not read battery thermal CSV: {e}")

    for csv_file in csv_files:
        if device_prefix is not None:
            output_filename = f"{device_prefix}_{csv_file.stem}"
        elif state.use_prefix_only:
            if state.output_file_name:
                output_filename = f"{state.output_file_name}_{csv_file.stem}"
            else:
                output_filename = csv_file.stem
        else:
            output_filename = (
                state.output_file_name if state.output_file_name else csv_file.stem
            )

        # User requested output directly in Profiling/ folder, not a subdir.
        # PerfReportTool with -o <dir> usually creates <dir>/<InputName>.html
        # We pass output_dir directly.

        cmd = [
            str(tool_path),
            "-csv",
            str(csv_file),
            "-reportType",
            "Default60fps",
            "-o",
            str(output_dir),
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
                # Tool outputs keys off the input filename usually.
                # If we want to support state.output_file_name (renaming), we must find the generated file.
                # Standard behavior: Input.csv -> OutputDir/Input.html
                generated_html_path = output_dir / f"{csv_file.stem}.html"

                if not generated_html_path.exists():
                    # Fallback check if it used some other naming convention?
                    # Try finding any HTML created recently?
                    # For now assume standard behavior.
                    log_message(
                        state,
                        "WARNING",
                        f"Expected output file not found: {generated_html_path}",
                    )
                else:
                    # Rename if requested via UI state (Prefix/Output Name)
                    final_name = csv_file.stem
                    if device_prefix is not None:
                        final_name = f"{device_prefix}_{csv_file.stem}"
                    elif state.use_prefix_only:
                        if state.output_file_name:
                            final_name = f"{state.output_file_name}_{csv_file.stem}"
                    elif state.output_file_name:
                        final_name = state.output_file_name

                    if final_name != csv_file.stem:
                        new_path = output_dir / f"{final_name}.html"
                        # Handle collision
                        c = 1
                        while new_path.exists():
                            new_path = output_dir / f"{final_name}_{c}.html"
                            c += 1

                        try:
                            generated_html_path.rename(new_path)
                            generated_html_path = new_path
                        except Exception as e:
                            log_message(
                                state, "WARNING", f"Failed to rename output: {e}"
                            )

                    log_message(
                        state,
                        "SUCCESS",
                        f"Generated report: {generated_html_path.name}",
                    )

                try:
                    _inject_metadata_into_report(state, csv_file, generated_html_path)
                except Exception as e:
                    log_message(state, "WARNING", f"Metadata injection failed: {e}")

                try:
                    _post_process_perf_report(state, generated_html_path)
                except Exception as e:
                    log_message(state, "WARNING", f"Post-processing failed: {e}")

                try:
                    _inject_percentile_gauges_into_report(
                        state, csv_file, generated_html_path
                    )
                except Exception as e:
                    log_message(
                        state, "WARNING", f"Percentile gauges injection failed: {e}"
                    )

                try:
                    _inject_raw_csv_into_report(state, csv_file, generated_html_path)
                except Exception as e:
                    log_message(state, "WARNING", f"Raw CSV injection failed: {e}")

                if thermal_samples:
                    try:
                        _inject_battery_thermal_into_report(
                            state, thermal_samples, generated_html_path
                        )
                    except Exception as e:
                        log_message(
                            state, "WARNING", f"Battery thermal injection failed: {e}"
                        )

                try:
                    csv_file.unlink()
                    log_message(state, "INFO", f"Deleted {csv_file.name}")
                except Exception as e:
                    log_message(
                        state, "WARNING", f"Failed to delete {csv_file.name}: {e}"
                    )

            else:
                log_message(state, "ERROR", f"Failed to process {csv_file.name}")
                log_message(state, "ERROR", f"Tool Output: {result.stdout}")

        except Exception as e:
            log_message(state, "ERROR", f"Exception processing {csv_file.name}: {e}")

    return len(csv_files)


def _handle_generate_mem_report(state: UIState) -> None:
    """Generate HTML reports from .memreport files."""
    base_path = state.base_output_path if state.base_output_path else state.output_path

    # A MemReports directory can live directly under base_path
    # (single-device sessions) or nested one level down inside a
    # per-device subfolder (multi-device sessions - see
    # `_move_files_from_device`). Collect every one that actually exists.
    mem_dirs = []
    flat_mem_dir = base_path / "MemReports"
    if flat_mem_dir.exists():
        mem_dirs.append(flat_mem_dir)
    mem_dirs.extend(sorted(base_path.glob("*/MemReports")))

    if not mem_dirs:
        log_message(state, "ERROR", f"MemReports directory not found: {flat_mem_dir}")
        return

    for mem_dir in mem_dirs:
        # Output goes next to where the source memreports actually live -
        # NOT `state.output_path`, which reflects whichever device row was
        # last clicked in the table and has no relation to which device's
        # files are being processed in this iteration. Using a sibling of
        # the discovered mem_dir keeps each device's generated reports
        # with that device's own data, and never depends on UI selection
        # state that can change between Start Profiling and Generate.
        if mem_dir == flat_mem_dir:
            dest_dir = state.output_path / "MemReports"
        else:
            dest_dir = mem_dir.parent / "MemReports"

        # Thermal capture for this same device (if any) lives as a sibling
        # of mem_dir too, so each device's memreport gets its OWN thermal
        # tab, not another device's.
        thermal_search_root = mem_dir.parent if mem_dir != flat_mem_dir else base_path

        # For a per-device subfolder, force the filename prefix to that
        # device's own folder name rather than `state.output_file_name`
        # (which reflects whichever device row was last clicked and has
        # no reliable relation to the device actually being processed
        # here) - this is what prevents every device's reports from
        # colliding on the same output filename.
        device_prefix = mem_dir.parent.name if mem_dir != flat_mem_dir else None

        _generate_mem_reports_in_directory(
            state, mem_dir, dest_dir, thermal_search_root, device_prefix
        )


def _generate_mem_reports_in_directory(
    state: UIState,
    mem_dir: Path,
    dest_dir: Path,
    thermal_search_root: Path,
    device_prefix: str | None,
) -> None:
    if not dest_dir.exists():
        dest_dir.mkdir(parents=True, exist_ok=True)

    report_files = list(mem_dir.glob("**/*.memreport"))
    if not report_files:
        log_message(state, "WARNING", f"No .memreport files found in {mem_dir}")
        return

    log_message(
        state, "INFO", f"Found {len(report_files)} memreport files in {mem_dir}. Generating..."
    )

    # If a battery-thermal capture was taken alongside this profiling
    # session, attach it as an extra tab on every generated report so the
    # temperature chart lives inside the same HTML rather than a separate
    # file. Scoped to this device's own subfolder, not the whole session,
    # so a device never picks up another device's thermal chart.
    thermal_samples = []
    thermal_csv_files = list(thermal_search_root.glob("*_battery_thermal.csv"))
    if thermal_csv_files:
        try:
            thermal_samples = _read_samples(thermal_csv_files[0])
            log_message(
                state,
                "INFO",
                f"Attaching battery thermal capture ({thermal_csv_files[0].name}, "
                f"{len(thermal_samples)} samples) to reports in {dest_dir}.",
            )
        except Exception as e:
            log_message(state, "WARNING", f"Could not read battery thermal CSV: {e}")

    for report_file in report_files:
        try:

            log_message(state, "INFO", f"Parsing {report_file.name}...")
            output_path = process_memreport(
                input_file=report_file,
                output_dir=dest_dir,
                use_as_prefix_only=state.use_prefix_only,
                output_name_prefix=(
                    state.output_file_name if state.use_prefix_only else None
                ),
            )
            if output_path is None:
                log_message(
                    state, "ERROR", f"Failed to generate report for {report_file.name}"
                )
                continue

            output_filename = report_file.stem
            if device_prefix is not None:
                output_filename = f"{device_prefix}_{report_file.stem}"
            elif state.use_prefix_only and state.output_file_name:
                output_filename = f"{state.output_file_name}_{report_file.stem}"

            output_filename += ".html"
            output_path = dest_dir / output_filename

            log_message(state, "INFO", f"Parsing {report_file.name}...")
            context = parse_memreport(report_file)

            if thermal_samples:
                context["tabs"].append(BatteryThermalTab(thermal_samples))

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

    logs_dirs = []
    flat_logs_dir = base_path / "Logs"
    if flat_logs_dir.exists():
        logs_dirs.append(flat_logs_dir)
    logs_dirs.extend(sorted(base_path.glob("*/Logs")))

    if not logs_dirs:
        log_message(state, "ERROR", f"Logs directory not found: {flat_logs_dir}")
        return

    for logs_dir in logs_dirs:
        if logs_dir == flat_logs_dir:
            output_dir = state.output_path / "Logs"
            device_prefix = None
        else:
            output_dir = logs_dir  # convert in place, alongside the source .log files
            device_prefix = logs_dir.parent.name

        _generate_colored_logs_in_directory(state, logs_dir, output_dir, device_prefix)


def _generate_colored_logs_in_directory(
    state: UIState, logs_dir: Path, output_dir: Path, device_prefix: str | None
) -> None:
    if not output_dir.exists():
        output_dir.mkdir(parents=True, exist_ok=True)

    log_files = list(logs_dir.glob("*.log")) + list(logs_dir.glob("*.txt"))
    if not log_files:
        log_message(state, "WARNING", f"No log files found in {logs_dir}")
        return

    log_message(
        state, "INFO", f"Found {len(log_files)} log files in {logs_dir}. Starting conversion..."
    )

    for log_file in log_files:
        if device_prefix is not None:
            output_filename = f"{device_prefix}_{log_file.stem}"
        elif state.use_prefix_only:
            if state.output_file_name:
                output_filename = f"{state.output_file_name}_{log_file.stem}"
            else:
                output_filename = log_file.stem
        else:
            output_filename = (
                state.output_file_name if state.output_file_name else log_file.stem
            )

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
        from cerebrus.core.paths import get_debug_dir

        debug_dir = get_debug_dir()
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


def _html_escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _inject_cerebrus_metadata_script(content: str, metadata: dict) -> str:
    cpu_parts = parse_cpu_device(metadata.get("cpu"))
    payload = {
        "build_config": metadata.get("config"),
        "os": metadata.get("os"),
        "cpu_device": metadata.get("cpu"),
        "device_manufacturer": cpu_parts.get("manufacturer"),
        "device_model": cpu_parts.get("model"),
        "device_gpu": cpu_parts.get("gpu"),
        "device_profile": metadata.get("DeviceProfile")
        or metadata.get("deviceprofile"),
        "scalability_tier": metadata.get("Scalability Tier"),
        "device_profile_chain": metadata.get("DeviceProfile Chain"),
        "device_profile_chain_depth": metadata.get("device_profile_chain_depth"),
        "device_profile_root": metadata.get("device_profile_root"),
        "device_profile_reference": metadata.get("DeviceProfile Reference"),
        "device_profile_reference_sha1": metadata.get("DeviceProfile Reference SHA1"),
        "target_fps": metadata.get("targetframerate"),
        "capture_duration_s": metadata.get("captureduration"),
        "report_value": metadata.get("report_value"),
    }
    payload = {key: value for key, value in payload.items() if value not in (None, "")}
    if not payload:
        return content

    script = (
        '<script type="application/json" id="cerebrus-metadata">'
        f"{json.dumps(payload, sort_keys=True)}"
        "</script>"
    )
    pattern = re.compile(
        r'<script\s+type="application/json"\s+id="cerebrus-metadata">.*?</script>',
        re.IGNORECASE | re.DOTALL,
    )
    if pattern.search(content):
        return pattern.sub(script, content, count=1)

    body_match = re.search(r"</body\s*>", content, re.IGNORECASE)
    if body_match:
        return content[: body_match.start()] + script + content[body_match.start() :]
    return content + script


def _inject_metadata_into_report(
    state: UIState, csv_file: Path, html_file: Path
) -> None:
    if not html_file.exists():
        return

    try:
        metadata = _read_csv_metadata(csv_file)
        if not metadata:
            return
        tier_metadata = enrich_with_device_profile_tier(
            metadata,
            state.device_profile_config_path,
        )
        metadata.update(tier_metadata)

        config = metadata.get("config", "Unknown")
        os_name = metadata.get("os", "Unknown")
        cpu = metadata.get("cpu", "Unknown")
        cpu_parts = parse_cpu_device(cpu)
        device_manufacturer = cpu_parts.get("manufacturer", "Unknown")
        device_model = cpu_parts.get("model", "Unknown")
        device_gpu = cpu_parts.get("gpu", "Unknown")
        device_profile = metadata.get("DeviceProfile") or metadata.get(
            "deviceprofile", "Unknown"
        )
        scalability_tier = metadata.get("Scalability Tier", "Unknown")
        profile_chain = metadata.get("DeviceProfile Chain", "")
        profile_root = metadata.get("device_profile_root", "")
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
            if pgo == "1":
                enabled.append("PGO")
            if lto == "1":
                enabled.append("LTO")
            if asan == "1":
                enabled.append("ASAN")
            if enabled:
                features_list.append(f"{'/'.join(enabled)} Enabled")

        features_str = "; ".join(features_list)

        # Compute Report Value (1-100). To guarantee parity with the analytics
        # JSON, route the same raw CSV through the same parser + normalizer the
        # JSON ingest uses, then read report_value off the resulting flat doc.
        # This keeps the HTML row, the embedded cerebrus-metadata JSON, and the
        # ES-indexed document in lockstep.
        from cerebrus.plugins.analytics.core.csv_report_parser import (
            PerformanceCSVReportParser,
        )
        from cerebrus.plugins.analytics.core.normalizer import (
            build_analytics_document,
        )

        try:
            raw_values = PerformanceCSVReportParser(csv_file).parse()
            preview_doc = build_analytics_document(
                source_path=csv_file,
                source_type="profiling_csv",
                raw_values=raw_values,
                device_profile_config_path=state.device_profile_config_path,
            )
            report_value = int(preview_doc.get("report_value") or 1)
        except Exception:
            report_value = 1

        # Audit core metadata; flag any "Unknown"/blank values for the banner.
        audit_fields = {
            "Configuration": config,
            "OS": os_name,
            "CPU/Device": cpu,
            "Device GPU": device_gpu,
            "DeviceProfile": device_profile,
            "Scalability Tier": scalability_tier,
            "Capture Duration": duration_str,
            "Target Framerate": target_fps,
        }
        corrupt_fields = [
            name
            for name, value in audit_fields.items()
            if not value
            or str(value).strip() == ""
            or str(value).strip().lower() in {"unknown", "n/a", "0", "0 s", "0.00 s"}
        ]
        metadata["report_value"] = report_value
        if corrupt_fields:
            warning_row = (
                '<tr style="background-color:#ff4d4d;color:#ffffff;font-weight:bold;">'
                "<td>&#9888; DATA QUALITY WARNING</td>"
                f'<td>Corrupt or missing fields: {_html_escape(", ".join(corrupt_fields))}. '
                "Sentinels written into analytics JSON. Investigate report source.</td>"
                "</tr>"
            )
        else:
            warning_row = ""

        extra_rows = f"""
        {warning_row}
        <tr><td>Configuration</td><td><b>{_html_escape(config)}</b></td></tr>
        <tr><td>OS</td><td><b>{_html_escape(os_name)}</b></td></tr>
        <tr><td>CPU/Device</td><td><b>{_html_escape(cpu)}</b></td></tr>
        <tr><td>Device Manufacturer</td><td><b>{_html_escape(device_manufacturer)}</b></td></tr>
        <tr><td>Device Model</td><td><b>{_html_escape(device_model)}</b></td></tr>
        <tr><td>Device GPU</td><td><b>{_html_escape(device_gpu)}</b></td></tr>
        <tr><td>DeviceProfile</td><td><b>{_html_escape(device_profile)}</b></td></tr>
        <tr><td>Scalability Tier</td><td><b>{_html_escape(scalability_tier)}</b></td></tr>
        <tr><td>DeviceProfile Root</td><td><b>{_html_escape(profile_root or "n/a")}</b></td></tr>
        <tr><td>DeviceProfile Chain</td><td><b>{_html_escape(profile_chain)}</b></td></tr>
        <tr><td>Capture Duration</td><td><b>{_html_escape(duration_str)}</b></td></tr>
        <tr><td>Command Line</td><td><b>{_html_escape(cmd_line)}</b></td></tr>
        <tr><td>Features</td><td><b>{_html_escape(features_str)}</b></td></tr>
        <tr><td>Target Framerate</td><td><b>{_html_escape(target_fps)} FPS</b></td></tr>
        <tr><td>Report Value (1-100)</td><td><b>{report_value}</b> &nbsp;<i>(Grafana weighted_avg weight)</i></td></tr>
        <tr><td colspan="2" style="background-color:#f7f7fa;border-left:4px solid #4a90e2;padding:10px 14px;">
          <details>
            <summary style="cursor:pointer;font-weight:bold;color:#2c5aa0;">
              &#9432; What is Report Value? (click to expand)
            </summary>
            <div style="margin-top:10px;font-size:13px;line-height:1.5;">
              <p><b>What it is.</b> A single integer 1&ndash;100 attached to this report. It is the
              <b>weight</b> Grafana uses to combine many reports into one trend line via the
              Elasticsearch <code>weighted_avg</code> aggregation. Higher = this report contributes
              more confidence to cohort averages.</p>

              <p><b>Why it exists.</b> A 5-second capture and a 10-minute capture are not equal evidence.
              Treating them as equal averages noise alongside signal. Report Value lets dashboards
              weight long, clean, on-target captures higher than short, corrupt, or off-target ones &mdash;
              without filtering anything out.</p>

              <p><b>How it is calculated.</b> Four components, each 0&ndash;1, combined and scaled to 100:</p>
              <table style="margin:6px 0 6px 12px;border-collapse:collapse;font-size:12px;">
                <tr><th align="left" style="padding:2px 10px 2px 0;">Component</th>
                    <th align="left" style="padding:2px 10px 2px 0;">Weight</th>
                    <th align="left" style="padding:2px 10px 2px 0;">Formula</th>
                    <th align="left" style="padding:2px 10px 2px 0;">Caps at</th></tr>
                <tr><td style="padding:2px 10px 2px 0;">Volume</td>
                    <td style="padding:2px 10px 2px 0;">50%</td>
                    <td style="padding:2px 10px 2px 0;"><code>min(frame_count / 36000, 1)</code></td>
                    <td style="padding:2px 10px 2px 0;">10 min @ 60 fps</td></tr>
                <tr><td style="padding:2px 10px 2px 0;">Duration</td>
                    <td style="padding:2px 10px 2px 0;">25%</td>
                    <td style="padding:2px 10px 2px 0;"><code>min(duration_s / 600, 1)</code></td>
                    <td style="padding:2px 10px 2px 0;">10 min wall clock</td></tr>
                <tr><td style="padding:2px 10px 2px 0;">Consistency</td>
                    <td style="padding:2px 10px 2px 0;">10%</td>
                    <td style="padding:2px 10px 2px 0;">observed_fps within &plusmn;25% of target</td>
                    <td style="padding:2px 10px 2px 0;">1.0 if in band</td></tr>
                <tr><td style="padding:2px 10px 2px 0;">Completeness</td>
                    <td style="padding:2px 10px 2px 0;">15%</td>
                    <td style="padding:2px 10px 2px 0;"><code>1 - (missing_fields / expected_fields)</code></td>
                    <td style="padding:2px 10px 2px 0;">21 expected fields</td></tr>
              </table>
              <p style="margin:6px 0;"><code>report_value = round(100 &times; (0.50&middot;V + 0.25&middot;D + 0.10&middot;C + 0.15&middot;K))</code>,
              clamped to <code>[1, 100]</code>.</p>

              <p><b>What raises it.</b></p>
              <ul style="margin:4px 0 4px 18px;padding:0;">
                <li><b>Longer captures.</b> Aim for 10 minutes (36,000 frames at 60 fps) to max the volume +
                duration components &mdash; 75% of the score.</li>
                <li><b>Match the target framerate.</b> If the build targets 60 fps, capture in a scenario that
                actually runs near 60. Wildly off ratios kill the consistency component.</li>
                <li><b>Healthy metadata.</b> Make sure <code>DeviceProfile</code>, <code>BuildVersion</code>,
                <code>CSVId</code>, and the like are present in the CSV footer. Each missing expected field
                shaves the completeness component.</li>
                <li><b>Configure BaseDeviceProfiles.ini in Cerebrus.</b> Lets the converter resolve
                Scalability Tier, removing a sentinel from <code>device_tier</code>.</li>
              </ul>

              <p><b>What lowers it.</b></p>
              <ul style="margin:4px 0 4px 18px;padding:0;">
                <li><b>Short runs.</b> A 30-second capture caps the volume component at ~5% and duration at
                ~5% &mdash; ceiling already &lt; 25 before quality is even considered.</li>
                <li><b>Hitchy or off-target captures.</b> If observed framerate is far from the target, the
                consistency band is missed.</li>
                <li><b>Truncated or corrupt CSV.</b> Missing footer markers (<code>[csvid]</code>,
                <code>[deviceprofile]</code>, <code>[buildversion]</code>) flip fields to sentinels and
                drop completeness.</li>
                <li><b>Data quality failure.</b> When <code>data_quality_has_corruption = 1</code>,
                Report Value falls fast because many expected fields go missing at once.</li>
              </ul>

              <p><b>How Grafana uses it.</b> Every weighted_avg panel passes
              <code>weight = report_value</code>. A run with Report Value 55 contributes ~5&times; more to
              the cohort average than one with Report Value 11, so a single 5-minute clean capture can
              outweigh ten noisy 10-second blips &mdash; the trend line follows the trustworthy data.</p>

              <p><b>Practical targets.</b> 50+ is a strong report. 30&ndash;50 is acceptable trend fodder.
              Below 25 is a short or partial capture; usable but should not dominate dashboards.
              Below 10 typically means corruption; investigate the source.</p>
            </div>
          </details>
        </td></tr>
        """

        content = html_file.read_text(encoding="utf-8")
        pattern = re.compile(
            r"(<tr[^>]*>.*?Frame\s*count.*?</tr>)", re.IGNORECASE | re.DOTALL
        )
        match = pattern.search(content)

        if match:
            insertion_point = match.end()
            new_content = (
                content[:insertion_point] + extra_rows + content[insertion_point:]
            )
            new_content = _inject_cerebrus_metadata_script(new_content, metadata)
            html_file.write_text(new_content, encoding="utf-8")
            log_message(
                state, "SUCCESS", f"Metadata successfully appended to {html_file.name}"
            )
        else:
            log_message(
                state,
                "WARNING",
                f"Metadata injection failed: Could not find 'Frame count' row.",
            )

    except Exception as e:
        log_message(state, "ERROR", f"Failed to inject metadata: {e}")


def _post_process_perf_report(state: UIState, file_path: Path) -> None:
    if not file_path.exists():
        return

    try:
        content = file_path.read_text(encoding="utf-8")
        chart_start_match = re.search(r"FPSChart", content)
        if not chart_start_match:
            return

        table_start_match = re.search(r"<table", content[chart_start_match.end() :])
        if not table_start_match:
            return

        real_table_start_idx = chart_start_match.end() + table_start_match.start()
        table_end_match = re.search(r"</table>", content[real_table_start_idx:])
        if not table_end_match:
            return

        real_table_end_idx = real_table_start_idx + table_end_match.end()
        table_content = content[real_table_start_idx:real_table_end_idx]

        if "Frametime" in table_content:
            header_pattern = re.compile(
                r"(<th[^>]*>.*?Frametime.*?</th>)", re.IGNORECASE | re.DOTALL
            )
            if header_pattern.search(table_content):
                table_content = header_pattern.sub(
                    r"\1<th style=\"background-color:#e0e0e0\">FPS Avg</th>",
                    table_content,
                    count=1,
                )

        def row_processor(match):
            row_html = match.group(0)
            if "<th" in row_html:
                return row_html
            cells_match = list(
                re.finditer(r"(<td[^>]*>.*?</td>)", row_html, re.IGNORECASE | re.DOTALL)
            )
            if not cells_match:
                return row_html

            target_idx = 5
            if len(cells_match) > target_idx:
                try:
                    cell_html = cells_match[target_idx].group(0)
                    cell_text = re.sub(r"<[^>]+>", "", cell_html).strip()
                    frametime = float(cell_text)

                    if frametime > 0:
                        fps = 1000.0 / frametime
                        color = (
                            "#87d387"
                            if fps >= 59.99
                            else "#ff6666" if fps <= 30.0 else "#ffedcc"
                        )
                        new_cell = f'<td bgcolor="{color}" style="font-weight:bold;">{fps:.2f}</td>'
                        target_end = cells_match[target_idx].end()
                        return row_html[:target_end] + new_cell + row_html[target_end:]
                except ValueError:
                    pass
            return row_html

        new_table_content = re.sub(
            r"<tr[^>]*>.*?</tr>", row_processor, table_content, flags=re.DOTALL
        )
        new_content = (
            content[:real_table_start_idx]
            + new_table_content
            + content[real_table_end_idx:]
        )
        file_path.write_text(new_content, encoding="utf-8")
        log_message(state, "SUCCESS", "Added FPS Avg column to report.")

    except Exception as e:
        log_message(state, "ERROR", f"Failed to post-process report: {e}")


def _inject_percentile_gauges_into_report(
    state: UIState, csv_file: Path, html_file: Path
) -> None:
    if not html_file.exists() or not csv_file.exists():
        return

    fps_values = []
    try:
        with open(csv_file, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return

            frame_time_idx = -1
            for i, col in enumerate(header):
                if col.strip().lower() == "frametime":
                    frame_time_idx = i
                    break

            if frame_time_idx == -1:
                log_message(
                    state,
                    "WARNING",
                    "FrameTime column not found in CSV. Cannot generate percentiles.",
                )
                return

            for row in reader:
                if len(row) > frame_time_idx:
                    try:
                        ft = float(row[frame_time_idx].strip())
                        if ft > 0:
                            fps_values.append(1000.0 / ft)
                    except ValueError:
                        pass
    except Exception as e:
        log_message(state, "ERROR", f"Failed to read CSV for percentiles: {e}")
        return

    if not fps_values:
        log_message(state, "WARNING", "No valid FrameTime data found for percentiles.")
        return

    fps_values.sort()
    n = len(fps_values)

    p1 = fps_values[int(n * 0.01)]
    p5 = fps_values[int(n * 0.05)]
    p50 = fps_values[int(n * 0.50)]
    p90 = fps_values[int(n * 0.90)]
    p95 = fps_values[int(n * 0.95)]
    p99 = fps_values[int(n * 0.99)]

    import statistics

    try:
        sd_val = statistics.stdev(fps_values) if n > 1 else 0.0
    except statistics.StatisticsError:
        sd_val = 0.0

    p75 = fps_values[int(n * 0.75)]
    p25 = fps_values[int(n * 0.25)]
    iqr_val = p75 - p25

    metadata = _read_csv_metadata(csv_file)
    target_fps_str = metadata.get("targetframerate", "60")
    try:
        target_fps = float(target_fps_str)
    except ValueError:
        target_fps = 60.0

    def generate_svg(title, value, target):
        max_val = max(90.0, target * 1.5)
        radius = 80
        stroke_width = 20
        circumference = math.pi * radius

        val_clamped = min(max(value, 0), max_val)
        fill_percentage = val_clamped / max_val
        fill_length = fill_percentage * circumference

        target_percentage = min(target / max_val, 1.0)
        angle = math.pi * (1.0 - target_percentage)
        outer_r = radius + stroke_width / 2.0
        inner_r = radius - stroke_width / 2.0

        x_target = 100 + outer_r * math.cos(angle)
        y_target = 90 - outer_r * math.sin(angle)
        x_target_inner = 100 + inner_r * math.cos(angle)
        y_target_inner = 90 - inner_r * math.sin(angle)

        fill_color = "#a67f59"
        bg_color = "#d9d9d9"

        svg = f"""
        <div class="gauge-wrapper" style="text-align: center; width: 250px; margin: 10px;">
            <div class="gauge-title" style="font-size: 14px; margin-bottom: 10px; color: #333;">{title}</div>
            <svg class="gauge-svg" viewBox="0 0 200 110" style="width: 100%; height: auto;">
                <path d="M 20 90 A 80 80 0 0 1 180 90" fill="none" stroke="{bg_color}" stroke-width="{stroke_width}" stroke-linecap="butt"/>
                <path d="M 20 90 A 80 80 0 0 1 180 90" fill="none" stroke="{fill_color}" stroke-width="{stroke_width}" stroke-linecap="butt" 
                      stroke-dasharray="{circumference}" stroke-dashoffset="{circumference - fill_length}"/>
                <line x1="{x_target_inner}" y1="{y_target_inner}" x2="{x_target}" y2="{y_target}" stroke="black" stroke-width="3"/>
                <text x="100" y="60" style="font-size: 12px; fill: #666; text-anchor: middle;">{title.split(',')[0]}</text>
                <text x="100" y="85" style="font-size: 24px; fill: #333; text-anchor: middle;">{value:.1f}</text>
                <text x="20" y="105" style="font-size: 12px; fill: #666; text-anchor: middle;">0</text>
                <text x="180" y="105" style="font-size: 12px; fill: #666; text-anchor: middle;">{int(max_val)}</text>
            </svg>
        </div>
        """
        return svg

    gauges_html = '<div class="gauges-container" style="border: 1px solid #ccc; border-radius: 8px; padding: 20px; margin: 20px 0; font-family: sans-serif; background-color: #fcfcfc;">'
    gauges_html += '<div style="display: flex; justify-content: space-around; margin-bottom: 20px; flex-wrap: wrap;">'
    gauges_html += generate_svg(
        f"99th Percentile, Target is {int(target_fps)}", p99, target_fps
    )
    gauges_html += generate_svg(
        f"95th Percentile, Target is {int(target_fps)}", p95, target_fps
    )
    gauges_html += '</div><div style="display: flex; justify-content: space-around; margin-bottom: 20px; flex-wrap: wrap;">'
    gauges_html += generate_svg(
        f"1st Percentile, Target is {int(target_fps)}", p1, target_fps
    )
    gauges_html += generate_svg(
        f"5th Percentile, Target is {int(target_fps)}", p5, target_fps
    )
    gauges_html += generate_svg(
        f"50th Percentile, Target is {int(target_fps)}", p50, target_fps
    )
    gauges_html += generate_svg(
        f"90th Percentile, Target is {int(target_fps)}", p90, target_fps
    )
    gauges_html += "</div>"

    stats_html = f"""
    <div style="margin-top: 20px;">
        <h3 style="margin-top: 0; margin-bottom: 15px; color: #333; font-family: 'Segoe UI', Tahoma, sans-serif;">Statistical Metrics Breakdown</h3>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; font-family: 'Segoe UI', Tahoma, sans-serif;">
            
            <div style="background: #e3f2fd; border-left: 5px solid #1e88e5; padding: 15px; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <h4 style="margin-top: 0; color: #1565c0; font-size: 16px;">📉 Standard Deviation (SD): {sd_val:.2f} FPS</h4>
                <p style="font-size: 13px; color: #333; margin-bottom: 6px;"><strong>What it is:</strong> Measures the amount of variation or dispersion of FPS values from the average.</p>
                <p style="font-size: 13px; color: #333; margin-bottom: 6px;"><strong>Why it matters:</strong> A high SD indicates erratic performance (stuttering). Even if the average FPS is high, visual stutters make the experience feel poor.</p>
                <p style="font-size: 13px; color: #333; margin-bottom: 0;"><strong>How to utilize:</strong> Use SD to compare the overall stability between builds. The build with the lower SD always provides a progressively smoother gameplay experience.</p>
            </div>

            <div style="background: #f3e5f5; border-left: 5px solid #8e24aa; padding: 15px; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <h4 style="margin-top: 0; color: #6a1b9a; font-size: 16px;">⚖️ Interquartile Range (IQR): {iqr_val:.2f} FPS</h4>
                <p style="font-size: 13px; color: #333; margin-bottom: 6px;"><strong>What it is:</strong> The spread of the middle 50% of frames (75th percentile minus 25th percentile).</p>
                <p style="font-size: 13px; color: #333; margin-bottom: 6px;"><strong>Why it matters:</strong> Unlike SD, IQR ignores extreme statistical outliers (random rare hitches) and tells you how consistent the "typical" gameplay feels.</p>
                <p style="font-size: 13px; color: #333; margin-bottom: 0;"><strong>How to utilize:</strong> Target a low IQR. If SD is high but IQR is low, you have isolated, large hitches. If IQR is high, the game's core base performance simply fluctuates too much.</p>
            </div>

            <div style="background: #fff3e0; border-left: 5px solid #e53935; padding: 15px; border-radius: 6px; box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
                <h4 style="margin-top: 0; color: #c62828; font-size: 16px;">⏱️ Percentiles (1st, 5th, 50th, 95th, 99th)</h4>
                <p style="font-size: 13px; color: #333; margin-bottom: 6px;"><strong>What they are:</strong> Percentiles are computed from each frame's <strong>FrameTime</strong> converted to FPS. The <strong>1st/5th Percentile</strong> graphs show the FPS of the worst 1% and 5% of frame samples (the "lows"). The <strong>50th</strong> is your median FPS. The <strong>95th/99th</strong> show your peak smoothness.</p>
                <p style="font-size: 13px; color: #333; margin-bottom: 6px;"><strong>Why they matter:</strong> Look at the <strong>1st Percentile gauge</strong> to see your true baseline performance. High average FPS can successfully hide game-breaking hitches, but 1st/5th Percentiles completely expose them.</p>
                <p style="font-size: 13px; color: #333; margin-bottom: 0;"><strong>How to utilize:</strong> Prioritize optimizing the <strong>1st and 5th Percentile gauges</strong> to meet your target FPS. Raising the frame-rate floor (lows) is much more critical for perceived smoothness than raising the ceiling (99th).</p>
            </div>

        </div>
    </div>
    """
    gauges_html += stats_html
    gauges_html += "</div>"

    try:
        content = html_file.read_text(encoding="utf-8")
        hitches_match = re.search(
            r"(<h\d[^>]*>.*?Hitches.*?</h\d>.*?</table>)",
            content,
            re.IGNORECASE | re.DOTALL,
        )

        if hitches_match:
            insertion_point = hitches_match.end()
            new_content = (
                content[:insertion_point] + gauges_html + content[insertion_point:]
            )
            html_file.write_text(new_content, encoding="utf-8")
            log_message(state, "SUCCESS", "Injected Percentile Gauges.")
        else:
            tables = list(re.finditer(r"</table>", content, re.IGNORECASE))
            if tables:
                insertion_point = tables[-1].end()
                new_content = (
                    content[:insertion_point] + gauges_html + content[insertion_point:]
                )
                html_file.write_text(new_content, encoding="utf-8")
                log_message(state, "SUCCESS", "Injected Percentile Gauges (Fallback).")
    except Exception as e:
        log_message(state, "ERROR", f"Failed to inject gauges into HTML: {e}")


def _inject_battery_thermal_into_report(
    state: UIState, thermal_samples: list, html_file: Path
) -> None:
    """Add a 'Battery Thermal' tab to an already-generated perf report,
    reusing the same tab bar that `_inject_raw_csv_into_report` creates.
    Must run after that function, since it relies on the tab bar already
    existing in the file.
    """
    if not html_file.exists() or not thermal_samples:
        return

    content = html_file.read_text(encoding="utf-8")

    raw_csv_button_marker = (
        '<button class="perf-tab-btn" onclick="openPerfTab(event, \'RawCSVTab\')">'
        "Raw CSV Data</button>"
    )
    if raw_csv_button_marker not in content:
        # Tab bar doesn't exist yet (e.g. raw CSV injection failed/was
        # skipped) - nothing safe to attach the new tab to.
        log_message(
            state, "WARNING", "Could not find tab bar to attach Battery Thermal tab."
        )
        return

    new_button = (
        raw_csv_button_marker
        + '\n  <button class="perf-tab-btn" onclick="openPerfTab(event, \'BatteryThermalTab\')">'
        "Battery Thermal</button>"
    )
    content = content.replace(raw_csv_button_marker, new_button, 1)

    temps = [s.temp_c for s in thermal_samples]
    min_temp, max_temp = min(temps), max(temps)
    avg_temp = sum(temps) / len(temps)
    duration = thermal_samples[-1].elapsed_seconds
    peak_label, peak_color = _status_for_temp(max_temp)
    chart_svg = _build_svg_chart(thermal_samples)

    thermal_tab = f"""
<div id="BatteryThermalTab" class="perf-tab-content">
    <h2 style="font-family: sans-serif; color: #ddd;">Battery Thermal</h2>
    <div style="display:flex; gap:16px; margin-bottom:20px; flex-wrap:wrap; font-family: sans-serif;">
        <div style="background:#2d2d2d; border-radius:8px; padding:14px 20px; min-width:140px;">
            <div style="color:#999; font-size:12px; text-transform:uppercase;">Peak Temp</div>
            <div style="font-size:22px; font-weight:600; color:{peak_color};">{max_temp:.1f}&#176;C ({peak_label})</div>
        </div>
        <div style="background:#2d2d2d; border-radius:8px; padding:14px 20px; min-width:140px;">
            <div style="color:#999; font-size:12px; text-transform:uppercase;">Min Temp</div>
            <div style="font-size:22px; font-weight:600; color:#ddd;">{min_temp:.1f}&#176;C</div>
        </div>
        <div style="background:#2d2d2d; border-radius:8px; padding:14px 20px; min-width:140px;">
            <div style="color:#999; font-size:12px; text-transform:uppercase;">Average Temp</div>
            <div style="font-size:22px; font-weight:600; color:#ddd;">{avg_temp:.1f}&#176;C</div>
        </div>
        <div style="background:#2d2d2d; border-radius:8px; padding:14px 20px; min-width:140px;">
            <div style="color:#999; font-size:12px; text-transform:uppercase;">Duration</div>
            <div style="font-size:22px; font-weight:600; color:#ddd;">{duration:.0f}s</div>
        </div>
        <div style="background:#2d2d2d; border-radius:8px; padding:14px 20px; min-width:140px;">
            <div style="color:#999; font-size:12px; text-transform:uppercase;">Samples</div>
            <div style="font-size:22px; font-weight:600; color:#ddd;">{len(thermal_samples)}</div>
        </div>
    </div>
    <div style="background:#1e1e1e; padding:15px; border-radius:6px; border:1px solid #444;">
        {chart_svg}
    </div>
</div>
"""

    insertion_point = content.rfind("</body>")
    if insertion_point == -1:
        log_message(state, "WARNING", "Could not find </body> to inject Battery Thermal tab.")
        return

    content = content[:insertion_point] + thermal_tab + content[insertion_point:]
    html_file.write_text(content, encoding="utf-8")
    log_message(state, "SUCCESS", "Injected Battery Thermal Tab.")


def _inject_raw_csv_into_report(
    state: UIState, csv_file: Path, html_file: Path
) -> None:
    if not html_file.exists() or not csv_file.exists():
        return

    try:
        content = html_file.read_text(encoding="utf-8")
        csv_content = csv_file.read_text(encoding="utf-8", errors="ignore")

        import html

        escaped_csv = html.escape(csv_content)

        tab_css_and_js = """
<style>
.perf-tabs { display: flex; border-bottom: 2px solid #3b82f6; background: #2d2d2d; padding: 10px 10px 0 10px; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; position: sticky; top: 0; z-index: 100; }
.perf-tab-btn { padding: 10px 20px; background: none; border: none; color: #aaa; cursor: pointer; font-size: 15px; transition: 0.3s; margin-right: 5px; border-radius: 6px 6px 0 0; font-weight: 500; }
.perf-tab-btn:hover { color: #fff; background-color: rgba(255, 255, 255, 0.05); }
.perf-tab-btn.active { background-color: #3b82f6; color: white; }
.perf-tab-content { display: none; padding: 20px; }
.perf-tab-content.active { display: block; animation: fadeIn 0.3s ease; }
.download-btn { background-color: #3b82f6; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; font-size: 14px; font-weight: bold; transition: 0.2s; margin-bottom: 15px; box-shadow: 0 2px 4px rgba(0,0,0,0.2); }
.download-btn:hover { background-color: #2563eb; transform: translateY(-1px); }
@keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
</style>
<script>
function openPerfTab(evt, tabName) {
  var i, tabcontent, tablinks;
  tabcontent = document.getElementsByClassName("perf-tab-content");
  for (i = 0; i < tabcontent.length; i++) { tabcontent[i].classList.remove("active"); }
  tablinks = document.getElementsByClassName("perf-tab-btn");
  for (i = 0; i < tablinks.length; i++) { tablinks[i].classList.remove("active"); }
  document.getElementById(tabName).classList.add("active");
  evt.currentTarget.classList.add("active");
}
function downloadRawCSV() {
    var csvText = document.getElementById("rawCsvDataHidden").textContent;
    // Decode HTML entities safely just in case although it's pre formatted
    var textarea = document.createElement("textarea");
    textarea.innerHTML = csvText;
    
    var blob = new Blob([textarea.value], { type: 'text/csv;charset=utf-8;' });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = "RAW_EXPORT.csv";
    link.style.display = 'none';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}
</script>
<div class="perf-tabs">
  <button class="perf-tab-btn active" onclick="openPerfTab(event, 'PerfReportTab')">Performance Report</button>
  <button class="perf-tab-btn" onclick="openPerfTab(event, 'RawCSVTab')">Raw CSV Data</button>
</div>
<div id="PerfReportTab" class="perf-tab-content active">
"""

        # Replace <body> with <body> + tab_css_and_js so original content goes into PerfReportTab
        body_idx = content.lower().find("<body")
        if body_idx != -1:
            end_body_idx = content.find(">", body_idx) + 1
            new_content = (
                content[:end_body_idx] + "\n" + tab_css_and_js + content[end_body_idx:]
            )
        else:
            new_content = content

        original_filename = csv_file.name

        csv_tab = f"""
</div>
<div id="RawCSVTab" class="perf-tab-content">
    <h2 style="font-family: sans-serif;">Raw Profiling Data</h2>
    <p style="font-family: sans-serif; color: #555; margin-bottom: 20px;">This tab contains the raw CSV data originally generated by the Unreal Engine. You can extract it back out for external analysis using the button below.</p>
    <button class="download-btn" onclick="downloadRawCSV()">⬇️ Download CSV File</button>
    <pre id="rawCsvDataHidden" style="display:none;">{escaped_csv}</pre>
    <div style="background: #1e1e1e; padding: 15px; border-radius: 6px; overflow-x: auto; max-height: 80vh; overflow-y: auto; border: 1px solid #444;">
        <pre style="color: #d4d4d4; font-family: Consolas, monospace; font-size: 12px; margin: 0;">{escaped_csv}</pre>
    </div>
</div>
<script>
    // Update the download link with the actual filename dynamically to bypass f-string limits if needed
    var dlBtn = document.querySelector(".download-btn");
    dlBtn.onclick = function() {{
        var csvText = document.getElementById("rawCsvDataHidden").textContent;
        var textarea = document.createElement("textarea");
        textarea.innerHTML = csvText;
        var blob = new Blob([textarea.value], {{ type: 'text/csv;charset=utf-8;' }});
        var url = URL.createObjectURL(blob);
        var link = document.createElement("a");
        link.href = url;
        link.download = "{original_filename}";
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    }};
</script>
"""
        # Find the closing </body> tag to end the tabs before it
        insertion_point = new_content.rfind("</body>")
        if insertion_point != -1:
            new_content = (
                new_content[:insertion_point] + csv_tab + new_content[insertion_point:]
            )
            html_file.write_text(new_content, encoding="utf-8")
            log_message(state, "SUCCESS", "Injected RAW CSV Tab.")
        else:
            log_message(state, "WARNING", "Could not find </body> to inject RAW CSV.")

    except Exception as e:
        log_message(state, "ERROR", f"Failed to inject RAW CSV: {e}")
