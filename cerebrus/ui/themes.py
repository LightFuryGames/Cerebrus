import json
import os
import winreg
from pathlib import Path

import dearpygui.dearpygui as dpg

from cerebrus.core.paths import get_app_data_dir


class ThemeManager:
    def __init__(self):
        self.themes = {}  # {palette_name: {mode: theme_data}}
        self.theme_tags = {}  # {palette_name: {mode: dpg_tag}}
        self.theme_color_ids = {}  # {palette: {mode: {color_key: dpg_item_id}}}
        self.aux_theme_ids = {}  # {category: {key: dpg_color_item_id}}
        self.current_palette = "Standard"
        self.current_mode = "Dark"
        self._initialize_aux_themes()

        # We look for themes in two places:
        # 1. Bundled with the app (read-only)
        # 2. In the user's AppData (writable)
        self.bundled_palettes_dir = (
            Path(__file__).parent / "resources" / "AppColorPalettes"
        )
        self.user_palettes_dir = get_app_data_dir() / "Themes"

        self._discover_and_load_themes()

    def _discover_and_load_themes(self):
        """Scan both bundled and user palette directories and load all JSON themes."""
        # Load bundled themes first (so user themes can override them)
        if self.bundled_palettes_dir.exists():
            self._load_from_dir(self.bundled_palettes_dir)

        # Load user themes
        try:
            if not self.user_palettes_dir.exists():
                self.user_palettes_dir.mkdir(parents=True, exist_ok=True)
            self._load_from_dir(self.user_palettes_dir)
        except (PermissionError, OSError) as e:
            print(
                f"Warning: Could not access or create user themes directory at {self.user_palettes_dir}: {e}"
            )

    def _load_from_dir(self, directory: Path):
        """Load all JSON themes from a specific directory."""
        for json_file in directory.glob("*.json"):
            try:
                with open(json_file, "r") as f:
                    data = json.load(f)

                palette = data.get("palette", "Unknown")
                mode = data.get("mode", "Dark")

                if palette not in self.themes:
                    self.themes[palette] = {}
                    self.theme_tags[palette] = {}
                    self.theme_color_ids[palette] = {}

                if mode not in self.theme_color_ids[palette]:
                    self.theme_color_ids[palette][mode] = {}

                self.themes[palette][mode] = data
                self._create_dpg_theme(palette, mode, data)
            except Exception as e:
                print(f"Error loading theme {json_file}: {e}")

    def _create_dpg_theme(self, palette, mode, data):
        """Register a theme variant with DearPyGui."""
        tag = f"theme_{palette.lower().replace(' ', '_')}_{mode.lower()}"
        colors = data.get("colors", {})

        # Reset ID tracking for this theme variant
        if palette not in self.theme_color_ids:
            self.theme_color_ids[palette] = {}
        self.theme_color_ids[palette][mode] = {}

        if dpg.does_item_exist(tag):
            dpg.delete_item(tag)

        with dpg.theme(tag=tag):
            with dpg.theme_component(dpg.mvAll):
                for col_name, color in colors.items():
                    if hasattr(dpg, col_name):
                        col_id = getattr(dpg, col_name)
                        # Ensure color is a tuple/list of 3 or 4
                        # We use add_theme_color and capture the returned ID
                        item_id = dpg.add_theme_color(
                            col_id, color, category=dpg.mvThemeCat_Core
                        )
                        self.theme_color_ids[palette][mode][col_name] = item_id

        self.theme_tags[palette][mode] = tag

    def _initialize_aux_themes(self):
        """Create persistent themes for Headers, Subheaders, Logs, etc."""

        # Helper to create a single-color theme
        def create_simple_theme(tag, default_color):
            if dpg.does_item_exist(tag):
                dpg.delete_item(tag)
            with dpg.theme(tag=tag):
                with dpg.theme_component(dpg.mvAll):
                    return dpg.add_theme_color(
                        dpg.mvThemeCol_Text, default_color, category=dpg.mvThemeCat_Core
                    )

        self.aux_theme_ids["header"] = create_simple_theme(
            "theme_aux_header", (120, 180, 255)
        )
        self.aux_theme_ids["subheader"] = create_simple_theme(
            "theme_aux_subheader", (200, 200, 200)
        )

        # Profile Status Themes
        self.aux_theme_ids["profile_status"] = {}
        for status in ["DEFAULT", "LOADED", "ERROR", "INFO"]:
            self.aux_theme_ids["profile_status"][status] = create_simple_theme(
                f"theme_aux_profile_{status}", (255, 255, 255)
            )

        # Log Themes
        self.aux_theme_ids["log"] = {}
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "SUCCESS"]:
            self.aux_theme_ids["log"][level] = create_simple_theme(
                f"theme_aux_log_{level}", (255, 255, 255)
            )

        self.aux_theme_ids["help_button"] = create_simple_theme(
            "theme_aux_help", (100, 100, 100)
        )
        self.aux_theme_ids["hyperlink"] = create_simple_theme(
            "theme_aux_hyperlink", (59, 130, 246)
        )

        # Transparent Log Input Theme
        if dpg.does_item_exist("theme_log_input"):
            dpg.delete_item("theme_log_input")
        with dpg.theme(tag="theme_log_input"):
            with dpg.theme_component(dpg.mvAll):
                dpg.add_theme_color(
                    dpg.mvThemeCol_FrameBg, (0, 0, 0, 0), category=dpg.mvThemeCat_Core
                )
                dpg.add_theme_color(
                    dpg.mvThemeCol_FrameBgHovered,
                    (0, 0, 0, 0),
                    category=dpg.mvThemeCat_Core,
                )
                dpg.add_theme_color(
                    dpg.mvThemeCol_FrameBgActive,
                    (0, 0, 0, 0),
                    category=dpg.mvThemeCat_Core,
                )
                dpg.add_theme_color(
                    dpg.mvThemeCol_Border, (0, 0, 0, 0), category=dpg.mvThemeCat_Core
                )
                dpg.add_theme_style(
                    dpg.mvStyleVar_FramePadding, 0, 0, category=dpg.mvThemeCat_Core
                )
                dpg.add_theme_style(
                    dpg.mvStyleVar_ItemSpacing, 0, 0, category=dpg.mvThemeCat_Core
                )

    def _update_aux_themes(self):
        """Update the persistent aux themes with values from the current active palette."""
        data = self._get_active_data()
        if not data:
            return

        # Update Headers
        lbl = data.get("label_colors", {})
        if "header" in lbl and self.aux_theme_ids["header"]:
            dpg.configure_item(self.aux_theme_ids["header"], value=tuple(lbl["header"]))
        if "subheader" in lbl and self.aux_theme_ids["subheader"]:
            dpg.configure_item(
                self.aux_theme_ids["subheader"], value=tuple(lbl["subheader"])
            )

        # Update Profile Status
        st = data.get("profile_status_colors", {})
        for status, color in st.items():
            if status in self.aux_theme_ids["profile_status"]:
                dpg.configure_item(
                    self.aux_theme_ids["profile_status"][status], value=tuple(color)
                )

        # Update Logs
        lg = data.get("log_colors", {})
        for level, color in lg.items():
            if level in self.aux_theme_ids["log"]:
                dpg.configure_item(self.aux_theme_ids["log"][level], value=tuple(color))

        # Update Misc
        if "hyperlink" in lbl and self.aux_theme_ids["hyperlink"]:
            dpg.configure_item(
                self.aux_theme_ids["hyperlink"], value=tuple(lbl["hyperlink"])
            )

        if "help_button" in lbl and self.aux_theme_ids["help_button"]:
            dpg.configure_item(
                self.aux_theme_ids["help_button"], value=tuple(lbl["help_button"])
            )

    def apply_theme(self, palette=None, mode=None):
        if palette:
            self.current_palette = palette
        if mode:
            self.current_mode = mode

        target_mode = self.current_mode
        if target_mode == "System":
            target_mode = self._get_system_theme()

        if target_mode not in ["Light", "Dark"]:
            target_mode = "Dark"

        palette_data = self.themes.get(self.current_palette, {})
        theme_tag = self.theme_tags.get(self.current_palette, {}).get(target_mode)

        # Fallback logic
        if not theme_tag:
            # Try to find any mode in the requested palette
            if palette_data:
                first_mode = list(palette_data.keys())[0]
                theme_tag = self.theme_tags[self.current_palette][first_mode]
            else:
                # Absolute fallback to Standard Dark
                theme_tag = self.theme_tags.get("Standard", {}).get("Dark")

        if theme_tag:
            dpg.bind_theme(theme_tag)
            self._update_aux_themes()

    def _get_system_theme(self):
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "Light" if value == 1 else "Dark"
        except Exception:
            return "Dark"

    def _get_active_data(self):
        """Helper to get the data for the currently applied theme."""
        mode = self.current_mode
        if mode == "System":
            mode = self._get_system_theme()

        palette_data = self.themes.get(self.current_palette, {})
        data = palette_data.get(mode)

        if not data and palette_data:
            # Try the other mode in the same palette
            other_mode = "Light" if mode == "Dark" else "Dark"
            data = palette_data.get(other_mode)

        if not data:
            # Try Standard
            data = self.themes.get("Standard", {}).get(mode)

        return data

    def get_header_color(self):
        data = self._get_active_data()
        if data and "label_colors" in data:
            return tuple(data["label_colors"].get("header", [120, 180, 255]))

        # Fallback
        mode = self.current_mode
        if mode == "System":
            mode = self._get_system_theme()
        return (0, 0, 0) if mode == "Light" else (120, 180, 255)

    def get_subheader_color(self):
        data = self._get_active_data()
        if data and "label_colors" in data:
            return tuple(data["label_colors"].get("subheader", [200, 200, 200]))

        # Fallback
        mode = self.current_mode
        if mode == "System":
            mode = self._get_system_theme()
        return (20, 20, 25) if mode == "Light" else (200, 200, 200)

    def get_text_color(self, key: str, default: tuple = (200, 200, 200)):
        """Get a specific text color from label_colors."""
        data = self._get_active_data()
        if data and "label_colors" in data:
            return tuple(data["label_colors"].get(key, default))
        return default

    def get_profile_status_colors(self):
        data = self._get_active_data()
        if data and "profile_status_colors" in data:
            # Convert lists to tuples
            return {k: tuple(v) for k, v in data["profile_status_colors"].items()}

        # Manual Fallback
        mode = self.current_mode
        if mode == "System":
            mode = self._get_system_theme()
        if mode == "Light":
            return {
                "DEFAULT": (110, 60, 0),
                "LOADED": (0, 90, 0),
                "ERROR": (140, 0, 0),
                "INFO": (0, 40, 120),
            }
        else:
            return {
                "DEFAULT": (255, 210, 120),
                "LOADED": (15, 240, 15),
                "ERROR": (255, 120, 120),
                "INFO": (120, 200, 255),
            }

    def get_log_colors(self):
        data = self._get_active_data()
        if data and "log_colors" in data:
            return {k: tuple(v) for k, v in data["log_colors"].items()}

        # Manual Fallback
        mode = self.current_mode
        if mode == "System":
            mode = self._get_system_theme()
        if mode == "Light":
            return {
                "DEBUG": (80, 80, 90),
                "INFO": (0, 40, 120),
                "WARNING": (110, 60, 0),
                "ERROR": (140, 0, 0),
                "SUCCESS": (0, 90, 0),
            }
        else:
            return {
                "DEBUG": (170, 170, 170),
                "INFO": (120, 200, 255),
                "WARNING": (255, 210, 120),
                "ERROR": (255, 120, 120),
                "SUCCESS": (15, 240, 15),
            }

    def reload_palettes(self):
        """Reload all JSON files from the palettes directory."""
        self.themes = {}
        self.theme_tags = {}
        self._discover_and_load_themes()
        self.apply_theme()

    def update_theme_color(
        self, palette: str, mode: str, category: str, key: str, value: tuple | list
    ) -> None:
        """
        Update a specific color in the theme data and re-apply if active.
        """
        if palette not in self.themes:
            self.themes[palette] = {}
        if palette not in self.theme_tags:
            self.theme_tags[palette] = {}

        if mode not in self.themes[palette]:
            self.themes[palette][mode] = {
                "palette": palette,
                "mode": mode,
                "colors": {},
            }

        data = self.themes[palette][mode]

        if category == "colors":
            if "colors" not in data:
                data["colors"] = {}

            # Convert float 0-1.0 to int 0-255 if needed
            # DPG add_color_edit often returns normalized floats
            if (
                value
                and len(value) >= 3
                and isinstance(value[0], float)
                and max(value) <= 1.0
            ):
                value = tuple(int(x * 255) for x in value)

            data["colors"][key] = value

            # DEBUG: Check what we are receiving
            # print(f"Theme Update: {key} -> {value} (Types: {[type(x) for x in value]})")

            # OPTIMIZED UPDATE:
            # Check if we have an existing DPG item ID for this color
            item_id = self.theme_color_ids.get(palette, {}).get(mode, {}).get(key)

            if item_id and dpg.does_item_exist(item_id):
                # Efficiently update just this color node
                dpg.configure_item(item_id, value=value)
            else:
                # Fallback: Re-create DPG theme if we can't find the item (rare)
                # print(f"Fallback rebuild for {key}")
                self._create_dpg_theme(palette, mode, data)

                # If this is current theme, re-apply needed?
                # _create_dpg_theme deletes the tag, so we MUST rebind.
                # But dpg.configure_item does NOT require rebind.
                is_current_palette = self.current_palette == palette
                is_current_mode = self.current_mode == mode
                is_system_match = (
                    self.current_mode == "System" and self._get_system_theme() == mode
                )

                if is_current_palette and (is_current_mode or is_system_match):
                    self.apply_theme()

        else:
            # Custom categories (label_colors, etc.)
            if category not in data:
                data[category] = {}
            data[category][key] = value

            # Update dynamic aux themes
            self._update_aux_themes()

    def save_theme(self, palette: str, mode: str) -> None:
        """Save the current in-memory theme data to its JSON file."""
        if palette not in self.themes or mode not in self.themes[palette]:
            return

        data = self.themes[palette][mode]

        # Determine filename. Try to find existing file for this palette.
        filename = f"{palette.lower().replace(' ', '_')}.json"

        # If the palette has multiple modes split across files, we might need logic.
        # But here we assume one file per palette or one file per variant?
        # _discover_and_load_themes reads all JSONs.
        # We should check if we loaded this from a specific file?
        # Metadata doesn't store source filename currently.
        # Simple approach: one file per palette containing both modes?
        # Current loader treats each JSON as a SINGLE mode variant (palette + mode fields).
        # So we should save as {palette}_{mode}.json ?
        # Or if we want to bundle...
        # The loader: "palette" and "mode" are keys in the JSON.
        # So each JSON file represents ONE variant.
        # So filename should be unique per variant.

        filename = f"{palette.lower().replace(' ', '_')}_{mode.lower()}.json"

        # Always save to the user's writable palettes directory
        file_path = self.user_palettes_dir / filename

        try:
            # Ensure the directory exists before saving (if it didn't exist or was deleted)
            if not self.user_palettes_dir.exists():
                self.user_palettes_dir.mkdir(parents=True, exist_ok=True)

            with open(file_path, "w") as f:
                json.dump(data, f, indent=4)
            print(f"Saved theme to {file_path}")
        except Exception as e:
            print(f"Failed to save theme: {e}")

    def get_header_theme(self):
        return "theme_aux_header"

    def get_subheader_theme(self):
        return "theme_aux_subheader"

    def get_profile_status_theme(self, status):
        return f"theme_aux_profile_{status}"

    def get_log_theme(self, level):
        return f"theme_aux_log_{level}"

    def get_hyperlink_theme(self):
        return "theme_aux_hyperlink"

    def get_help_theme(self):
        return "theme_aux_help"


_theme_manager = None


def get_theme_manager():
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager
