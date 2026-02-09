from __future__ import annotations

import dearpygui.dearpygui as dpg

from cerebrus._version import __version__
from cerebrus.ui.components.ui_config import UIConfig
from cerebrus.ui.state import UIState


def _show_about_dialog(state: UIState) -> None:
    """Show the About dialog."""
    if dpg.does_item_exist("about_dialog"):
        dpg.delete_item("about_dialog")

    # Load config
    config = UIConfig.get_instance()

    # Calculate center position
    viewport_width = dpg.get_viewport_width() or 1280
    viewport_height = dpg.get_viewport_height() or 720
    window_width = 460
    window_height = 460
    pos_x = (viewport_width - window_width) // 2
    pos_y = (viewport_height - window_height) // 2

    # Brighter blue colors
    text_blue = (0, 160, 255)

    # Link style theme
    with dpg.theme() as link_theme:
        with dpg.theme_component(dpg.mvAll):
            dpg.add_theme_color(dpg.mvThemeCol_Button, (0, 0, 0, 0))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonHovered, (30, 30, 30, 50))
            dpg.add_theme_color(dpg.mvThemeCol_ButtonActive, (50, 50, 50, 50))
            dpg.add_theme_color(dpg.mvThemeCol_Text, text_blue)

    with dpg.window(
        label="About",
        tag="about_dialog",
        pos=(pos_x, pos_y),
        width=window_width,
        height=window_height,
        no_scrollbar=True,
        no_scroll_with_mouse=True,
        no_resize=True,
        no_collapse=True,
        modal=True,
    ):
        dpg.add_spacer(height=5)

        # Center the Title
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=180)
            t = dpg.add_text("Cerebrus", color=text_blue)
            if dpg.does_item_exist("title_font"):
                dpg.bind_item_font(t, "title_font")

        dpg.add_spacer(height=10)

        with dpg.group():
            dpg.add_text(f"Version: {__version__}")
            dpg.add_text("Author: Lightfury Games")
            dpg.add_text(
                "Copyright © 2025 LeagueX Gaming Private Limited (LightFury Games)."
            )
            dpg.add_text("All rights reserved.")

        dpg.add_spacer(height=10)
        dpg.add_text("Repository:")

        dpg.add_button(
            label="https://github.com/LightFuryGames/Cerebrus",
            callback=lambda: _open_url("https://github.com/LightFuryGames/Cerebrus"),
        )
        dpg.bind_item_theme(dpg.last_item(), link_theme)

        dpg.add_spacer(height=10)
        dpg.add_text(
            "Python-based Windows-only toolkit with DearPyGUI UI for managing", wrap=600
        )
        dpg.add_text("Unreal Engine Android profiling workflows.", wrap=600)

        dpg.add_spacer(height=5)
        with dpg.group(horizontal=True):
            dpg.add_text("Licensed under the ")
            dpg.add_button(
                label="BSD 3-Clause License",
                callback=lambda: _open_url(
                    "https://github.com/LightFuryGames/Cerebrus?tab=BSD-3-Clause-1-ov-file"
                ),
                small=True,
            )
            dpg.bind_item_theme(dpg.last_item(), link_theme)
            dpg.add_text(" .")

        dpg.add_spacer(height=15)
        dpg.add_separator()
        dpg.add_spacer(height=10)

        # Center the Close button horizontally
        with dpg.group(horizontal=True):
            dpg.add_spacer(width=180)
            dpg.add_button(
                label="Close",
                width=100,
                callback=lambda: dpg.delete_item("about_dialog"),
            )


def _open_url(url: str) -> None:
    import webbrowser

    webbrowser.open(url)
