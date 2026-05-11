# AWS Secrets Plugin

The AWS Secrets plugin is the local key locker for Cerebrus.

## Kindergarten-Level Picture

Imagine you have a small box with labels on it.

- One label says `TeamPerfKey`.
- Inside that label are the AWS access key and secret key.
- Another label says which S3 bucket can use that key.
- The S3 Uploader does not ask you to type the secret every time. It asks the box for the right label.

That is all this plugin does: it keeps the keys and bucket map in one place so other plugins can use them safely.

## What Users See

The plugin adds an `AWS Secrets` tab and extra menu actions under:

```text
Settings -> Plugins -> AWS Secrets
```

In the tab, users can:

- Add an AWS key alias.
- Enter an access key ID.
- Enter a secret access key.
- Add or select allowed AWS regions.
- Map an S3 bucket to a region and key alias.

In the menu, users can:

- Manage saved keys.
- Manage saved bucket mappings.
- Manage allowed regions.
- Export plugin bucket/key-alias mappings as a `.cbx` JSON file.
- Import plugin bucket/key-alias mappings from a `.cbx` JSON file.

## Storage and Security

- Local plugin data is stored under `%LOCALAPPDATA%/Cerebrus`.
- Secret values use Windows DPAPI through `pywin32`.
- If DPAPI is unavailable, Cerebrus refuses to persist new AWS keys instead of writing plaintext secrets.
- `.cbx` export files are explicit JSON transfer files. They contain bucket mappings, key aliases, schema metadata, and `contains_secret_values: false`.
- `.cbx` export files do not contain AWS access key IDs or secret access keys. After import, users may need to re-enter credentials for the imported aliases.
- Do not commit exported `.cbx` files, AWS keys, or bucket-private data to the repository.

## `.cbx` JSON Shape

```json
{
  "schema_version": "2.0",
  "export_type": "aws_bucket_mappings",
  "contains_secret_values": false,
  "keys": {
    "TeamPerfKey": {
      "alias": "TeamPerfKey",
      "requires_reentry": true,
      "has_access_key": true,
      "has_secret_key": true
    }
  },
  "buckets": [
    {
      "name": "perf-reports",
      "region": "ap-south-1",
      "key_alias": "TeamPerfKey"
    }
  ]
}
```

## Dependencies

- `pywin32` enables Windows DPAPI encryption.
- The plugin can still load without `pywin32`, but it must not save new AWS keys because local credential encryption is unavailable.

## Current Tests

`tests/core/test_aws_secrets_manager.py` covers:

- `.cbx` exports do not contain secret values.
- Imports preserve existing local credentials.
- Bucket display labels include region to avoid ambiguity.
- New key saving is refused when DPAPI is unavailable.

## Required Tests

Add tests for:

- New manager schema defaults: `keys`, `buckets`, and default region.
- Add/remove key behavior.
- Add/remove bucket mapping behavior.
- Bucket display label generation.
- Credential lookup by display label.
- Region load/save behavior.
- Additional import/export merge edge cases.
- DPAPI encryption/decryption behavior when `win32crypt` is available.
- Corrupt or invalid cache file recovery.

## User Safety Notes

If a user says, "I do not see my bucket in the S3 plugin," check this plugin first. The uploader can only show buckets that were mapped here.
