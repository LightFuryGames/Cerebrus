"""S3 Uploader Plugin."""

from __future__ import annotations

import os
from typing import Optional

import dearpygui.dearpygui as dpg

from cerebrus.core.plugins import TabPlugin
from cerebrus.ui.state import UIState
from cerebrus.ui.themes import get_theme_manager
from cerebrus.ui.components.shared import log_message
import json
from pathlib import Path

def load_plugin_tooltips(filename: str) -> dict:
    try:
        path = Path(__file__).parent / "resources" / filename
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"Failed to load plugin tooltips {filename}: {e}")
    return {}

S3_TOOLTIPS = load_plugin_tooltips("s3_uploader_tooltips.json")

def _add_plugin_help_button(tooltip_key: str) -> None:
    if tooltip_key not in S3_TOOLTIPS:
        return
    text = S3_TOOLTIPS[tooltip_key]
    with dpg.group(horizontal=True):
        dpg.add_button(label="?", width=20, height=20, small=True)
        with dpg.tooltip(dpg.last_item()):
            dpg.add_text(text, wrap=350)

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
        dpg.bind_item_theme(dpg.add_text("S3 File Uploader - Cerebrus Profiling Reports"), tm.get_header_theme())
        
        # Check dynamic dependencies
        try:
            import boto3
            from botocore.exceptions import NoCredentialsError, ClientError
            has_boto3 = True
        except ImportError:
            has_boto3 = False

        if not has_boto3:
            dpg.add_text("Missing Dependency: 'boto3' is required for the S3 Uploader.", color=[255, 100, 100])
            dpg.add_text("Please install it (e.g., pip install boto3) and restart Cerebrus.")
            return

        if not AWSSecretsManager:
            dpg.add_text("Missing Dependency: AWS Secrets Manager plugin is required.", color=[255, 100, 100])
            return

        manager = AWSSecretsManager.get_instance()
        buckets = manager.get_bucket_display_items()

        dpg.add_spacer(height=10)
        
        def _build_upload_form(form_id: str, label_prefix: str, allowed_extensions: list[tuple[str, str]], hint_file: str, hint_dest: str, expected_exts: tuple[str, ...], content_type: str = None):
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
                        filetypes=allowed_extensions
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
                    
                    import re
                    # Check generator signature (flexible with quotes)
                    is_cerebrus = re.search(r'meta\s+name=["\']generator["\']\s+content=["\']Cerebrus Profiling Tool["\']', content)
                    if not is_cerebrus:
                        log_message(state, "WARNING", "Non-Cerebrus HTML selected. Attempting to backtrack metadata from content...")

                    # Extract metadata - Try JSON first
                    meta_match = re.search(r'<script type="application/json" id="cerebrus-metadata">(.*?)</script>', content, re.DOTALL)
                    metadata = {}
                    if meta_match:
                        metadata = json.loads(meta_match.group(1).strip())
                    else:
                        # Backtrack: Try to extract from stat-cards in HTML content
                        # This works for legacy Cerebrus reports too
                        patterns = {
                            "Build Configuration": r'<div class="stat-label">Build Configuration</div>\s*<div class="stat-value">(.*?)</div>',
                            "Device Make": r'<div class="stat-label">Device Make</div>\s*<div class="stat-value">(.*?)</div>',
                            "Device Model": r'<div class="stat-label">Device Model</div>\s*<div class="stat-value">(.*?)</div>',
                            "Changelist": r'<div class="stat-label">Changelist</div>\s*<div class="stat-value">(.*?)</div>',
                            "Date": r'<div class="stat-label">Date</div>\s*<div class="stat-value">(.*?)</div>'
                        }
                        for key, pattern in patterns.items():
                            match = re.search(pattern, content, re.IGNORECASE)
                            if match:
                                metadata[key] = match.group(1).strip()

                    if metadata:
                        config = metadata.get("Build Configuration", "UnknownConfig")
                        make = metadata.get("Device Make", "UnknownMake")
                        model = metadata.get("Device Model", "UnknownModel")
                        cl = metadata.get("Changelist", "UnknownCL")
                        date_val = metadata.get("Date", "UnknownDate")
                        
                        # Warn if CL is 0
                        if str(cl) == "0":
                            _show_popup("Build Warning", "The Changelist number in this report is '0'. This usually indicates a corrupted build or a local developer build. Please confirm if you want to upload this to the production bucket.", color=[255, 150, 0])

                        date_part = "UnknownDate"
                        time_part = "UnknownTime"
                        if "-" in date_val:
                            parts = date_val.split("-")
                            date_part = parts[0]
                            time_part = parts[1]
                        
                        def sanitize_path(s):
                            return str(s).replace(" ", "_").replace("/", "_").replace("\\", "_")

                        derived_dir = f"{sanitize_path(config)}/{sanitize_path(make)}/{sanitize_path(model)}/{sanitize_path(cl)}/{sanitize_path(date_part)}/{sanitize_path(time_part)}"
                        dpg.set_value(dest_dir_tag, derived_dir)
                        log_message(state, "INFO", f"Derived S3 path: {derived_dir}")
                    else:
                        _show_popup("Metadata Missing", "No Cerebrus metadata found in this HTML. You can still upload, but you must enter the Destination Path manually.", color=[200, 200, 200])
                except Exception as e:
                    print(f"Path derivation failed: {e}")
                    _show_popup("Error", f"Failed to parse report: {e}", color=[255, 100, 100])

            def _show_popup(title: str, message: str, color: list[int] = None):
                if dpg.does_item_exist("s3_uploader_popup"):
                    dpg.delete_item("s3_uploader_popup")
                
                with dpg.window(label=title, modal=True, show=True, tag="s3_uploader_popup", width=450, no_resize=True):
                    dpg.add_spacer(height=5)
                    with dpg.group(horizontal=True):
                        dpg.add_text("ℹ️" if not color or color[0] < 255 else "⚠️", color=color or [255, 255, 255])
                        dpg.add_text(message, wrap=400)
                    dpg.add_spacer(height=10)
                    dpg.add_separator()
                    dpg.add_spacer(height=5)
                    dpg.add_button(label="Close", width=100, callback=lambda: dpg.delete_item("s3_uploader_popup"))

            # Use a table to align inputs
            with dpg.table(header_row=False, borders_innerH=False, borders_outerH=False, borders_innerV=False, borders_outerV=False):
                dpg.add_table_column(width_fixed=True, init_width_or_weight=150)
                dpg.add_table_column(width_stretch=True, init_width_or_weight=1.0)
                
                with dpg.table_row():
                    with dpg.group(horizontal=True, horizontal_spacing=4):
                        dpg.add_text("Source File:")
                        _add_plugin_help_button("s3_source_file")
                        
                    with dpg.group(horizontal=True):
                        dpg.add_input_text(tag=file_path_tag, width=400, hint=hint_file)
                        dpg.add_button(label="Browse", callback=_browse_file)
                
                with dpg.table_row():
                    with dpg.group(horizontal=True, horizontal_spacing=4):
                        dpg.add_text("Target Bucket:")
                        _add_plugin_help_button("s3_target_bucket")
                        
                    dpg.add_combo(tag=bucket_combo_tag, items=buckets, width=400)
                
                with dpg.table_row():
                    with dpg.group(horizontal=True, horizontal_spacing=4):
                        dpg.add_text("Destination Path:")
                        _add_plugin_help_button("s3_dest_path")
                        
                    dpg.add_input_text(tag=dest_dir_tag, hint=hint_dest, width=400)

            dpg.add_spacer(height=15)

            def _handle_upload():
                source_path = dpg.get_value(file_path_tag)
                bucket_name = dpg.get_value(bucket_combo_tag)
                dest_dir = dpg.get_value(dest_dir_tag)

                if expected_exts and not source_path.lower().endswith(expected_exts):
                    ext_str = " or ".join([ext.upper() for ext in expected_exts])
                    log_message(state, "ERROR", f"Only {ext_str} files are supported for this upload.")
                    return

                if not os.path.isfile(source_path):
                    log_message(state, "ERROR", f"Source file does not exist: {source_path}")
                    return

                if not bucket_name:
                    log_message(state, "ERROR", "Please select a target bucket.")
                    return

                # Fetch credentials
                creds = manager.get_credentials_for_bucket(bucket_name)
                if not creds:
                    log_message(state, "ERROR", f"Could not retrieve credentials for bucket: {bucket_name}. Check AWS Secrets tab.")
                    return

                # Validate it's a Cerebrus report if it's HTML
                if source_path.lower().endswith(".html"):
                    try:
                        with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
                            head = f.read(2048) # Just check start
                        if 'meta name="generator" content="Cerebrus Profiling Tool"' not in head:
                            log_message(state, "WARNING", "Uploading non-Cerebrus HTML report. Some features might not work.")
                    except:
                        pass

                # Upload Logic
                file_name = os.path.basename(source_path)
                dest_dir = dest_dir.strip("/")
                s3_key = f"{dest_dir}/{file_name}" if dest_dir else file_name

                import boto3
                from botocore.exceptions import NoCredentialsError, ClientError

                try:
                    log_message(state, "INFO", f"Initializing S3 client for {bucket_name}...")
                    s3_client = boto3.client(
                        's3',
                        aws_access_key_id=creds.get('aws_access_key_id'),
                        aws_secret_access_key=creds.get('aws_secret_access_key'),
                        region_name=creds.get('region_name')
                    )

                    log_message(state, "INFO", f"Uploading '{source_path}' to 's3://{bucket_name}/{s3_key}' ...")
                    
                    extra_args = {}
                    if content_type:
                        extra_args['ContentType'] = content_type
                    
                    # Strip Raw Mem Report to save space (bloat removal)
                    final_content = None
                    if source_path.lower().endswith(".html"):
                        try:
                            with open(source_path, "r", encoding="utf-8", errors="ignore") as f:
                                final_content = f.read()
                            
                            import re
                            # Remove the Raw Data tab content (it has 3 nested divs)
                            # <div id="raw-mem-report" class="tab-content"> ... </div>
                            final_content = re.sub(r'<div id="raw-mem-report" class="tab-content">.*?</div>\s*</div>\s*</div>', '', final_content, flags=re.DOTALL)
                            
                            # Remove the Raw Data navigation group
                            # <div class="tab-group ..."><div class="group-title">Raw Data</div> ... </div></div>
                            final_content = re.sub(r'<div class="tab-group[^"]*">\s*<div class="group-title">Raw Data</div>.*?</div>\s*</div>', '', final_content, flags=re.DOTALL)
                            
                            log_message(state, "INFO", "Stripped 'Raw Mem Report' section to optimize S3 storage.")
                        except Exception as e:
                            log_message(state, "WARNING", f"Failed to strip raw data: {e}. Uploading original file.")
                            final_content = None

                    if final_content:
                        log_message(state, "INFO", f"Uploading optimized '{source_path}' to 's3://{bucket_name}/{s3_key}' ...")
                        s3_client.put_object(
                            Bucket=bucket_name,
                            Key=s3_key,
                            Body=final_content.encode("utf-8"),
                            ContentType=content_type or 'text/html'
                        )
                    else:
                        log_message(state, "INFO", f"Uploading original '{source_path}' to 's3://{bucket_name}/{s3_key}' ...")
                        s3_client.upload_file(
                            source_path, 
                            bucket_name, 
                            s3_key,
                            ExtraArgs=extra_args if extra_args else None
                        )
                    
                    log_message(state, "SUCCESS", f"Upload successful: {s3_key}")
                    
                except NoCredentialsError:
                    log_message(state, "ERROR", "AWS credentials missing or invalid in Secrets Manager.")
                except ClientError as e:
                    log_message(state, "ERROR", f"AWS Error: {e}")
                except Exception as e:
                    log_message(state, "ERROR", f"Upload Failed: {e}")

            dpg.add_button(label="Upload Performance Report to S3", callback=_handle_upload, width=300, height=30)
            
        dpg.add_spacer(height=10)
        _build_upload_form(
            form_id="profiling_report",
            label_prefix="HTML",
            allowed_extensions=[("HTML files", "*.html"), ("All files", "*.*")],
            hint_file="Select an HTML file...",
            hint_dest="e.g. Profiling/Reports/",
            expected_exts=(".html",),
            content_type="text/html"
        )
