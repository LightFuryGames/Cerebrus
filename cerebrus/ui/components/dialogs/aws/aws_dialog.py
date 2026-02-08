from __future__ import annotations
import dearpygui.dearpygui as dpg
from cerebrus.ui.state import UIState
from cerebrus.ui.components.shared import log_message, _auto_save_profile
from cerebrus.ui.components.ui_config import UIConfig

def _update_aws_credential(state: UIState, key: str, value: str) -> None:
    """Update AWS credential in current profile and auto-save."""
    profile = state.profile_manager.current_profile
    if not profile:
        return

    if key == "access_key":
        profile.aws_access_key = value
    elif key == "secret_key":
        profile.aws_secret_key = value
    elif key == "region":
        profile.aws_region = value
    elif key == "profile":
        profile.aws_profile = value
    elif key == "base_url":
        profile.remote_config_base_url = value
    elif key.startswith("url_"):
        env = key.split("_")[1]
        if not profile.remote_configs:
            profile.remote_configs = {}
        profile.remote_configs[env] = value
    
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
    width = settings.get("width", 500)
    height = settings.get("height", 300)
    
    pos = [(viewport_width - width) // 2, (viewport_height - height) // 2]

    # Merge settings with dynamic pos
    # Merge settings with dynamic pos
    window_args = settings.copy()
    window_args["pos"] = pos
    window_args["width"] = 600
    window_args["height"] = 500
    window_args["autosize"] = False
    window_args["min_size"] = [500, 400]
    window_args["no_collapse"] = True

    with dpg.window(**window_args):
        # Force to front
        dpg.focus_item("aws_config_dialog")
        
        from cerebrus.ui.themes import get_theme_manager
        tm = get_theme_manager()
        
        dpg.add_text(
            "Configure Remote Config URLs and AWS credentials.",
            color=tm.get_header_color(),
        )
        dpg.add_spacer(height=config.get_spacer("standard"))

        # --- Remote Config Section ---
        dpg.add_text("Remote Config Setup", color=tm.get_subheader_color())
        dpg.add_separator()
        
        with dpg.table(header_row=False, policy=config.get_table_policy("policy_stretch")):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=140)
            dpg.add_table_column(init_width_or_weight=1)

            with dpg.table_row():
                dpg.add_text("Base URL:")
                dpg.add_input_text(
                    tag="dlg_base_url",
                    default_value=profile.remote_config_base_url or "",
                    hint="Leave empty to use default S3 Bucket",
                    callback=lambda s, a: _update_aws_credential(state, "base_url", a),
                )

            remote_configs = profile.remote_configs or {}
            # Added Test env and updated labels
            for env, label in [
                ("Development", "Development Override"),
                ("Test", "Test Override"),
                ("Shipping", "Shipping Override"),
                ("Debug", "Debug Override")
            ]:
                with dpg.table_row():
                    dpg.add_text(f"{label}:")
                    dpg.add_input_text(
                        tag=f"dlg_url_{env}",
                        default_value=remote_configs.get(env, ""),
                        callback=lambda s, a, e=env: _update_aws_credential(state, f"url_{e}", a),
                    )

        dpg.add_spacer(height=config.get_spacer("large"))

        # --- AWS Credentials Section ---
        dpg.add_text("AWS S3 Auth", color=tm.get_subheader_color())
        dpg.add_separator()

        with dpg.table(header_row=False, policy=config.get_table_policy("policy_stretch")):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=140)
            dpg.add_table_column(init_width_or_weight=1)

            with dpg.table_row():
                dpg.add_text("Access Key:")
                dpg.add_input_text(
                    tag="dlg_aws_access_key",
                    default_value=profile.aws_access_key,
                    password=True,
                    callback=lambda s, a: _update_aws_credential(
                        state, "access_key", a
                    ),
                )

            with dpg.table_row():
                dpg.add_text("Secret Key:")
                dpg.add_input_text(
                    tag="dlg_aws_secret_key",
                    default_value=profile.aws_secret_key,
                    password=True,
                    callback=lambda s, a: _update_aws_credential(
                        state, "secret_key", a
                    ),
                )

            with dpg.table_row():
                dpg.add_text("Region:")
                dpg.add_input_text(
                    tag="dlg_aws_region",
                    default_value=profile.aws_region or "ap-south-1",
                    callback=lambda s, a: _update_aws_credential(state, "region", a),
                )

            with dpg.table_row():
                dpg.add_text("AWS Profile:")
                dpg.add_input_text(
                    tag="dlg_aws_profile",
                    default_value=profile.aws_profile,
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
            
            dpg.add_button(
                label="Export Config",
                width=100,
                callback=lambda: _export_aws_config(state),
            )
            dpg.add_button(
                label="Import Config",
                width=100,
                callback=lambda: _import_aws_config_dialog(state),
            )
            
            dpg.add_text("(Auto-saved)", color=(150, 150, 150))


def _export_aws_config(state: UIState) -> None:
    """Export current AWS/Remote configurations to a JSON file."""
    from tkinter import Tk, filedialog
    import json
    import base64

    profile = state.profile_manager.current_profile
    if not profile:
        return

    try:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        file_path = filedialog.asksaveasfilename(
            title="Export AWS Configuration",
            defaultextension=".json",
            filetypes=[("JSON Files", "*.json")],
            initialfile="aws_config.json"
        )
        root.destroy()

        if not file_path:
            return

        # Prepare data with simple obfuscation for keys
        data = {
            "remote_config_base_url": profile.remote_config_base_url,
            "remote_configs": profile.remote_configs,
            "aws_region": profile.aws_region,
            "aws_profile": profile.aws_profile,
        }
        
        if profile.aws_access_key:
            data["aws_access_key_b64"] = base64.b64encode(profile.aws_access_key.encode()).decode()
            
        if profile.aws_secret_key:
            data["aws_secret_key_b64"] = base64.b64encode(profile.aws_secret_key.encode()).decode()

        with open(file_path, "w") as f:
            json.dump(data, f, indent=4)
            
        log_message(state, "SUCCESS", f"AWS Config exported to {file_path}")

    except Exception as e:
        log_message(state, "ERROR", f"Failed to export config: {e}")


def _import_aws_config_dialog(state: UIState) -> None:
    """Import AWS/Remote configurations from a JSON file."""
    from tkinter import Tk, filedialog
    import json
    import base64

    try:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        file_path = filedialog.askopenfilename(
            title="Import AWS Configuration",
            filetypes=[("JSON Files", "*.json")],
        )
        root.destroy()

        if not file_path:
            return

        with open(file_path, "r") as f:
            data = json.load(f)

        profile = state.profile_manager.current_profile
        if not profile:
            return

        # Restore values
        if "remote_config_base_url" in data:
            profile.remote_config_base_url = data["remote_config_base_url"]
            if dpg.does_item_exist("dlg_base_url"):
                dpg.set_value("dlg_base_url", profile.remote_config_base_url or "")
        
        if "remote_configs" in data:
            profile.remote_configs = data["remote_configs"]
            if profile.remote_configs:
                for env, val in profile.remote_configs.items():
                    tag = f"dlg_url_{env}"
                    if dpg.does_item_exist(tag):
                        dpg.set_value(tag, val)
        
        if "aws_region" in data:
            profile.aws_region = data["aws_region"]
            if dpg.does_item_exist("dlg_aws_region"):
                dpg.set_value("dlg_aws_region", profile.aws_region)

        if "aws_profile" in data:
            profile.aws_profile = data["aws_profile"]
            if dpg.does_item_exist("dlg_aws_profile"):
                dpg.set_value("dlg_aws_profile", profile.aws_profile)

        # De-obfuscate keys
        if "aws_access_key_b64" in data:
            try:
                profile.aws_access_key = base64.b64decode(data["aws_access_key_b64"]).decode()
                if dpg.does_item_exist("dlg_aws_access_key"):
                    dpg.set_value("dlg_aws_access_key", profile.aws_access_key)
            except:
                pass

        if "aws_secret_key_b64" in data:
            try:
                profile.aws_secret_key = base64.b64decode(data["aws_secret_key_b64"]).decode()
                if dpg.does_item_exist("dlg_aws_secret_key"):
                    dpg.set_value("dlg_aws_secret_key", profile.aws_secret_key)
            except:
                pass
        
        _auto_save_profile(state)
        log_message(state, "SUCCESS", f"AWS Config imported from {file_path}")

    except Exception as e:
        log_message(state, "ERROR", f"Failed to import config: {e}")
