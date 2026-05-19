"""AWS Secrets Manager Plugin."""

from __future__ import annotations

import base64
import json
from pathlib import Path

import dearpygui.dearpygui as dpg

try:
    import win32crypt
except ImportError:
    win32crypt = None

from cerebrus.core.paths import get_app_data_dir
from cerebrus.core.plugins import TabPlugin
from cerebrus.ui.components.shared import (
    add_plugin_help_button,
)
from cerebrus.ui.components.shared import (
    load_plugin_tooltips,
    log_message,
)
from cerebrus.ui.state import UIState
from cerebrus.ui.themes import get_theme_manager

AWS_TOOLTIPS = load_plugin_tooltips("aws_secrets/resources/tooltips.json")


class AWSSecretsManager:
    """Singleton to manage AWS credentials locally."""

    _instance = None
    EXPORT_SCHEMA_VERSION = "2.0"
    LEGACY_PORTABLE_KEY = "Cerebrus_AWS_Secret_Key_2026_!@#"

    def __init__(self):
        self.cache_file = get_app_data_dir() / "aws_secrets.json"
        self.regions_file = get_app_data_dir() / "aws_regions.json"
        self.data = {"keys": {}, "buckets": {}}
        self.regions = ["ap-south-1"]
        self.load()
        self.load_regions()

    @classmethod
    def get_instance(cls) -> AWSSecretsManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _local_encryption_available(self) -> bool:
        """Return whether local credential encryption is available."""
        return win32crypt is not None

    def _encrypt_local(self, value: str) -> str:
        """Encrypts a string for local storage using DPAPI."""
        if not value:
            return value
        if win32crypt is None:
            raise RuntimeError("DPAPI encryption is unavailable on this system.")
        try:
            encrypted = win32crypt.CryptProtectData(
                value.encode("utf-8"), "CerebrusAWS", None, None, None, 0
            )
            return base64.b64encode(encrypted).decode("utf-8")
        except Exception as e:
            raise RuntimeError(f"Local encryption failed: {e}") from e

    def _decrypt_local(self, value: str) -> str:
        """Decrypts a string from local storage using DPAPI."""
        if not value or win32crypt is None:
            return value
        try:
            decoded = base64.b64decode(value.encode("utf-8"))
            _, decrypted = win32crypt.CryptUnprotectData(decoded, None, None, None, 0)
            return decrypted.decode("utf-8")
        except Exception:
            # Fallback to plain text if decryption fails (e.g. if it wasn't encrypted)
            return value

    def _xor_legacy_scramble(self, data: str) -> str:
        """Decode legacy portable exports created before schema 2.0."""
        key = self.LEGACY_PORTABLE_KEY
        return "".join(chr(ord(c) ^ ord(key[i % len(key)])) for i, c in enumerate(data))

    def _build_export_payload(self) -> dict:
        """Build a portable JSON export without secret values."""
        keys = {}
        seen_access_keys = set()
        seen_secret_keys = set()
        for alias, key_info in self.data.get("keys", {}).items():
            access_key = self._normalize_key_value(key_info.get("access_key"))
            secret_key = self._normalize_key_value(key_info.get("secret_key"))
            if access_key and access_key in seen_access_keys:
                continue
            if secret_key and secret_key in seen_secret_keys:
                continue

            keys[alias] = {
                "alias": alias,
                "requires_reentry": True,
                "has_access_key": bool(key_info.get("access_key")),
                "has_secret_key": bool(key_info.get("secret_key")),
            }
            if access_key:
                seen_access_keys.add(access_key)
            if secret_key:
                seen_secret_keys.add(secret_key)

        buckets = [
            bucket
            for bucket in self.data.get("buckets", [])
            if not bucket.get("key_alias") or bucket.get("key_alias") in keys
        ]

        return {
            "schema_version": self.EXPORT_SCHEMA_VERSION,
            "export_type": "aws_bucket_mappings",
            "contains_secret_values": False,
            "keys": keys,
            "buckets": buckets,
        }

    def _decrypt_legacy_portable(self, encrypted_str: str) -> dict | None:
        """Decrypt legacy .cbx files created with the old XOR portable format."""
        try:
            decoded = base64.b64decode(encrypted_str.encode("utf-8")).decode("latin1")
            unscrambled = self._xor_legacy_scramble(decoded)
            return json.loads(unscrambled)
        except Exception as e:
            print(f"Legacy portable import failed: {e}")
            return None

    def _normalize_key_value(self, value: str | None) -> str:
        return str(value or "").strip()

    def _find_duplicate_key_field(
        self,
        field: str,
        value: str,
        exclude_alias: str | None = None,
    ) -> str | None:
        normalized = self._normalize_key_value(value)
        if not normalized:
            return None

        for alias, key_info in self.data.get("keys", {}).items():
            if exclude_alias is not None and alias == exclude_alias:
                continue
            if self._normalize_key_value(key_info.get(field)) == normalized:
                return alias
        return None

    def _validate_unique_key(
        self,
        alias: str,
        access_key: str = "",
        secret_key: str = "",
    ) -> str:
        if alias in self.data.get("keys", {}):
            return f"AWS key alias already exists: {alias}"

        duplicate_access_alias = self._find_duplicate_key_field(
            "access_key", access_key
        )
        if duplicate_access_alias:
            return (
                f"Access Key ID is already saved under alias: {duplicate_access_alias}"
            )

        duplicate_secret_alias = self._find_duplicate_key_field(
            "secret_key", secret_key
        )
        if duplicate_secret_alias:
            return (
                "Secret Access Key is already saved under alias: "
                f"{duplicate_secret_alias}"
            )

        return ""

    def load_regions(self):
        if self.regions_file.exists():
            try:
                with open(self.regions_file, "r") as f:
                    self.regions = json.load(f)
            except Exception as e:
                print(f"Failed to load AWS regions: {e}")
        if not self.regions:
            self.regions = ["ap-south-1"]

    def save_regions(self):
        self.regions_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.regions_file, "w") as f:
                json.dump(self.regions, f, indent=4)
        except Exception as e:
            print(f"Failed to save AWS regions: {e}")

    def load(self):
        if self.cache_file.exists():
            try:
                with open(self.cache_file, "r") as f:
                    content = f.read()
                    if content.strip():
                        raw_data = json.loads(content)
                        # Decrypt sensitive fields
                        for key_info in raw_data.get("keys", {}).values():
                            if "access_key" in key_info:
                                key_info["access_key"] = self._decrypt_local(
                                    key_info["access_key"]
                                )
                            if "secret_key" in key_info:
                                key_info["secret_key"] = self._decrypt_local(
                                    key_info["secret_key"]
                                )
                        self.data = raw_data
            except Exception as e:
                print(f"Failed to load AWS secrets: {e}")

        # Ensure schema
        if "keys" not in self.data:
            self.data["keys"] = {}
        if "buckets" not in self.data:
            self.data["buckets"] = []
        elif isinstance(self.data["buckets"], dict):
            # Migration from dict to list
            self.data["buckets"] = list(self.data["buckets"].values())

    def save(self) -> bool:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            # Create a copy to encrypt without affecting in-memory data
            save_data = json.loads(json.dumps(self.data))
            has_plain_secret = any(
                key_info.get("access_key") or key_info.get("secret_key")
                for key_info in save_data.get("keys", {}).values()
            )
            if has_plain_secret and not self._local_encryption_available():
                print("Refusing to save AWS secrets because DPAPI is unavailable.")
                return False

            for key_info in save_data.get("keys", {}).values():
                if "access_key" in key_info:
                    key_info["access_key"] = self._encrypt_local(key_info["access_key"])
                if "secret_key" in key_info:
                    key_info["secret_key"] = self._encrypt_local(key_info["secret_key"])

            with open(self.cache_file, "w") as f:
                json.dump(save_data, f, indent=4)
            return True
        except Exception as e:
            print(f"Failed to save AWS secrets: {e}")
            return False

    def export_data(self, path: Path) -> bool:
        """Export portable bucket mappings as explicit JSON without secret values."""
        try:
            with open(path, "w") as f:
                json.dump(self._build_export_payload(), f, indent=4)
            return True
        except Exception as e:
            print(f"Failed to export data: {e}")
            return False

    def import_data(self, path: Path) -> str:
        """Imports portable configuration. Returns error message or empty string."""
        try:
            with open(path, "r") as f:
                content = f.read()

            try:
                imported_data = json.loads(content)
            except json.JSONDecodeError:
                imported_data = self._decrypt_legacy_portable(content)

            if imported_data and "keys" in imported_data and "buckets" in imported_data:
                contains_secret_values = imported_data.get(
                    "contains_secret_values",
                    imported_data.get("schema_version") is None,
                )

                for alias, key_info in imported_data.get("keys", {}).items():
                    alias = self._normalize_key_value(key_info.get("alias", alias))
                    access_key = self._normalize_key_value(key_info.get("access_key"))
                    secret_key = self._normalize_key_value(key_info.get("secret_key"))
                    if not alias:
                        continue
                    if alias in self.data["keys"]:
                        continue
                    if contains_secret_values and self._validate_unique_key(
                        alias,
                        access_key,
                        secret_key,
                    ):
                        continue
                    if contains_secret_values:
                        self.data["keys"][alias] = {
                            "alias": alias,
                            "access_key": "",
                            "secret_key": "",
                            "requires_reentry": True,
                        }
                    else:
                        self.data["keys"][alias] = {
                            "alias": alias,
                            "access_key": "",
                            "secret_key": "",
                            "requires_reentry": True,
                        }

                # Merge buckets (avoid exact duplicates)
                imported_buckets = imported_data.get("buckets", [])
                if isinstance(imported_buckets, dict):
                    imported_buckets = list(imported_buckets.values())

                for b in imported_buckets:
                    if b not in self.data["buckets"]:
                        self.data["buckets"].append(b)

                if not self.save():
                    return "Imported data could not be saved."
                return ""
            return "Invalid or corrupted export file."
        except Exception as e:
            return f"Import failed: {str(e)}"

    def add_key(self, alias: str, access_key: str, secret_key: str) -> str:
        alias = self._normalize_key_value(alias)
        access_key = self._normalize_key_value(access_key)
        secret_key = self._normalize_key_value(secret_key)

        duplicate_error = self._validate_unique_key(alias, access_key, secret_key)
        if duplicate_error:
            return duplicate_error

        if not self._local_encryption_available():
            return (
                "Local credential encryption is unavailable; AWS keys were not saved."
            )

        self.data["keys"][alias] = {
            "alias": alias,
            "access_key": access_key,
            "secret_key": secret_key,
        }
        if not self.save():
            self.data["keys"].pop(alias, None)
            return "Failed to save AWS key securely."
        return ""

    def remove_key(self, alias: str):
        if alias in self.data["keys"]:
            del self.data["keys"][alias]
            # Clean up bucket mappings that use this key?
            # Actually, let's keep them so the user can fix them.
            self.save()

    def add_bucket(self, name: str, region: str, key_alias: str):
        new_mapping = {"name": name, "region": region, "key_alias": key_alias}
        if new_mapping not in self.data["buckets"]:
            self.data["buckets"].append(new_mapping)
            self.save()

    def remove_bucket(self, index: int):
        if 0 <= index < len(self.data["buckets"]):
            self.data["buckets"].pop(index)
            self.save()

    def get_credentials_for_bucket(self, display_name: str) -> dict | None:
        """Return boto3 kwargs and the real bucket name for a bucket display item."""
        for b_info in self.data["buckets"]:
            name = b_info.get("name")
            region = b_info.get("region")
            key_alias = b_info.get("key_alias")
            match_name = name
            if region:
                match_name = f"{match_name} [{region}]"
            if key_alias:
                match_name = f"{match_name} ({key_alias})"

            if match_name == display_name:
                if key_alias not in self.data["keys"]:
                    return None

                key_info = self.data["keys"][key_alias]
                access_key = key_info.get("access_key")
                secret_key = key_info.get("secret_key")
                if not access_key or not secret_key:
                    return None
                return {
                    "aws_access_key_id": access_key,
                    "aws_secret_access_key": secret_key,
                    "region_name": b_info.get("region"),
                    "bucket_name": name,
                }
        return None

    def get_bucket_display_items(self) -> list[str]:
        items = []
        for b in self.data["buckets"]:
            name = b.get("name")
            region = b.get("region")
            alias = b.get("key_alias")
            display_name = name
            if region:
                display_name = f"{display_name} [{region}]"
            if alias:
                display_name = f"{display_name} ({alias})"
            items.append(display_name)
        return items


class AWSSecretsPlugin(TabPlugin):
    @property
    def id(self) -> str:
        return "aws_secrets"

    @property
    def name(self) -> str:
        return "AWS Secrets"

    @property
    def version(self) -> str:
        return "1.0.0"

    def _refresh_ui(self, manager: AWSSecretsManager):
        if dpg.does_item_exist("aws_key_combo"):
            dpg.configure_item("aws_key_combo", items=list(manager.data["keys"].keys()))
        if dpg.does_item_exist("aws_new_region"):
            dpg.configure_item("aws_new_region", items=manager.regions)
        for tag in ["s3_bucket_select", "profiling_report_bucket_select"]:
            if dpg.does_item_exist(tag):
                dpg.configure_item(tag, items=manager.get_bucket_display_items())
        if dpg.does_item_exist("aws_json_edit_modal"):
            dpg.set_value("aws_json_edit_modal", json.dumps(manager.data, indent=4))

    def build_tab(self, state: UIState) -> None:
        manager = AWSSecretsManager.get_instance()
        tm = get_theme_manager()

        dpg.add_spacer(height=10)
        dpg.bind_item_theme(
            dpg.add_text("AWS Secrets & Bucket Manager"), tm.get_header_theme()
        )
        dpg.add_text("Manage credentials securely for other plugins to use.")
        dpg.add_spacer(height=15)

        alias_tag = "aws_new_alias"
        ak_tag = "aws_new_ak"
        sk_tag = "aws_new_sk"
        bucket_tag = "aws_new_bucket"
        region_tag = "aws_new_region"
        key_combo_tag = "aws_key_combo"

        def _add_key_cb():
            alias = dpg.get_value(alias_tag)
            ak = dpg.get_value(ak_tag)
            sk = dpg.get_value(sk_tag)
            if alias and ak and sk:
                error = manager.add_key(alias, ak, sk)
                if error:
                    log_message(state, "ERROR", error)
                else:
                    log_message(state, "SUCCESS", f"Added AWS Key: {alias}")
                    self._refresh_ui(manager)
            else:
                log_message(state, "ERROR", "All key fields are required.")

        def _add_bucket_cb():
            b_name = dpg.get_value(bucket_tag)
            region = dpg.get_value(region_tag)
            k_alias = dpg.get_value(key_combo_tag)
            if b_name and region and k_alias:
                manager.add_bucket(b_name, region, k_alias)
                log_message(
                    state, "SUCCESS", f"Mapped bucket {b_name} to key {k_alias}"
                )
                self._refresh_ui(manager)
            else:
                log_message(state, "ERROR", "All bucket fields are required.")

        with dpg.table(header_row=False, policy=dpg.mvTable_SizingFixedFit):
            dpg.add_table_column(width_fixed=True, init_width_or_weight=640)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=32)
            dpg.add_table_column(width_fixed=True, init_width_or_weight=640)

            with dpg.table_row():
                with dpg.group():
                    dpg.bind_item_theme(
                        dpg.add_text("Add Credential Key"), tm.get_subheader_theme()
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
                        dpg.add_table_column(width_fixed=True, init_width_or_weight=440)

                        with dpg.table_row():
                            dpg.add_text("Key Alias:")
                            add_plugin_help_button(AWS_TOOLTIPS, "aws_key_alias")
                            dpg.add_input_text(
                                tag=alias_tag, hint="e.g. TeamKey", width=420
                            )

                        with dpg.table_row():
                            dpg.add_text("Access Key ID:")
                            add_plugin_help_button(AWS_TOOLTIPS, "aws_access_key")
                            dpg.add_input_text(tag=ak_tag, hint="AKIA...", width=420)

                        with dpg.table_row():
                            dpg.add_text("Secret Access Key:")
                            add_plugin_help_button(AWS_TOOLTIPS, "aws_secret_key")
                            dpg.add_input_text(
                                tag=sk_tag,
                                hint="Your secret key",
                                password=True,
                                width=420,
                            )

                        with dpg.table_row():
                            dpg.add_spacer()
                            dpg.add_spacer()
                            with dpg.group(horizontal=True, horizontal_spacing=8):
                                dpg.add_button(
                                    label="Save Key", callback=_add_key_cb, width=120
                                )
                                add_plugin_help_button(AWS_TOOLTIPS, "aws_save_key")

                with dpg.group():
                    with dpg.drawlist(width=2, height=150):
                        dpg.draw_line(
                            (1, 0),
                            (1, 150),
                            color=(90, 105, 125, 255),
                            thickness=1,
                        )

                with dpg.group():
                    dpg.bind_item_theme(
                        dpg.add_text("Map S3 Bucket"), tm.get_subheader_theme()
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
                        dpg.add_table_column(width_fixed=True, init_width_or_weight=440)

                        with dpg.table_row():
                            dpg.add_text("Bucket Name:")
                            add_plugin_help_button(AWS_TOOLTIPS, "aws_bucket_name")
                            dpg.add_input_text(
                                tag=bucket_tag,
                                hint="e.g. cerebrus-assets-bucket",
                                width=420,
                            )

                        with dpg.table_row():
                            dpg.add_text("Region:")
                            add_plugin_help_button(AWS_TOOLTIPS, "aws_region")
                            dpg.add_combo(
                                tag=region_tag,
                                items=manager.regions,
                                width=420,
                                default_value=(
                                    manager.regions[0] if manager.regions else ""
                                ),
                            )

                        with dpg.table_row():
                            dpg.add_text("Assigned Key Alias:")
                            add_plugin_help_button(AWS_TOOLTIPS, "aws_key_mapping")
                            dpg.add_combo(
                                tag=key_combo_tag,
                                items=list(manager.data["keys"].keys()),
                                width=420,
                            )

                        with dpg.table_row():
                            dpg.add_spacer()
                            dpg.add_spacer()
                            with dpg.group(horizontal=True, horizontal_spacing=8):
                                dpg.add_button(
                                    label="Save Bucket Mapping",
                                    callback=_add_bucket_cb,
                                    width=150,
                                )
                                add_plugin_help_button(
                                    AWS_TOOLTIPS, "aws_save_bucket_mapping"
                                )

        dpg.add_spacer(height=15)
        dpg.add_separator()
        dpg.add_spacer(height=15)

    def build_menu(self, state: UIState) -> None:
        """Inject menu items under this plugin's settings menu."""
        manager = AWSSecretsManager.get_instance()

        # --- Table Refresh Methods ---
        def _refresh_keys_table():
            if not dpg.does_item_exist("aws_keys_container"):
                return
            dpg.delete_item("aws_keys_container", children_only=True)
            with dpg.table(
                parent="aws_keys_container",
                header_row=True,
                borders_innerH=True,
                borders_outerH=True,
                borders_innerV=True,
                borders_outerV=True,
                resizable=True,
            ):
                dpg.add_table_column(label="Alias")
                dpg.add_table_column(label="Access Key ID")
                dpg.add_table_column(label="Secret Key")
                dpg.add_table_column(
                    label="Action", width_fixed=True, init_width_or_weight=150
                )

                for alias in manager.data["keys"]:
                    key_info = manager.data["keys"][alias]
                    with dpg.table_row():
                        dpg.add_text(alias)
                        ak = key_info.get("access_key", "")
                        dpg.add_text("****************" if ak else "")
                        dpg.add_text("****************")
                        with dpg.group(horizontal=True):

                            def _del_key_cb(s, a, u):
                                manager.remove_key(u)
                                self._refresh_ui(manager)
                                _refresh_keys_table()

                            dpg.add_button(
                                label="Delete",
                                user_data=alias,
                                callback=_del_key_cb,
                                small=True,
                            )

        def _refresh_buckets_table():
            if not dpg.does_item_exist("aws_buckets_container"):
                return
            dpg.delete_item("aws_buckets_container", children_only=True)
            with dpg.table(
                parent="aws_buckets_container",
                header_row=True,
                borders_innerH=True,
                borders_outerH=True,
                borders_innerV=True,
                borders_outerV=True,
                resizable=True,
            ):
                dpg.add_table_column(label="Bucket Name")
                dpg.add_table_column(label="Region")
                dpg.add_table_column(label="Key Alias")
                dpg.add_table_column(
                    label="Action", width_fixed=True, init_width_or_weight=150
                )

                for i, b_info in enumerate(manager.data["buckets"]):
                    with dpg.table_row():
                        dpg.add_text(b_info.get("name", ""))
                        dpg.add_text(b_info.get("region", ""))
                        dpg.add_text(b_info.get("key_alias", ""))
                        with dpg.group(horizontal=True):

                            def _del_bucket_cb(s, a, u):
                                manager.remove_bucket(u)
                                self._refresh_ui(manager)
                                _refresh_buckets_table()

                            dpg.add_button(
                                label="Delete",
                                user_data=i,
                                callback=_del_bucket_cb,
                                small=True,
                            )

        def _refresh_regions_table():
            if not dpg.does_item_exist("aws_regions_table_container"):
                return
            dpg.delete_item("aws_regions_table_container", children_only=True)
            with dpg.table(
                parent="aws_regions_table_container",
                header_row=True,
                borders_innerH=True,
                borders_outerH=True,
                borders_innerV=True,
                borders_outerV=True,
            ):
                dpg.add_table_column(label="Region Name")
                dpg.add_table_column(
                    label="Action", width_fixed=True, init_width_or_weight=150
                )

                for r in manager.regions:
                    with dpg.table_row():
                        dpg.add_text(r)
                        with dpg.group(horizontal=True):

                            def _del_region_cb(s, a, u):
                                if u in manager.regions:
                                    manager.regions.remove(u)
                                    manager.save_regions()
                                    self._refresh_ui(manager)
                                    _refresh_regions_table()

                            dpg.add_button(
                                label="Delete",
                                user_data=r,
                                callback=_del_region_cb,
                                small=True,
                            )

        # --- Main Modals ---
        def _show_edit_popup():
            if not dpg.does_item_exist("aws_edit_modal"):
                with dpg.window(
                    tag="aws_edit_modal",
                    modal=True,
                    show=True,
                    label="Manage AWS Secrets",
                    width=750,
                    height=550,
                ):
                    with dpg.tab_bar():
                        with dpg.tab(label="AWS Keys"):
                            dpg.add_group(tag="aws_keys_container")
                        with dpg.tab(label="Bucket Mappings"):
                            dpg.add_group(tag="aws_buckets_container")
                    dpg.add_spacer(height=10)
                    dpg.add_button(
                        label="Close",
                        callback=lambda: dpg.configure_item(
                            "aws_edit_modal", show=False
                        ),
                        width=100,
                    )

            dpg.configure_item("aws_edit_modal", show=True)
            _refresh_keys_table()
            _refresh_buckets_table()

        def _show_regions_popup():
            if not dpg.does_item_exist("aws_regions_modal"):
                with dpg.window(
                    tag="aws_regions_modal",
                    modal=True,
                    show=True,
                    label="Manage Allowed Regions",
                    width=450,
                    height=450,
                ):
                    with dpg.group(horizontal=True):
                        dpg.add_input_text(
                            tag="aws_new_region_input", hint="e.g. eu-west-1", width=250
                        )

                        def _add_region_cb():
                            new_r = dpg.get_value("aws_new_region_input").strip()
                            if new_r and new_r not in manager.regions:
                                manager.regions.append(new_r)
                                manager.save_regions()
                                dpg.set_value("aws_new_region_input", "")
                                self._refresh_ui(manager)
                                _refresh_regions_table()
                            elif new_r in manager.regions:
                                log_message(state, "ERROR", "Region already exists.")

                        dpg.add_button(label="Add Region", callback=_add_region_cb)

                    dpg.add_spacer(height=10)
                    dpg.add_group(tag="aws_regions_table_container")
                    dpg.add_spacer(height=10)
                    dpg.add_button(
                        label="Close",
                        callback=lambda: dpg.configure_item(
                            "aws_regions_modal", show=False
                        ),
                        width=100,
                    )

            dpg.configure_item("aws_regions_modal", show=True)
            _refresh_regions_table()

        # --- Menu Registration ---
        with dpg.menu(label="AWS Secrets"):
            dpg.add_menu_item(label="Manage AWS Secrets", callback=_show_edit_popup)
            dpg.add_menu_item(
                label="Manage Allowed Regions", callback=_show_regions_popup
            )
            dpg.add_separator()
            dpg.add_menu_item(
                label="Export AWS Secrets (.cbx)",
                callback=lambda: self._handle_export(manager, state),
            )
            dpg.add_menu_item(
                label="Import AWS Secrets (.cbx)",
                callback=lambda: self._handle_import(manager, state),
            )

    def _handle_export(self, manager, state):
        import tkinter as tk
        from tkinter import filedialog

        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.asksaveasfilename(
                title="Export AWS Secrets",
                defaultextension=".cbx",
                filetypes=[("Cerebrus Export", "*.cbx"), ("All files", "*.*")],
            )
            root.destroy()
            if path:
                if manager.export_data(Path(path)):
                    log_message(
                        state, "SUCCESS", f"Exported AWS secrets to {Path(path).name}"
                    )
                else:
                    log_message(state, "ERROR", "Failed to export AWS secrets.")
        except Exception as e:
            log_message(state, "ERROR", f"Export failed: {e}")

    def _handle_import(self, manager, state):
        import tkinter as tk
        from tkinter import filedialog

        try:
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(
                title="Import AWS Secrets",
                filetypes=[("Cerebrus Export", "*.cbx"), ("All files", "*.*")],
            )
            root.destroy()
            if path:
                error = manager.import_data(Path(path))
                if not error:
                    log_message(
                        state,
                        "SUCCESS",
                        f"Imported AWS secrets from {Path(path).name}",
                    )
                    self._refresh_ui(manager)
                else:
                    log_message(state, "ERROR", error)
        except Exception as e:
            log_message(state, "ERROR", f"Import failed: {e}")
