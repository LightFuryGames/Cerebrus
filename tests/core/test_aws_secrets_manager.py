import json

import cerebrus.plugins.aws_secrets.plugin as aws_secrets
from cerebrus.plugins.aws_secrets.plugin import AWSSecretsManager


def make_manager(tmp_path):
    manager = AWSSecretsManager.__new__(AWSSecretsManager)
    manager.cache_file = tmp_path / "aws_secrets.json"
    manager.regions_file = tmp_path / "aws_regions.json"
    manager.data = {"keys": {}, "buckets": []}
    manager.regions = ["ap-south-1"]
    return manager


def test_export_data_writes_encrypted_binary_with_secrets(tmp_path):
    """CBX3 exports MUST encrypt the file and MUST include credentials.

    Plaintext access_key / secret_key values must never appear in the bytes
    on disk -- if they do, a passphrase leak isn't even necessary to lift
    them. Plaintext on disk is the regression we're guarding against.
    """
    from cerebrus.plugins.aws_secrets.portable_crypto import (
        decrypt_payload,
        looks_like_cbx3,
    )

    manager = make_manager(tmp_path)
    manager.data = {
        "keys": {
            "team": {
                "alias": "team",
                "access_key": "AKIA_TEST",
                "secret_key": "SECRET_TEST",
            }
        },
        "buckets": [
            {"name": "perf-reports", "region": "ap-south-1", "key_alias": "team"}
        ],
    }

    export_path = tmp_path / "aws.cbx"
    assert manager.export_data(export_path) is True

    raw = export_path.read_bytes()
    assert looks_like_cbx3(raw), "Export must be CBX3 binary, not text."
    assert b"AKIA_TEST" not in raw
    assert b"SECRET_TEST" not in raw

    decrypted = decrypt_payload(raw, None)
    assert decrypted["schema_version"] == "3.0"
    assert decrypted["contains_secret_values"] is True
    assert decrypted["keys"]["team"]["access_key"] == "AKIA_TEST"
    assert decrypted["keys"]["team"]["secret_key"] == "SECRET_TEST"


def test_export_data_passphrase_mode_requires_passphrase_to_decrypt(tmp_path):
    from cerebrus.plugins.aws_secrets.portable_crypto import (
        DecryptionFailed,
        PassphraseRequired,
        decrypt_payload,
    )

    manager = make_manager(tmp_path)
    manager.data = {
        "keys": {
            "team": {
                "alias": "team",
                "access_key": "AKIA_TEST",
                "secret_key": "SECRET_TEST",
            }
        },
        "buckets": [],
    }
    export_path = tmp_path / "aws.cbx"
    assert manager.export_data(export_path, passphrase="hunter2") is True

    raw = export_path.read_bytes()
    try:
        decrypt_payload(raw, None)
        raise AssertionError("embedded key must not decrypt passphrase exports")
    except PassphraseRequired:
        pass

    try:
        decrypt_payload(raw, "wrong")
        raise AssertionError("wrong passphrase must not decrypt")
    except DecryptionFailed:
        pass

    payload = decrypt_payload(raw, "hunter2")
    assert payload["keys"]["team"]["access_key"] == "AKIA_TEST"


def test_export_data_skips_duplicate_secret_entries(tmp_path):
    from cerebrus.plugins.aws_secrets.portable_crypto import decrypt_payload

    manager = make_manager(tmp_path)
    manager.data = {
        "keys": {
            "team": {
                "alias": "team",
                "access_key": "AKIA_TEST",
                "secret_key": "SECRET_TEST",
            },
            "duplicate-access": {
                "alias": "duplicate-access",
                "access_key": "AKIA_TEST",
                "secret_key": "OTHER_SECRET",
            },
            "duplicate-secret": {
                "alias": "duplicate-secret",
                "access_key": "OTHER_AKIA",
                "secret_key": "SECRET_TEST",
            },
        },
        "buckets": [
            {"name": "perf-reports", "region": "ap-south-1", "key_alias": "team"},
            {
                "name": "duplicate-bucket",
                "region": "ap-south-1",
                "key_alias": "duplicate-access",
            },
        ],
    }

    export_path = tmp_path / "aws.cbx"
    assert manager.export_data(export_path) is True

    payload = decrypt_payload(export_path.read_bytes(), None)
    assert set(payload["keys"]) == {"team"}
    assert payload["buckets"] == [
        {"name": "perf-reports", "region": "ap-south-1", "key_alias": "team"}
    ]


def test_import_data_preserves_existing_key_secret_values(tmp_path):
    manager = make_manager(tmp_path)
    manager.data = {
        "keys": {
            "team": {
                "alias": "team",
                "access_key": "EXISTING_AK",
                "secret_key": "EXISTING_SK",
            }
        },
        "buckets": [],
    }
    manager.save = lambda: True

    import_path = tmp_path / "aws.cbx"
    import_path.write_text(
        json.dumps(
            {
                "schema_version": "2.0",
                "contains_secret_values": False,
                "keys": {"team": {"alias": "team", "requires_reentry": True}},
                "buckets": [
                    {
                        "name": "perf-reports",
                        "region": "us-east-1",
                        "key_alias": "team",
                    }
                ],
            }
        )
    )

    assert manager.import_data(import_path) == ""
    assert manager.data["keys"]["team"]["access_key"] == "EXISTING_AK"
    assert manager.data["keys"]["team"]["secret_key"] == "EXISTING_SK"
    assert manager.data["buckets"] == [
        {"name": "perf-reports", "region": "us-east-1", "key_alias": "team"}
    ]


def test_import_data_skips_duplicate_secret_entries(tmp_path):
    manager = make_manager(tmp_path)
    manager.data = {
        "keys": {
            "team": {
                "alias": "team",
                "access_key": "EXISTING_AK",
                "secret_key": "EXISTING_SK",
            }
        },
        "buckets": [],
    }
    manager.save = lambda: True

    import_path = tmp_path / "legacy.cbx"
    import_path.write_text(
        json.dumps(
            {
                "keys": {
                    "duplicate-access": {
                        "alias": "duplicate-access",
                        "access_key": "EXISTING_AK",
                        "secret_key": "NEW_SK",
                    },
                    "duplicate-secret": {
                        "alias": "duplicate-secret",
                        "access_key": "NEW_AK",
                        "secret_key": "EXISTING_SK",
                    },
                    "new-team": {
                        "alias": "new-team",
                        "access_key": "NEW_AK_2",
                        "secret_key": "NEW_SK_2",
                    },
                },
                "buckets": [],
            }
        )
    )

    assert manager.import_data(import_path) == ""
    assert set(manager.data["keys"]) == {"team", "new-team"}


def test_add_key_rejects_duplicate_alias_access_key_and_secret_key(tmp_path):
    manager = make_manager(tmp_path)
    manager.data["keys"]["team"] = {
        "alias": "team",
        "access_key": "AKIA_TEST",
        "secret_key": "SECRET_TEST",
    }
    manager._local_encryption_available = lambda: True
    manager.save = lambda: True

    assert "alias already exists" in manager.add_key("team", "AKIA_NEW", "SECRET_NEW")
    assert "Access Key ID" in manager.add_key("other", "AKIA_TEST", "SECRET_NEW")
    assert "Secret Access Key" in manager.add_key("other", "AKIA_NEW", "SECRET_TEST")

    assert manager.add_key("other", "AKIA_NEW", "SECRET_NEW") == ""
    assert set(manager.data["keys"]) == {"team", "other"}


def test_bucket_display_names_include_region_to_avoid_ambiguity(tmp_path):
    manager = make_manager(tmp_path)
    manager.data["buckets"] = [
        {"name": "perf-reports", "region": "ap-south-1", "key_alias": "team"},
        {"name": "perf-reports", "region": "us-east-1", "key_alias": "team"},
    ]

    assert manager.get_bucket_display_items() == [
        "perf-reports [ap-south-1] (team)",
        "perf-reports [us-east-1] (team)",
    ]


def test_get_credentials_for_bucket_returns_real_bucket_name(tmp_path):
    manager = make_manager(tmp_path)
    manager.data = {
        "keys": {
            "team": {
                "alias": "team",
                "access_key": "AKIA_TEST",
                "secret_key": "SECRET_TEST",
            }
        },
        "buckets": [
            {"name": "perf-reports", "region": "ap-south-1", "key_alias": "team"}
        ],
    }

    credentials = manager.get_credentials_for_bucket("perf-reports [ap-south-1] (team)")

    assert credentials == {
        "aws_access_key_id": "AKIA_TEST",
        "aws_secret_access_key": "SECRET_TEST",
        "region_name": "ap-south-1",
        "bucket_name": "perf-reports",
    }


def test_export_payload_embeds_version_metadata(tmp_path):
    """Every export must carry enough metadata for a future build to know
    what it's looking at without filename inference."""
    from cerebrus.plugins.aws_secrets.portable_crypto import decrypt_payload

    manager = make_manager(tmp_path)
    manager.data = {
        "keys": {
            "team": {
                "alias": "team",
                "access_key": "AKIA_TEST",
                "secret_key": "SECRET_TEST",
            }
        },
        "buckets": [],
    }
    export_path = tmp_path / "aws.cbx"
    assert manager.export_data(export_path) is True

    payload = decrypt_payload(export_path.read_bytes(), None)
    assert payload["schema_version"] == AWSSecretsManager.EXPORT_SCHEMA_VERSION
    assert payload["min_supported_schema"] == AWSSecretsManager.MIN_SUPPORTED_SCHEMA
    assert "cerebrus_version" in payload and payload["cerebrus_version"]
    # ISO-8601 UTC timestamp; sanity check the shape, not exact value.
    assert "T" in payload["created_at"] and payload["created_at"].endswith(
        ("+00:00", "Z")
    )


def test_import_rejects_unsupported_future_schema(tmp_path):
    """Files tagged with a schema newer than this build understands must
    fail loud, not silently drop fields."""
    from cerebrus.plugins.aws_secrets.portable_crypto import encrypt_payload

    manager = make_manager(tmp_path)
    manager.save = lambda: True

    future_payload = {
        "schema_version": "99.0",
        "min_supported_schema": "99.0",
        "cerebrus_version": "v99.0.0",
        "contains_secret_values": True,
        "export_type": "aws_bucket_mappings",
        "keys": {
            "team": {
                "alias": "team",
                "access_key": "AKIA_FUTURE",
                "secret_key": "SK_FUTURE",
            }
        },
        "buckets": [],
    }

    import_path = tmp_path / "future.cbx"
    import_path.write_bytes(encrypt_payload(future_payload, None))

    error = manager.import_data(import_path)
    assert "Unsupported export schema" in error
    assert "99.0" in error
    assert (
        manager.data["keys"] == {}
    ), "No keys should be imported when schema gate trips."


def test_import_accepts_legacy_unversioned_payload(tmp_path):
    """Pre-versioning files (no ``schema_version``) must still import so
    teams upgrading from old Cerebrus builds don't lose their configs."""
    manager = make_manager(tmp_path)
    manager.save = lambda: True

    import_path = tmp_path / "ancient.cbx"
    import_path.write_text(
        json.dumps(
            {
                "keys": {
                    "old-team": {
                        "alias": "old-team",
                        "access_key": "AKIA_OLD",
                        "secret_key": "SK_OLD",
                    }
                },
                "buckets": [],
            }
        )
    )

    assert manager.import_data(import_path) == ""
    # Legacy payload had no contains_secret_values=True marker, so credentials
    # land as metadata-only entries requiring re-entry. The point of this
    # test is that the import is *not* rejected on schema grounds.
    assert "old-team" in manager.data["keys"]


def test_schema_version_parsing_tolerates_malformed_values():
    assert AWSSecretsManager._is_schema_supported("3.0") is True
    assert AWSSecretsManager._is_schema_supported("2.0") is True
    assert AWSSecretsManager._is_schema_supported("1.9") is False
    assert AWSSecretsManager._is_schema_supported("3.1") is False
    assert AWSSecretsManager._is_schema_supported("not-a-version") is False
    assert AWSSecretsManager._is_schema_supported("") is False


def test_add_key_refuses_to_save_without_local_encryption(tmp_path, monkeypatch):
    manager = make_manager(tmp_path)
    monkeypatch.setattr(aws_secrets, "win32crypt", None)

    error = manager.add_key("team", "AKIA_TEST", "SECRET_TEST")

    assert "encryption is unavailable" in error
    assert manager.data["keys"] == {}
