# Install/update the distribution for this user. No elevation and no data deletion.
param([string]$InstallDirectory = "")
$ErrorActionPreference = "Stop"
if (-not $InstallDirectory) { $InstallDirectory = Join-Path $env:LOCALAPPDATA "DDLAssistant\bin" }
New-Item -ItemType Directory -Path $InstallDirectory -Force | Out-Null
$TargetRoot = [IO.Path]::GetFullPath($InstallDirectory).TrimEnd('\')
$SourceRoot = [IO.Path]::GetFullPath($PSScriptRoot).TrimEnd('\')
foreach ($File in @("DDLAssistant.exe", "DDLAssistantReminder.exe", "install_reminder.ps1", "README.md", "LICENSE")) {
    $Source = Join-Path $PSScriptRoot $File
    if (-not (Test-Path -LiteralPath $Source)) { throw "Missing release file: $Source" }
    if ($TargetRoot -ne $SourceRoot) {
        Copy-Item -LiteralPath $Source -Destination (Join-Path $InstallDirectory $File) -Force
    }
}
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File (Join-Path $InstallDirectory "install_reminder.ps1") -ExeDirectory $InstallDirectory
if ($LASTEXITCODE -ne 0) { throw "Reminder setup failed; see LOCALAPPDATA\DDLAssistant\logs\install.log" }
Write-Host "Installed: $InstallDirectory. Start Menu: DDL Assistant"
Start-Process -FilePath (Join-Path $InstallDirectory "DDLAssistant.exe") -WorkingDirectory $InstallDirectory
