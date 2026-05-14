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


def test_export_data_does_not_write_secret_values(tmp_path):
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

    payload = json.loads(export_path.read_text())
    assert payload["schema_version"] == "2.0"
    assert payload["contains_secret_values"] is False
    serialized = json.dumps(payload)
    assert "AKIA_TEST" not in serialized
    assert "SECRET_TEST" not in serialized
    assert payload["keys"]["team"]["requires_reentry"] is True


def test_export_data_skips_duplicate_secret_entries(tmp_path):
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

    payload = json.loads(export_path.read_text())
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


def test_add_key_refuses_to_save_without_local_encryption(tmp_path, monkeypatch):
    manager = make_manager(tmp_path)
    monkeypatch.setattr(aws_secrets, "win32crypt", None)

    error = manager.add_key("team", "AKIA_TEST", "SECRET_TEST")

    assert "encryption is unavailable" in error
    assert manager.data["keys"] == {}
