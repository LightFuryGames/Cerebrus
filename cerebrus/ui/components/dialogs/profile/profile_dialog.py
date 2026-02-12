from __future__ import annotations

from pathlib import Path
from tkinter import Tk, filedialog

import dearpygui.dearpygui as dpg

from cerebrus.ui.components.shared import _auto_save_profile, log_message
from cerebrus.ui.components.ui_config import UIConfig
from cerebrus.ui.state import UIState
from cerebrus.ui.themes import get_theme_manager


def _show_profile_dialog(state: UIState, is_edit: bool = False) -> None:
    if is_edit:
        # Check if default profile
        if not state.profile_manager.current_profile_path:
            # Show warning and log it
            log_message(
                state,
                "WARNING",
                "Cannot edit Default Profile. Please create a New Profile or Open an existing one.",
            )
            if not dpg.does_item_exist("default_profile_warning"):
                config = UIConfig.get_instance()
                settings = config.get_component_settings("profile_warning_modal")
                settings["no_resize"] = True

                with dpg.window(**settings):
                    dpg.add_text(
                        "Cannot edit the Default Profile.\nPlease create a New Profile or Open an existing one."
                    )
                    dpg.add_spacer(height=10)
                    with dpg.group(horizontal=True):
                        # Center: (width 400 - button 120) / 2 = 140
                        dpg.add_spacer(width=140)
                        dpg.add_button(
                            label="OK",
                            width=config.get_dimension("button_width_standard"),
                            callback=lambda: dpg.delete_item("default_profile_warning"),
                        )
            return
    else:
        # Creating new profile
        log_message(state, "INFO", "Opening New Profile dialog")
        # Mark that we're creating a new profile
        state.is_creating_new_profile = True

    if dpg.does_item_exist("profile_dialog"):
        dpg.delete_item("profile_dialog")

    title = "Edit Profile" if is_edit else "New Profile"

    # Pre-fill values ONLY if editing an existing profile
    if is_edit:
        profile = state.profile_manager.current_profile
        nickname = profile.nickname if profile else ""
        package_name = state.package_name
    else:
        # For new profiles, start with empty values
        nickname = ""
        package_name = ""

    config = UIConfig.get_instance()
    # Merge settings with title
    # Merge settings with title
    dialog_settings = config.get_component_settings("profile_dialog")
    dialog_settings["label"] = title
    dialog_settings["no_resize"] = True
    dialog_settings["no_scrollbar"] = True
    dialog_settings["width"] = 500
    dialog_settings["height"] = 180  # Increased slightly to ensure no scrollbar

    with dpg.window(**dialog_settings):
        # Use a table with fixed widths to avoid wastage
        with dpg.table(header_row=False, policy=dpg.mvTable_SizingFixedFit):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=120)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=350)

            with dpg.table_row():
                dpg.add_text("Profile Name:")
                dpg.add_input_text(
                    tag="pd_nickname", default_value=nickname or "", width=-1
                )

            with dpg.table_row():
                dpg.add_text("Package Name:")
                dpg.add_input_text(
                    tag="pd_package_name", default_value=package_name, width=-1
                )

        dpg.add_spacer(height=15)
        dpg.add_separator()
        dpg.add_spacer(height=10)

        with dpg.group(horizontal=True):
            # Calculate spacer to center: (window_width - (btn1_width + spacing + btn2_width)) / 2
            # (500 - (80 + 8 + 80)) / 2 = (500 - 168) / 2 = 166
            dpg.add_spacer(width=166)
            dpg.add_button(
                label="Save",
                width=80,
                callback=lambda: _handle_profile_save(state, is_edit),
            )
            dpg.add_button(
                label="Cancel",
                width=80,
                callback=lambda: dpg.delete_item("profile_dialog"),
            )


def _handle_profile_save(state: UIState, is_edit: bool) -> None:
    package_name = dpg.get_value("pd_package_name")
    nickname = dpg.get_value("pd_nickname")

    # Enhanced validation for package name format: com.{company}.{product}
    if not package_name:
        log_message(state, "ERROR", "Package Name cannot be empty.")
        return

    if not package_name.startswith("com."):
        log_message(
            state,
            "ERROR",
            f"Invalid Package Name: '{package_name}'. Package name must start with 'com.'",
        )
        return

    # Check if it has at least 3 parts: com.company.product
    parts = package_name.split(".")
    if len(parts) < 3:
        log_message(
            state,
            "ERROR",
            f"Invalid Package Name: '{package_name}'. Must have format: com.{{company}}.{{product}}",
        )
        return

    dpg.delete_item("profile_dialog")

    # Update state
    state.package_name = package_name
    if dpg.does_item_exist("package_input"):
        dpg.set_value("package_input", package_name)

    # For NEW profiles, ALWAYS prompt for save location
    # For EDIT, only prompt if no path exists (shouldn't happen but safety check)
    if not is_edit or not state.profile_manager.current_profile_path:
        # This is a new profile - prompt for location
        # Store the temp values to save after path selection
        state.temp_profile_data = {
            "nickname": nickname,
            "package_name": package_name,
            "package_name": package_name,
        }
        _save_profile_native(state, nickname)
    else:
        # Update existing profile
        profile = state.profile_manager.current_profile
        if profile:
            profile.nickname = nickname
            profile.package_name = package_name

            # Update remote configs
            # Sync Settings are now managed in the Configuration Sync panel
            # We preserve existing values but don't update them from this dialog

            state.profile_manager.save_current_profile()
            state.profile_nickname = nickname or "None"

            log_message(
                state,
                "SUCCESS",
                f"Profile '{state.profile_nickname}' saved successfully.",
            )

            # Refresh UI
            if dpg.does_item_exist("profile_nickname_input"):
                dpg.set_value("profile_nickname_input", state.profile_nickname)

            from cerebrus.ui.components.shared import _update_profile_display_colors

            _update_profile_display_colors(state)


def _save_profile_native(state: UIState, default_name: str) -> None:
    """Open native save dialog for profile."""
    try:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        default_filename = f"{default_name}.json" if default_name else "profile.json"

        file_path = filedialog.asksaveasfilename(
            title="Save Profile As",
            initialfile=default_filename,
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )

        root.destroy()

        if file_path:
            path = Path(file_path)
            _finalize_profile_save(state, path)

    except Exception as e:
        log_message(state, "ERROR", f"Failed to open save dialog: {e}")


def _finalize_profile_save(state: UIState, path: Path) -> None:
    """Complete profile creation after path selection."""
    temp_data = getattr(state, "temp_profile_data", {})
    nickname = temp_data.get("nickname")
    package_name = temp_data.get("package_name") or state.package_name

    # Update state.output_file_name from UI if exists
    if dpg.does_item_exist("output_file_name"):
        state.output_file_name = dpg.get_value("output_file_name")

    profile = state.profile_manager.create_new_profile(
        nickname=nickname, package_name=package_name, path=path
    )

    # Apply additional fields if they were in temp_data
    # Sync Settings - preserved initialized defaults if not in temp_data (which they aren't anymore)

    # Populate fields
    profile.output_file_name = state.output_file_name
    profile.input_path = str(state.input_path)
    profile.output_path = str(state.output_path)
    profile.config_output_path = str(state.config_output_path)
    profile.use_prefix_only = state.use_prefix_only

    profile.move_logs_enabled = state.move_logs_enabled
    profile.move_csv_enabled = state.move_csv_enabled
    profile.generate_perf_report_enabled = state.generate_perf_report_enabled
    profile.generate_colored_logs_enabled = state.generate_colored_logs_enabled

    # Update remote configs from dialog if tags exist
    # Sync Settings logic removed

    profile.save(path)

    log_message(state, "SUCCESS", f"New profile '{nickname}' created at {path}")

    # Update UI
    state.profile_nickname = nickname or "None"
    state.package_name = package_name
    state.profile_path = path

    if dpg.does_item_exist("profile_nickname_input"):
        dpg.set_value("profile_nickname_input", nickname or "None")
    if dpg.does_item_exist("profile_path_input"):
        dpg.set_value("profile_path_input", str(path))
    if dpg.does_item_exist("package_input"):
        dpg.set_value("package_input", package_name)

    from cerebrus.ui.components.shared import _update_profile_display_colors

    _update_profile_display_colors(state)


def _open_profile_native(state: UIState) -> None:
    """Open native open dialog for profile."""
    try:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        file_path = filedialog.askopenfilename(
            title="Open Profile",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )

        root.destroy()

        if file_path:
            path = Path(file_path)
            _load_profile_from_path(state, path)

    except Exception as e:
        log_message(state, "ERROR", f"Failed to open file dialog: {e}")


def _load_profile_from_path(state: UIState, path: Path) -> None:
    try:
        from cerebrus.core.profile import Profile

        profile = Profile.load(path)

        # Validate that required fields exist
        if not hasattr(profile, "nickname") or not hasattr(profile, "package_name"):
            raise ValueError("Profile missing required fields")

        state.profile_manager.current_profile = profile
        state.profile_manager.current_profile_path = path
        state.profile_manager.set_last_used_profile_path(path)

        log_message(state, "SUCCESS", f"Profile loaded: {profile.nickname} from {path}")

        # Update UI
        state.profile_nickname = profile.nickname or "None"
        state.package_name = profile.package_name
        state.profile_path = path

        # Load persisted fields
        state.output_file_name = profile.output_file_name
        state.input_path = Path(profile.input_path) if profile.input_path else Path("")
        state.output_path = (
            Path(profile.output_path) if profile.output_path else Path("")
        )
        state.base_output_path = state.output_path  # Set base path to loaded path

        state.config_output_path = (
            Path(profile.config_output_path) if profile.config_output_path else Path("")
        )
        state.base_config_output_path = state.config_output_path

        state.use_prefix_only = profile.use_prefix_only

        # Load bulk action states (with defaults if missing in old profiles)
        state.move_logs_enabled = getattr(profile, "move_logs_enabled", True)
        state.move_csv_enabled = getattr(profile, "move_csv_enabled", True)
        state.move_memreport_enabled = getattr(profile, "move_memreport_enabled", True)
        state.generate_perf_report_enabled = getattr(
            profile, "generate_perf_report_enabled", True
        )
        state.generate_colored_logs_enabled = getattr(
            profile, "generate_colored_logs_enabled", True
        )
        state.generate_memreport_enabled = getattr(
            profile, "generate_memreport_enabled", False
        )

        # Update UI elements
        if dpg.does_item_exist("package_input"):
            dpg.set_value("package_input", profile.package_name)

        if dpg.does_item_exist("profile_nickname_input"):
            dpg.set_value("profile_nickname_input", profile.nickname or "None")

        if dpg.does_item_exist("profile_path_input"):
            dpg.set_value("profile_path_input", str(path))

        if dpg.does_item_exist("output_file_name"):
            dpg.set_value("output_file_name", state.output_file_name)

        if dpg.does_item_exist("input_path_label"):
            dpg.set_value("input_path_label", str(state.input_path))

        if dpg.does_item_exist("output_path_label"):
            dpg.set_value("output_path_label", str(state.output_path))

        if dpg.does_item_exist("config_output_path_label"):
            dpg.set_value("config_output_path_label", str(state.config_output_path))

        if dpg.does_item_exist("remote_manifest_url_input"):
            manifest_url = state.remote_manifest_url
            if profile.aws_config and profile.aws_config.remote_manifest_url:
                manifest_url = profile.aws_config.remote_manifest_url

            dpg.set_value("remote_manifest_url_input", manifest_url)

        from cerebrus.ui.components.dialogs.aws.sync_panel import (
            _render_downloaded_configs_list,
        )

        _render_downloaded_configs_list(state)

        if dpg.does_item_exist("use_prefix_only"):
            dpg.set_value("use_prefix_only", state.use_prefix_only)

        if dpg.does_item_exist("cb_move_logs"):
            dpg.set_value("cb_move_logs", state.move_logs_enabled)
        if dpg.does_item_exist("cb_move_csv"):
            dpg.set_value("cb_move_csv", state.move_csv_enabled)
        if dpg.does_item_exist("cb_move_mem"):
            dpg.set_value("cb_move_mem", state.move_memreport_enabled)

        # Refresh AWS S3 fields in dialog if open
        # AWS fields removed from this dialog

        if dpg.does_item_exist("cb_gen_perf"):
            dpg.set_value("cb_gen_perf", state.generate_perf_report_enabled)
        if dpg.does_item_exist("cb_gen_logs"):
            dpg.set_value("cb_gen_logs", state.generate_colored_logs_enabled)
        if dpg.does_item_exist("cb_gen_mem"):
            dpg.set_value("cb_gen_mem", state.generate_memreport_enabled)

        from cerebrus.ui.components.shared import _update_profile_display_colors

        _update_profile_display_colors(state)

    except (ValueError, KeyError, TypeError) as e:
        # Invalid profile schema
        filename = path.name if path else "Unknown"
        log_message(
            state,
            "ERROR",
            f"{filename} is not a valid Profile. Please create a new profile or open a valid existing profile.",
        )
        print(f"Error loading profile: {e}")
    except Exception as e:
        filename = path.name if path else "Unknown"
        log_message(state, "ERROR", f"Failed to load {filename}: {str(e)}")
        print(f"Error loading profile: {e}")
