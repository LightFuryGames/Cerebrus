# Installation Guide

This guide describes how to install and update Project Cerebrus on a Windows machine.

## Prerequisites

- Windows 10 or newer (64-bit).
- Sufficient disk space for:
  - Unreal Engine tools (UAFT, CsvTools, PerfReportTool).
  - Profiling captures (potentially tens of GB per project).
- Access to:
  - Android SDK / ADB tools.
  - Unreal Engine installation that provides the required binaries.

## Option 1: One-Click Installer (Recommended)

Once available, the Cerebrus installer will:

- Bundle a compatible Python runtime.
- Install Python dependencies in an isolated environment.
- Install required .NET Runtimes (.NET 6 and .NET 8).
- Prompt for:
  - Unreal Engine root or CsvTools/PerfReportTool locations.
  - Default cache and reports directories.
- Create Start Menu shortcuts and an optional desktop shortcut.

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

4. Configure tool paths (see `docs/config/TOOLS_PATHS.md`):

   - Create `config/tools.paths.json` based on the example paths in that document.
   - Ensure UAFT, CsvTools, and PerfReportTool paths are correct.

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

## Uninstallation

- One-click installer:
  - Use the Windows “Apps & features” uninstaller entry for Cerebrus.
- Manual installation:
  - Delete the repo directory (e.g. `cerebrus`).
  - Remove any per-user cache and report directories if desired (locations are configurable).
