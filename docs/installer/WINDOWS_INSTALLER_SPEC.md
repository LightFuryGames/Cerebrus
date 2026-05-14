# Windows Installer Specification

Technical specification for the Cerebrus Windows installer.

## Technology Choice

- Use a robust Windows installer technology (e.g. WiX Toolset, NSIS, or similar).
- Bundle a standalone Python environment (e.g. embeddable Python or a pre-built venv).
- **IT Friendly**: Must support `/S` or `/VERYSILENT` flags to install without UI.

## Install Layout

Suggested installation directory (per user):

```text
%LOCALAPPDATA%\Cerebrus\
  app\
  python\
  env\
  config\
  logs\
  cache\
```

## Steps

1. Copy application files to `app\`.
2. Install or extract Python to `python\` or `env\`.
3. Install Python packages using an offline wheel cache or pre-bundled environment.
4. Create launcher executable or script that:
   - Activates the environment.
   - Launches `python -m cerebrus`.

## Environment Validation

On first run, Cerebrus should:

- Check for presence of ADB.
- Prompt for Unreal Engine / CsvTools / PerfReportTool paths if not configured.
- Offer to save configuration to `config\`.

## Updates

- Implement a strategy for in-place updates:
  - Overwrite `app\` while preserving `config\`, `logs\`, and `cache\`.
  - Optionally migrate configuration formats if they change.

This spec will evolve as the installer implementation progresses.
