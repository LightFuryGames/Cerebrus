from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path
from tkinter import Tk, filedialog
import dearpygui.dearpygui as dpg

from cerebrus.ui.state import UIState
from cerebrus.ui.components.shared import log_message, _auto_save_profile
from cerebrus.ui.components.file_manager import _handle_output_file_name_change, _handle_use_prefix_toggle, _open_html_file, _open_all_html_files
from cerebrus.ui.components.ui_config import UIConfig


# Helper for DPG callbacks
def _handle_path_selected_generic(state: UIState, path_type: str, app_data: dict) -> None:
    # Generic handler for DPG file dialog
    selection = app_data.get("file_path_name") or next(
        iter(app_data.get("selections", {}).values()), None
    )
    if selection is None:
        return

    path = Path(selection)
    
    if path_type == "input":
        if not path.exists():
            return
        state.input_path = path
        if dpg.does_item_exist("input_path_label"):
            dpg.set_value("input_path_label", str(path))
        # trigger save if needed
        _auto_save_profile(state)
        
    elif path_type == "output":
         state.output_path = path
         state.input_path = path # sync
         state.base_output_path = path # sync base
         if dpg.does_item_exist("output_path_label"):
             dpg.set_value("output_path_label", str(path))
         _auto_save_profile(state)


def _browse_folder_native(state: UIState, purpose: str = "output") -> None:
    """Open native directory selector dialog."""
    try:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        initial_dir = str(state.output_path) if state.output_path.exists() else None
        
        path_str = filedialog.askdirectory(
            title="Select Folder",
            initialdir=initial_dir
        )

        root.destroy()

        if path_str:
            path = Path(path_str)
            if purpose == "output":
                state.output_path = path
                # Sync input path if needed?
                # In original code, output path change synced input path unless separate
                state.input_path = path 
                state.base_output_path = path # Set base path explicitly
                
                if dpg.does_item_exist("output_path_label"):
                    dpg.set_value("output_path_label", str(path))
            elif purpose == "config_output":
                 state.config_output_path = path
                 state.base_config_output_path = path
                 if dpg.does_item_exist("config_output_path_label"):
                    dpg.set_value("config_output_path_label", str(path))

            _auto_save_profile(state)

    except Exception as e:
        log_message(state, "ERROR", f"Failed to browse folder: {e}")


def _register_file_dialogs(state: UIState) -> None:
    config = UIConfig.get_instance()
    if not dpg.does_item_exist("input_path_dialog"):
        settings = config.get_component_settings("input_path_dialog")
        # Callback needs to be added manually as it contains lambda
        with dpg.file_dialog(
            callback=lambda s, a: _handle_path_selected_generic(state, "input", a),
            **settings
        ):
            dpg.add_file_extension(".csv", color=(0, 120, 255, 255))
            dpg.add_file_extension(".txt", color=(120, 255, 120, 255))
            dpg.add_file_extension(".*")

    if not dpg.does_item_exist("output_path_dialog"):
        settings = config.get_component_settings("output_path_dialog")
        with dpg.file_dialog(
            callback=lambda s, a: _handle_path_selected_generic(state, "output", a),
            **settings
        ):
            dpg.add_file_extension(".*")


def _show_html_file_selector(state: UIState, html_files: list) -> None:
    """Show a dialog to select and open HTML files."""
    if dpg.does_item_exist("html_viewer_dialog"):
        dpg.delete_item("html_viewer_dialog")

    config = UIConfig.get_instance()
    with dpg.window(**config.get_component_settings("html_viewer_dialog")):
        from cerebrus.ui.themes import get_theme_manager
        dpg.bind_item_theme(dpg.add_text("Available HTML Log Files:"), get_theme_manager().get_header_theme())
        dpg.add_separator()

        with dpg.child_window(**config.get_component_settings("html_viewer_list")):
            for html_file in html_files:
                # Get file modification time
                from datetime import datetime

                mtime = datetime.fromtimestamp(html_file.stat().st_mtime)
                time_str = mtime.strftime("%Y-%m-%d %H:%M:%S")

                # Create a button for each file
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label=f"📄 {html_file.name}",
                        width=400,
                        callback=lambda s, a, u: _open_html_file(state, u),
                        user_data=html_file,
                    )
                    dpg.add_text(f"Modified: {time_str}", color=(150, 150, 150))

        dpg.add_separator()
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Open All",
                width=config.get_dimension("button_width_standard"),
                callback=lambda: _open_all_html_files(state, html_files),
            )
            dpg.add_button(
                label="Close",
                width=config.get_dimension("button_width_standard"),
                callback=lambda: dpg.delete_item("html_viewer_dialog"),
            )
