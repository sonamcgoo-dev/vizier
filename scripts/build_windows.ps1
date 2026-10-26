# ---------------------------------------------------------------------------
# Build a complete, release-ready Vizier Windows bundle.
#
# Usage (from any directory):
#   powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
#   ... -SkipInstaller      # portable bundle/zip only
#   ... -SkipTests          # faster iteration (not for releases)
#   ... -SkipPrune          # keep optional Qt/Pillow/llama files (debug only)
#   ... -Python C:\Python313\python.exe
#
# Outputs:
#   dist\Vizier\                              PyInstaller onedir bundle
#   dist\Vizier-<version>-portable-x64.zip    portable archive
#   dist\installer\Vizier-Setup-<ver>-x64.exe Inno Setup installer
#   dist\SHA256SUMS-<version>.txt             checksums
# ---------------------------------------------------------------------------
[CmdletBinding()]
param(
    [string]$Python = "",
    [string]$InnoCompiler = "",
    [switch]$SkipTests,
    [switch]$SkipLint,
    [switch]$SkipPrune,
    [switch]$SkipInstaller
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

$Dist = Join-Path $Root "dist"
$Bundle = Join-Path $Dist "Vizier"
$InstallerDir = Join-Path $Dist "installer"

function Write-Step([string]$Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Red
}

function Assert-LastExit([string]$What) {
    if ($LASTEXITCODE -ne 0) {
        throw "$What failed with exit code $LASTEXITCODE."
    }
}

function Resolve-Python {
    param([string]$Requested)
    if ($Requested) {
        if (-not (Test-Path $Requested)) { throw "Python not found: $Requested" }
        return (Resolve-Path $Requested).Path
    }
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $fallback = Join-Path $env:LOCALAPPDATA "Programs\Python\Python313\python.exe"
    if (Test-Path $fallback) { return $fallback }
    throw "Python 3.10+ was not found. Pass -Python <path-to-python.exe>."
}

$PythonExe = Resolve-Python -Requested $Python
Write-Host "Using Python: $PythonExe"

$VersionText = & $PythonExe -c "import re,pathlib; t=pathlib.Path('vizier/__version__.py').read_text(encoding='utf-8'); print(re.search(r'__version__\s*=\s*[\x22\x27]([^\x22\x27]+)', t).group(1))"
Assert-LastExit "Reading the version"
$Version = $VersionText.Trim()
$Version4 = (($Version -split "\.") + @("0", "0", "0", "0"))[0..3] -join "."
Write-Host "Vizier version: $Version ($Version4)"

# ---------------------------------------------------------------------------
# 1. Quality gates
# ---------------------------------------------------------------------------
if (-not $SkipLint) {
    Write-Step "Linting with ruff"
    & $PythonExe -m ruff check vizier tests packaging scripts
    Assert-LastExit "ruff"
}

Write-Step "Byte-compiling sources"
& $PythonExe -m compileall -q vizier tests packaging scripts
Assert-LastExit "compileall"

if (-not $SkipTests) {
    Write-Step "Running the test suite"
    $previousPlatform = $env:QT_QPA_PLATFORM
    $env:QT_QPA_PLATFORM = "offscreen"
    try {
        & $PythonExe -m pytest -q
        Assert-LastExit "pytest"
    }
    finally {
        if ($null -eq $previousPlatform) { Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue }
        else { $env:QT_QPA_PLATFORM = $previousPlatform }
    }
}

# ---------------------------------------------------------------------------
# 2. Assets and version resource
# ---------------------------------------------------------------------------
Write-Step "Generating branding assets"
& $PythonExe scripts\make_assets.py
Assert-LastExit "asset generation"

Write-Step "Generating Windows version resource"
& $PythonExe scripts\make_version_info.py
Assert-LastExit "version resource generation"

# ---------------------------------------------------------------------------
# 3. PyInstaller bundle
# ---------------------------------------------------------------------------
Write-Step "Building the application bundle (PyInstaller)"
& $PythonExe -m PyInstaller --noconfirm --clean --log-level WARN packaging\windows\Vizier.spec
Assert-LastExit "PyInstaller"

foreach ($exe in @("Vizier.exe", "VizierCLI.exe", "VizierMCP.exe")) {
    $path = Join-Path $Bundle $exe
    if (-not (Test-Path $path)) { throw "Missing packaged executable: $path" }
}
if (-not (Test-Path (Join-Path $Bundle "_internal"))) {
    throw "PyInstaller bundle is missing _internal."
}

# ---------------------------------------------------------------------------
# 3b. Prune optional runtime files
# ---------------------------------------------------------------------------
if (-not $SkipPrune) {
    Write-Step "Pruning unused runtime files"
    & $PythonExe scripts\prune_bundle.py --bundle $Bundle
    Assert-LastExit "bundle prune"
}
$bundleMb = [math]::Round((Get-ChildItem $Bundle -Recurse -File | Measure-Object Length -Sum).Sum / 1MB, 1)
Write-Host "Bundle size: $bundleMb MB"

# ---------------------------------------------------------------------------
# 4. Packaged smoke tests
# ---------------------------------------------------------------------------
Write-Step "Smoke-testing the packaged CLI"
$reportedVersion = (& (Join-Path $Bundle "VizierCLI.exe") version | Select-Object -Last 1).Trim()
Assert-LastExit "VizierCLI.exe version"
if ($reportedVersion -ne $Version) {
    throw "Packaged CLI reports version '$reportedVersion', expected '$Version'."
}
& (Join-Path $Bundle "VizierCLI.exe") doctor
Assert-LastExit "VizierCLI.exe doctor"

Write-Step "Smoke-testing the packaged GUI (headless)"
$previousPlatform = $env:QT_QPA_PLATFORM
$previousSmoke = $env:VIZIER_SMOKE_TEST
$env:QT_QPA_PLATFORM = "offscreen"
$env:VIZIER_SMOKE_TEST = "1"
try {
    $gui = Start-Process -FilePath (Join-Path $Bundle "Vizier.exe") -PassThru -Wait
    if ($gui.ExitCode -ne 0) { throw "Packaged GUI exited with code $($gui.ExitCode)." }
}
finally {
    if ($null -eq $previousPlatform) { Remove-Item Env:QT_QPA_PLATFORM -ErrorAction SilentlyContinue }
    else { $env:QT_QPA_PLATFORM = $previousPlatform }
    if ($null -eq $previousSmoke) { Remove-Item Env:VIZIER_SMOKE_TEST -ErrorAction SilentlyContinue }
    else { $env:VIZIER_SMOKE_TEST = $previousSmoke }
}

Write-Step "Smoke-testing the packaged MCP server"
$mcpHelp = & (Join-Path $Bundle "VizierMCP.exe") --help 2>&1
Assert-LastExit "VizierMCP.exe --help"
if (($mcpHelp -join "`n") -notmatch "stdio") {
    throw "VizierMCP.exe --help did not mention stdio transport."
}

# ---------------------------------------------------------------------------
# 5. Portable archive and checksums
# ---------------------------------------------------------------------------
Write-Step "Creating portable archive"
$ZipPath = Join-Path $Dist "Vizier-$Version-portable-x64.zip"
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }
Compress-Archive -Path (Join-Path $Bundle "*") -DestinationPath $ZipPath -CompressionLevel Optimal
Write-Host "Wrote $ZipPath"

# ---------------------------------------------------------------------------
# 6. Installer
# ---------------------------------------------------------------------------
$InstallerPath = $null
if (-not $SkipInstaller) {
    Write-Step "Compiling the Inno Setup installer"
    if (-not $InnoCompiler) {
        $candidates = @(
            (Join-Path $env:LOCALAPPDATA "Programs\Inno\ISCC.exe"),
            (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
            (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
        )
        $InnoCompiler = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
    }
    if (-not $InnoCompiler) {
        throw "Inno Setup 6 (ISCC.exe) was not found. Install it from https://jrsoftware.org/isdl.php or pass -InnoCompiler."
    }
    New-Item -ItemType Directory -Force -Path $InstallerDir | Out-Null
    & $InnoCompiler "/Q" "/DMyAppVersion=$Version" "/DMyAppVersion4=$Version4" "packaging\windows\Vizier.iss"
    Assert-LastExit "Inno Setup"

    $InstallerPath = Join-Path $InstallerDir "Vizier-Setup-$Version-x64.exe"
    if (-not (Test-Path $InstallerPath)) {
        throw "Installer was not produced at $InstallerPath."
    }
    $installerMb = [math]::Round((Get-Item $InstallerPath).Length / 1MB, 1)
    Write-Host "Installer size: $installerMb MB"
}

# ---------------------------------------------------------------------------
# 7. Checksums + summary
# ---------------------------------------------------------------------------
Write-Step "Writing checksums"
$ChecksumPath = Join-Path $Dist "SHA256SUMS-$Version.txt"
$artifacts = @($ZipPath)
if ($InstallerPath) { $artifacts += $InstallerPath }
$lines = foreach ($artifact in $artifacts) {
    $hash = (Get-FileHash $artifact -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $(Split-Path -Leaf $artifact)"
}
$lines | Set-Content -Path $ChecksumPath -Encoding ASCII
Get-Content $ChecksumPath | ForEach-Object { Write-Host "  $_" }

$signature = Get-AuthenticodeSignature (Join-Path $Bundle "Vizier.exe")
Write-Host ""
Write-Host "Build complete." -ForegroundColor Green
Write-Host "  Version:   $Version"
Write-Host "  Bundle:    $Bundle"
Write-Host "  Portable:  $ZipPath"
if ($InstallerPath) { Write-Host "  Installer: $InstallerPath" }
Write-Host "  Checksums: $ChecksumPath"
Write-Host "  Signature: $($signature.Status) (unsigned builds are expected)"
Write-Host ""
Write-Host "Note: the installer and executables are unsigned. Windows SmartScreen may warn on first run." -ForegroundColor Yellow
