"""Utility to assemble a distributable Windows installer bundle."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Iterable


def build_windows_installer(output_dir: Path | None = None) -> Path:
    """Create a zipped installer bundle and return the archive path.

    The bundle is structured for a Windows user-facing delivery:
    - `app/` holds the Cerebrus package, binaries, and metadata.
    - `launch_cerebrus.bat` provides a simple entry point.
    - `install.ps1` provides dependency validation and upgrade routines.
    - `INSTALLER_CONTENTS.txt` records what was bundled.
    """

    repo_root = Path(__file__).resolve().parent.parent.parent
    app_source = repo_root / "cerebrus"
    binaries_source = repo_root / "Binaries"
    requirements_file = repo_root / "requirements.txt"

    if output_dir is None:
        output_dir = repo_root / "installer_output"

    staging_root = output_dir / "Cerebrus"
    app_target = staging_root / "app"

    if staging_root.exists():
        shutil.rmtree(staging_root)

    app_target.mkdir(parents=True, exist_ok=True)

    shutil.copytree(app_source, app_target / "cerebrus")

    bundled_items: list[Path | str] = [app_target / "cerebrus"]

    if binaries_source.exists():
        shutil.copytree(binaries_source, app_target / "Binaries")
        bundled_items.append(app_target / "Binaries")

    shutil.copy(requirements_file, app_target / requirements_file.name)
    bundled_items.append(requirements_file.name)

    _write_launcher(staging_root)
    _write_bootstrapper(staging_root)
    _write_manifest(staging_root, bundled_items)

    archive_path = output_dir / "Cerebrus"
    if archive_path.with_suffix(".zip").exists():
        archive_path.with_suffix(".zip").unlink()

    archive_file = shutil.make_archive(str(archive_path), "zip", staging_root)
    return Path(archive_file)


def _write_launcher(staging_root: Path) -> None:
    launcher_path = staging_root / "launch_cerebrus.bat"
    launcher_content = """@echo off
setlocal
set BASE_DIR=%~dp0
set APP_DIR=%BASE_DIR%app
set PY_EXE=%APP_DIR%\\python\\python.exe

if not exist "%PY_EXE%" (
    echo No bundled Python found. Please place a Python 3.11+ build in "%APP_DIR%\\python".
    exit /b 1
)

"%PY_EXE%" -m pip install --upgrade pip --quiet
"%PY_EXE%" -m pip install -r "%APP_DIR%\\requirements.txt" --quiet
"%PY_EXE%" -m cerebrus
"""
    launcher_path.write_text(launcher_content)


def _write_bootstrapper(staging_root: Path) -> None:
    """Write a bootstrapper that validates and installs dependencies.

    The bootstrapper is designed for Windows end-users that may not have
    Python or the Android platform tools available. It attempts to upgrade
    dependencies in-place when they are found and falls back to
    winget-provided installers when they are missing.
    """

    bootstrap_script = staging_root / "install.ps1"
    bootstrap_cmd = staging_root / "install.cmd"

    bootstrap_script.write_text(
        """param(
    [string]$Destination = "$env:ProgramFiles\\Cerebrus"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Write-Section($message) {
    Write-Host "`n==== $message ====" -ForegroundColor Cyan
}

function Ensure-WingetAvailable {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget is required to bootstrap dependencies. Install the latest App Installer from the Microsoft Store."
    }
}

function Ensure-Python {
    Write-Section "Checking Python"
    $python = Get-Command py -ErrorAction SilentlyContinue
    if (-not $python) {
        $python = Get-Command python -ErrorAction SilentlyContinue
    }

    if ($python) {
        $version = & $python.Source -c "import sys; print('{}.{}'.format(*sys.version_info[:2]))" 2>$null
        if ($version -and [version]$version -ge [version]"3.11") {
            Write-Host "Found Python $version" -ForegroundColor Green
            & $python.Source -m pip install --upgrade pip --quiet
            return $python.Source
        }
        Write-Host "Python found but below 3.11; upgrading via winget..." -ForegroundColor Yellow
    } else {
        Write-Host "Python not found; installing via winget..." -ForegroundColor Yellow
    }

    Ensure-WingetAvailable
    winget install --id Python.Python.3.11 --exact --silent --accept-package-agreements --accept-source-agreements
    $python = Get-Command py -ErrorAction SilentlyContinue
    if (-not $python) {
        $python = Get-Command python -ErrorAction SilentlyContinue
    }
    if (-not $python) {
        throw "Python installation did not succeed."
    }
    return $python.Source
}

function Ensure-AdbTools {
    Write-Section "Checking Android platform tools (adb)"
    $adb = Get-Command adb -ErrorAction SilentlyContinue
    if ($adb) {
        Write-Host "adb located at $($adb.Source)" -ForegroundColor Green
        return
    }

    Write-Host "adb not found; installing platform tools via winget..." -ForegroundColor Yellow
    Ensure-WingetAvailable
    winget install --id Google.AndroidSDK.PlatformTools --exact --silent --accept-package-agreements --accept-source-agreements
}

function Install-Cerebrus($pythonPath) {
    Write-Section "Installing Cerebrus into $Destination"
    $staging = "$PSScriptRoot\\app"
    if (-not (Test-Path $staging)) {
        throw "Staging directory '$staging' missing from installer payload."
    }

    if (Test-Path $Destination) {
        Write-Host "Existing install detected. Replacing contents..." -ForegroundColor Yellow
        Remove-Item -Path $Destination -Recurse -Force
    }
    Copy-Item -Path $staging -Destination $Destination -Recurse

    & $pythonPath -m pip install -r "$Destination\\requirements.txt" --quiet
    Write-Host "Cerebrus installed to $Destination" -ForegroundColor Green
}

try {
    $pythonPath = Ensure-Python
    Ensure-AdbTools
    Install-Cerebrus -pythonPath $pythonPath
    Write-Host "Installation complete. Launch using launch_cerebrus.bat inside $Destination" -ForegroundColor Green
    exit 0
}
catch {
    Write-Error $_
    exit 1
}
"""
    )

    bootstrap_cmd.write_text(
        """@echo off
setlocal
set SCRIPT_DIR=%~dp0
powershell -ExecutionPolicy Bypass -File "%SCRIPT_DIR%install.ps1" %*
"""
    )


def _write_manifest(staging_root: Path, items: Iterable[str | Path]) -> None:
    manifest_path = staging_root / "INSTALLER_CONTENTS.txt"
    entries = []
    for item in items:
        path = Path(item)
        entries.append(f"- {path.as_posix()}")

    manifest_lines = [
        "Cerebrus installer bundle contents:",
        "This bundle is intended for Windows distribution.",
        "Included items:",
        *entries,
        "",
        "Use install.cmd to validate Python and adb prerequisites with winget before launching.",
        "launch_cerebrus.bat expects a Python 3.11+ interpreter to be available in app/python/.",
    ]
    manifest_path.write_text("\n".join(manifest_lines))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Cerebrus Windows installer bundle."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Directory where the installer bundle should be created (defaults to installer_output/).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    archive_path = build_windows_installer(args.output)
    print(f"Installer archive created at: {archive_path}")


if __name__ == "__main__":
    main()
