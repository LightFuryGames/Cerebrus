from __future__ import annotations

import sys
import threading
import time
import webbrowser

import dearpygui.dearpygui as dpg

from cerebrus.core.updater import check_for_updates, download_update, run_installer
from cerebrus.ui.components.shared import log_message
from cerebrus.ui.components.ui_config import UIConfig
from cerebrus.ui.state import UIState


def check_for_updates_ui(state: UIState, silent_on_up_to_date: bool = False) -> None:
    """Check for updates and show dialog. Set silent_on_up_to_date=True for startup checks."""
    if not silent_on_up_to_date:
        log_message(state, "INFO", "Checking for updates...")

    # Run in thread to avoid UI freeze
    def check_thread():
        is_available, latest_tag, download_url = check_for_updates()

        if is_available:
            # Always show updates
            _show_update_dialog(state, latest_tag, download_url)
        else:
            if not silent_on_up_to_date:
                # If explicit check (button press), show "Up to date" dialog
                # But we need to switch back to main thread or ensure DPG calls are safe?
                # DPG calls are generally safe from threads if simple, but better to be sure.
                # actually DPG is not thread safe for UI creation usually, but existing code does it.
                # existing _show_update_dialog is called from thread.
                _show_up_to_date_dialog(state, latest_tag)

    threading.Thread(target=check_thread, daemon=True).start()


def _show_up_to_date_dialog(state: UIState, latest_tag: str | None) -> None:
    """Show dialog when already on latest version."""
    if dpg.does_item_exist("update_dialog"):
        dpg.delete_item("update_dialog")

    config = UIConfig.get_instance()
    settings = config.get_component_settings("update_dialog")  # Re-use same settings?

    viewport_width = dpg.get_viewport_width() or 1280
    viewport_height = dpg.get_viewport_height() or 720
    width = 400
    height = 180
    pos_x = (viewport_width - width) // 2
    pos_y = (viewport_height - height) // 2

    with dpg.window(
        label="Updates",
        pos=(pos_x, pos_y),
        width=width,
        height=height,
        modal=True,
        no_resize=True,
        tag="update_dialog",
    ):
        dpg.add_text("You are up to date!", color=(100, 255, 100))
        dpg.add_spacer(height=10)

        version_text = (
            f"Latest version: {latest_tag}"
            if latest_tag
            else "You are on the latest version."
        )
        dpg.add_text(version_text)

        dpg.add_spacer(height=20)
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=140)
            dpg.add_button(
                label="Close",
                width=100,
                callback=lambda: dpg.delete_item("update_dialog"),
            )


def _show_update_dialog(
    state: UIState, latest_tag: str, download_url: str = None
) -> None:
    """Show update confirmation dialog."""
    if dpg.does_item_exist("update_dialog"):
        dpg.delete_item("update_dialog")

    config = UIConfig.get_instance()
    settings = config.get_component_settings("update_dialog")

    viewport_width = dpg.get_viewport_width() or 1280
    viewport_height = dpg.get_viewport_height() or 720
    width = settings.get("width", 500)
    height = settings.get("height", 300)
    pos_x = (viewport_width - width) // 2
    pos_y = (viewport_height - height) // 2

    # Merge settings with dynamic pos
    window_args = settings.copy()
    window_args["pos"] = (pos_x, pos_y)

    with dpg.window(**window_args):
        dpg.add_text(f"A new version is available: {latest_tag}")

        is_frozen = getattr(sys, "frozen", False)

        if is_frozen and download_url:
            dpg.add_text("Ready to download and install.", color=(120, 255, 120))
            dpg.add_text(f"Installer: {download_url.split('/')[-1]}")

            dpg.add_spacer(height=config.get_spacer("standard"))
            dpg.add_progress_bar(
                tag="update_progress_bar",
                label="Progress",
                width=-1,
                default_value=0.0,
                show=False,
            )
            dpg.add_text(
                tag="update_status_text", default_value="", color=(200, 200, 200)
            )

            dpg.add_spacer(height=config.get_spacer("section"))
            with dpg.group(horizontal=True, tag="update_button_group"):
                dpg.add_spacer(width=200)
                dpg.add_button(
                    label="Cancel", callback=lambda: dpg.delete_item("update_dialog")
                )
                dpg.add_button(
                    label="Download & Install",
                    width=150,
                    callback=lambda: _start_download_update(state, download_url),
                )
        else:
            # Source mode or no installer found
            dpg.add_text(
                "Please pull the latest changes from git.", color=(200, 200, 200)
            )
            dpg.add_text(
                "Auto-update is only available for installed versions.",
                wrap=380,
                color=(255, 100, 100),
            )
            if not download_url:
                dpg.add_text(
                    "(No installer found for this release)", color=(255, 100, 100)
                )

            dpg.add_spacer(height=config.get_spacer("section"))
            with dpg.group(horizontal=True):
                dpg.add_spacer(width=250)
                dpg.add_button(
                    label="OK",
                    width=config.get_dimension("button_width_small"),
                    callback=lambda: dpg.delete_item("update_dialog"),
                )
                dpg.add_button(
                    label="Open GitHub",
                    callback=lambda: webbrowser.open(
                        "https://github.com/LightFuryGames/Cerebrus/releases"
                    ),
                )


def _start_download_update(state: UIState, url: str) -> None:
    dpg.configure_item("update_button_group", show=False)
    dpg.configure_item("update_progress_bar", show=True)
    dpg.set_value("update_status_text", "Starting download...")

    def download_thread():
        try:

            def progress(current, total):
                if total > 0:
                    dpg.set_value("update_progress_bar", current / total)
                    dpg.set_value(
                        "update_status_text",
                        f"Downloading: {current/1024/1024:.1f}/{total/1024/1024:.1f} MB",
                    )

            installer_path = download_update(url, progress)

            dpg.set_value(
                "update_status_text", "Download complete. Launching installer..."
            )
            time.sleep(1)  # Give user a moment to see completion

            # Launch installer
            if run_installer(installer_path):
                dpg.set_value("update_status_text", "Installer launched. Exiting...")
                time.sleep(2)
                sys.exit(0)
            else:
                dpg.set_value("update_status_text", "Failed to launch installer.")
                dpg.configure_item("update_button_group", show=True)

        except Exception as e:
            dpg.set_value("update_status_text", f"Error: {e}")
            dpg.configure_item("update_button_group", show=True)

    threading.Thread(target=download_thread, daemon=True).start()
