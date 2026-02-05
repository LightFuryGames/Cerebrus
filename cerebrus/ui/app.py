"""DearPyGui application entry point."""

from __future__ import annotations

from pathlib import Path

import dearpygui.dearpygui as dpg

from cerebrus.ui import components
from cerebrus.ui.state import UIState


class CerebrusApp:
    """Build and run the Cerebrus UI described in the sketch."""

    def __init__(self, state: UIState | None = None) -> None:
        self.state = state or UIState()
        profile, path = self.state.profile_manager.load_last_profile()
        self.state.profile_nickname = profile.nickname or "None"
        self.state.package_name = profile.package_name
        self.state.profile_path = path if path else Path("No profile loaded")

        # Load persisted fields from profile into state
        if profile:
            self.state.output_file_name = profile.output_file_name
            self.state.input_path = (
                Path(profile.input_path) if profile.input_path else Path("C:/")
            )
            self.state.output_path = (
                Path(profile.output_path) if profile.output_path else Path("C:/")
            )
            self.state.use_prefix_only = profile.use_prefix_only
            self.state.append_device_to_path = True  # Always enabled now

            # Fix for legacy default paths or placeholders
            path_str = str(self.state.output_path).replace("\\", "/")
            if "path/to/output" in path_str:
                self.state.output_path = Path("C:/")
                self.state.input_path = Path("C:/")

    def build(self) -> None:
        dpg.create_context()

        # Initialize theme
        from cerebrus.ui.themes import get_theme_manager

        get_theme_manager().apply_theme("System")

        components.setup_fonts()
        components.log_message(self.state, "INFO", "Cerebrus App Loaded")

        # Check environment
        from cerebrus.core.setup import check_and_setup_environment

        # Run in background or just run? It might block UI.
        # For now, run synchronously as it's critical.
        check_and_setup_environment(
            lambda level, msg: components.log_message(self.state, level, msg)
        )

        if (
            self.state.profile_path
            and str(self.state.profile_path) != "No profile loaded"
        ):
            components.log_message(
                self.state,
                "INFO",
                f"Last used profile loaded: {self.state.profile_nickname}",
            )
        with dpg.window(
            tag="MainWindow",
            label="Cerebrus - An Unreal Engine Perf Report UI Toolkit",
            width=1100,
            height=750,
        ):
            components.build_menu_bar(self.state)
            components.build_profile_summary(self.state)
            components.build_device_controls(self.state)
            components.build_file_actions(self.state)

        dpg.set_primary_window("MainWindow", True)

        # Register keyboard handlers
        with dpg.handler_registry():
            dpg.add_key_press_handler(
                dpg.mvKey_F1, callback=lambda: components._open_user_guide(self.state)
            )

    def run(self) -> None:
        self.build()
        resources_dir = Path(__file__).resolve().parent.parent / "resources"
        small_icon_path = resources_dir / "icon64x64.ico"
        large_icon_path = resources_dir / "icon256x256.ico"
        dpg.create_viewport(
            title="Cerebrus",
            width=1200,
            height=800,
            small_icon=str(small_icon_path),
            large_icon=str(large_icon_path),
        )
        dpg.setup_dearpygui()
        dpg.show_viewport()
        dpg.start_dearpygui()
        dpg.destroy_context()
