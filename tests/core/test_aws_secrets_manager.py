import json

import cerebrus.plugins.aws_secrets as aws_secrets
from cerebrus.plugins.aws_secrets import AWSSecretsManager


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


def test_add_key_refuses_to_save_without_local_encryption(tmp_path, monkeypatch):
    manager = make_manager(tmp_path)
    monkeypatch.setattr(aws_secrets, "win32crypt", None)

    error = manager.add_key("team", "AKIA_TEST", "SECRET_TEST")

    assert "encryption is unavailable" in error
    assert manager.data["keys"] == {}
