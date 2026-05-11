# Project Structure

> **⚠️ AUTO-GENERATED/UPDATED FILE**
> This file is maintained by AI Agents. Do not manually edit unless strictly necessary.
> AI Agents: When creating or deleting files/directories, YOU MUST update this file to reflect the changes immediately.

## Directory Layout

```text
cerebrus/                   # Main package directory
  __init__.py
  __main__.py               # Entry point
  _version.py               # Version definition
  
  cache/                    # Cache management
    __init__.py
    manager.py              # Cache logic

  config/                   # Configuration management
    __init__.py
    defaults.py             # Default settings
    loader.py               # Config loading logic
    models.py               # Pydantic data models

  core/                     # Core application logic
    __init__.py
    devices.py              # Device management and ADB interaction
    plugins.py              # Plugin manager logic
    preflight.py            # Startup checks
    profile.py              # User profile management
    setup.py                # Environment setup
    updater.py              # Auto-update logic

  installers/               # Installer generation logic
    __init__.py
    builder.py              # Logic to build installers (Inno Setup)

  plugins/                  # Extensible plugin system
    README.md               # Plugin system overview and documentation index
    TESTING.md              # Plugin test coverage plan
    profiling.md            # Profiling plugin user/developer notes
    aws_secrets.md          # AWS Secrets plugin user/developer notes
    s3_uploader.md          # S3 Uploader plugin user/developer notes
    aws_secrets.py          # AWS credential management
    profiling_plugin.py     # Main profiling workflow plugin
    s3_uploader.py          # S3 report upload logic
    resources/              # Plugin tooltip resources

  resources/                # Static assets
    Titan.json              # Theme variant
    icon.png                # Main app icon (large)
    icon128x128.ico         # Windows Icon resources...
    icon16x16.ico
    icon256x256.ico
    icon32x32.ico
    icon64x64.ico
    user_guide.html         # Embeddable user guide

  tools/                    # Standalone tools and wrappers
    __init__.py
    adb.py                  # ADB wrapper
    log_to_html.py          # Log conversion tool (Text -> HTML)
    memreport_to_html.py    # Memreport HTML generator entry
    memreport/              # Memreport tool implementation (See MEMREPORT_TOOL_REFERENCE.md)
      __init__.py
      main.py               # Orchestration
      tabs/                 # Report tab implementations (class_stats, texture_stats, etc.)
      templates/            # HTML templates for report generation

  ui/                       # User Interface (Dear PyGui)
    __init__.py
    app.py                  # Main UI entry point / definitions
    components/             # Reusable UI components
      __init__.py
      dialogs/              # Dialog implementations
        app/
        files/
        profile/
      panels/               # Panel implementations
        device/
        logs_panel/
        profiling/
      file_manager.py
      layout.py
      menu.py
      palette_manager.py
      shared.py
      ui_config.py          # UI Configuration logic
    resources/              # UI specific resources
      AppColorPalettes/     # JSON Theme definitions
      layouts/              # JSON Layout configurations
    state.py                # UI State management
    themes.py               # UI Theming

docs/                       # Documentation
  ARCHITECTURE_OVERVIEW.md  # High-level architecture
  AUTO_UPDATE.md            # Updater documentation
  BUILDING.md               # Build instructions
  CSVTOOLS_REFERENCE.md     # Reference for CSV tools
  MEMREPORT_TOOL_REFERENCE.md # Reference for MemReport tool
  PERFREPORTTOOL_REFERENCE.md # Reference for PerfReport tool
  ROADMAP.md                # Project roadmap
  output_filename_guide.md  # Naming convention guide
  user_guide.md             # End-user documentation
  
  developer/                # Developer internals & guides
    LOGGING_AND_ERROR_HANDLING.md
    PROJECT_STRUCTURE.md    # This file
    SETUP.md                # Environment setup guide
    TESTING_GUIDE.md        # Testing strategies
    TOOL_WRAPPER_DESIGN.md  # Design patterns for tool wrappers
    
  technical/                # Technical implementation details
    html_viewer_implementation.md
    native_file_dialog_implementation.md

  installer/                # Installer specifications
    OVERVIEW.md
    WINDOWS_INSTALLER_SPEC.md

  ui/                       # UI/UX specifications & patterns
    IMGUI_LAYOUT_GUIDELINES.md
    THEME_SPECIFICATION.md
    WIDGET_PATTERNS.md

  user/                     # Topic-specific user guides
    DEVICE_CAPTURE_WORKFLOWS.md
    INSTALLATION.md
    REPORTING_AND_ANALYSIS.md
    RUNNING_CEREBRUS.md
    TROUBLESHOOTING.md

tests/                      # Automated tests
  cache/
  config/
  core/
    test_plugin_manager.py  # Plugin manager tests
  tools/
    test_memreport_naming.py # Memreport naming tests
  ui/
```

## Module Descriptions

- **`core`**: Contains the business logic of the application. It handles device application state, profile management, and environment prerequisites. It should be framework-agnostic where possible.
- **`tools`**: Contains self-contained tools or wrappers around external executables (like ADB). These should be usable independently of the UI.
- **`ui`**: Contains all presentation logic. It uses Dear PyGui for rendering. It observes state from `core` and calls into `core` or `tools` to perform actions.
- **`config`**: Defines the data schema for application settings and handles loading/saving to disk.
- **`cache`**: Manages temporary data and caching to improve performance or persistence across sessions.
- **`installers`**: logic for packaging the application for distribution.
- **`docs`**: Comprehensive documentation split by audience (Developer vs User).
- **`cerebrus/plugins/*.md`**: Plugin-specific documentation. Do not move detailed AWS/S3 plugin docs back into `docs/`; link to the plugin-local files instead.

## Maintenance

This file must be kept in sync with the file system.
**AI Agents**: When you add a new file or directory, add it to the tree above. When you rename or delete, reflect that here.
