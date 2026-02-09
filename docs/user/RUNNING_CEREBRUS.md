# Running Cerebrus

This guide explains how to start and stop Cerebrus once installed.

## From the One-Click Installer

When installed via the one-click installer:

- Use the **Start Menu** entry “Project Cerebrus”.
- Optionally use the desktop shortcut if enabled during installation.

The application will:

- Initialize its Python environment.
- Validate configuration and external tool availability.
- **Check for Updates**: Automatically queries GitHub for a new version and prompts for update if available.
- Open the Dear ImGui-based UI main window.

## From Source (Developer Mode)

1. Activate your virtual environment and run the main entrypoint:

   ```bash
   .venv\Scripts\activate
   python -m cerebrus.main
   ```

The main window will appear and present:

- Device list panel.
- Capture workflows.
- Reporting and analysis tools.
- Configuration access.

## Command-Line Arguments (Planned)

Cerebrus will support a small set of CLI options, for example:

- `--config <file>` – override default config file.
- `--project <name>` – select a project profile on startup.
- `--log-level <level>` – set initial log level (e.g. DEBUG, INFO, WARNING).

See `docs/developer/SETUP.md` and `docs/developer/PROJECT_STRUCTURE.md` as the runtime entrypoints solidify.

## Shutting Down

- Use the window close button or the **File → Exit** menu (if provided).
- Cerebrus should:
  - Flush logs.
  - Close any open file handles.
  - Stop any ongoing external tool processes gracefully.

If the UI becomes unresponsive, use the Windows Task Manager as a last resort, then inspect logs for root cause.
