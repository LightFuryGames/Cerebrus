"""Dialog for generating A/B Comparison Reports."""

from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Optional

import dearpygui.dearpygui as dpg

from cerebrus.tools.stats_compare import generate_comparison_report
from cerebrus.ui.components.file_manager import _read_csv_metadata
from cerebrus.ui.components.shared import log_message
from cerebrus.ui.state import UIState


def _show_ab_compare_dialog(state: UIState) -> None:
    """Show the A/B compare report selection dialog."""
    dialog_id = "ab_compare_dialog"
    if dpg.does_item_exist(dialog_id):
        dpg.delete_item(dialog_id)

    with dpg.window(
        tag=dialog_id,
        label="Generate A/B Compare Report",
        modal=True,
        show=True,
        no_collapse=True,
        no_resize=True,
        width=600,
        height=300,
    ):
        dpg.add_text("Select two CSV profile runs to compare.")
        dpg.add_spacer(height=10)

        # Baseline Selection
        with dpg.group(horizontal=True):
            dpg.add_text("Baseline CSV:")
            dpg.add_input_text(tag="ab_baseline_path", width=350, readonly=True)
            dpg.add_button(
                label="Browse", callback=lambda: _browse_csv("ab_baseline_path", state)
            )

        dpg.add_spacer(height=10)

        # Target Selection
        with dpg.group(horizontal=True):
            dpg.add_text("Target CSV:  ")
            dpg.add_input_text(tag="ab_target_path", width=350, readonly=True)
            dpg.add_button(
                label="Browse", callback=lambda: _browse_csv("ab_target_path", state)
            )

        dpg.add_spacer(height=30)

        # Action Buttons
        with dpg.group(horizontal=True):
            dpg.add_button(
                label="Generate Report",
                width=150,
                callback=lambda: _run_comparison(state, dialog_id),
            )
            dpg.add_button(
                label="Cancel", width=100, callback=lambda: dpg.delete_item(dialog_id)
            )


def _browse_csv(target_input_tag: str, state: UIState) -> None:
    """Open a native file dialog to select a CSV file."""
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        initial_dir = str(state.output_path) if state.output_path.exists() else None

        file_path = filedialog.askopenfilename(
            title="Select Profiling CSV",
            initialdir=initial_dir,
            filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        )

        if file_path:
            dpg.set_value(target_input_tag, file_path)

        root.destroy()
    except Exception as e:
        log_message(state, "ERROR", f"Failed to browse file: {e}")


def _run_comparison(state: UIState, dialog_id: str) -> None:
    """Execute the comparison logic and show results."""
    baseline_path_str = dpg.get_value("ab_baseline_path")
    target_path_str = dpg.get_value("ab_target_path")

    if not baseline_path_str or not target_path_str:
        log_message(state, "ERROR", "Please select both a baseline and a target CSV.")
        return

    baseline_path = Path(baseline_path_str)
    target_path = Path(target_path_str)

    if not baseline_path.exists():
        log_message(state, "ERROR", f"Baseline CSV not found: {baseline_path}")
        return

    if not target_path.exists():
        log_message(state, "ERROR", f"Target CSV not found: {target_path}")
        return

    # Validate Metadata
    try:
        baseline_meta = _read_csv_metadata(baseline_path)
        target_meta = _read_csv_metadata(target_path)

        base_hw = baseline_meta.get("deviceprofile")
        if not base_hw:
            cpu_val = baseline_meta.get("cpu", "")
            base_hw = (
                cpu_val.split("|")[-1].strip() if "|" in cpu_val else cpu_val.strip()
            )

        target_hw = target_meta.get("deviceprofile")
        if not target_hw:
            cpu_val = target_meta.get("cpu", "")
            target_hw = (
                cpu_val.split("|")[-1].strip() if "|" in cpu_val else cpu_val.strip()
            )

        if base_hw and target_hw and base_hw.lower() != target_hw.lower():
            log_message(
                state,
                "ERROR",
                f"Hardware mismatch! Baseline ({base_hw}) vs Target ({target_hw}). Cannot compare disparate devices.",
            )
            return

    except Exception as e:
        log_message(state, "WARNING", f"Failed to validate metadata: {e}")

    output_html = (
        target_path.parent
        / f"{target_path.stem}_vs_{baseline_path.stem}_comparison.html"
    )

    log_message(state, "INFO", f"Generating A/B Compare Report...")

    try:
        results = generate_comparison_report(baseline_path, target_path, output_html)
        log_message(state, "SUCCESS", f"Report generated: {output_html.name}")

        # Open in browser
        webbrowser.open(f"file:///{output_html.as_posix()}")

        # Close dialog
        dpg.delete_item(dialog_id)
    except Exception as e:
        import traceback

        traceback.print_exc()
        log_message(state, "ERROR", f"Failed to generate A/B comparison: {e}")
