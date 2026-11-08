# Build real Windows executables and a portable release bundle.
param([string]$PythonPath = "", [switch]$SkipTests)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if (-not $PythonPath) { $PythonPath = Join-Path $ProjectRoot ".venv\Scripts\python.exe" }
if (-not (Test-Path -LiteralPath $PythonPath)) { throw "Python not found: $PythonPath" }
Push-Location $ProjectRoot
try {
    if (-not $SkipTests) {
        & $PythonPath -m pytest tests -q
        if ($LASTEXITCODE -ne 0) { throw "Tests failed; build stopped." }
    }
    & $PythonPath -m PyInstaller --noconfirm (Join-Path $PSScriptRoot "DDLAssistant.spec")
    if ($LASTEXITCODE -ne 0) { throw "GUI packaging failed." }
    & $PythonPath -m PyInstaller --noconfirm (Join-Path $PSScriptRoot "DDLAssistantReminder.spec")
    if ($LASTEXITCODE -ne 0) { throw "Reminder packaging failed." }
    & $PythonPath (Join-Path $PSScriptRoot "check_executables.py")
    if ($LASTEXITCODE -ne 0) { throw "EXE startup verification failed; release stopped." }
    foreach ($File in @("install.ps1", "install.cmd", "install_reminder.ps1")) {
        Copy-Item -LiteralPath (Join-Path $PSScriptRoot $File) -Destination (Join-Path $ProjectRoot "dist\$File") -Force
    }
    foreach ($File in @("README.md", "LICENSE")) {
        Copy-Item -LiteralPath (Join-Path $ProjectRoot $File) -Destination (Join-Path $ProjectRoot "dist\$File") -Force
    }
    $DocsDirectory = Join-Path $ProjectRoot "dist\docs"
    New-Item -ItemType Directory -Path $DocsDirectory -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $ProjectRoot "docs\acceptance.md") -Destination (Join-Path $DocsDirectory "acceptance.md") -Force
    $Outputs = @("DDLAssistant.exe", "DDLAssistantReminder.exe", "install.ps1", "install.cmd", "install_reminder.ps1", "README.md", "LICENSE", "docs\acceptance.md")
    foreach ($File in $Outputs) {
        if (-not (Test-Path -LiteralPath (Join-Path $ProjectRoot "dist\$File"))) { throw "Missing output: $File" }
    }
    $Checksums = foreach ($File in $Outputs) {
        $Hash = Get-FileHash -Algorithm SHA256 -LiteralPath (Join-Path $ProjectRoot "dist\$File")
        "$($Hash.Hash)  $File"
    }
    $Checksums | Set-Content -LiteralPath (Join-Path $ProjectRoot "dist\SHA256SUMS.txt") -Encoding UTF8
    # Include the directory itself so the README's relative docs link survives ZIP extraction.
    $ReleasePaths = @($Outputs | Where-Object { $_ -ne "docs\acceptance.md" }) + @("SHA256SUMS.txt", "docs")
    $ReleasePaths = $ReleasePaths | ForEach-Object { Join-Path $ProjectRoot "dist\$_" }
    Compress-Archive -LiteralPath $ReleasePaths -DestinationPath (Join-Path $ProjectRoot "dist\DDLAssistant-Windows-x64.zip") -Force
    Write-Host "Build complete: $ProjectRoot\dist"
    Get-ChildItem -LiteralPath (Join-Path $ProjectRoot "dist") | Select-Object Name, Length
} finally { Pop-Location }
