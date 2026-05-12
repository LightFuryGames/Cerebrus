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

For Cerebrus reports, the plugin first reads:

```html
<script type="application/json" id="cerebrus-metadata">
```

For newer PerfReportTool HTML reports, the plugin can also read the visible report table:

```text
Build Version -> ++titan-game+development-CL-33425
Configuration -> Test
CPU/Device -> OnePlus|ONEPLUS A3003|Qualcomm Technologies, Inc MSM8996
Profile(...) -> Profile(20260511_082831)
```

That becomes:

```text
Test/OnePlus/A3003/CL-33425/11-05-2026/082831/Filename.html
```

If the visible table is unavailable, the plugin falls back to the embedded CSV footer fields such as `[config]`, `[buildversion]`, and `[cpu]`.

When metadata is available, the default S3 path is:

```text
BuildConfiguration/DeviceMake/DeviceModel/Changelist/Date/Time/Filename.html
```

If metadata is missing, the user can still upload, but they must review or type the path manually.

## Upload Behavior

The plugin uploads the selected HTML report as-is. It does not rewrite, strip, or optimize the report before upload. This keeps the uploaded artifact byte-for-byte aligned with the file the user reviewed locally.

Bucket labels in the UI may include region and key alias, for example:

```text
perf-reports [ap-south-1] (team)
```

That label is only for humans. During upload, Cerebrus resolves it back to the real S3 bucket name before calling AWS.

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
- Metadata extraction from current PerfReportTool HTML tables.
- Metadata extraction from current PerfReportTool embedded CSV footers.
- Destination path derivation and sanitization.
- Upload call construction with and without `ContentType`.

## Required Tests

Add tests for:

- Warning behavior for changelist `0`.
- Rejection of non-HTML files.
- Behavior when no bucket is selected.
- Behavior when credentials are missing.
- Upload call construction for `upload_file`.
- `ContentType` handling through `ExtraArgs`.
- HTML validation read failures logging a warning.

Use mocks for `boto3.client`, file dialogs, and Dear PyGui calls. Do not call AWS in unit tests.
