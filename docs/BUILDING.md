# Building Cerebrus Installers

This document explains how to build Cerebrus installers using PyInstaller and Inno Setup.

## Build System Overview

Our build system uses a two-step process:

1. **PyInstaller** - Bundles Python + dependencies + code into a standalone application folder
2. **Inno Setup** - Packages the PyInstaller output into a professional Windows installer

This approach gives us:
- ✅ **Reliability**: No WiX version conflicts or complex MSI issues
- ✅ **Proper installer**: Professional Windows installer with uninstall, shortcuts, etc.
- ✅ **Portability**: Also creates a ZIP for users who prefer portable apps
- ✅ **Simplicity**: Much easier to maintain than WiX
- ✅ **CI/CD friendly**: Both tools work reliably in GitHub Actions

## Why This Approach?

We switched from WiX Toolset because:
- **Simpler**: No external tooling required beyond Python
- **More reliable**: Works consistently across environments
- **Cross-platform ready**: Easy to extend to Linux/macOS if needed
- **Better CI/CD**: No complex dependencies in GitHub Actions

## Prerequisites

- Python 3.12+
- pip
- **Inno Setup 6** (optional, but required for creating installers)
  - Download from: https://jrsoftware.org/isdl.php
  - Or install via Chocolatey: `choco install innosetup`

## Building Locally

### Quick Build

```powershell
# Install PyInstaller
python -m pip install pyinstaller

# Run the build script (creates both ZIP and installer)
./scripts/build_pyinstaller.ps1
```

This creates:
- `dist/Cerebrus/` - Standalone application folder (PyInstaller output)
- `dist/Cerebrus-<version>-win64.zip` - Portable ZIP archive
- `dist/Cerebrus-<version>-Setup.exe` - Windows installer (if Inno Setup is installed)

### Custom Build

```powershell
# Build with a specific version
./scripts/build_pyinstaller.ps1 -TagVersion "1.2.3" -OutputDir "my_dist"

# Skip installer creation (only create ZIP)
./scripts/build_pyinstaller.ps1 -SkipInstaller
```

## What Gets Bundled

The PyInstaller build includes:
- ✅ Python interpreter
- ✅ All Python dependencies (DearPyGUI, psutil, pywin32, etc.)
- ✅ All Cerebrus source code
- ✅ Resources (icons, etc.)
- ✅ Binaries folder (if present)

## Distribution

The build creates two distribution formats:

### Windows Installer (Recommended for most users)
- **File**: `Cerebrus-<version>-Setup.exe`
- Professional installer with Start Menu shortcuts
- Includes uninstaller
- Can be installed to Program Files
- Requires admin rights to install

### Portable ZIP (For advanced users)
- **File**: `Cerebrus-<version>-win64.zip`
- Extract and run anywhere
- No installation required
- No admin rights needed
- Good for USB drives or restricted environments

## CI/CD Process

The GitHub Actions workflow automatically:
1. Installs Python, PyInstaller, and Inno Setup
2. Runs `build_pyinstaller.ps1`
3. Creates both ZIP and installer
4. Uploads both as release artifacts
5. Attaches both to the GitHub release

## Customization

To modify the build process, edit:
- `scripts/cerebrus.spec` - PyInstaller configuration (what gets bundled)
- `scripts/cerebrus.iss` - Inno Setup configuration (installer behavior, shortcuts, etc.)
- `scripts/build_pyinstaller.ps1` - Build orchestration script

## Troubleshooting

### Missing Dependencies

If PyInstaller misses a dependency, add it to `hiddenimports` in `cerebrus.spec`:

```python
hiddenimports = [
    'dearpygui',
    'your_missing_module',  # Add here
]
```

### Missing Data Files

If resources aren't bundled, check the `datas` section in `cerebrus.spec`.

### Build Fails

1. Ensure all dependencies are installed: `pip install -r requirements.txt`
2. Try cleaning previous builds: Remove `build/` and `dist/` folders
3. Check Python version: Must be 3.12+
