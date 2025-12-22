param(
    [switch]$Force
)

$ErrorActionPreference = "Stop"
$LogFile = "$env:TEMP\cerebrus_install_debug.txt"

function Write-Log($message) {
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMsg = "[$timestamp] [DependencyInstaller] $message"
    Write-Host $logMsg -ForegroundColor Cyan
    Add-Content -Path $LogFile -Value $logMsg
}

function Install-Python {
    Write-Log "Checking Python..."
    $python = Get-Command py -ErrorAction SilentlyContinue
    if (-not $python) { $python = Get-Command python -ErrorAction SilentlyContinue }

    if ($python) {
        $version = & $python.Source -c "import sys; print('{}.{}'.format(*sys.version_info[:2]))" 2>$null
        if ($version -and [version]$version -ge [version]"3.11") {
            Write-Log "Found Python $version. Skipping install."
            return
        }
    }

    Write-Log "Downloading Python 3.11.9 installer..."
    $installerUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $installerPath = "$env:TEMP\python-3.11.9-amd64.exe"
    
    Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath
    
    Write-Log "Installing Python 3.11.9..."
    $process = Start-Process -FilePath $installerPath -ArgumentList "/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_test=0" -Wait -PassThru
    
    if ($process.ExitCode -eq 0) {
        Write-Log "Python installation successful."
    }
    else {
        Write-Log "Python installation failed with exit code $($process.ExitCode)."
        throw "Python installation failed."
    }
}

function Install-Adb {
    Write-Log "Checking ADB..."
    if (Get-Command adb -ErrorAction SilentlyContinue) {
        Write-Log "ADB found. Skipping install."
        return
    }

    $adbInstallDir = "$env:ProgramFiles\Android\platform-tools"
    if (Test-Path "$adbInstallDir\adb.exe") {
        Write-Log "ADB found at $adbInstallDir. Updating PATH..."
        [System.Environment]::SetEnvironmentVariable("Path", $env:Path + ";$adbInstallDir", [System.EnvironmentVariableTarget]::Machine)
        $env:Path += ";$adbInstallDir"
        return
    }

    Write-Log "Downloading Android Platform Tools..."
    $url = "https://dl.google.com/android/repository/platform-tools-latest-windows.zip"
    $zipPath = "$env:TEMP\platform-tools.zip"
    
    Invoke-WebRequest -Uri $url -OutFile $zipPath
    
    Write-Log "Extracting to $adbInstallDir..."
    if (-not (Test-Path "$env:ProgramFiles\Android")) {
        New-Item -ItemType Directory -Path "$env:ProgramFiles\Android" | Out-Null
    }
    
    Expand-Archive -Path $zipPath -DestinationPath "$env:ProgramFiles\Android" -Force
    
    if (Test-Path "$adbInstallDir\adb.exe") {
        Write-Log "ADB extracted successfully."
        
        Write-Log "Adding to System PATH..."
        $currentPath = [System.Environment]::GetEnvironmentVariable("Path", [System.EnvironmentVariableTarget]::Machine)
        if ($currentPath -notlike "*$adbInstallDir*") {
            [System.Environment]::SetEnvironmentVariable("Path", $currentPath + ";$adbInstallDir", [System.EnvironmentVariableTarget]::Machine)
            $env:Path += ";$adbInstallDir"
            Write-Log "PATH updated."
        }
    }
    else {
        Write-Log "Extraction failed. adb.exe not found."
        throw "ADB installation failed."
    }
}

try {
    Write-Log "Starting dependency installation..."
    Install-Python
    Install-Adb

    function Install-DotNet6 {
        Write-Log "Checking .NET 6 Desktop Runtime..."
        $dotnetInstalled = Get-Command dotnet -ErrorAction SilentlyContinue
        $needInstall = $true

        if ($dotnetInstalled) {
            $runtimes = dotnet --list-runtimes 2>$null
            if ($runtimes -match "Microsoft.WindowsDesktop.App 6\.") {
                Write-Log ".NET 6 Desktop Runtime found. Skipping install."
                $needInstall = $false
            }
        }

        if ($needInstall) {
            Write-Log "Downloading .NET 6 Desktop Runtime..."
            # Using aka.ms link for latest 6.0 patch
            $url = "https://aka.ms/dotnet/6.0/windowsdesktop-runtime-win-x64.exe"
            $installerPath = "$env:TEMP\windowsdesktop-runtime-6.0-win-x64.exe"
        
            try {
                Invoke-WebRequest -Uri $url -OutFile $installerPath
            
                Write-Log "Installing .NET 6 Desktop Runtime..."
                $process = Start-Process -FilePath $installerPath -ArgumentList "/install", "/quiet", "/norestart" -Wait -PassThru
            
                if ($process.ExitCode -eq 0 -or $process.ExitCode -eq 3010) {
                    # 3010 is restart required
                    Write-Log ".NET 6 installation successful."
                }
                else {
                    Write-Log ".NET 6 installation failed with exit code $($process.ExitCode)."
                    throw ".NET 6 installation failed."
                }
            }
            catch {
                Write-Log "Failed to download or install .NET 6: $_"
                throw
            }
        }
    }

    function Install-DotNet8 {
        Write-Log "Checking .NET 8 Desktop Runtime..."
        $dotnetInstalled = Get-Command dotnet -ErrorAction SilentlyContinue
        $needInstall = $true

        if ($dotnetInstalled) {
            $runtimes = dotnet --list-runtimes 2>$null
            if ($runtimes -match "Microsoft.WindowsDesktop.App 8\.") {
                Write-Log ".NET 8 Desktop Runtime found. Skipping install."
                $needInstall = $false
            }
        }

        if ($needInstall) {
            Write-Log "Downloading .NET 8 Desktop Runtime..."
            # Using aka.ms link for latest 8.0 patch
            $url = "https://aka.ms/dotnet/8.0/windowsdesktop-runtime-win-x64.exe"
            $installerPath = "$env:TEMP\windowsdesktop-runtime-8.0-win-x64.exe"
        
            try {
                Invoke-WebRequest -Uri $url -OutFile $installerPath
            
                Write-Log "Installing .NET 8 Desktop Runtime..."
                $process = Start-Process -FilePath $installerPath -ArgumentList "/install", "/quiet", "/norestart" -Wait -PassThru
            
                if ($process.ExitCode -eq 0 -or $process.ExitCode -eq 3010) {
                    Write-Log ".NET 8 installation successful."
                }
                else {
                    Write-Log ".NET 8 installation failed with exit code $($process.ExitCode)."
                    throw ".NET 8 installation failed."
                }
            }
            catch {
                Write-Log "Failed to download or install .NET 8: $_"
                throw
            }
        }
    }

    Install-DotNet6
    Install-DotNet8
    Write-Log "All dependencies installed successfully."
    exit 0
}
catch {
    Write-Log "Error: $_"
    exit 1
}
