# S3 Uploader Plugin

The S3 Uploader plugin sends generated Cerebrus HTML reports to a configured S3 bucket.

## Kindergarten-Level Picture

AWS Secrets is the key locker.

S3 Uploader is the delivery cart.

1. Pick a report file.
2. Pick the bucket label.
3. Cerebrus reads the small metadata note hidden inside the report.
4. Cerebrus builds a neat S3 folder path.
5. The delivery cart uploads the report.

## What Users See

The plugin adds the `S3 Uploader - Profiling Reports` tab.

Users choose:

- Source HTML report.
- Target bucket mapping from AWS Secrets.
- Destination path, either auto-filled from metadata or typed manually.

Then they click:

```text
Upload Performance Report to S3
```

## Metadata-Based Pathing

For Cerebrus reports, the plugin reads:

```html
<script type="application/json" id="cerebrus-metadata">
```

When metadata is available, the default S3 path is:

```text
BuildConfiguration/DeviceMake/DeviceModel/Changelist/Date/Time/Filename.html
```

If metadata is missing, the user can still upload, but they must review or type the path manually.

## Upload Behavior

The plugin uploads the selected HTML report as-is. It does not rewrite, strip, or optimize the report before upload. This keeps the uploaded artifact byte-for-byte aligned with the file the user reviewed locally.

## Warnings

The plugin warns when:

- The selected file is not an HTML report.
- The file does not look like a Cerebrus report.
- The report changelist is `0`, which often means a local or unversioned build.
- Credentials cannot be found for the selected bucket mapping.
- `boto3` is missing.

## Dependencies

- `boto3`
- `botocore`
- A configured bucket mapping from the AWS Secrets plugin.

## Current Tests

`tests/core/test_s3_uploader.py` covers:

- Metadata extraction from embedded JSON.
- Metadata extraction from legacy stat cards.
- Destination path derivation and sanitization.
- Upload call construction with and without `ContentType`.

## Required Tests

Add tests for:

- Metadata extraction from the embedded JSON block.
- Legacy metadata fallback from visible report cards.
- Destination path derivation and sanitization.
- Warning behavior for changelist `0`.
- Rejection of non-HTML files.
- Behavior when no bucket is selected.
- Behavior when credentials are missing.
- Upload call construction for `upload_file`.
- `ContentType` handling through `ExtraArgs`.
- HTML validation read failures logging a warning.

Use mocks for `boto3.client`, file dialogs, and Dear PyGui calls. Do not call AWS in unit tests.
