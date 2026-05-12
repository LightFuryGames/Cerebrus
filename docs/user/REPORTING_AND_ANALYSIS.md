# Reporting and Analysis

Cerebrus turns raw Unreal Android captures into readable HTML reports.

## Overview

From the Profiling plugin, you can:

- Select a connected device.
- Move collected logs, CSV captures, and memreports from the device.
- Generate PerfReportTool HTML reports.
- Generate colored log HTML.
- Generate memreport HTML dashboards.
- Open generated HTML from the output folder.

## Typical Workflow

1. Choose or create a **profile**.
2. Connect a phone and click **List Devices**.
3. Select the device row.
4. Pick the output folder.
5. Choose the move/generate checkboxes.
6. Click **Generate**.
7. Inspect the generated HTML in a browser.

## Current Output Locations

When a device is selected, Cerebrus writes into a device-specific folder under the output path:

```text
OutputPath/
  DeviceMake_DeviceModel/
    Profiling/          # Performance reports
    Logs/               # Colored logs
    MemReports/         # Memory reports
```

## Report Features

Generated HTML reports include:

- **Dark Mode Toggle**: Switch between light and dark themes.
- **Scroll to Top**: Quickly navigate to the top of long reports.
- **Embedded Metadata**: A hidden JSON block (`<script id="cerebrus-metadata">`) containing session details such as build, device, changelist, and date.

## Metadata-Driven Naming (MemReports)

Memory reports use a deterministic naming convention when generated through the memreport processing helper:

```text
[BuildConfig]_[DeviceMake]_[DeviceModel]_[CL]_[Date].html
```

This helps teams find the right report without opening every file.

## Cloud Integration (S3 Upload)

Cloud sharing is handled by plugins:

1. Configure keys and bucket mappings in the **AWS Secrets** tab.
2. Select a generated HTML report in the **S3 Uploader - Profiling Reports** tab.
3. Let Cerebrus read the hidden metadata note inside the report.
4. Review the destination path.
5. Upload.

Think of it this way: AWS Secrets is the key locker, and S3 Uploader is the delivery cart.

Plugin-specific details live in:

- `cerebrus/plugins/aws_secrets.md`
- `cerebrus/plugins/s3_uploader.md`

## Troubleshooting

- If reports fail to generate:
  - Check the Cerebrus live log.
  - Check that `Binaries/CsvTools/PerfReportTool.exe` exists.
  - Check that the device output folders contain the expected files.
  - Validate metadata if S3 path derivation looks wrong.

See `docs/user/TROUBLESHOOTING.md` for common failure modes.
