# Cerebrus User Guide

Cerebrus is a comprehensive GUI toolkit for Unreal Engine Android profiling workflows. It simplifies the process of collecting logs, moving files, and generating performance reports.

## Table of Contents
1. [Getting Started](#getting-started)
2. [Profile Management](#profile-management)
3. [Device Management](#device-management)
4. [File Actions](#file-actions)
5. [Report Generation](#report-generation)
6. [Cloud Integration & AWS Plugins](#cloud-integration--aws-plugins)
7. [Analytics & Trends](#analytics--trends)
8. [Plugins](#plugins)
9. [Settings](#settings)
10. [Troubleshooting](#troubleshooting)

## Getting Started
Launch Cerebrus to see the main dashboard. The interface is divided into several sections:
- **Menu Bar**: Access file operations, views, tools, settings, and help.
- **Profile Summary**: Displays the currently loaded profile information.
- **Device List**: Shows connected Android devices.
- **Data and Perf Report**: Configure paths and perform bulk actions.
- **Logging**: View real-time application logs.

## Profile Management
Profiles allow you to save and load configurations for different projects or devices.
- **New Profile**: Create a fresh configuration.
- **Open Profile**: Load an existing JSON profile.
- **Edit Profile**: Modify the current profile settings.
- **Auto-Save**: Changes to paths and settings are automatically saved to the current profile.

## Device Management
The device list shows all connected Android devices.
- **Automatic scan**: Cerebrus polls ADB on a background thread every ~10 seconds. Plug in a phone and the row appears within a few seconds without clicking anything. Scans are silent — no console windows flash on screen.
- **Refresh (manual)**: Click "List Devices" to force an immediate rescan. Bypasses the debounce so it always fires.
- **Start ADB Server**: Manual override. Boots the local ADB daemon (`adb start-server`) when it has not been brought up yet. Cerebrus retries device detection automatically afterwards.
- **Stop ADB Server**: Manual override. Stops the local ADB daemon (`adb kill-server`). Use it when ADB is wedged after a USB hot-swap.
- **Selection**: Click on a device row to select it for operations.
- **Status**: The table shows the device model, serial number, Android version, and if the target package is installed.
- **Remote Controls**:
    - **Launch Package**: Launch or resume the target application (supports Launch Package v2.0.0).
    - **Profiling**: Start/Stop CSV profiling.
    - **Remote Console**: Send `memreport` or custom console commands (e.g., `stat unit`).

## File Actions
Manage files between your PC and the connected Android device.

### Configuration
- **Output File Name**: The base name for generated files.
- **Move Files Folder Path**: The directory on your PC where files will be copied to.
- **Output Folder Path**: The destination for generated reports.
- **Append Device Make/Model**: Automatically creates subfolders based on the device name.

### Bulk Actions (Phone to PC)
- **Move Logs**: Copies logs from `Saved/Logs` on the device to your PC.
- **Move CSV Data**: Copies profiling data from `Saved/Profiling/CSV` on the device to your PC.

## Cloud Integration & AWS Plugins
Cerebrus uses plugins for cloud workflows. A plugin is a small extra work area that can add a tab and menu actions without changing the whole app.

For detailed plugin help, see:
- `cerebrus/plugins/README.md`
- `cerebrus/plugins/aws_secrets/README.md`
- `cerebrus/plugins/s3_uploader/README.md`
- `cerebrus/plugins/analytics/README.md`

### AWS Secrets Manager
Think of AWS Secrets as the key locker. You give a key a friendly label, then map that label to an S3 bucket. The uploader later asks the locker for the right key.

- **Key Alias**: A friendly name for one AWS access key pair.
- **Unique Credentials**: Key aliases, access key IDs, and secret access keys cannot be duplicated, including during imports.
- **Bucket Mapping**: The bucket name, region, and key alias that belong together.
- **Local Protection**: Credentials use Windows DPAPI. If DPAPI is unavailable, Cerebrus refuses to save new AWS keys instead of writing plaintext secrets.
- **Portable Export**: Export/import `.cbx` JSON files when a teammate needs the same bucket map. These files include bucket mappings and key aliases, not AWS secret values.

### S3 Uploader
Think of S3 Uploader as the delivery cart. It picks up one generated HTML report, reads the hidden metadata note inside it, builds a tidy folder path, and uploads it to the bucket you selected.

- **Automatic Pathing**: Reads metadata from reports to determine the S3 path (`BuildConfig/Device/CL/Date/Time`).
- **Optimization**: Strips redundant raw memreport data before upload when possible.
- **Requirements**: Requires the `boto3` Python package.

## Analytics & Trends
The Analytics & Trends tab turns a finished perf report into a small JSON record the team's Elasticsearch + Grafana dashboards can read, then uploads it. Two buttons, two text fields, one checkbox.

### What the fields mean
- **Source File**: The report you want to convert or upload. Accepts `.html`, `.csv`, or `.analytics.json`. Auto-filled with the freshly-generated JSON path after a successful **Convert**, so the next click can be **Upload**.
- **Output File Path** (optional): The folder where **Convert** writes the JSON. Leave blank to write the JSON next to the Source File. When set with no Source File, **Upload** treats every `.analytics.json` in that folder as a target so you can push a backlog in one click.
- **Use Profiling Output**: Fills Output File Path with the Profiling tab's current output directory.
- **Upload Endpoint**: The Elasticsearch document URL (e.g. `http://host:9200/your-index-name/_doc`). The **Save** button persists it so you don't retype between sessions.
- **Delete Analytics JSON after Upload Success**: When on, removes the `.analytics.json` from disk only after the dashboard confirms a clean upload. Failed uploads always keep the file so you can retry.

### Buttons
- **Convert File to Analytics JSON**: Reads the Source File, extracts every dashboard-relevant field (device, build, FPS, percentiles, Report Value, data-quality flag, Scalability Tier), and writes a single flat `<stem>.analytics.json`. After it writes, the Source File field is rewritten to point at the new JSON.
- **Upload Analytics Document**: Sends the JSON to the Upload Endpoint. Single file if Source File points to one; folder-wide if Source File is empty and Output File Path is a folder. Each upload uses the report's `report_fingerprint` as the document ID — re-uploads overwrite the existing record instead of creating duplicates.

### Shortest workflow
1. Generate the perf report from the Profiling tab.
2. Open Analytics & Trends. Browse to the HTML report.
3. Click **Convert File to Analytics JSON**. A green `Analytics JSON written: ...` line confirms success.
4. Click **Upload Analytics Document**. A green `Uploaded analytics document: ...` line means the dashboard has it.

To push a folder of older reports at once: set Output File Path, leave Source File empty, click Upload. Each report uploads in turn; failed ones stay on disk for retry.

### Reading the log lines
- `SUCCESS` `Analytics JSON written: ...` — conversion done.
- `SUCCESS` `Uploaded analytics document: ...` — dashboard accepted one record.
- `INFO` `Uploaded: 5 / 7` — folder upload summary; `Failures:` rows underneath name each failed path and HTTP status.
- `WARNING` `upload ignored: another upload is still running.` — second click during an in-flight upload. Wait for the first to log SUCCESS, then click again.
- `ERROR` `Enter the Elasticsearch document endpoint URL before uploading.` — Upload Endpoint is blank.
- `ERROR` `Select a Source File or an Output File Path containing *.analytics.json files first.` — nothing to send; need either a specific file or a folder of converted JSONs.

## Report Generation
Process collected data into readable formats.

### Bulk Actions (PC to PC)
- **Generate Perf Report Only**: Runs `PerfreportTool.exe` on CSV files to create visual reports.
    - **New Metrics**: Reports now include System Metadata, FPS Analysis, and Average FPS.
- **Generate Memory Report Only**: Converts `.memreport` files into interactive HTML visualizations.
    - **Visualization**: Provides tree maps and detailed object tracking for memory analysis.
    - **Automatic Naming**: Reports are named as `{BuildConfig}_{Device}_{CL}_{Date}.html`.
    - **Metadata**: Embeds session data for S3 uploading and downstream analysis.
- **Generate Colored Logs Only**: Converts text logs to color-coded HTML files.
- **Generate All**: Performs all enabled operations in sequence.
- **View HTML Logs**: Opens the `Logs` output folder to view generated HTML logs.

### Local Report Comparison
- **Generate A/B Compare Report**: Compares two local profiling CSV runs and creates a statistical HTML comparison report.

> **Note**: Generated reports are automatically organized into `Profiling/`, `Logs/`, and `MemReports/` subdirectories within your Output Path.

## Plugins
Access plugin tabs in the main tab area. Enable or disable plugins from **Settings -> Plugins**.

- **Profiling**: Main capture and report workflow.
- **AWS Secrets**: Key locker and bucket map.
- **S3 Uploader - Profiling Reports**: Upload generated HTML reports.
- **Analytics & Trends**: Convert HTML/CSV reports to `.analytics.json` and push them to the Elasticsearch/OpenSearch trend index.

### Auto-Update
Cerebrus automatically checks for updates on startup.
- If a new version is available, a prompt will appear.
- The update is downloaded and installed automatically.

## Settings
Customize your experience via the Settings menu.
- **Load Theme**: Switch between Dark, Light, or System themes.
- **Log Colors**: Customize the colors used in the application log window.
- **Key Bindings**: View or edit keyboard shortcuts.

## Troubleshooting
- **No Devices Found**: Ensure USB debugging is enabled and ADB is running.
- **Tool Not Found**: Verify that `PerfreportTool.exe` path is correctly configured in your environment or settings.
- **Report Features**: Generated HTML reports include a **Dark Mode** toggle and **Scroll to Top** button for better readability.

## Changelog

### v3.0.4 — Bug-fix & hardening (against v2.4.0 baseline)
Targeted fixes on top of the v2.4.0 baseline most teams are upgrading from. No workflow changes; nothing to relearn.

- **New profile package-name persistence.** Creating a new profile no longer loses the `Package Name` after a restart. Previously, cancelling the file-save dialog left the UI showing the new package name even though nothing reached disk; on next launch Cerebrus silently fell back to the default `com.lightfury.titan`. The save dialog now updates state *after* the file is written, and a cancelled save is logged as a warning so you know nothing was saved.
- **Encrypted `.cbx` AWS exports (CBX3, schema v3.0).** `.cbx` files now embed the actual `Access Key ID` / `Secret Access Key` behind two-layer authenticated encryption: AES-256-GCM inside Fernet, both keys derived via PBKDF2-HMAC-SHA256 with independent random per-export salts. Export accepts an optional passphrase — recipients must enter the same passphrase to import. Leave it blank to use the embedded-key fallback if you only want tamper-evidence. Plaintext credentials on disk are no longer possible. Legacy unencrypted JSON and XOR-scrambled `.cbx` files continue to import unchanged.
- **Export versioning.** Every `.cbx` now carries `schema_version`, `min_supported_schema`, `cerebrus_version`, and `created_at`. Imports from a future Cerebrus release fail with a clear *"upgrade Cerebrus to import this file"* message instead of dropping fields silently. This build accepts schema versions 2.0 through 3.0.
- **Sub-window UI scale & dialog scrollbars.** The Encrypt / Decrypt AWS Export modals, Manage AWS Secrets, and Manage Allowed Regions windows now respect *Settings → UI Scale...*. The passphrase dialog no longer renders a scrollbar that clipped the header text at default scale.

**Compatibility:** Existing `.cbx` files from v2.4.0 still import normally on v3.0.4. Passphrase-protected exports require both ends to run v3.0.4 or newer.


