from __future__ import annotations

from pathlib import Path

import dearpygui.dearpygui as dpg

from cerebrus.ui.components.shared import _auto_save_profile, log_message
from cerebrus.ui.components.ui_config import UIConfig
from cerebrus.ui.state import UIState


def _update_aws_credential(state: UIState, key: str, value: str) -> None:
    """Update AWS credential in current profile's AWS config and auto-save."""
    profile = state.profile_manager.current_profile
    if not profile:
        return

    from cerebrus.core.aws_config import AWSConfig

    if not profile.aws_config:
        profile.aws_config = AWSConfig()

    cfg = profile.aws_config
    if key == "access_key":
        cfg.aws_access_key = value
    elif key == "secret_key":
        cfg.aws_secret_key = value
    elif key == "region":
        cfg.aws_region = value
    elif key == "profile":
        cfg.aws_profile = value
    elif key == "base_url":
        cfg.remote_config_base_url = value
    elif key.startswith("url_"):
        env = key.split("_")[1]
        if not cfg.remote_configs:
            cfg.remote_configs = {}
        cfg.remote_configs[env] = value

    # Save AWS config if it has a path
    if profile.aws_config_path:
        try:
            cfg.save(Path(profile.aws_config_path))
        except Exception as e:
            log_message(state, "ERROR", f"Failed to save AWS Config: {e}")

    _auto_save_profile(state)


def _show_aws_config_dialog(state: UIState) -> None:
    """Show the AWS Configuration dialog."""
    if dpg.does_item_exist("aws_config_dialog"):
        dpg.delete_item("aws_config_dialog")

    profile = state.profile_manager.current_profile
    if not profile:
        log_message(state, "ERROR", "No active profile. Please load a profile first.")
        return

    # Calculate center position
    viewport_width = dpg.get_viewport_width() or 1280
    viewport_height = dpg.get_viewport_height() or 720

    config = UIConfig.get_instance()
    settings = config.get_component_settings("aws_config_dialog")
    width = 650
    height = 800

    pos = [(viewport_width - width) // 2, (viewport_height - height) // 2]

    window_args = settings.copy()
    window_args["pos"] = pos
    window_args["width"] = width
    window_args["height"] = height
    window_args["autosize"] = True
    window_args["min_size"] = [600, 800]
    window_args["no_collapse"] = True

    with dpg.window(**window_args):
        # Force to front
        dpg.focus_item("aws_config_dialog")

        from cerebrus.ui.themes import get_theme_manager

        tm = get_theme_manager()

        dpg.add_text(
            "Configure Decoupled AWS S3 Configuration.",
            color=tm.get_header_color(),
        )
        dpg.add_spacer(height=config.get_spacer("standard"))

        # --- AWS Config File Manager ---
        dpg.add_text("AWS External Config Link", color=tm.get_subheader_color())
        dpg.add_separator()

        path_val = profile.aws_config_path
        path_exists = Path(path_val).exists() if path_val else True

        with dpg.group(horizontal=True):
            dpg.add_text("Status:", color=(200, 200, 200))
            if not path_val:
                status_text = "NOT LINKED (Local Cache Only)"
                status_color = (255, 150, 0)
            elif path_exists:
                status_text = "LINKED"
                status_color = (100, 255, 100)
            else:
                status_text = "ERROR: FILE NOT FOUND"
                status_color = (255, 50, 50)
            dpg.add_text(status_text, color=status_color, tag="aws_status_label")

        with dpg.group(horizontal=True):
            dpg.add_text("Path:")
            dpg.add_input_text(
                tag="dlg_aws_config_path",
                default_value=path_val or "",
                hint="No external file linked.",
                readonly=True,
                width=450,
            )
            if not path_exists and path_val:
                with dpg.tooltip("dlg_aws_config_path"):
                    dpg.add_text(f"File missing at: {path_val}", color=(255, 100, 100))

        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Link Existing File",
                width=150,
                callback=lambda: _link_aws_config_file(state),
            )
            dpg.add_button(
                label="Create New Config",
                width=150,
                callback=lambda: _create_new_aws_config_file(state),
            )
            if path_val:
                dpg.add_button(
                    label="Unlink",
                    width=80,
                    callback=lambda: _unlink_aws_config_file(state),
                )

        if not path_exists and path_val:
            dpg.add_text(
                f"WARNING: The linked AWS Config file is MISSING.\nChanges will NOT be saved to disk until you Link/Create a new one.",
                color=(255, 100, 100),
            )
        elif not path_val and profile.aws_config:
            dpg.add_text(
                "NOTE: These settings are not yet decoupled into a separate file.\nClick 'Create New Config' to move them to a dedicated JSON.",
                color=(255, 200, 100),
            )

        dpg.add_spacer(height=config.get_spacer("large"))

        # --- Remote Config Section ---
        dpg.add_text("Remote Config Setup", color=tm.get_subheader_color())
        dpg.add_separator()

        cfg = profile.aws_config or None

        with dpg.table(
            header_row=False, policy=config.get_table_policy("policy_stretch")
        ):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=140)
            dpg.add_table_column(init_width_or_weight=1)

            with dpg.table_row():
                dpg.add_text("Base URL:")
                dpg.add_input_text(
                    tag="dlg_base_url",
                    default_value=cfg.remote_config_base_url if cfg else "",
                    hint="Leave empty to use default S3 Bucket",
                    callback=lambda s, a: _update_aws_credential(state, "base_url", a),
                )

            remote_configs = cfg.remote_configs if cfg and cfg.remote_configs else {}
            for env, label in [
                ("Development", "Development Override"),
                ("Test", "Test Override"),
                ("Shipping", "Shipping Override"),
                ("Debug", "Debug Override"),
            ]:
                with dpg.table_row():
                    dpg.add_text(f"{label}:")
                    dpg.add_input_text(
                        tag=f"dlg_url_{env}",
                        default_value=remote_configs.get(env, ""),
                        callback=lambda s, a, e=env: _update_aws_credential(
                            state, f"url_{e}", a
                        ),
                    )

        dpg.add_spacer(height=config.get_spacer("large"))

        # --- AWS Credentials Section ---
        dpg.add_text("AWS S3 Auth", color=tm.get_subheader_color())
        dpg.add_separator()

        with dpg.table(
            header_row=False, policy=config.get_table_policy("policy_stretch")
        ):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=140)
            dpg.add_table_column(init_width_or_weight=1)

            with dpg.table_row():
                dpg.add_text("Access Key:")
                dpg.add_input_text(
                    tag="dlg_aws_access_key",
                    default_value=cfg.aws_access_key if cfg else "",
                    password=True,
                    callback=lambda s, a: _update_aws_credential(
                        state, "access_key", a
                    ),
                )

            with dpg.table_row():
                dpg.add_text("Secret Key:")
                dpg.add_input_text(
                    tag="dlg_aws_secret_key",
                    default_value=cfg.aws_secret_key if cfg else "",
                    password=True,
                    callback=lambda s, a: _update_aws_credential(
                        state, "secret_key", a
                    ),
                )

            with dpg.table_row():
                dpg.add_text("Region:")
                dpg.add_input_text(
                    tag="dlg_aws_region",
                    default_value=(cfg.aws_region if cfg else "ap-south-1")
                    or "ap-south-1",
                    callback=lambda s, a: _update_aws_credential(state, "region", a),
                )

            with dpg.table_row():
                dpg.add_text("AWS Profile:")
                dpg.add_input_text(
                    tag="dlg_aws_profile",
                    default_value=cfg.aws_profile if cfg else "",
                    hint="e.g. default",
                    callback=lambda s, a: _update_aws_credential(state, "profile", a),
                )

        dpg.add_spacer(height=config.get_spacer("large"))
        dpg.add_separator()

        # --- Action Buttons ---
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Done",
                width=config.get_dimension("button_width_standard"),
                callback=lambda: dpg.delete_item("aws_config_dialog"),
            )
            dpg.add_spacer(width=20)
            dpg.add_text("(Auto-saved to linked file)", color=(150, 150, 150))


def _link_aws_config_file(state: UIState) -> None:
    """Link an existing AWS JSON config file."""
    from tkinter import Tk, filedialog

    from cerebrus.core.aws_config import AWSConfig

    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    file_path = filedialog.askopenfilename(
        title="Select AWS Configuration File",
        filetypes=[("JSON Files", "*.json")],
    )
    root.destroy()

    if not file_path:
        return

    try:
        path = Path(file_path)
        cfg = AWSConfig.load(path)

        profile = state.profile_manager.current_profile
        if profile:
            profile.aws_config_path = str(path.absolute())
            profile.aws_config = cfg
            _auto_save_profile(state)
            # Refresh dialog
            _show_aws_config_dialog(state)
            log_message(state, "SUCCESS", f"Linked AWS Config: {path.name}")
    except Exception as e:
        log_message(state, "ERROR", f"Failed to link AWS Config: {e}")


def _create_new_aws_config_file(state: UIState) -> None:
    """Create a new AWS JSON config file and link it."""
    from tkinter import Tk, filedialog

    from cerebrus.core.aws_config import AWSConfig

    profile = state.profile_manager.current_profile
    if not profile:
        return

    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    file_path = filedialog.asksaveasfilename(
        title="Create New AWS Configuration",
        defaultextension=".json",
        filetypes=[("JSON Files", "*.json")],
        initialfile="aws_config.json",
    )
    root.destroy()

    if not file_path:
        return

    try:
        path = Path(file_path)
        # Use existing in-memory config if available (migration) or new one
        cfg = profile.aws_config or AWSConfig()
        cfg.save(path)

        profile.aws_config_path = str(path.absolute())
        profile.aws_config = cfg
        _auto_save_profile(state)
        # Refresh dialog
        _show_aws_config_dialog(state)
        log_message(state, "SUCCESS", f"Created and Linked AWS Config: {path.name}")
    except Exception as e:
        log_message(state, "ERROR", f"Failed to create AWS Config: {e}")


def _unlink_aws_config_file(state: UIState) -> None:
    """Unlink the AWS JSON config file from the profile."""
    profile = state.profile_manager.current_profile
    if profile:
        profile.aws_config_path = None
        # We keep the in-memory aws_config so they don't lose current edits immediately
        _auto_save_profile(state)
        _show_aws_config_dialog(state)
        log_message(
            state,
            "INFO",
            "Unlinked AWS Config file. Settings are now local to session.",
        )
