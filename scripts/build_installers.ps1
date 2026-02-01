param(
  [Parameter(Mandatory = $false)][string]$TagVersion = "0.0.0",
  [Parameter(Mandatory = $false)][string]$OutputDir = "installer_output"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Write-Section($text) {
  Write-Host "`n== $text ==" -ForegroundColor Cyan
}

$version = $TagVersion.TrimStart('v').TrimStart('.')
if (-not $version) {
  $version = "0.0.0"
}
$displayVersion = "v.$version"

Write-Section "Freezing version to cerebrus/_frozen_version.py"
$frozenVerPath = "cerebrus/_frozen_version.py"
Set-Content -Path $frozenVerPath -Value "__version__ = `"$version`"" -Encoding UTF8

try {
  Write-Section "Preparing staging layout"
  python -m cerebrus.installers.builder --output $OutputDir
}
finally {
  if (Test-Path $frozenVerPath) {
    Remove-Item $frozenVerPath
  }
}

$resolvedOutput = Resolve-Path $OutputDir
$stagingRoot = Join-Path $resolvedOutput "Cerebrus"

Write-Section "Ensuring WiX Toolset"
$heatCmd = Get-Command heat.exe -ErrorAction SilentlyContinue
$heat = if ($heatCmd) { $heatCmd.Source } else { $null }
$candleCmd = Get-Command candle.exe -ErrorAction SilentlyContinue
$candle = if ($candleCmd) { $candleCmd.Source } else { $null }
$lightCmd = Get-Command light.exe -ErrorAction SilentlyContinue
$light = if ($lightCmd) { $lightCmd.Source } else { $null }

# If not in PATH, try standard installation location
if (-not $heat) {
  $wixBinPath = "${env:ProgramFiles(x86)}\WiX Toolset v3.11\bin"
  if (Test-Path $wixBinPath) {
    $heat = Join-Path $wixBinPath "heat.exe"
    $candle = Join-Path $wixBinPath "candle.exe"
    $light = Join-Path $wixBinPath "light.exe"
  }
  else {
    throw "WiX Toolset not found. Please install WiX Toolset v3.11 or later."
  }
}

Write-Host "Using WiX tools:"
Write-Host "  heat: $heat"
Write-Host "  candle: $candle"
Write-Host "  light: $light"


Write-Section "Generating WiX sources"
$componentsWxs = Join-Path $resolvedOutput "components.wxs"
& $heat dir $stagingRoot -dr INSTALLFOLDER -cg CerebrusComponents -sfrag -srd -var var.StagingDir -out $componentsWxs

$productWxs = @"
<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi">
  <Product Id="*" Name="Cerebrus" Language="1033" Version="$(var.ProductVersion)" Manufacturer="Cerebrus" UpgradeCode="0446F967-2C20-4EFD-AEDC-479F38A94F2F">
    <Package InstallerVersion="500" Compressed="yes" InstallScope="perMachine"/>
    <MajorUpgrade DowngradeErrorMessage="A newer version of [ProductName] is already installed."/>
    <MediaTemplate/>
    <Feature Id="FeatureMain" Title="Cerebrus" Level="1">
      <ComponentGroupRef Id="CerebrusComponents"/>
    </Feature>
    <Directory Id="TARGETDIR" Name="SourceDir">
      <Directory Id="ProgramFiles64Folder">
        <Directory Id="INSTALLFOLDER" Name="Cerebrus" />
      </Directory>
    </Directory>
  </Product>
</Wix>
"@
$productWxsPath = Join-Path $resolvedOutput "product.wxs"
Set-Content -Path $productWxsPath -Value $productWxs -Encoding UTF8

Write-Section "Building MSI"
& $candle -dStagingDir=$stagingRoot -dProductVersion=$version -out (Join-Path $resolvedOutput "") $productWxsPath $componentsWxs
& $light -ext WixUIExtension -out (Join-Path $resolvedOutput "Cerebrus-$displayVersion.msi") (Join-Path $resolvedOutput "product.wixobj") (Join-Path $resolvedOutput "components.wixobj")

Write-Section "Building Burn bootstrapper (.exe)"
$bundleWxs = @"
<?xml version="1.0" encoding="UTF-8"?>
<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi" xmlns:bal="http://schemas.microsoft.com/wix/BalExtension">
  <Bundle Name="Cerebrus" Version="$(var.ProductVersion)" Manufacturer="Cerebrus" UpgradeCode="77F1E6F2-05B4-4F98-97B4-41C1AE101A5A" Compressed="yes">
    <BootstrapperApplicationRef Id="WixStandardBootstrapperApplication.RtfLicense" />
    <Chain>
      <MsiPackage SourceFile="$(var.MsiPath)" DisplayInternalUI="yes" Vital="yes" />
    </Chain>
  </Bundle>
</Wix>
"@
$bundleWxsPath = Join-Path $resolvedOutput "bundle.wxs"
Set-Content -Path $bundleWxsPath -Value $bundleWxs -Encoding UTF8

& $candle -ext WixBalExtension -dProductVersion=$version -dMsiPath="$(Join-Path $resolvedOutput "Cerebrus-$displayVersion.msi")" -out (Join-Path $resolvedOutput "") $bundleWxsPath
& $light -ext WixBalExtension -out (Join-Path $resolvedOutput "Cerebrus-$displayVersion.exe") (Join-Path $resolvedOutput "bundle.wixobj")

Write-Section "Artifacts"
Get-ChildItem $resolvedOutput -Filter "Cerebrus-$displayVersion.*" | ForEach-Object { Write-Host "Created $_" }
