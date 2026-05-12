from __future__ import annotations

from datetime import datetime
from pathlib import Path
from tkinter import Tk, filedialog

import dearpygui.dearpygui as dpg

from ....state import UIState
from ....themes import get_theme_manager


def log_message(state: UIState, level: str, message: str) -> None:
    timestamp = datetime.now().strftime("%d-%m-%y %H:%M:%S")
    state.logs.append((timestamp, level, message))

    # Constantly keep a temporary overwriteable file for ease of multi-line selection
    try:
        from cerebrus.core.paths import get_debug_dir

        debug_dir = get_debug_dir()
        debug_dir.mkdir(parents=True, exist_ok=True)
        live_log_file = debug_dir / "live_logs.txt"
        # Always append to keep it "active"
        with open(live_log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{level}] {message}\n")
    except Exception:
        pass

    _render_log_entries(state)


def _render_log_entries(state: UIState) -> None:
    try:
        if not dpg.is_dearpygui_running():
            return
        if not dpg.does_item_exist("log_container"):
            return

        dpg.delete_item("log_container", children_only=True)
        filter_value = state.log_filter.lower() if state.log_filter else ""

        all_logs = state.logs
        if len(all_logs) > 1000:
            display_logs = all_logs[-1000:]
        else:
            display_logs = all_logs

        filtered_logs = [
            entry
            for entry in display_logs
            if filter_value in entry[1].lower() or filter_value in entry[2].lower()
        ]

        if not filtered_logs:
            dpg.add_text(
                "No log entries match the filter.",
                color=(180, 180, 180),
                parent="log_container",
            )
            return

        tm = get_theme_manager()

        # Group adjacent entries by level so users can select multi-line substrings
        # while preserving the level color for each visible block.
        grouped_logs = []
        for timestamp, level, message in filtered_logs:
            full_msg = f"[{timestamp}] [{level}] {message}"
            if grouped_logs and grouped_logs[-1]["level"] == level:
                grouped_logs[-1]["lines"].append(full_msg)
            else:
                grouped_logs.append({"level": level, "lines": [full_msg]})

        for group in grouped_logs:
            level = group["level"]
            block_text = "\n".join(group["lines"])
            line_count = max(1, block_text.count("\n") + 1)
            height = max(24, min(260, 18 * line_count + 8))
            item = dpg.add_input_text(
                default_value=block_text,
                readonly=True,
                multiline=True,
                width=-1,
                height=height,
                parent="log_container",
            )

            with dpg.theme() as block_theme:
                with dpg.theme_component(dpg.mvAll):
                    dpg.add_theme_color(dpg.mvThemeCol_FrameBg, (0, 0, 0, 0))
                    dpg.add_theme_color(dpg.mvThemeCol_FrameBgHovered, (40, 40, 40, 40))
                    dpg.add_theme_color(dpg.mvThemeCol_FrameBgActive, (60, 60, 60, 40))
                    dpg.add_theme_color(dpg.mvThemeCol_Border, (0, 0, 0, 0))
                    dpg.add_theme_style(dpg.mvStyleVar_FramePadding, 0, 1)
                    dpg.add_theme_style(dpg.mvStyleVar_ItemSpacing, 0, 0)
                    text_color = tm.get_log_colors().get(level.upper(), (200, 200, 200))
                    dpg.add_theme_color(dpg.mvThemeCol_Text, text_color)

            dpg.bind_item_theme(item, block_theme)

            with dpg.popup(item):
                dpg.add_menu_item(
                    label="Copy Block",
                    callback=lambda s, a, u: _copy_to_clipboard(u),
                    user_data=block_text,
                )

        dpg.set_y_scroll("log_container", -1.0)
    except Exception as e:
        print(f"ERROR in _render_log_entries: {e}")


def _copy_to_clipboard(text: str) -> None:
    try:
        from tkinter import Tk

        r = Tk()
        r.withdraw()
        r.clipboard_clear()
        r.clipboard_append(text)
        r.update()
        r.destroy()
    except Exception:
        pass


def _clear_logs(state: UIState) -> None:
    state.logs.clear()
    try:
        from cerebrus.core.paths import get_debug_dir

        live_log_file = get_debug_dir() / "live_logs.txt"
        if live_log_file.exists():
            with open(live_log_file, "w", encoding="utf-8") as f:
                f.truncate(0)
    except Exception:
        pass
    _render_log_entries(state)


def _handle_export_logs(state: UIState) -> None:
    """Export current logs to a text file."""
    try:
        # Re-import because of dynamic callback scope
        from tkinter import Tk, filedialog

        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        file_path = filedialog.asksaveasfilename(
            title="Export Logs",
            defaultextension=".log",
            filetypes=[
                ("Log Files", "*.log"),
                ("Text Files", "*.txt"),
                ("All Files", "*.*"),
            ],
        )

        root.destroy()

        if file_path:
            with open(file_path, "w", encoding="utf-8") as f:
                for timestamp, level, message in state.logs:
                    f.write(f"[{timestamp}] [{level}] {message}\n")

            log_message(state, "SUCCESS", f"Logs exported to {file_path}")

    except Exception as e:
        log_message(state, "ERROR", f"Failed to export logs: {e}")


def _handle_log_filter(sender, app_data, user_data) -> None:
    """Handle log filtering input."""
    state = user_data
    if state:
        state.log_filter = app_data
        _render_log_entries(state)
