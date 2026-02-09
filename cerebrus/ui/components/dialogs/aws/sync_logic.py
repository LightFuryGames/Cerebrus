from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import dearpygui.dearpygui as dpg

from cerebrus.tools.adb import AdbClient
from cerebrus.ui.components.shared import _auto_save_profile, log_message
from cerebrus.ui.state import UIState


def is_aws_configured(state: UIState) -> bool:
    """Check if AWS credentials, profile, or Remote URL are configured."""
    profile = state.profile_manager.current_profile
    if not profile:
        return False

    # Check for AWS Creds OR AWS Profile OR Base URL (public bucket)
    has_aws = bool(
        (profile.aws_access_key and profile.aws_secret_key) or profile.aws_profile
    )
    has_url = bool(profile.remote_config_base_url)

    return has_aws or has_url


def update_manifest_url_state(state: UIState, value: str) -> None:
    """Update manifest URL in state and profile."""
    state.remote_manifest_url = value
    if state.profile_manager.current_profile:
        state.profile_manager.current_profile.remote_manifest_url = value
        _auto_save_profile(state)


def smart_download(state: UIState, url: str, dest_path: Path) -> bool:
    """Download a file from an S3 URL or standard HTTP URL."""
    parsed = urlparse(url)

    bucket = ""
    key = ""

    # 1. Detect S3 URLs
    if parsed.scheme == "s3":
        bucket = parsed.netloc
        key = parsed.path.lstrip("/")
    elif "s3" in parsed.netloc and ".amazonaws.com" in parsed.netloc:
        parts = parsed.netloc.split(".")
        if len(parts) >= 3:
            bucket = parts[0]
            key = parsed.path.lstrip("/")

    if bucket and key:
        log_message(state, "INFO", f"S3 detected. Bucket: '{bucket}', Key: '{key}'")
        try:
            import boto3
            from botocore.exceptions import NoCredentialsError

            profile = state.profile_manager.current_profile
            session_kwargs = {}
            region = "ap-south-1"

            if profile:
                if profile.aws_access_key and profile.aws_secret_key:
                    log_message(
                        state, "INFO", "Using AWS Access Keys for authentication..."
                    )
                    session_kwargs["aws_access_key_id"] = profile.aws_access_key
                    session_kwargs["aws_secret_access_key"] = profile.aws_secret_key
                    region = profile.aws_region or region
                elif profile.aws_profile:
                    log_message(
                        state,
                        "INFO",
                        f"Using AWS Profile '{profile.aws_profile}' for authentication...",
                    )
                    session_kwargs["profile_name"] = profile.aws_profile
                    region = profile.aws_region or region
                else:
                    log_message(
                        state,
                        "WARNING",
                        "No Keys or Profile provided in UI. Attempting default machine auth...",
                    )

            session_kwargs["region_name"] = region
            session = boto3.Session(**session_kwargs)
            s3 = session.client("s3")

            dest_path.parent.mkdir(parents=True, exist_ok=True)

            response = s3.get_object(Bucket=bucket, Key=key)
            with open(dest_path, "wb") as f:
                f.write(response["Body"].read())

            return True
        except NoCredentialsError:
            log_message(
                state,
                "WARNING",
                "No AWS credentials found. Falling back to public URL request.",
            )
        except Exception as e:
            log_message(state, "WARNING", f"S3 authenticated download failed: {e}")
            log_message(state, "INFO", "Falling back to public URL request...")

    # 2. Fallback to standard requests
    try:
        import requests

        response = requests.get(url, timeout=15)
        response.raise_for_status()
        with open(dest_path, "wb") as f:
            f.write(response.content)
        return True
    except Exception as e:
        log_message(state, "ERROR", f"Download failed: {e}")
        return False
