"""S3 Uploader Plugin."""

from __future__ import annotations

import html
import json
import os
import re
from pathlib import Path
from typing import Optional

import dearpygui.dearpygui as dpg

from cerebrus.core.plugins import TabPlugin
from cerebrus.ui.state import UIState
from cerebrus.ui.themes import get_theme_manager
from cerebrus.ui.components.shared import (
    _add_plugin_help_button as add_plugin_help_button,
    load_plugin_tooltips,
    log_message,
)


def _clean_html_fragment(value: str) -> str:
    """Convert a small HTML fragment into readable text."""
    text = re.sub(r"<[^>]*>", "", value)
    # PerfReportTool can double-escape CSV values inside HTML blocks.
    text = html.unescape(html.unescape(text))
    return re.sub(r"\s+", " ", text).strip()


def _extract_table_value(content: str, label: str) -> Optional[str]:
    pattern = (
        rf"<tr>\s*<td\b[^>]*>\s*{re.escape(label)}\s*</td>\s*"
        rf"<td\b[^>]*>(.*?)</td>\s*</tr>"
    )
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _clean_html_fragment(match.group(1))


def _extract_bracket_field(content: str, field: str) -> Optional[str]:
    pattern = rf"\[{re.escape(field)}\],(.*?)(?=,\[[^\]]+\]|</pre>|$)"
    match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    return _clean_html_fragment(match.group(1))


def _extract_changelist(value: str) -> str:
    match = re.search(r"\bCL[-_ ]?(\d+)\b", value, re.IGNORECASE)
    if match:
        return f"CL-{match.group(1)}"
    return value.strip()


def _extract_profile_timestamp(content: str) -> tuple[Optional[str], Optional[str]]:
    match = re.search(r"Profile\((\d{8})_(\d{6})\)", content)
    if not match:
        return None, None

    date_raw, time_raw = match.groups()
    year = date_raw[0:4]
    month = date_raw[4:6]
    day = date_raw[6:8]
    return f"{day}-{month}-{year}", time_raw


def _extract_device_parts(cpu_device: str) -> tuple[Optional[str], Optional[str]]:
    parts = [part.strip() for part in cpu_device.split("|") if part.strip()]
    if not parts:
        return None, None

    make = parts[0]
    model = parts[1] if len(parts) > 1 else None
    if model and model.lower().startswith(f"{make.lower()} "):
        model = model[len(make) :].strip()

    return make, model


def _extract_report_metadata(content: str) -> dict:
    """Extract report metadata from embedded JSON, legacy cards, or PerfReportTool HTML."""
    meta_match = re.search(
        r'<script type="application/json" id="cerebrus-metadata">(.*?)</script>',
        content,
        re.DOTALL,
    )
    if meta_match:
        try:
            return json.loads(meta_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    patterns = {
        "Build Configuration": r'<div class="stat-label">Build Configuration</div>\s*<div class="stat-value">(.*?)</div>',
        "Device Make": r'<div class="stat-label">Device Make</div>\s*<div class="stat-value">(.*?)</div>',
        "Device Model": r'<div class="stat-label">Device Model</div>\s*<div class="stat-value">(.*?)</div>',
        "Changelist": r'<div class="stat-label">Changelist</div>\s*<div class="stat-value">(.*?)</div>',
        "Date": r'<div class="stat-label">Date</div>\s*<div class="stat-value">(.*?)</div>',
    }
    metadata = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
        if match:
            metadata[key] = _clean_html_fragment(match.group(1))
    if metadata:
        return metadata

    config = _extract_table_value(content, "Configuration") or _extract_bracket_field(
        content, "config"
    )
    build_version = _extract_table_value(
        content, "Build Version"
    ) or _extract_bracket_field(content, "buildversion")
    cpu_device = _extract_table_value(content, "CPU/Device") or _extract_bracket_field(
        content, "cpu"
    )
    date_part, time_part = _extract_profile_timestamp(content)

    if config:
        metadata["Build Configuration"] = config
    if build_version:
        metadata["Changelist"] = _extract_changelist(build_version)
    if cpu_device:
        make, model = _extract_device_parts(cpu_device)
        if make:
            metadata["Device Make"] = make
        if model:
            metadata["Device Model"] = model
    if date_part:
        metadata["Date"] = date_part
    if time_part:
        metadata["Time"] = time_part
    return metadata


def _sanitize_s3_path_part(value: object) -> str:
    """Sanitize one metadata value for an S3 path segment."""
    return str(value).replace(" ", "_").replace("/", "_").replace("\\", "_")


def _derive_s3_dir_from_metadata(metadata: dict) -> str:
    """Build the data-driven S3 directory from Cerebrus report metadata."""
    config = metadata.get("Build Configuration", "UnknownConfig")
    make = metadata.get("Device Make", "UnknownMake")
    model = metadata.get("Device Model", "UnknownModel")
    cl = metadata.get("Changelist", "UnknownCL")
    date_val = metadata.get("Date", "UnknownDate")
    time_val = metadata.get("Time")

    date_part = "UnknownDate"
    time_part = "UnknownTime"
    if time_val:
        date_part = str(date_val)
        time_part = str(time_val)
    elif "-" in str(date_val):
        possible_date, possible_time = str(date_val).rsplit("-", 1)
        if re.fullmatch(r"\d{6}|\d{2}\.\d{2}\.\d{2}", possible_time):
            date_part, time_part = possible_date, possible_time
        else:
            date_part = str(date_val)

    return "/".join(
        _sanitize_s3_path_part(part)
        for part in [config, make, model, cl, date_part, time_part]
    )


def _upload_file_to_s3(
    s3_client,
    source_path: str,
    bucket_name: str,
    s3_key: str,
    content_type: str | None = None,
) -> None:
    """Upload a file without mutating the report content."""
    if content_type:
        s3_client.upload_file(
            source_path,
            bucket_name,
            s3_key,
            ExtraArgs={"ContentType": content_type},
        )
    else:
        s3_client.upload_file(source_path, bucket_name, s3_key)


S3_TOOLTIPS = load_plugin_tooltips("s3_uploader_tooltips.json")

# We import the secrets manager to fetch credentials dynamically
try:
    from cerebrus.plugins.aws_secrets import AWSSecretsManager
except ImportError:
    AWSSecretsManager = None


class S3UploaderPlugin(TabPlugin):
    @property
    def id(self) -> str:
        return "s3_uploader"

    @property
    def name(self) -> str:
        return "S3 Uploader - Profiling Reports"

    @property
    def version(self) -> str:
        return "1.0.0"

    def build_tab(self, state: UIState) -> None:
        tm = get_theme_manager()

        dpg.add_spacer(height=10)
        dpg.bind_item_theme(
            dpg.add_text("S3 File Uploader - Cerebrus Profiling Reports"),
            tm.get_header_theme(),
        )

        # Check dynamic dependencies
        try:
            import boto3
            from botocore.exceptions import NoCredentialsError, ClientError

            has_boto3 = True
        except ImportError:
            has_boto3 = False

        if not has_boto3:
            dpg.add_text(
                "Missing Dependency: 'boto3' is required for the S3 Uploader.",
                color=[255, 100, 100],
            )
            dpg.add_text(
                "Please install it (e.g., pip install boto3) and restart Cerebrus."
            )
            return

        if not AWSSecretsManager:
            dpg.add_text(
                "Missing Dependency: AWS Secrets Manager plugin is required.",
                color=[255, 100, 100],
            )
            return

        manager = AWSSecretsManager.get_instance()
        buckets = manager.get_bucket_display_items()

        dpg.add_spacer(height=10)

        def _build_upload_form(
            form_id: str,
            label_prefix: str,
            allowed_extensions: list[tuple[str, str]],
            hint_file: str,
            hint_dest: str,
            expected_exts: tuple[str, ...],
            content_type: str = None,
        ):
            file_path_tag = f"{form_id}_source_file"
            bucket_combo_tag = f"{form_id}_bucket_select"
            dest_dir_tag = f"{form_id}_dest_dir"

            def _browse_file():
                import tkinter as tk
                from tkinter import filedialog

                try:
                    root = tk.Tk()
                    root.withdraw()
                    root.attributes("-topmost", True)
                    file_path = filedialog.askopenfilename(
                        title=f"Select {label_prefix} File to Upload",
                        filetypes=allowed_extensions,
                    )
                    root.destroy()
                    if file_path:
                        dpg.set_value(file_path_tag, file_path)
                        _derive_path_from_file(file_path)
                except Exception as e:
                    log_message(state, "ERROR", f"Failed to browse file: {e}")

            def _derive_path_from_file(file_path: str):
                if not file_path.lower().endswith(".html"):
                    return

                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    # Check generator signature (flexible with quotes)
                    is_cerebrus = re.search(
                        r'meta\s+name=["\']generator["\']\s+content=["\']Cerebrus Profiling Tool["\']',
                        content,
                    )
                    if not is_cerebrus:
                        log_message(
                            state,
                            "WARNING",
                            "Non-Cerebrus HTML selected. Attempting to backtrack metadata from content...",
                        )

                    metadata = _extract_report_metadata(content)

                    if metadata:
                        cl = metadata.get("Changelist", "UnknownCL")

                        # Warn if CL is 0
                        if str(cl) == "0":
                            _show_popup(
                                "Build Warning",
                                "The Changelist number in this report is '0'. This usually indicates a corrupted build or a local developer build. Please confirm if you want to upload this to the production bucket.",
                                color=[255, 150, 0],
                            )

                        derived_dir = _derive_s3_dir_from_metadata(metadata)
                        dpg.set_value(dest_dir_tag, derived_dir)
                        log_message(state, "INFO", f"Derived S3 path: {derived_dir}")
                    else:
                        _show_popup(
                            "Metadata Missing",
                            "No report metadata found in this HTML. You can still upload, but you must enter the Destination Path manually.",
                            color=[200, 200, 200],
                        )
                except Exception as e:
                    print(f"Path derivation failed: {e}")
                    _show_popup(
                        "Error", f"Failed to parse report: {e}", color=[255, 100, 100]
                    )

            def _show_popup(title: str, message: str, color: list[int] = None):
                if dpg.does_item_exist("s3_uploader_popup"):
                    dpg.delete_item("s3_uploader_popup")

                with dpg.window(
                    label=title,
                    modal=True,
                    show=True,
                    tag="s3_uploader_popup",
                    width=450,
                    no_resize=True,
                ):
                    dpg.add_spacer(height=5)
                    with dpg.group(horizontal=True):
                        dpg.add_text(
                            "!" if color and color[0] >= 255 else "i",
                            color=color or [255, 255, 255],
                        )
                        dpg.add_text(message, wrap=400)
                    dpg.add_spacer(height=10)
                    dpg.add_separator()
                    dpg.add_spacer(height=5)
                    dpg.add_button(
                        label="Close",
                        width=100,
                        callback=lambda: dpg.delete_item("s3_uploader_popup"),
                    )

            # Use a table to align inputs
            with dpg.table(
                header_row=False,
                borders_innerH=False,
                borders_outerH=False,
                borders_innerV=False,
                borders_outerV=False,
            ):
                dpg.add_table_column(width_fixed=True, init_width_or_weight=150)
                dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)

                with dpg.table_row():
                    with dpg.group(horizontal=True, horizontal_spacing=4):
                        dpg.add_text("Source File:")
                        add_plugin_help_button(S3_TOOLTIPS, "s3_source_file")

                    with dpg.group(horizontal=True):
                        dpg.add_input_text(tag=file_path_tag, width=400, hint=hint_file)
                        dpg.add_button(label="Browse", callback=_browse_file)

                with dpg.table_row():
                    with dpg.group(horizontal=True, horizontal_spacing=4):
                        dpg.add_text("Target Bucket:")
                        add_plugin_help_button(S3_TOOLTIPS, "s3_target_bucket")

                    dpg.add_combo(tag=bucket_combo_tag, items=buckets, width=400)

                with dpg.table_row():
                    with dpg.group(horizontal=True, horizontal_spacing=4):
                        dpg.add_text("Destination Path:")
                        add_plugin_help_button(S3_TOOLTIPS, "s3_dest_path")

                    dpg.add_input_text(tag=dest_dir_tag, hint=hint_dest, width=400)

            dpg.add_spacer(height=15)

            def _handle_upload():
                source_path = dpg.get_value(file_path_tag)
                bucket_display_name = dpg.get_value(bucket_combo_tag)
                dest_dir = dpg.get_value(dest_dir_tag)

                if expected_exts and not source_path.lower().endswith(expected_exts):
                    ext_str = " or ".join([ext.upper() for ext in expected_exts])
                    log_message(
                        state,
                        "ERROR",
                        f"Only {ext_str} files are supported for this upload.",
                    )
                    return

                if not os.path.isfile(source_path):
                    log_message(
                        state, "ERROR", f"Source file does not exist: {source_path}"
                    )
                    return

                if not bucket_display_name:
                    log_message(state, "ERROR", "Please select a target bucket.")
                    return

                # Fetch credentials
                creds = manager.get_credentials_for_bucket(bucket_display_name)
                if not creds:
                    log_message(
                        state,
                        "ERROR",
                        f"Could not retrieve credentials for bucket: {bucket_display_name}. Check AWS Secrets tab.",
                    )
                    return
                bucket_name = creds.get("bucket_name", bucket_display_name)

                # Validate it's a Cerebrus report if it's HTML
                if source_path.lower().endswith(".html"):
                    try:
                        with open(
                            source_path, "r", encoding="utf-8", errors="ignore"
                        ) as f:
                            head = f.read(2048)  # Just check start
                        if (
                            'meta name="generator" content="Cerebrus Profiling Tool"'
                            not in head
                        ):
                            log_message(
                                state,
                                "WARNING",
                                "Uploading non-Cerebrus HTML report. Some features might not work.",
                            )
                    except Exception as e:
                        log_message(
                            state,
                            "WARNING",
                            f"Could not validate HTML report before upload: {e}",
                        )

                # Upload Logic
                file_name = os.path.basename(source_path)
                dest_dir = dest_dir.strip("/")
                s3_key = f"{dest_dir}/{file_name}" if dest_dir else file_name

                import boto3
                from botocore.exceptions import NoCredentialsError, ClientError

                try:
                    log_message(
                        state,
                        "INFO",
                        f"Initializing S3 client for {bucket_display_name}...",
                    )
                    s3_client = boto3.client(
                        "s3",
                        aws_access_key_id=creds.get("aws_access_key_id"),
                        aws_secret_access_key=creds.get("aws_secret_access_key"),
                        region_name=creds.get("region_name"),
                    )

                    log_message(
                        state,
                        "INFO",
                        f"Uploading '{source_path}' to 's3://{bucket_name}/{s3_key}' ...",
                    )

                    log_message(
                        state,
                        "INFO",
                        f"Uploading original '{source_path}' to 's3://{bucket_name}/{s3_key}' ...",
                    )
                    _upload_file_to_s3(
                        s3_client,
                        source_path,
                        bucket_name,
                        s3_key,
                        content_type=content_type,
                    )

                    log_message(state, "SUCCESS", f"Upload successful: {s3_key}")

                except NoCredentialsError:
                    log_message(
                        state,
                        "ERROR",
                        "AWS credentials missing or invalid in Secrets Manager.",
                    )
                except ClientError as e:
                    log_message(state, "ERROR", f"AWS Error: {e}")
                except Exception as e:
                    log_message(state, "ERROR", f"Upload Failed: {e}")

            dpg.add_button(
                label="Upload Performance Report to S3",
                callback=_handle_upload,
                width=300,
                height=30,
            )

        dpg.add_spacer(height=10)
        _build_upload_form(
            form_id="profiling_report",
            label_prefix="HTML",
            allowed_extensions=[("HTML files", "*.html"), ("All files", "*.*")],
            hint_file="Select an HTML file...",
            hint_dest="e.g. Profiling/Reports/",
            expected_exts=(".html",),
            content_type="text/html",
        )
