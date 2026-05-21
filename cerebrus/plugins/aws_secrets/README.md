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
- Export plugin bucket/key-alias mappings as an encrypted `.cbx` (CBX3) file.
- Import plugin bucket/key-alias mappings from a `.cbx` file (CBX3, legacy JSON, or legacy XOR all supported).

## Storage and Security

- Local plugin data is stored under `%LOCALAPPDATA%/Cerebrus`.
- Secret values use Windows DPAPI through `pywin32`.
- Saved credentials are unique by alias, access key ID, and secret access key. Imports skip credential entries that would duplicate an existing local credential.
- If DPAPI is unavailable, Cerebrus refuses to persist new AWS keys instead of writing plaintext secrets.
- `.cbx` export files (schema 3.0, CBX3 format) are **encrypted binary**. They embed `Access Key ID` / `Secret Access Key` values behind two-layer authenticated encryption (AES-256-GCM inside Fernet, PBKDF2-HMAC-SHA256 key derivation with independent per-export random salts, 600k inner / 200k outer iterations).
- Export accepts an optional passphrase. With a passphrase, only recipients who know it can decrypt the file. Without a passphrase, an embedded app key is used — anyone with a Cerebrus install can decrypt the file (useful for tamper-evidence and intra-team distribution, but treat the file as "as sensitive as the cleartext credentials" since the embedded key offers no real secrecy against anyone with the binary).
- Do not commit exported `.cbx` files, AWS keys, or bucket-private data to the repository.

## `.cbx` Binary Layout (CBX3, schema 3.0)

```
offset  size   field
0       4      magic "CBX3"
4       1     version (=3)
5       1     mode    (0 = embedded key, 1 = passphrase)
6       16    salt_inner (PBKDF2 salt, random per export)
22      16    salt_outer (PBKDF2 salt, random per export)
38      12    nonce_inner (AES-GCM nonce)
50      ..    Fernet(K_outer).encrypt(AES-GCM(K_inner).encrypt(json_payload))
```

The decrypted JSON payload carries:

```json
{
  "schema_version": "3.0",
  "min_supported_schema": "2.0",
  "cerebrus_version": "v3.0.4",
  "created_at": "2026-05-21T12:34:56+00:00",
  "export_type": "aws_bucket_mappings",
  "contains_secret_values": true,
  "keys": {
    "TeamPerfKey": {
      "alias": "TeamPerfKey",
      "access_key": "AKIA...",
      "secret_key": "...",
      "requires_reentry": false,
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

### Versioning policy

- `schema_version` is the format version of the payload.
- `min_supported_schema` is the oldest reader that can parse it without migration.
- `cerebrus_version` records the build that produced the file (informational; not used for gating).
- This build accepts `2.0..3.0`. Anything outside that range is refused with a clear "upgrade Cerebrus" message rather than parsed with missing/extra fields.

## Dependencies

- `pywin32` enables Windows DPAPI encryption for the local credential cache.
- `cryptography` enables CBX3 portable export encryption (AES-GCM, Fernet, PBKDF2).
- The plugin can still load without `pywin32`, but it must not save new AWS keys because local credential encryption is unavailable.

## Current Tests

`tests/core/test_aws_secrets_manager.py` covers:

- `.cbx` exports are CBX3 binary; cleartext credentials never appear in the file bytes.
- Passphrase-mode exports refuse the embedded key, reject wrong passphrases, accept the correct passphrase.
- Export payload embeds `schema_version`, `min_supported_schema`, `cerebrus_version`, and a UTC `created_at`.
- Imports tagged with a future schema (e.g. `99.0`) are rejected with a guidance message; no keys are written.
- Legacy unversioned JSON `.cbx` files still import.
- Schema version parser tolerates malformed values.
- Imports preserve existing local credentials.
- Imports skip duplicate credential entries.
- New key saving rejects duplicate aliases, access key IDs, and secret access keys.
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
