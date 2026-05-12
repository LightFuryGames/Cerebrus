"""Palette Management and Theme Editor components."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from tkinter import Tk, filedialog

import dearpygui.dearpygui as dpg

from ..state import UIState
from ..themes import get_theme_manager
from .panels.logs_panel.logs_panel import _render_log_entries
from .shared import log_message


def _show_create_palette_dialog(state: UIState) -> None:
    """Show dialog to create a new custom palette."""
    if dpg.does_item_exist("create_palette_dialog"):
        dpg.focus_item("create_palette_dialog")
        return

    tm = get_theme_manager()
    base_palettes = list(tm.themes.keys())

    with dpg.window(
        tag="create_palette_dialog",
        label="Create Custom Palette",
        modal=True,
        width=400,
        height=200,
        no_resize=True,
    ):
        dpg.add_text("Create a new palette based on an existing one.")
        dpg.add_spacer(height=10)

        dpg.add_input_text(
            tag="cp_name_input", label="Palette Name", hint="e.g. My Custom Theme"
        )
        dpg.add_combo(
            tag="cp_base_combo",
            label="Base On",
            items=base_palettes,
            default_value=(
                tm.current_palette
                if tm.current_palette in base_palettes
                else base_palettes[0]
            ),
        )

        dpg.add_spacer(height=20)
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Create",
                width=100,
                callback=lambda: _handle_create_palette(state),
            )
            dpg.add_button(
                label="Cancel",
                width=100,
                callback=lambda: dpg.delete_item("create_palette_dialog"),
            )


def _handle_create_palette(state: UIState) -> None:
    name = dpg.get_value("cp_name_input")
    base = dpg.get_value("cp_base_combo")

    if not name:
        log_message(state, "ERROR", "Palette name cannot be empty.")
        return

    tm = get_theme_manager()

    # Check if exists
    if name in tm.themes:
        log_message(state, "ERROR", f"Palette '{name}' already exists.")
        return

    log_message(state, "INFO", f"Creating palette '{name}' based on '{base}'...")

    # Copy data for all modes of the base palette
    base_data_map = tm.themes.get(base, {})

    success_count = 0
    for mode, data in base_data_map.items():
        new_data = json.loads(json.dumps(data))  # Deep copy
        new_data["palette"] = name

        # Save new file
        # We manually call save logic or simulate it
        # We can inject into TM and call save_theme

        # Initialize in TM
        if name not in tm.themes:
            tm.themes[name] = {}
        if name not in tm.theme_tags:
            tm.theme_tags[name] = {}

        tm.themes[name][mode] = new_data

        # Save
        tm.save_theme(name, mode)
        success_count += 1

    if success_count > 0:
        log_message(
            state, "SUCCESS", f"Created palette '{name}' with {success_count} modes."
        )
        dpg.delete_item("create_palette_dialog")

        # Reload to ensure clean state and tags
        tm.reload_palettes()

        # Switch to new palette
        tm.apply_theme(palette=name)
        log_message(state, "INFO", f"Switched to '{name}'.")
    else:
        log_message(state, "ERROR", "Failed to create palette.")


def _show_load_palette_dialog(state: UIState) -> None:
    """Load an external specific JSON theme file."""
    try:
        root = Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        file_path = filedialog.askopenfilename(
            title="Import Palette JSON",
            filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        )
        root.destroy()

        if file_path:
            path = Path(file_path)
            tm = get_theme_manager()
            dest = tm.palettes_dir / path.name

            if dest.exists():
                stem = path.stem
                suffix = path.suffix
                index = 1
                while dest.exists():
                    dest = tm.palettes_dir / f"{stem}_{index}{suffix}"
                    index += 1

            shutil.copy2(path, dest)
            log_message(state, "SUCCESS", f"Imported {path.name}")

            tm.reload_palettes()

            # Try to determine palette name from file to switch to it
            try:
                with open(dest, "r") as f:
                    data = json.load(f)
                    p_name = data.get("palette")
                    if p_name:
                        tm.apply_theme(palette=p_name)
                        log_message(
                            state, "INFO", f"Switched to imported palette '{p_name}'."
                        )
            except (OSError, json.JSONDecodeError) as e:
                log_message(
                    state,
                    "WARNING",
                    f"Imported palette, but could not activate it: {e}",
                )

    except Exception as e:
        log_message(state, "ERROR", f"Failed to import palette: {e}")


def _show_theme_editor(state: UIState, palette: str = None) -> None:
    """Show the Theme Editor window with Save/Cancel workflows."""
    import copy

    tm = get_theme_manager()
    if not palette:
        palette = tm.current_palette

    tag = f"theme_editor_{palette}"

    # If window exists, just focus it
    if dpg.does_item_exist(tag):
        if dpg.is_item_shown(tag):
            dpg.focus_item(tag)
            return
        else:
            # It exists but hidden? destroy and recreate to be safe
            dpg.delete_item(tag)

    # 1. Capture State for Cancel (Revert)
    # We must deepcopy the ENTIRE palette data for the current mode(s)
    # to revert correctly.
    # Actually, we usually edit one mode. But the UI lets us switch modes.
    # So we should probably backup the whole palette entry in memory.
    original_palette_data = copy.deepcopy(tm.themes.get(palette, {}))

    def _on_cancel():
        # Revert changes
        tm.themes[palette] = original_palette_data
        # Re-apply theme to reflect revert
        active_mode = tm.current_mode
        if active_mode == "System":
            active_mode = tm._get_system_theme()

        # We need to re-create the DPG theme for the current mode
        # (and potentially others if we edited them)
        for mode, data in original_palette_data.items():
            tm._create_dpg_theme(palette, mode, data)

        tm.apply_theme()

        # Force log re-render to revert colors
        _render_log_entries(state)

        dpg.delete_item(tag)
        log_message(state, "INFO", "Theme editing cancelled. Changes reverted.")

    def _on_save():
        # Changes are already in tm.themes (via real-time update callbacks)
        # We just need to persist them to disk.
        # Save ALL modes for this palette?
        for mode in tm.themes[palette]:
            tm.save_theme(palette, mode)

        dpg.delete_item(tag)
        log_message(state, "SUCCESS", f"Theme '{palette}' saved successfully.")

    def _on_close():
        # Default behavior for X button: acts like Cancel? or Save?
        # Usually X implies "Close without saving" or "Minimize".
        # Given we have explicit Save, X should probably Cancel/Revert?
        # Or maybe prompt? For now, let's treat X as Cancel for safety.
        _on_cancel()

    # Categorized DPG Colors
    color_categories = {
        "Window & Backgrounds": [
            ("Window Background", "mvThemeCol_WindowBg"),
            ("Child Background", "mvThemeCol_ChildBg"),
            ("Popup Background", "mvThemeCol_PopupBg"),
            ("Border", "mvThemeCol_Border"),
            ("Border Shadow", "mvThemeCol_BorderShadow"),
            ("Frame Background", "mvThemeCol_FrameBg"),
            ("Frame Background Hovered", "mvThemeCol_FrameBgHovered"),
            ("Frame Background Active", "mvThemeCol_FrameBgActive"),
            ("Title Background", "mvThemeCol_TitleBg"),
            ("Title Background Active", "mvThemeCol_TitleBgActive"),
            ("Title Background Collapsed", "mvThemeCol_TitleBgCollapsed"),
            ("MenuBar Background", "mvThemeCol_MenuBarBg"),
            ("Scrollbar Background", "mvThemeCol_ScrollbarBg"),
            ("Scrollbar Grab", "mvThemeCol_ScrollbarGrab"),
            ("Scrollbar Grab Hovered", "mvThemeCol_ScrollbarGrabHovered"),
            ("Scrollbar Grab Active", "mvThemeCol_ScrollbarGrabActive"),
            ("Check Mark", "mvThemeCol_CheckMark"),
            ("Slider Grab", "mvThemeCol_SliderGrab"),
            ("Slider Grab Active", "mvThemeCol_SliderGrabActive"),
        ],
        "Text": [
            ("Text", "mvThemeCol_Text"),
            ("Text Disabled", "mvThemeCol_TextDisabled"),
            ("Text Selected Background", "mvThemeCol_TextSelectedBg"),
        ],
        "Buttons": [
            ("Button", "mvThemeCol_Button"),
            ("Button Hovered", "mvThemeCol_ButtonHovered"),
            ("Button Active", "mvThemeCol_ButtonActive"),
        ],
        "Headers": [
            ("Header", "mvThemeCol_Header"),
            ("Header Hovered", "mvThemeCol_HeaderHovered"),
            ("Header Active", "mvThemeCol_HeaderActive"),
        ],
        "Tabs": [
            ("Tab", "mvThemeCol_Tab"),
            ("Tab Hovered", "mvThemeCol_TabHovered"),
            ("Tab Active", "mvThemeCol_TabActive"),
            ("Tab Unfocused", "mvThemeCol_TabUnfocused"),
            ("Tab Unfocused Active", "mvThemeCol_TabUnfocusedActive"),
        ],
        "Tables": [
            ("Table Header Background", "mvThemeCol_TableHeaderBg"),
            ("Table Border Strong", "mvThemeCol_TableBorderStrong"),
            ("Table Border Light", "mvThemeCol_TableBorderLight"),
            ("Table Row Background", "mvThemeCol_TableRowBg"),
            ("Table Row Background Alt", "mvThemeCol_TableRowBgAlt"),
        ],
        "Graph & Plots": [
            ("Plot Lines", "mvThemeCol_PlotLines"),
            ("Plot Lines Hovered", "mvThemeCol_PlotLinesHovered"),
            ("Plot Histogram", "mvThemeCol_PlotHistogram"),
            ("Plot Histogram Hovered", "mvThemeCol_PlotHistogramHovered"),
        ],
        "Inputs & Nav": [
            ("Nav Highlight", "mvThemeCol_NavHighlight"),
            ("Nav Windowing Highlight", "mvThemeCol_NavWindowingHighlight"),
            ("Nav Windowing Dim Background", "mvThemeCol_NavWindowingDimBg"),
            ("Modal Window Dim Background", "mvThemeCol_ModalWindowDimBg"),
        ],
    }

    quick_color_groups = {
        "Foundation": [
            ("App Background", "mvThemeCol_WindowBg"),
            ("Panel Background", "mvThemeCol_ChildBg"),
            ("Popup Background", "mvThemeCol_PopupBg"),
            ("Border", "mvThemeCol_Border"),
        ],
        "Text": [
            ("Primary Text", "mvThemeCol_Text"),
            ("Muted Text", "mvThemeCol_TextDisabled"),
            ("Heading Text", ("label_colors", "header")),
            ("Help Text", ("label_colors", "help_button")),
        ],
        "Controls": [
            ("Input Background", "mvThemeCol_FrameBg"),
            ("Input Hover", "mvThemeCol_FrameBgHovered"),
            ("Button", "mvThemeCol_Button"),
            ("Button Hover", "mvThemeCol_ButtonHovered"),
            ("Check Mark", "mvThemeCol_CheckMark"),
        ],
        "Navigation": [
            ("Tab", "mvThemeCol_Tab"),
            ("Active Tab", "mvThemeCol_TabActive"),
            ("Hovered Tab", "mvThemeCol_TabHovered"),
            ("Active Header", "mvThemeCol_HeaderActive"),
            ("Link", ("label_colors", "hyperlink")),
        ],
        "Tables & Logs": [
            ("Table Header", "mvThemeCol_TableHeaderBg"),
            ("Table Row", "mvThemeCol_TableRowBg"),
            ("Alternate Row", "mvThemeCol_TableRowBgAlt"),
            ("Info Log", ("log_colors", "INFO")),
            ("Warning Log", ("log_colors", "WARNING")),
            ("Error Log", ("log_colors", "ERROR")),
            ("Success Log", ("log_colors", "SUCCESS")),
        ],
    }

    def _normalize_color(value):
        if not value:
            return [0, 0, 0, 255]
        color = list(value)
        if color and isinstance(color[0], float) and max(color) <= 1.0:
            color = [int(channel * 255) for channel in color]
        if len(color) == 3:
            color.append(255)
        return color

    def _color_to_hex(value):
        color = _normalize_color(value)
        return "#{:02X}{:02X}{:02X}".format(*[max(0, min(255, int(c))) for c in color[:3]])

    def _safe_tag(value):
        return "".join(ch if ch.isalnum() else "_" for ch in str(value))

    def _get_color_value(data, target):
        if isinstance(target, tuple):
            category, key = target
            return data.get(category, {}).get(key, [0, 0, 0, 255])
        return data.get("colors", {}).get(target, [0, 0, 0, 255])

    def _set_color_value(selected_mode, target, value):
        if isinstance(target, tuple):
            category, key = target
        else:
            category, key = "colors", target
        tm.update_theme_color(palette, selected_mode, category, key, value)
        if category == "log_colors":
            _render_log_entries(state)

    def _open_color_picker_modal(label, key, initial_color, callback, button_tag):
        modal_tag = f"picker_modal_{key}"
        picker_tag = f"picker_{key}"
        if dpg.does_item_exist(modal_tag):
            dpg.delete_item(modal_tag)

        def _on_cancel_picker():
            # Revert to initial color
            callback(None, initial_color, None)
            if dpg.does_item_exist(button_tag):
                dpg.configure_item(button_tag, default_value=initial_color)
            dpg.delete_item(modal_tag)

        def _on_ok_picker():
            if dpg.does_item_exist(picker_tag):
                new_val = dpg.get_value(picker_tag)
                if dpg.does_item_exist(button_tag):
                    dpg.configure_item(button_tag, default_value=new_val)
            dpg.delete_item(modal_tag)

        with dpg.window(
            tag=modal_tag,
            label=f"Edit {label}",
            modal=True,
            width=420,
            height=470,
            no_resize=True,
        ):
            dpg.add_text(label)
            dpg.add_text(_color_to_hex(initial_color), tag=f"{picker_tag}_hex")
            dpg.add_separator()

            dpg.add_color_picker(
                tag=picker_tag,
                default_value=initial_color,
                display_rgb=True,
                display_hex=True,
                callback=lambda s, a, u: (
                    callback(s, a, u),
                    dpg.set_value(f"{picker_tag}_hex", _color_to_hex(a)),
                ),
                user_data=key,
                width=250,
            )

            dpg.add_spacer(height=10)
            with dpg.group(horizontal=True):
                dpg.add_button(label="Keep", width=100, callback=_on_ok_picker)
                dpg.add_button(label="Revert", width=100, callback=_on_cancel_picker)

    def _add_color_row(label, target, selected_mode, data, parent=None, context=""):
        value = _normalize_color(_get_color_value(data, target))
        key_part = target[1] if isinstance(target, tuple) else target
        tag_seed = _safe_tag(f"{context}_{selected_mode}_{key_part}_{label}")
        btn_tag = f"swatch_{tag_seed}"
        callback_key = f"picker_{tag_seed}"
        args = {
            "label": label,
            "target": target,
            "selected_mode": selected_mode,
            "value": value,
            "button_tag": btn_tag,
        }

        def _open_picker(sender, app_data, user_data):
            _open_color_picker_modal(
                user_data["label"],
                callback_key,
                user_data["value"],
                lambda s, a, k: _set_color_value(
                    user_data["selected_mode"], user_data["target"], a
                ),
                user_data["button_tag"],
            )

        if parent:
            with dpg.table_row(parent=parent):
                dpg.add_text(label)
                dpg.add_color_button(
                    tag=btn_tag,
                    default_value=value,
                    width=54,
                    height=24,
                    callback=_open_picker,
                    user_data=args,
                )
                dpg.add_text(_color_to_hex(value))
        else:
            with dpg.group(horizontal=True):
                dpg.add_color_button(
                    tag=btn_tag,
                    default_value=value,
                    width=54,
                    height=24,
                    callback=_open_picker,
                    user_data=args,
                )
                dpg.add_text(label)

    with dpg.window(
        tag=tag,
        label=f"Edit Palette: {palette}",
        width=720,
        height=760,
        on_close=_on_close,
    ):
        dpg.add_text(f"Palette: {palette}", color=tm.get_header_color())
        dpg.add_spacer(height=4)
        with dpg.group(horizontal=True):
            dpg.add_button(label="Save Changes", width=130, height=28, callback=_on_save)
            dpg.add_button(label="Cancel", width=110, height=28, callback=_on_cancel)
        dpg.add_separator()

        modes = list(tm.themes.get(palette, {}).keys())
        if not modes:
            dpg.add_text("No modes found for this palette.")
            return

        # Mode Selection - LOCKED to current active mode
        limit_mode = tm.current_mode
        if limit_mode == "System":
            limit_mode = tm._get_system_theme()

        if limit_mode not in modes:
            limit_mode = modes[0]

        dpg.add_text(f"Editing {limit_mode} mode")

        def _rebuild_editor(selected_mode):
            container = f"{tag}_container"
            if dpg.does_item_exist(container):
                dpg.delete_item(container)

            with dpg.group(tag=container, parent=tag):
                data = tm.themes[palette][selected_mode]
                colors_data = data.get("colors", {})

                with dpg.tab_bar():
                    with dpg.tab(label="Quick Edit"):
                        for group_name, items in quick_color_groups.items():
                            if dpg.collapsing_header(label=group_name, default_open=True):
                                with dpg.table(
                                    header_row=False,
                                    policy=dpg.mvTable_SizingFixedFit,
                                ) as table_id:
                                    dpg.add_table_column(
                                        width_fixed=True, init_width_or_weight=180
                                    )
                                    dpg.add_table_column(
                                        width_fixed=True, init_width_or_weight=70
                                    )
                                    dpg.add_table_column(
                                        width_fixed=True, init_width_or_weight=100
                                    )
                                    for label, target in items:
                                        _add_color_row(
                                            label,
                                            target,
                                            selected_mode,
                                            data,
                                            table_id,
                                            f"quick_{group_name}",
                                        )

                    with dpg.tab(label="Advanced"):
                        dpg.add_text("All DearPyGui colors")

                        # Render Categories
                        for cat_name, items in color_categories.items():
                            dpg.add_separator()
                            dpg.add_spacer(height=5)
                            if dpg.collapsing_header(
                                label=cat_name, default_open=False
                            ):
                                with dpg.table(
                                    header_row=False,
                                    policy=dpg.mvTable_SizingFixedFit,
                                ) as table_id:
                                    dpg.add_table_column(
                                        width_fixed=True, init_width_or_weight=220
                                    )
                                    dpg.add_table_column(
                                        width_fixed=True, init_width_or_weight=70
                                    )
                                    dpg.add_table_column(
                                        width_fixed=True, init_width_or_weight=100
                                    )

                                    for label, key in items:
                                        _add_color_row(
                                            label,
                                            key,
                                            selected_mode,
                                            data,
                                            table_id,
                                            f"advanced_{cat_name}",
                                        )

                    with dpg.tab(label="App Colors"):
                        lbl_dummy = data.get("label_colors", {})
                        dpg.add_text("Labels")
                        for k in ["header", "subheader", "hyperlink", "help_button"]:
                            if k in lbl_dummy:
                                _add_color_row(
                                    k.replace("_", " ").title(),
                                    ("label_colors", k),
                                    selected_mode,
                                    data,
                                    context="app_labels",
                                )

                        dpg.add_separator()
                        dpg.add_text("Status Colors")
                        stat_dummy = data.get("profile_status_colors", {})
                        for k in ["DEFAULT", "LOADED", "ERROR", "INFO"]:
                            if k in stat_dummy:
                                _add_color_row(
                                    k.title(),
                                    ("profile_status_colors", k),
                                    selected_mode,
                                    data,
                                    context="app_status",
                                )

                        dpg.add_separator()
                        dpg.add_text("Log Colors")
                        log_dummy = data.get("log_colors", {})
                        for k in ["DEBUG", "INFO", "WARNING", "ERROR", "SUCCESS"]:
                            if k in log_dummy:
                                _add_color_row(
                                    k.title(),
                                    ("log_colors", k),
                                    selected_mode,
                                    data,
                                    context="app_logs",
                                )

        # Removed Combo, just call rebuild once
        _rebuild_editor(limit_mode)
