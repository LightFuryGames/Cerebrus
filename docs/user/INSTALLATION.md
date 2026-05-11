# Installation Guide

This guide describes how to install and update Project Cerebrus on a Windows machine.

## Prerequisites

- Windows 10 or newer (64-bit).
- **Python 3.12+** (if running from source or customizing).
- Sufficient disk space for:
  - Unreal Engine tools (CsvTools, PerfReportTool).
  - Profiling captures (potentially tens of GB per project).
- Access to:
  - Android SDK / ADB tools.
  - Unreal Engine installation that provides the required binaries.

## Option 1: Official Distribution (Recommended)

- **Cerebrus_Setup.exe**: The official installer for end-users.
- **Portable ZIP**: Self-contained archive for manual execution.

Refer to `docs/installer/WINDOWS_INSTALLER_SPEC.md` for technical details.

## Option 2: Manual Developer Installation

1. Clone the repository:

   ```bash
   git clone <REPO_URL> cerebrus
   cd cerebrus
   ```

2. Create a virtual environment:

   ```bash
   py -3 -m venv .venv
   .venv\Scripts\activate
   ```

3. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Verify bundled and local tools:

   - Ensure `Binaries/CsvTools/PerfReportTool.exe` exists for performance report generation.
   - Ensure ADB is available on PATH or let Cerebrus install Android platform tools during startup.
   - Install plugin dependencies from `requirements.txt`, including `boto3` for the S3 Uploader plugin.

5. (Optional) Run tests:

   ```bash
   pytest
   ```

## Updating Cerebrus

1. Pull the latest changes:

   ```bash
   git pull
   ```

2. Reinstall dependencies if `requirements.txt` changed:

   ```bash
   pip install -r requirements.txt
   ```

3. Review `CHANGELOG.md` if present and relevant docs under `docs/developer` for any migration steps.

## Plugin Documentation

Runtime plugin docs live beside the plugin code:

- `cerebrus/plugins/README.md`
- `cerebrus/plugins/aws_secrets.md`
- `cerebrus/plugins/s3_uploader.md`

Old AWS configuration docs that mention `Tools -> AWS Configuration` are deprecated. Current cloud setup happens through the AWS Secrets and S3 Uploader plugins.

## Uninstallation

- One-click installer:
  - Use the Windows “Apps & features” uninstaller entry for Cerebrus.
- Manual installation:
  - Delete the repo directory (e.g. `cerebrus`).
  - Remove any per-user cache and report directories if desired (locations are configurable).
