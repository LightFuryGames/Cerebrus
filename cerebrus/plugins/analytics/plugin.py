"""Analytics and telemetry trend plugin (DPG wiring layer)."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

import dearpygui.dearpygui as dpg

from cerebrus.core.plugins import TabPlugin
from cerebrus.plugins.analytics.controller import AnalyticsController
from cerebrus.ui.components.file_manager import (
    open_folder_in_explorer,
    pick_file,
    pick_folder,
)
from cerebrus.ui.components.shared import (
    add_button_tooltip,
    add_plugin_help_button,
    load_plugin_tooltips,
    log_message,
)
from cerebrus.ui.state import UIState
from cerebrus.ui.themes import get_theme_manager

ANALYTICS_TOOLTIPS = load_plugin_tooltips("analytics/resources/tooltips.json")

_FILE_DIALOG_TYPES = [
    ("Report files", "*.html *.htm *.csv *.json"),
    ("HTML reports", "*.html *.htm"),
    ("CSV captures", "*.csv"),
    ("JSON files", "*.json"),
    ("All files", "*.*"),
]


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

        def _log(level: str, message: str) -> None:
            log_message(state, level, message, source="ANALYTICS")

        controller = AnalyticsController(logger=_log)
        settings = controller.load_settings()

        source_file_tag = "analytics_source_file"
        output_dir_tag = "analytics_output_dir"
        upload_url_tag = "analytics_upload_url"
        delete_after_upload_tag = "analytics_delete_after_upload"

        # Guards against double-clicks during a long-running upload — DPG
        # callbacks are reentrant from the user's POV even while a worker
        # thread is mid-request.
        upload_in_flight = threading.Lock()

        def _run_in_background(label: str, work: Callable[[], None]) -> None:
            """Spawn ``work`` on a daemon thread; refuse if one is in flight.

            Elasticsearch single uploads carry a 30s request timeout and bulk
            uploads carry a 60s timeout. Running them on the DPG callback
            thread freezes the entire UI for that duration. The worker logs
            and mutates DPG state directly — DPG serialises those calls, so
            no extra marshalling is required.
            """
            if not upload_in_flight.acquire(blocking=False):
                _log("WARNING", f"{label} ignored: another upload is still running.")
                return

            def _runner() -> None:
                try:
                    work()
                except Exception as exc:
                    _log("ERROR", f"{label} crashed: {exc}")
                finally:
                    upload_in_flight.release()

            threading.Thread(target=_runner, name=f"analytics-{label}", daemon=True).start()

        def _emit_summary(lines: list[str] | str) -> None:
            if isinstance(lines, str):
                lines = lines.splitlines() or [lines]
            for line in lines:
                _log("INFO", line)

        def _get_source_path() -> Path | None:
            value = dpg.get_value(source_file_tag) or ""
            return Path(value) if value else None

        def _get_output_dir() -> Path | None:
            value = (dpg.get_value(output_dir_tag) or "").strip()
            return Path(value) if value else None

        def _resolve_targets() -> list[Path]:
            # The output-dir field doubles as a folder of pre-built
            # ``.analytics.json`` files. If the user has set it AND the source
            # file slot is empty, fall back to globbing the directory so a
            # single Upload click can re-push everything in that folder.
            return controller.resolve_targets(_get_source_path(), _get_output_dir())

        def _save_upload_url() -> str:
            return controller.save_upload_url(dpg.get_value(upload_url_tag) or "")

        def _browse_source_file() -> None:
            selected = pick_file("Select Analytics Source", _FILE_DIALOG_TYPES)
            if selected:
                dpg.set_value(source_file_tag, selected)

        def _browse_output_dir() -> None:
            selected = pick_folder("Select Output File Path")
            if selected:
                dpg.set_value(output_dir_tag, selected)

        def _use_profiling_output() -> None:
            profiling_output = Path(state.output_path)
            if not profiling_output.exists() or not profiling_output.is_dir():
                _log("ERROR", "Profiling output path is not set or does not exist.")
                return
            dpg.set_value(output_dir_tag, str(profiling_output))
            _log("INFO", f"Output File Path set to Profiling output: {profiling_output}")

        def _open_selected_source_folder() -> None:
            source = _get_source_path()
            folder = _get_output_dir()
            if source and source.is_file():
                open_folder_in_explorer(source.parent)
            elif folder and folder.is_dir():
                open_folder_in_explorer(folder)
            elif Path(state.output_path).exists():
                open_folder_in_explorer(Path(state.output_path))
            else:
                _log("ERROR", "No existing analytics folder to open.")

        def _convert_source_to_json() -> None:
            source = _get_source_path()
            if not source or not source.is_file():
                _log("ERROR", "Select an HTML, CSV, or JSON source file first.")
                return
            output_dir = _get_output_dir()
            try:
                output = controller.convert_to_json_file(source, output_dir=output_dir)
                _log("SUCCESS", f"Analytics JSON written: {output}")
                document = controller.convert_to_document(output)
                _emit_summary(
                    [
                        f"Converted {source.name}",
                        f"Timestamp: {document.get('@timestamp', 'not found')}",
                        f"Fields: {len(document)}",
                    ]
                )
                # Auto-select the generated JSON so the user can hit
                # "Upload Analytics Document" immediately without re-browsing.
                dpg.set_value(source_file_tag, str(output))
            except Exception as exc:
                _log("ERROR", f"Analytics conversion failed: {exc}")

        def _prepare_upload() -> tuple[str, list[Path]] | None:
            """Validate input on the UI thread before spawning a worker."""
            url = _save_upload_url()
            targets = _resolve_targets()
            if not targets:
                _log(
                    "ERROR",
                    "Select a Source File or an Output File Path containing "
                    "*.analytics.json files first.",
                )
                return None
            if not url:
                _log(
                    "ERROR",
                    "Enter the Elasticsearch document endpoint URL before uploading.",
                )
                return None
            return url, targets

        def _upload_individual() -> None:
            prep = _prepare_upload()
            if prep is None:
                return
            url, targets = prep
            delete_after = bool(dpg.get_value(delete_after_upload_tag))
            _log("INFO", f"Upload started for {len(targets)} document(s).")

            def _work() -> None:
                outcome = controller.upload_individual(
                    targets, url, delete_after_success=delete_after
                )
                _emit_summary(outcome.summary_lines)

            _run_in_background("upload", _work)

        def _save_settings_only() -> None:
            url = _save_upload_url()
            _emit_summary(
                "Saved Elasticsearch upload endpoint."
                if url
                else "Cleared Elasticsearch upload endpoint."
            )

        dpg.add_spacer(height=8)
        dpg.bind_item_theme(
            dpg.add_text("Analytics and Trend Prep"),
            tm.get_header_theme(),
        )
        dpg.add_spacer(height=6)

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
                        hint="HTML, CSV, or JSON report (auto-filled after Convert)",
                        width=720,
                    )
                    dpg.add_button(label="Browse", callback=_browse_source_file)
                    dpg.add_button(
                        label="Open Folder", callback=_open_selected_source_folder
                    )

            with dpg.table_row():
                dpg.add_text("Output File Path:")
                add_plugin_help_button(ANALYTICS_TOOLTIPS, "analytics_output_dir")
                with dpg.group(horizontal=True):
                    dpg.add_input_text(
                        tag=output_dir_tag,
                        hint="Optional. If empty, .analytics.json is written next to the source.",
                        width=720,
                    )
                    dpg.add_button(label="Browse", callback=_browse_output_dir)
                    use_profiling_btn = dpg.add_button(
                        label="Use Profiling Output",
                        callback=_use_profiling_output,
                    )
                    add_button_tooltip(
                        use_profiling_btn,
                        ANALYTICS_TOOLTIPS,
                        "analytics_btn_use_profiling_output",
                    )
                    add_plugin_help_button(
                        ANALYTICS_TOOLTIPS, "analytics_btn_use_profiling_output"
                    )

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
                    dpg.add_button(label="Save", callback=_save_settings_only)

        dpg.add_spacer(height=10)
        with dpg.group(horizontal=True):
            for label, key, callback, width in (
                (
                    "Convert File to Analytics JSON",
                    "analytics_btn_convert",
                    _convert_source_to_json,
                    240,
                ),
                (
                    "Upload Analytics Document",
                    "analytics_btn_upload",
                    _upload_individual,
                    220,
                ),
            ):
                btn = dpg.add_button(
                    label=label, callback=callback, width=width, height=30
                )
                add_button_tooltip(btn, ANALYTICS_TOOLTIPS, key)
                add_plugin_help_button(ANALYTICS_TOOLTIPS, key)

            dpg.add_checkbox(
                tag=delete_after_upload_tag,
                label="Delete Analytics JSON after Upload Success",
                default_value=True,
            )
