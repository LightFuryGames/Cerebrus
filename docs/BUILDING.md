# Building Cerebrus Installers

This document explains how to build Cerebrus installers using PyInstaller and Inno Setup.

## Publisher Metadata

Official builds must identify **LeagueX Gaming Private Limited** as the Company Name and Publisher.

Configured in:

- `scripts/cerebrus.spec`: Windows executable version metadata.
- `scripts/cerebrus.iss`: Inno Setup publisher metadata.

## Build System Overview

The build has two steps:

1. **PyInstaller** bundles Python, dependencies, source code, resources, and binaries into a standalone application folder.
2. **Inno Setup** packages that folder into a Windows installer.

The build also creates a portable ZIP for users who do not want an installer.

## Prerequisites

- Python 3.12+
- pip
- Inno Setup 6 for installer creation

Install Inno Setup manually or with Chocolatey:

```powershell
choco install innosetup
```

## Quick Build

```powershell
python -m pip install pyinstaller
./scripts/build_pyinstaller.ps1
```

Outputs:

- `dist/Cerebrus/`
- `dist/Cerebrus-<version>-win64.zip`
- `dist/Cerebrus-<version>-Setup.exe` when Inno Setup is available

## Custom Build

```powershell
./scripts/build_pyinstaller.ps1 -TagVersion "1.2.3" -OutputDir "my_dist"
./scripts/build_pyinstaller.ps1 -SkipInstaller
```

## What Gets Bundled

The PyInstaller build should include:

- Python interpreter.
- Python dependencies, including Dear PyGui, psutil, pywin32, requests, boto3, and botocore.
- All Cerebrus source code.
- `cerebrus/resources` files such as icons and `user_guide.html`.
- `cerebrus/ui/resources` files such as themes, layouts, and tooltips.
- `cerebrus/plugins/resources` files such as AWS/S3 plugin tooltip JSON.
- `Binaries/` folder contents when present.

Plugin resources are important. `scripts/cerebrus.spec` bundles `cerebrus/plugins/resources/*.json`; if that rule is removed or broken, the AWS Secrets and S3 Uploader plugin help buttons may be empty in the installed app.

## Distribution

### Windows Installer

- File: `Cerebrus-<version>-Setup.exe`
- Adds Start Menu shortcuts.
- Includes an uninstaller.
- Can install to Program Files.

### Portable ZIP

- File: `Cerebrus-<version>-win64.zip`
- Extract and run without installing.
- Useful for restricted environments.

## CI/CD Process

The GitHub Actions release workflow:

1. Installs Python, PyInstaller, dependencies, and Inno Setup.
2. Runs `scripts/build_pyinstaller.ps1`.
3. Creates ZIP and installer artifacts.
4. Uploads both artifacts.
5. Attaches both files to the GitHub release.

## Customization

Edit these files when changing build behavior:

- `scripts/cerebrus.spec`: PyInstaller collection rules, hidden imports, resources, and version info.
- `scripts/cerebrus.iss`: Installer behavior and metadata.
- `scripts/build_pyinstaller.ps1`: Build orchestration.

## Troubleshooting

### Missing Python Dependency

If PyInstaller misses a dependency, add it to `hiddenimports` in `scripts/cerebrus.spec`.

```python
hiddenimports = [
    "dearpygui",
    "your_missing_module",
]
```

### Missing Data Files

If icons, UI JSON, plugin tooltips, or other resources are missing, check the `datas` section in `scripts/cerebrus.spec`.

Required resource roots:

- `cerebrus/resources`
- `cerebrus/ui/resources`
- `cerebrus/plugins/resources`

### Build Fails

1. Install dependencies: `pip install -r requirements.txt`
2. Remove old `build/` and `dist/` folders.
3. Confirm Python is 3.12+.
4. Re-run `./scripts/build_pyinstaller.ps1`.
