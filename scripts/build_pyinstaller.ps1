param(
    [Parameter(Mandatory = $false)][string]$TagVersion = "0.0.0",
    [Parameter(Mandatory = $false)][string]$OutputDir = "dist",
    [Parameter(Mandatory = $false)][switch]$SkipInstaller = $false
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Section($text) {
    Write-Host "`n== $text ==" -ForegroundColor Cyan
}

$repoRoot = Split-Path $PSScriptRoot -Parent
$version = $TagVersion.TrimStart('v')
if (-not $version) {
    $version = "0.0.0"
}

Write-Section "Building Cerebrus v$version"
Write-Host "Output Directory: $OutputDir"

# Install PyInstaller if not already available
Write-Section "Ensuring PyInstaller is available"
python -m pip install pyinstaller --quiet

# Clean previous builds
Write-Section "Cleaning previous builds"
Push-Location $repoRoot
try {
    if (Test-Path "build") {
        Remove-Item -Path "build" -Recurse -Force
    }
    if (Test-Path "dist") {
        Remove-Item -Path "dist" -Recurse -Force  
    }
    
    # Run PyInstaller
    Write-Section "Running PyInstaller"
    $specFile = Join-Path $PSScriptRoot "cerebrus.spec"
    python -m PyInstaller $specFile --clean --noconfirm
    
    # Verify build output
    $distFolder = Join-Path $repoRoot "dist\Cerebrus"
    if (-not (Test-Path $distFolder)) {
        throw "Build output not found at $distFolder"
    }
    
    Write-Host "PyInstaller build successful!" -ForegroundColor Green
    Get-ChildItem $distFolder | ForEach-Object {
        Write-Host "  - $($_.Name)"
    }
    
    # Create output directory
    if (-not (Test-Path $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir | Out-Null
    }
    
    # Create ZIP archive
    Write-Section "Creating ZIP archive"
    $zipName = "Cerebrus-$version-win64.zip"
    $zipPath = Join-Path $OutputDir $zipName
    
    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }
    
    Compress-Archive -Path "$distFolder\*" -DestinationPath $zipPath
    Write-Host "Created: $zipPath" -ForegroundColor Green
    Write-Host "Size: $([Math]::Round((Get-Item $zipPath).Length / 1MB, 2)) MB"
    
    # Create Windows Installer using Inno Setup
    if (-not $SkipInstaller) {
        Write-Section "Creating Windows Installer with Inno Setup"
        
        # Check for Inno Setup
        $iscc = $null
        $isccPaths = @(
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "${env:ProgramFiles}\Inno Setup 6\ISCC.exe",
            "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
        )
        
        foreach ($path in $isccPaths) {
            if (Test-Path $path) {
                $iscc = $path
                break
            }
        }
        
        # Try to find in PATH
        if (-not $iscc) {
            $isccCmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
            if ($isccCmd) {
                $iscc = $isccCmd.Source
            }
        }
        
        if (-not $iscc) {
            Write-Host "Inno Setup not found. Installer will not be created." -ForegroundColor Yellow
            Write-Host "Install Inno Setup from: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
            Write-Host "Or via Chocolatey: choco install innosetup" -ForegroundColor Yellow
        }
        else {
            Write-Host "Using Inno Setup: $iscc"
            
            # Set version environment variable for Inno Setup
            $env:CEREBRUS_VERSION = $version
            
            # Run Inno Setup compiler
            $issFile = Join-Path $PSScriptRoot "cerebrus.iss"
            & $iscc $issFile
            
            $installerName = "Cerebrus-$version-Setup.exe"
            $installerPath = Join-Path $OutputDir $installerName
            
            if (Test-Path $installerPath) {
                Write-Host "Created: $installerPath" -ForegroundColor Green
                Write-Host "Size: $([Math]::Round((Get-Item $installerPath).Length / 1MB, 2)) MB"
            }
            else {
                Write-Host "Warning: Installer was not created at expected path: $installerPath" -ForegroundColor Yellow
            }
        }
    }
    
    Write-Section "Build Complete!"
    Write-Host "`nArtifacts created:" -ForegroundColor Cyan
    Get-ChildItem $OutputDir -Filter "Cerebrus-$version*" | ForEach-Object {
        Write-Host "  [+] $($_.Name) ($([Math]::Round($_.Length / 1MB, 2)) MB)" -ForegroundColor Green
    }
    
}
finally {
    Pop-Location
}
