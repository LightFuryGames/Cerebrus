"""Palette Management and Theme Editor components."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from tkinter import Tk, filedialog

import dearpygui.dearpygui as dpg

from ..state import UIState
from ..themes import get_theme_manager
from .panels.logs.logs_panel import _render_log_entries
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
                # Allow overwrite? Prompt? For now, auto-rename if collision?
                # Or just overwrite if user selected it?
                # Let's simple copy.
                pass

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
            except:
                pass

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

    def _open_color_picker_modal(label, key, initial_color, callback, button_tag):
        modal_tag = f"picker_modal_{key}"
        if dpg.does_item_exist(modal_tag):
            dpg.delete_item(modal_tag)

        def _on_cancel_picker():
            # Revert to initial color
            callback(None, initial_color, None)
            if dpg.does_item_exist(button_tag):
                dpg.configure_item(button_tag, default_value=initial_color)
            dpg.delete_item(modal_tag)

        def _on_ok_picker():
            picker_tag = f"picker_{key}"
            if dpg.does_item_exist(picker_tag):
                new_val = dpg.get_value(picker_tag)
                if dpg.does_item_exist(button_tag):
                    dpg.configure_item(button_tag, default_value=new_val)
            dpg.delete_item(modal_tag)

        # Ensure correct window size for picker
        with dpg.window(
            tag=modal_tag, label=f"Edit {label}", modal=True, width=400, height=450
        ):
            dpg.add_text("Adjust color to see live preview.", color=(200, 200, 200))

            picker_tag = f"picker_{key}"
            dpg.add_color_picker(
                tag=picker_tag,
                default_value=initial_color,
                display_rgb=True,
                display_hex=True,
                callback=callback,
                user_data=key,
                width=250,
            )

            dpg.add_spacer(height=10)
            with dpg.group(horizontal=True):
                dpg.add_button(label="OK (Keep)", width=100, callback=_on_ok_picker)

    # ... [Layout code] ...

    with dpg.window(
        tag=tag,
        label=f"Edit Palette: {palette}",
        width=550,
        height=700,
        on_close=_on_close,
    ):
        dpg.add_text(f"Editing: {palette}", color=(100, 255, 100))
        dpg.add_text("Changes are previewed instantly.", color=(150, 150, 150))
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

        dpg.add_text(f"Mode: {limit_mode} (Active)", color=(200, 200, 200))

        def _rebuild_editor(selected_mode):
            container = f"{tag}_container"
            if dpg.does_item_exist(container):
                dpg.delete_item(container)

            with dpg.group(tag=container, parent=tag):
                data = tm.themes[palette][selected_mode]
                colors_data = data.get("colors", {})

                with dpg.tab_bar():
                    with dpg.tab(label="UI Colors"):
                        dpg.add_text("Core UI Colors (DearPyGui)")

                        # Render Categories
                        for cat_name, items in color_categories.items():
                            dpg.add_separator()
                            dpg.add_spacer(height=5)
                            if dpg.collapsing_header(label=cat_name):
                                with dpg.table(
                                    header_row=False,
                                    policy=dpg.mvTable_SizingStretchProp,
                                ):
                                    dpg.add_table_column(
                                        width_fixed=True, init_width_or_weight=200
                                    )
                                    dpg.add_table_column(width_stretch=True)

                                    for label, key in items:
                                        val = colors_data.get(key, [0, 0, 0, 255])
                                        if len(val) == 3:
                                            val = list(val) + [255]

                                        with dpg.table_row():
                                            dpg.add_text(label)
                                            # Use a Button with background color as the "swatch"
                                            # When clicked, opens modal
                                            # We need a unique tag for the swatch key
                                            btn_tag = f"swatch_{selected_mode}_{key}"

                                            # Define callback for the PICKER that updates theme AND this button
                                            # The button background update is handled by theme update if we use theme colors?
                                            # No, button background is Button Color.
                                            # We want this specific button to show the color.
                                            # Use dpg.add_color_button for preview, it has no callback but can show color.
                                            # Or add_button and set standard theme color... hard.
                                            # dpg.add_color_button is best. Click callback? dpg 1.0 color_button doesn't support callback directly?
                                            # It does! callback=...

                                            dpg.add_color_button(
                                                tag=btn_tag,
                                                default_value=val,
                                                width=50,
                                                height=25,
                                                callback=lambda s, a, u: _open_color_picker_modal(
                                                    u[0],
                                                    u[1],
                                                    u[2],
                                                    lambda s, a, k: (
                                                        tm.update_theme_color(
                                                            palette,
                                                            selected_mode,
                                                            "colors",
                                                            k,
                                                            a,
                                                        )
                                                    ),
                                                    s,  # Pass button tag
                                                ),
                                                user_data=(label, key, val),
                                            )

                    with dpg.tab(label="Custom Colors"):
                        dpg.add_text(
                            "Application Specific Colors (Requires Restart for some)"
                        )

                        # Headers
                        dpg.add_text("Headers")
                        lbl_dummy = data.get("label_colors", {})
                        for k in ["header", "subheader"]:
                            val = lbl_dummy.get(k, [255, 255, 255])

                            with dpg.group(horizontal=True):
                                btn_tag = f"swatch_{selected_mode}_label_{k}"
                                dpg.add_color_button(
                                    tag=btn_tag,
                                    default_value=val,
                                    width=50,
                                    height=25,
                                    label=k.title(),
                                    callback=lambda s, a, u: _open_color_picker_modal(
                                        u[0],
                                        u[1],
                                        u[2],
                                        lambda s, a, k: tm.update_theme_color(
                                            palette, selected_mode, "label_colors", k, a
                                        ),
                                        s,
                                    ),
                                    user_data=(k.title(), k, val),
                                )
                                dpg.add_text(k.title())

                        dpg.add_separator()
                        dpg.add_text("Status Colors")
                        stat_dummy = data.get("profile_status_colors", {})
                        for k in ["DEFAULT", "LOADED", "ERROR", "INFO"]:
                            val = stat_dummy.get(k, [255, 255, 255])
                            with dpg.group(horizontal=True):
                                btn_tag = f"swatch_{selected_mode}_status_{k}"
                                dpg.add_color_button(
                                    tag=btn_tag,
                                    default_value=val,
                                    width=50,
                                    height=25,
                                    callback=lambda s, a, u: _open_color_picker_modal(
                                        u[0],
                                        u[1],
                                        u[2],
                                        lambda s, a, k: tm.update_theme_color(
                                            palette,
                                            selected_mode,
                                            "profile_status_colors",
                                            k,
                                            a,
                                        ),
                                        s,
                                    ),
                                    user_data=(k, k, val),
                                )
                                dpg.add_text(k)

                        dpg.add_separator()
                        dpg.add_text("Log Colors")
                        log_dummy = data.get("log_colors", {})
                        for k in ["DEBUG", "INFO", "WARNING", "ERROR", "SUCCESS"]:
                            val = log_dummy.get(k, [255, 255, 255])
                            with dpg.group(horizontal=True):
                                btn_tag = f"swatch_{selected_mode}_log_{k}"
                                dpg.add_color_button(
                                    tag=btn_tag,
                                    default_value=val,
                                    width=50,
                                    height=25,
                                    callback=lambda s, a, u: _open_color_picker_modal(
                                        u[0],
                                        u[1],
                                        u[2],
                                        lambda s, a, k: (
                                            tm.update_theme_color(
                                                palette,
                                                selected_mode,
                                                "log_colors",
                                                k,
                                                a,
                                            ),
                                            _render_log_entries(state),
                                        ),
                                        s,
                                    ),
                                    user_data=(k, k, val),
                                )
                                dpg.add_text(k)

                dpg.add_separator()
                with dpg.group(horizontal=True):
                    dpg.add_button(
                        label="Save Changes", width=150, height=30, callback=_on_save
                    )
                    dpg.add_button(
                        label="Cancel", width=150, height=30, callback=_on_cancel
                    )

        # Removed Combo, just call rebuild once
        _rebuild_editor(limit_mode)
