from __future__ import annotations

import dearpygui.dearpygui as dpg

from cerebrus.ui.state import UIState

# Log colors reference (kept for compatibility if imported directly, though moved to ThemeManager)
SELECTED_ROW_COLOR = (0, 119, 200, 153)

# Search Bar settings
SEARCH_BAR_WIDTH_PERCENT = 0.5  # 50% of available width

import json
import sys
from pathlib import Path


def _load_tooltips() -> dict[str, str]:
    """Load tooltips from resources JSON file."""
    try:
        # Determine base path
        if getattr(sys, "frozen", False):
            base_path = Path(sys._MEIPASS)
            json_path = base_path / "cerebrus" / "ui" / "resources" / "tooltips.json"
            # Fallback
            if not json_path.exists():
                json_path = base_path / "ui" / "resources" / "tooltips.json"
        else:
            # dev mode: current file is in ui/components/shared.py
            # json is in ui/resources/tooltips.json
            base_path = Path(__file__).resolve().parent.parent
            json_path = base_path / "resources" / "tooltips.json"

        if json_path.exists():
            with open(json_path, "r") as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Failed to load tooltips: {e}")
        return {}


TOOLTIPS = _load_tooltips()

# S3 Config URL
S3_CONFIG_BASE_URL = "https://titan-cerebrus-configurations.s3.ap-south-1.amazonaws.com"


def log_message(state: UIState, level: str, message: str) -> None:
    """Deprecating wrapper for centralized logging."""
    from cerebrus.ui.components.panels.logs_panel.logs_panel import log_message as _log

    _log(state, level, message)


def _add_hyperlink(text: str, url: str) -> None:
    """Add a clickable text hyperlink."""
    import webbrowser

    from cerebrus.ui.themes import get_theme_manager

    tm = get_theme_manager()

    link = dpg.add_text(text)
    dpg.bind_item_theme(link, tm.get_hyperlink_theme())

    # Create a unique handler registry for this link
    with dpg.item_handler_registry() as registry:
        dpg.add_item_clicked_handler(callback=lambda: webbrowser.open(url))

    dpg.bind_item_handler_registry(link, registry)

    # Add a tooltip to show the URL
    with dpg.tooltip(link):
        dpg.add_text(url)


def _add_help_button(tooltip_key: str, state: UIState | None = None) -> None:
    """Add a small (?) help button with a tooltip."""

    # Check if tooltip exists
    if tooltip_key not in TOOLTIPS:
        return

    text = TOOLTIPS[tooltip_key]

    with dpg.group(horizontal=True):
        btn = dpg.add_button(label="?", width=20, height=20, small=True)

        with dpg.tooltip(dpg.last_item()):
            dpg.add_text(text, wrap=350)


# -----------------------------------------------------------------------------
# Profile Save Helpers
# -----------------------------------------------------------------------------


def _save_current_profile(state: UIState) -> None:
    """Save the current profile state."""
    # Ensure profile manager has current profile
    if (
        state.profile_manager.current_profile
        and state.profile_manager.current_profile_path
    ):
        # Update profile from current UI state
        profile = state.profile_manager.current_profile
        profile.package_name = state.package_name

        # Update fields from UI/State if elements exist or state is updated
        if dpg.does_item_exist("output_file_name"):
            state.output_file_name = dpg.get_value("output_file_name")

        profile.output_file_name = state.output_file_name
        profile.input_path = str(state.input_path)

        # Save base_output_path if available to avoid saving device-specific path
        # But only if different?
        if state.base_output_path:
            profile.output_path = str(state.base_output_path)
        else:
            profile.output_path = str(state.output_path)

        if state.base_config_output_path:
            profile.config_output_path = str(state.base_config_output_path)
        else:
            profile.config_output_path = str(state.config_output_path)

        profile.use_prefix_only = state.use_prefix_only

        state.profile_manager.save_current_profile()
    else:
        # No current profile path, prompt to save as new
        # Import dynamically to avoid circular import
        from cerebrus.ui.components.dialogs.profile.profile_dialog import (
            _save_profile_native,
        )

        log_message(state, "INFO", "Please save profile with a name first")
        _save_profile_native(state, state.profile_nickname or "profile")


def _auto_save_profile(state: UIState) -> None:
    """Automatically save specific fields to the current profile."""
    if state.profile_manager.current_profile:
        profile = state.profile_manager.current_profile

        # Update fields
        if dpg.does_item_exist("output_file_name"):
            state.output_file_name = dpg.get_value("output_file_name")

        profile.output_file_name = state.output_file_name
        profile.input_path = str(state.input_path)

        # Save base_output_path if available
        if state.base_output_path:
            profile.output_path = str(state.base_output_path)
        else:
            profile.output_path = str(state.output_path)

        profile.use_prefix_only = state.use_prefix_only

        # Save bulk action states
        profile.move_logs_enabled = state.move_logs_enabled
        profile.move_csv_enabled = state.move_csv_enabled
        profile.move_memreport_enabled = state.move_memreport_enabled
        profile.generate_perf_report_enabled = state.generate_perf_report_enabled
        profile.generate_colored_logs_enabled = state.generate_colored_logs_enabled
        profile.generate_memreport_enabled = state.generate_memreport_enabled

        # Save manifest URL
        if dpg.does_item_exist("remote_manifest_url_input"):
            state.remote_manifest_url = dpg.get_value("remote_manifest_url_input")
            if profile.aws_config:
                profile.aws_config.remote_manifest_url = state.remote_manifest_url
                if profile.aws_config_path:
                    profile.aws_config.save(Path(profile.aws_config_path))

        if state.profile_manager.current_profile_path:
            state.profile_manager.save_current_profile()
        else:
            # Shadow save for default profile (allow caching for default)
            try:
                from cerebrus.core.profile import CONFIG_DIR

                shadow_path = CONFIG_DIR / "default_profile.json"
                if not CONFIG_DIR.exists():
                    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                profile.save(shadow_path)
            except Exception as e:
                print(f"Failed to shadow save default profile: {e}")


def _update_profile_display_colors(state: UIState) -> None:
    """Update the display colors for profile labels."""
    from cerebrus.ui.themes import get_theme_manager

    tm = get_theme_manager()
    status = "DEFAULT" if not state.profile_manager.current_profile_path else "LOADED"
    theme = tm.get_profile_status_theme(status)

    if dpg.does_item_exist("profile_nickname_input"):
        dpg.bind_item_theme("profile_nickname_input", theme)
    if dpg.does_item_exist("profile_path_input"):
        dpg.bind_item_theme("profile_path_input", theme)
    if dpg.does_item_exist("package_input"):
        dpg.bind_item_theme("package_input", theme)
