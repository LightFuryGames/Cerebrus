"""Analytics and telemetry trend plugin."""

from __future__ import annotations

from pathlib import Path
from tkinter import Tk, filedialog

import dearpygui.dearpygui as dpg

from cerebrus.core.plugins import TabPlugin
from cerebrus.plugins.analytics.core import (
    convert_file_to_json,
    summarize_folder,
)
from cerebrus.plugins.analytics.core.converter import (
    convert_file_to_document,
    push_document_to_elasticsearch,
)
from cerebrus.plugins.analytics.core.settings import (
    AnalyticsSettings,
    load_analytics_settings,
    save_analytics_settings,
)
from cerebrus.ui.components.file_manager import _open_folder_in_explorer
from cerebrus.ui.components.shared import (
    _add_plugin_help_button as add_plugin_help_button,
)
from cerebrus.ui.components.shared import (
    load_plugin_tooltips,
    log_message,
)
from cerebrus.ui.state import UIState
from cerebrus.ui.themes import get_theme_manager

ANALYTICS_TOOLTIPS = load_plugin_tooltips("analytics/resources/tooltips.json")


def _choose_file(title: str, filetypes: list[tuple[str, str]]) -> str | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        return filedialog.askopenfilename(title=title, filetypes=filetypes) or None
    finally:
        root.destroy()


def _choose_folder(title: str) -> str | None:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        return filedialog.askdirectory(title=title) or None
    finally:
        root.destroy()


class AnalyticsPlugin(TabPlugin):
    @property
    def id(self) -> str:
        return "analytics"

    @property
    def name(self) -> str:
        return "Analytics & Trends"

    @property
    def version(self) -> str:
        return "0.1.0"

    def build_tab(self, state: UIState) -> None:
        tm = get_theme_manager()

        dpg.add_spacer(height=8)
        dpg.bind_item_theme(
            dpg.add_text("Analytics and Trend Prep"),
            tm.get_header_theme(),
        )
        dpg.add_spacer(height=6)

        source_file_tag = "analytics_source_file"
        source_folder_tag = "analytics_source_folder"
        upload_url_tag = "analytics_upload_url"
        preview_tag = "analytics_preview"
        settings = load_analytics_settings()

        def _set_preview(message: str) -> None:
            if dpg.does_item_exist(preview_tag):
                dpg.set_value(preview_tag, message)

        def _browse_source_file() -> None:
            selected = _choose_file(
                "Select Analytics Source",
                [
                    ("Report files", "*.html *.htm *.csv *.json"),
                    ("HTML reports", "*.html *.htm"),
                    ("CSV captures", "*.csv"),
                    ("JSON files", "*.json"),
                    ("All files", "*.*"),
                ],
            )
            if selected:
                dpg.set_value(source_file_tag, selected)

        def _browse_source_folder() -> None:
            selected = _choose_folder("Select Folder of Reports")
            if selected:
                dpg.set_value(source_folder_tag, selected)

        def _open_selected_source_folder() -> None:
            source = Path(dpg.get_value(source_file_tag) or "")
            folder = Path(dpg.get_value(source_folder_tag) or "")
            if source.is_file():
                _open_folder_in_explorer(source.parent)
            elif folder.is_dir():
                _open_folder_in_explorer(folder)
            elif Path(state.output_path).exists():
                _open_folder_in_explorer(Path(state.output_path))
            else:
                log_message(state, "ERROR", "No existing analytics folder to open.")

        def _convert_source_to_json() -> None:
            _save_upload_settings()
            source = Path(dpg.get_value(source_file_tag) or "")
            if not source.is_file():
                log_message(
                    state, "ERROR", "Select an HTML, CSV, or JSON source file first."
                )
                return
            try:
                output = convert_file_to_json(source)
                log_message(state, "SUCCESS", f"Analytics JSON written: {output}")
                document = convert_file_to_document(output)
                _set_preview(
                    f"Converted {source.name}\n"
                    f"Timestamp: {document.get('@timestamp', 'not found')}\n"
                    f"Fields: {len(document)}"
                )
            except Exception as exc:
                log_message(state, "ERROR", f"Analytics conversion failed: {exc}")

        def _summarize_folder() -> None:
            _save_upload_settings()
            folder = Path(dpg.get_value(source_folder_tag) or "")
            if not folder.is_dir():
                log_message(
                    state, "ERROR", "Select a folder containing report files first."
                )
                return
            try:
                output = summarize_folder(folder)
                log_message(state, "SUCCESS", f"Trend summary written: {output}")
                _set_preview(f"Summary CSV written:\n{output}")
            except Exception as exc:
                log_message(state, "ERROR", f"Trend summary failed: {exc}")

        def _save_upload_settings() -> str:
            upload_url = (dpg.get_value(upload_url_tag) or "").strip()
            current_settings = load_analytics_settings()
            save_analytics_settings(
                AnalyticsSettings(
                    elasticsearch_url=upload_url,
                    device_profile_config_path=current_settings.device_profile_config_path,
                )
            )
            log_message(state, "SUCCESS", "Analytics upload endpoint saved.")
            return upload_url

        def _upload_source_to_elasticsearch() -> None:
            upload_url = _save_upload_settings()
            source = Path(dpg.get_value(source_file_tag) or "")
            if not source.is_file():
                log_message(
                    state, "ERROR", "Select an HTML, CSV, or JSON source file first."
                )
                return

            if not upload_url:
                log_message(
                    state,
                    "ERROR",
                    "Enter the Elasticsearch document endpoint URL before uploading.",
                )
                return

            try:
                document = convert_file_to_document(source)
                status_code, response_text = push_document_to_elasticsearch(
                    document,
                    upload_url,
                )
                if status_code in {200, 201}:
                    log_message(
                        state,
                        "SUCCESS",
                        f"Uploaded analytics document to Elasticsearch: {source.name}",
                    )
                    _set_preview(
                        f"Uploaded {source.name}\n"
                        f"Endpoint: {upload_url}\n"
                        f"Status: {status_code}\n"
                        f"Timestamp: {document.get('@timestamp', 'not found')}"
                    )
                else:
                    log_message(
                        state,
                        "ERROR",
                        f"Elasticsearch upload failed: {status_code} {response_text}",
                    )
                    _set_preview(
                        f"Upload failed for {source.name}\n"
                        f"Endpoint: {upload_url}\n"
                        f"Status: {status_code}\n"
                        f"Response: {response_text}"
                    )
            except Exception as exc:
                log_message(state, "ERROR", f"Elasticsearch upload failed: {exc}")

        def _save_upload_settings_only() -> None:
            upload_url = _save_upload_settings()
            _set_preview(
                "Saved Elasticsearch upload endpoint."
                if upload_url
                else "Cleared Elasticsearch upload endpoint."
            )

        with dpg.table(
            header_row=False,
            borders_innerH=False,
            borders_outerH=False,
            borders_innerV=False,
            borders_outerV=False,
        ):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=150)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=30)
            dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)

            with dpg.table_row():
                dpg.add_text("Source File:")
                add_plugin_help_button(ANALYTICS_TOOLTIPS, "analytics_source_file")
                with dpg.group(horizontal=True):
                    dpg.add_input_text(
                        tag=source_file_tag,
                        hint="HTML, CSV, or JSON report",
                        width=720,
                    )
                    dpg.add_button(label="Browse", callback=_browse_source_file)
                    dpg.add_button(
                        label="Open Folder", callback=_open_selected_source_folder
                    )

            with dpg.table_row():
                dpg.add_text("Report Folder:")
                add_plugin_help_button(ANALYTICS_TOOLTIPS, "analytics_source_folder")
                with dpg.group(horizontal=True):
                    dpg.add_input_text(
                        tag=source_folder_tag,
                        hint="Folder containing generated reports or converted JSON",
                        width=720,
                    )
                    dpg.add_button(label="Browse", callback=_browse_source_folder)

            with dpg.table_row():
                dpg.add_text("Upload Endpoint:")
                add_plugin_help_button(ANALYTICS_TOOLTIPS, "analytics_upload_url")
                with dpg.group(horizontal=True):
                    dpg.add_input_text(
                        tag=upload_url_tag,
                        default_value=settings.elasticsearch_url,
                        hint="http://host:9200/index-name/_doc",
                        width=720,
                    )
                    dpg.add_button(label="Save", callback=_save_upload_settings_only)

        dpg.add_spacer(height=10)
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Convert File to Analytics JSON",
                callback=_convert_source_to_json,
                width=240,
                height=30,
            )
            dpg.add_button(
                label="Build Trend Summary CSV",
                callback=_summarize_folder,
                width=210,
                height=30,
            )
            dpg.add_button(
                label="Upload Analytics Document",
                callback=_upload_source_to_elasticsearch,
                width=220,
                height=30,
            )

        dpg.add_spacer(height=8)
        dpg.add_input_text(
            tag=preview_tag,
            multiline=True,
            readonly=True,
            width=-1,
            height=95,
            default_value=(
                "Analytics output details will appear here.\n"
                "Device profile tier enrichment uses the cached Profiling tab "
                "BaseDeviceProfiles.ini reference when one is set."
            ),
        )
