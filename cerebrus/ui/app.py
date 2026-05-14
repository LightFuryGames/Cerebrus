"""DearPyGui application entry point."""

from __future__ import annotations

from pathlib import Path

import dearpygui.dearpygui as dpg

from cerebrus.plugins.analytics.core.settings import load_analytics_settings
from cerebrus.ui.components import (
    _open_user_guide,
    apply_responsive_layout,
    build_device_controls,
    build_file_actions,
    build_menu_bar,
    build_profile_summary,
    check_for_updates_ui,
    log_message,
    setup_fonts,
)
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
            # We start with empty output file name until a device is selected
            self.state.output_file_name = ""
            self.state.input_path = (
                Path(profile.input_path) if profile.input_path else Path("C:/")
            )
            self.state.output_path = (
                Path(profile.output_path) if profile.output_path else Path("C:/")
            )
            self.state.config_output_path = (
                Path(profile.config_output_path)
                if profile.config_output_path
                else Path("C:/")
            )
            profile_device_config = getattr(profile, "device_profile_config_path", "")
            cached_device_config = load_analytics_settings().device_profile_config_path
            self.state.device_profile_config_path = (
                Path(profile_device_config or cached_device_config)
                if (profile_device_config or cached_device_config)
                else Path("")
            )
            self.state.use_prefix_only = profile.use_prefix_only
            self.state.append_device_to_path = True  # Always enabled now

            # Fix for legacy default paths or placeholders
            path_str = str(self.state.output_path).replace("\\", "/")
            if "path/to/output" in path_str:
                self.state.output_path = Path("C:/")
                self.state.input_path = Path("C:/")

    def build(self) -> None:
        from cerebrus.core.logging_setup import setup_logging

        setup_logging()

        dpg.create_context()

        from cerebrus.core.plugins import PluginManager
        from cerebrus.plugins.analytics.plugin import AnalyticsPlugin
        from cerebrus.plugins.aws_secrets.plugin import AWSSecretsPlugin
        from cerebrus.plugins.profiling.plugin import ProfilingPlugin
        from cerebrus.plugins.s3_uploader.plugin import S3UploaderPlugin
        from cerebrus.ui.themes import get_theme_manager

        PluginManager.register(ProfilingPlugin())
        PluginManager.register(AWSSecretsPlugin())
        PluginManager.register(S3UploaderPlugin())
        PluginManager.register(AnalyticsPlugin())
        PluginManager.initialize()

        get_theme_manager().apply_theme(mode="System")

        setup_fonts()
        log_message(self.state, "INFO", "Cerebrus App Loaded")

        # Check environment
        from cerebrus.core.setup import check_and_setup_environment

        # Run in background or just run? It might block UI.
        # For now, run synchronously as it's critical.
        check_and_setup_environment(
            lambda level, msg: log_message(self.state, level, msg)
        )

        if (
            self.state.profile_path
            and str(self.state.profile_path) != "No profile loaded"
        ):
            log_message(
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
            build_menu_bar(self.state)
            build_profile_summary(self.state)
            build_device_controls(self.state)
            build_file_actions(self.state)

        dpg.set_primary_window("MainWindow", True)

        # Register keyboard handlers
        with dpg.handler_registry():
            dpg.add_key_press_handler(
                dpg.mvKey_F1, callback=lambda: _open_user_guide(self.state)
            )

        # Trigger auto-update check (silent if no update)
        check_for_updates_ui(self.state, silent_on_up_to_date=True)

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
        dpg.set_viewport_resize_callback(
            lambda sender=None, app_data=None, user_data=None: apply_responsive_layout()
        )
        dpg.setup_dearpygui()
        dpg.show_viewport()
        apply_responsive_layout()
        dpg.start_dearpygui()
        dpg.destroy_context()
