"""Remote Configuration Sync panel components."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import dearpygui.dearpygui as dpg

from cerebrus.tools.adb import AdbClient

from ....state import UIState
from ....themes import get_theme_manager
from ...dialogs.files.file_dialog import _browse_folder_native
from ...file_manager import _open_folder_in_explorer
from ...shared import _add_help_button, log_message
from ...ui_config import UIConfig
from .aws_dialog import _show_aws_config_dialog
from .sync_logic import is_aws_configured, smart_download, update_manifest_url_state


def build_remote_config_sync(state: UIState) -> None:
    """Render the Remote Configuration Sync panel."""
    tm = get_theme_manager()
    header_color = tm.get_header_color()
    status_colors = tm.get_profile_status_colors()
    config = UIConfig.get_instance()

    with dpg.group():
        with dpg.group(horizontal=True, horizontal_spacing=8):
            dpg.add_text("Remote Configuration Sync", color=header_color)
            _add_help_button("sync_remote_config")

            dpg.add_spacer(width=20)
            dpg.add_button(
                label="Sync Settings",
                width=120,
                callback=lambda: _show_aws_config_dialog(state),
            )

        # Show loaded AWS config file
        config_file = "Environment / None"
        try:
            aws_creds = Path.home() / ".aws" / "credentials"
            aws_config = Path.home() / ".aws" / "config"
            if aws_creds.exists():
                config_file = str(aws_creds)
            elif aws_config.exists():
                config_file = str(aws_config)
        except Exception:
            pass

        status_colors = get_theme_manager().get_profile_status_colors()
        dpg.add_text(
            f"AWS Config File: {config_file}",
            color=(
                status_colors.get("LOADED")
                if "aws" in config_file.lower()
                else status_colors.get("DEFAULT")
            ),
            bullet=True,
        )

        # Show current source
        profile = state.profile_manager.current_profile
        aws_cfg = profile.aws_config if profile else None

        if aws_cfg and aws_cfg.remote_config_base_url:
            source_msg = f"Source: Custom Base URL ({aws_cfg.remote_config_base_url})"
            msg_color = status_colors.get("DEFAULT")
        else:
            source_msg = "Source: Default S3 Bucket"
            msg_color = status_colors.get("LOADED")

        dpg.add_text(source_msg, color=msg_color, bullet=True, tag="sync_source_label")

        dpg.add_spacer(height=config.get_spacer("small"))

        # Added dedicated output path for config sync
        with dpg.group(horizontal=True, horizontal_spacing=8):
            dpg.add_text("Config Output Path:")
            dpg.add_input_text(
                tag="config_output_path_label",
                default_value=str(state.config_output_path),
                width=config.get_dimension("input_width_xlarge"),
                readonly=True,
            )
            dpg.add_button(
                label="Browse",
                width=config.get_dimension("button_width_small"),
                callback=lambda: _browse_folder_native(state, "config_output"),
            )
            dpg.add_button(
                label="Open",
                width=config.get_dimension("button_width_small"),
                callback=lambda: _open_folder_in_explorer(state.config_output_path),
            )

        dpg.add_spacer(height=config.get_spacer("small"))

        with dpg.group(horizontal=True, horizontal_spacing=8):
            dpg.add_text("Manifest URL:")
            dpg.add_input_text(
                tag="remote_manifest_url_input",
                default_value=(
                    aws_cfg.remote_manifest_url
                    if aws_cfg and aws_cfg.remote_manifest_url
                    else state.remote_manifest_url
                ),
                width=-1,
                callback=lambda s, a: update_manifest_url_state(state, a),
            )

        with dpg.group(horizontal=True, horizontal_spacing=8):
            dpg.add_button(
                label="Update Manifest",
                width=config.get_dimension("button_width_large"),
                callback=lambda: _ensure_aws_configured_with_prompt(
                    state, lambda: _update_manifest(state)
                ),
            )
            dpg.add_button(
                label="Download Config",
                width=config.get_dimension("button_width_large"),
                callback=lambda: _ensure_aws_configured_with_prompt(
                    state, lambda: _download_configs_from_manifest(state)
                ),
            )

        dpg.add_spacer(height=config.get_spacer("small"))

        with dpg.table(
            header_row=False, policy=config.get_table_policy("policy_stretch")
        ):
            dpg.add_table_column(init_width_or_weight=1.0)
            dpg.add_table_column(init_width_or_weight=1.0)

            with dpg.table_row():
                # Left Column: Local Configs
                with dpg.group():
                    with dpg.group(horizontal=True, horizontal_spacing=8):
                        dpg.add_text("Local Downloaded Configs:", color=header_color)
                        dpg.add_button(
                            label="Refresh",
                            width=config.get_dimension("button_width_standard"),
                            callback=lambda: _ensure_aws_configured_with_prompt(
                                state, lambda: _render_downloaded_configs_list(state)
                            ),
                        )
                    # Fixed height container for list
                    with dpg.child_window(
                        tag="local_configs_list", height=150, border=True
                    ):
                        with dpg.group(tag="config_files_list_container"):
                            pass

                # Right Column: Device Configs
                with dpg.group():
                    with dpg.group(horizontal=True, horizontal_spacing=8):
                        dpg.add_text(
                            "Configs on Device (Persistent):", color=header_color
                        )
                        dpg.add_button(
                            label="Refresh",
                            width=config.get_dimension("button_width_standard"),
                            callback=lambda: _ensure_aws_configured_with_prompt(
                                state, lambda: _render_device_configs_list(state)
                            ),
                        )
                    # Fixed height container for list
                    with dpg.child_window(
                        tag="device_configs_list", height=150, border=True
                    ):
                        with dpg.group(tag="device_config_files_list_container"):
                            pass

        # Initial render of the lists
        _render_downloaded_configs_list(state)
        _render_device_configs_list(state)


def _ensure_aws_configured_with_prompt(state: UIState, on_success_callback) -> None:
    """Check AWS config; if not set, prompt the user before proceeding."""
    if is_aws_configured(state):
        on_success_callback()
    else:
        _show_aws_not_configured_modal(state, on_success_callback)


def _show_aws_not_configured_modal(state: UIState, on_success_callback) -> None:
    """Show a modal prompt when AWS is not configured."""
    if dpg.does_item_exist("aws_not_configured_modal"):
        dpg.delete_item("aws_not_configured_modal")

    def _on_configure_click():
        # Log to both UI and console for debugging
        print("[Cerebrus] Configure Now clicked in modal.")
        log_message(state, "INFO", "Switching to AWS Configuration...")

        # Cleanup current modal first
        if dpg.does_item_exist("aws_not_configured_modal"):
            dpg.delete_item("aws_not_configured_modal")

        # Launch target window
        _show_aws_config_dialog(state)

    # Center position
    viewport_width = dpg.get_viewport_width() or 1280
    viewport_height = dpg.get_viewport_height() or 720
    width, height = 500, 250
    pos = [(viewport_width - width) // 2, (viewport_height - height) // 2]

    config = UIConfig.get_instance()
    # Explicitly set modal=True and larger size
    with dpg.window(
        label="Missing Configuration",
        modal=True,
        show=True,
        tag="aws_not_configured_modal",
        width=width,
        height=height,
        pos=pos,
        no_collapse=True,
        no_resize=True,
    ):
        dpg.add_text(
            "Remote Configuration is missing.\n\nTo use this feature, you must configure either:\n1. A valid AWS S3 Connection (keys or profile)\n2. A Base URL for a public bucket\n\nClick 'Configure Now' to set this up.",
            wrap=480,
        )
        dpg.add_spacer(height=config.get_spacer("section_gap"))

        with dpg.group(horizontal=True):
            # Calculate horizontal centering: (window_width - (btn1_width + spacing + btn2_width)) / 2
            # (500 - (140 + 8 + 120)) / 2 = (500 - 268) / 2 = 116
            dpg.add_spacer(width=116)
            dpg.add_button(
                label="Configure Now",
                width=config.get_dimension("button_width_large"),
                callback=_on_configure_click,
            )
            dpg.add_button(
                label="Cancel",
                width=config.get_dimension("button_width_standard"),
                callback=lambda: dpg.delete_item("aws_not_configured_modal"),
            )


def _update_manifest(state: UIState) -> None:
    """Download the remote manifest JSON file."""
    # Always pull current value from UI to be safe
    url = (
        dpg.get_value("remote_manifest_url_input")
        if dpg.does_item_exist("remote_manifest_url_input")
        else state.remote_manifest_url
    )

    if not url:
        log_message(state, "ERROR", "Manifest URL is empty.")
        return

    # Save to Configs subfolder to avoid root permission issues (like C:\)
    configs_dir = state.config_output_path / "Configs"
    if not configs_dir.exists():
        try:
            configs_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            log_message(state, "ERROR", f"Failed to create Configs directory: {e}")
            return

    manifest_path = configs_dir / "config_manifest.json"

    log_message(state, "INFO", f"Updating manifest from {url}...")

    if smart_download(state, url, manifest_path):
        # Validate JSON
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                json.load(f)
            log_message(
                state, "SUCCESS", f"Manifest updated and saved to: {manifest_path}"
            )
        except json.JSONDecodeError:
            log_message(state, "ERROR", "Downloaded manifest is not valid JSON.")
    else:
        log_message(state, "ERROR", "Failed to update manifest.")


def _download_configs_from_manifest(state: UIState) -> None:
    """Download configs based on the local manifest JSON."""
    configs_dir = state.config_output_path / "Configs"
    manifest_path = configs_dir / "config_manifest.json"

    if not manifest_path.exists():
        log_message(
            state,
            "ERROR",
            f"Manifest file not found at {manifest_path}. Please click 'Update Json' first.",
        )
        return

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        log_message(state, "ERROR", f"Failed to read manifest: {e}")
        return

    if not isinstance(manifest, dict):
        log_message(
            state,
            "ERROR",
            "Invalid manifest format. Expected a dictionary of {EnvName: URL/URLs}.",
        )
        return

    log_message(
        state,
        "INFO",
        f"Found {len(manifest)} entries in manifest. Starting download...",
    )

    configs_dir = state.config_output_path / "Configs"
    if not configs_dir.exists():
        configs_dir.mkdir(parents=True, exist_ok=True)

    for env_name, value in manifest.items():
        urls = [value] if isinstance(value, str) else value
        if not isinstance(urls, list):
            log_message(
                state,
                "WARNING",
                f"Invalid value for {env_name} in manifest. Expected string or list.",
            )
            continue

        for url in urls:
            if not url:
                continue

            try:
                # Derive filename from URL
                parsed_url = urlparse(url)
                remote_filename = os.path.basename(parsed_url.path)
                if not remote_filename:
                    remote_filename = f"BackendConfig_{env_name}.ini"

                local_file = configs_dir / remote_filename
                log_message(
                    state, "INFO", f"Downloading {remote_filename} for {env_name}..."
                )

                if smart_download(state, url, local_file):
                    log_message(state, "SUCCESS", f"Saved: {local_file.name}")
                else:
                    log_message(state, "ERROR", f"Failed to download {remote_filename}")

            except Exception as e:
                log_message(state, "ERROR", f"Error processing {url}: {e}")

    log_message(state, "INFO", "Batch download completed.")
    _render_downloaded_configs_list(state)


def _render_downloaded_configs_list(state: UIState) -> None:
    """Render the list of downloaded .ini files."""
    config = UIConfig.get_instance()
    if not dpg.does_item_exist("config_files_list_container"):
        return

    dpg.delete_item("config_files_list_container", children_only=True)

    configs_dir = state.config_output_path / "Configs"
    if not configs_dir.exists():
        dpg.add_text("No configs downloaded yet.", parent="config_files_list_container")
        return

    files = sorted(list(configs_dir.glob("*.ini")), key=lambda x: x.name.lower())
    if not files:
        dpg.add_text(
            "No .ini files found in Configs folder.",
            parent="config_files_list_container",
        )
        return

    for file_path in files:
        with dpg.group(horizontal=True, parent="config_files_list_container"):
            dpg.add_text(file_path.name)
            dpg.add_spacer(width=20)
            dpg.add_button(
                label="Push",
                width=config.get_dimension("button_width_small"),
                callback=lambda s, a, u: _push_single_file_to_device(state, u),
                user_data=file_path.name,
            )


def _push_single_file_to_device(state: UIState, filename: str) -> None:
    """Push a single local configuration file to the device."""
    if not state.selected_device_serial:
        log_message(state, "ERROR", "No device selected.")
        return

    if not state.package_name:
        log_message(state, "ERROR", "Package Name not set.")
        return

    parts = state.package_name.split(".")
    if len(parts) < 3:
        log_message(
            state,
            "ERROR",
            "Invalid Package Name format. Cannot derive Project Name.",
        )
        return
    project_name = parts[-1]

    local_file = state.config_output_path / "Configs" / filename

    if not local_file.exists():
        log_message(state, "ERROR", f"File not found: {local_file}")
        return

    client = AdbClient()
    serial = state.selected_device_serial
    device_dir = f"/sdcard/Android/data/{state.package_name}/files/UnrealGame/{project_name}/{project_name}/Saved/Persistent/"
    device_file = device_dir + filename

    try:
        log_message(state, "INFO", f"Pushing {filename} to {device_file}...")

        client.push(serial, str(local_file), device_file)
        log_message(state, "SUCCESS", f"Pushed: {filename}")

        if "backendconfig" in filename.lower():
            log_message(
                state, "INFO", f"Detected main config. Updating BackendConfig.ini..."
            )
            target_device_file = device_dir + "BackendConfig.ini"
            try:
                client.remove_file(serial, target_device_file)
            except:
                pass
            client.push(serial, str(local_file), target_device_file)
            log_message(state, "SUCCESS", "Updated BackendConfig.ini on device.")

        _render_device_configs_list(state)

    except Exception as e:
        log_message(state, "ERROR", f"Failed to push {filename}: {e}")


def _render_device_configs_list(state: UIState) -> None:
    """Render the list of .ini files present on the device's persistent storage."""
    config = UIConfig.get_instance()
    tm = get_theme_manager()
    if not dpg.does_item_exist("device_config_files_list_container"):
        return

    dpg.delete_item("device_config_files_list_container", children_only=True)

    if not state.selected_device_serial:
        dpg.add_text(
            "No device selected.",
            parent="device_config_files_list_container",
            color=tm.get_profile_status_colors().get("ERROR", (255, 100, 100)),
        )
        return

    if not state.package_name:
        dpg.add_text(
            "Package Name not set.",
            parent="device_config_files_list_container",
            color=tm.get_profile_status_colors().get("ERROR", (255, 100, 100)),
        )
        return

    parts = state.package_name.split(".")
    if len(parts) < 3:
        dpg.add_text(
            "Invalid Package Name.",
            parent="device_config_files_list_container",
            color=tm.get_profile_status_colors().get("ERROR", (255, 100, 100)),
        )
        return
    project_name = parts[-1]

    client = AdbClient()
    serial = state.selected_device_serial
    device_dir = f"/sdcard/Android/data/{state.package_name}/files/UnrealGame/{project_name}/{project_name}/Saved/Persistent/"

    dpg.add_text(
        f"Checking: {device_dir}",
        parent="device_config_files_list_container",
        color=get_theme_manager().get_subheader_color(),
        wrap=500,
    )
    dpg.add_separator(parent="device_config_files_list_container")

    try:
        remote_files = client.list_files(serial, device_dir)
        ini_files = sorted(
            [f for f in remote_files if f.lower().endswith(".ini")],
            key=lambda x: x.lower(),
        )

        if not ini_files:
            dpg.add_text(
                "No .ini files found on device.",
                parent="device_config_files_list_container",
            )
            return

        for filename in ini_files:
            with dpg.group(
                horizontal=True, parent="device_config_files_list_container"
            ):
                dpg.add_text(filename)
                dpg.add_spacer(width=20)
                dpg.add_button(
                    label="Delete",
                    width=config.get_dimension("button_width_small"),
                    callback=lambda s, a, u: _handle_delete_config_on_device(state, u),
                    user_data=filename,
                )

        dpg.add_button(
            label="Delete All",
            width=config.get_dimension("button_width_standard"),
            callback=lambda: _handle_delete_all_configs_on_device(state),
            parent="device_configs_list_container",
        )

    except Exception as e:
        dpg.add_text(
            f"Error: {e}",
            parent="device_config_files_list_container",
            color=tm.get_profile_status_colors().get("ERROR", (255, 100, 100)),
        )


def _handle_delete_config_on_device(state: UIState, filename: str) -> None:
    """Delete a configuration file from the device's persistent storage."""
    if not state.selected_device_serial or not state.package_name:
        return

    parts = state.package_name.split(".")
    project_name = parts[-1]

    client = AdbClient()
    serial = state.selected_device_serial
    device_file = f"/sdcard/Android/data/{state.package_name}/files/UnrealGame/{project_name}/{project_name}/Saved/Persistent/{filename}"

    try:
        log_message(state, "INFO", f"Deleting {filename} from device...")
        client.remove_file(serial, device_file)
        log_message(state, "SUCCESS", f"Deleted {filename} from device.")
        _render_device_configs_list(state)
    except Exception as e:
        log_message(state, "ERROR", f"Failed to delete {filename}: {e}")


def _handle_delete_all_configs_on_device(state: UIState) -> None:
    """Delete all .ini files from the device's persistent storage."""
    if not state.selected_device_serial or not state.package_name:
        log_message(state, "ERROR", "No device or package selected.")
        return

    parts = state.package_name.split(".")
    if len(parts) < 3:
        return
    project_name = parts[-1]

    client = AdbClient()
    serial = state.selected_device_serial
    device_dir = f"/sdcard/Android/data/{state.package_name}/files/UnrealGame/{project_name}/{project_name}/Saved/Persistent/"

    try:
        log_message(state, "INFO", "Attempting to delete all config files on device...")
        client.shell(serial, ["rm", "-f", f"{device_dir}*.ini"])
        log_message(
            state, "SUCCESS", "All .ini files deleted from device persistent storage."
        )
        _render_device_configs_list(state)
    except Exception as e:
        log_message(state, "ERROR", f"Failed to delete all configs: {e}")
