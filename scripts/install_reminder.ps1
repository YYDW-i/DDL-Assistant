# Current-user scheduler: interactive login + independent 15 minute checks.
param(
    [string]$ExeDirectory = "",
    [switch]$Uninstall,
    [switch]$Test,
    [switch]$TestToast,
    [string]$ExportXml = ""
)
$ErrorActionPreference = "Stop"
$Sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value
$TaskName = "DDL Assistant Reminder-$Sid"
$DataRoot = Join-Path $env:LOCALAPPDATA "DDLAssistant"
$LogRoot = Join-Path $DataRoot "logs"
New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
$LogPath = Join-Path $LogRoot "install.log"

try {
    if ($Uninstall) {
        $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($Task) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
        "Reminder task removed. User data preserved." | Tee-Object -FilePath $LogPath
        exit 0
    }
    if (-not $ExeDirectory) {
        if (Test-Path -LiteralPath (Join-Path $PSScriptRoot "DDLAssistantReminder.exe")) { $ExeDirectory = $PSScriptRoot }
    }
    if ($ExeDirectory) {
        $ReminderExe = Join-Path $ExeDirectory "DDLAssistantReminder.exe"
        $GuiExe = Join-Path $ExeDirectory "DDLAssistant.exe"
        $ReminderArgs = ""
        $Working = $ExeDirectory
        $IdentityArgs = @("--register-identity")
    } else {
        $Working = Split-Path -Parent $PSScriptRoot
        $ReminderExe = Join-Path $Working ".venv\Scripts\pythonw.exe"
        $GuiExe = Join-Path $Working ".venv\Scripts\python.exe"
        $ReminderArgs = '-m app.reminder'
        $IdentityArgs = @((Join-Path $Working "launcher.py"), "--register-identity")
    }
    if (-not (Test-Path -LiteralPath $ReminderExe)) { throw "Reminder executable not found: $ReminderExe" }
    if (-not (Test-Path -LiteralPath $GuiExe)) { throw "GUI executable not found: $GuiExe" }
    if ($Test -or $TestToast) {
        $Mode = if ($TestToast) { "--test-toast" } else { "--dry-run" }
        $ArgsText = ("$ReminderArgs $Mode").Trim()
        $Process = Start-Process -FilePath $ReminderExe -ArgumentList $ArgsText -WorkingDirectory $Working -WindowStyle Hidden -Wait -PassThru
        if ($Process.ExitCode -ne 0) { throw "Reminder test failed (exit $($Process.ExitCode)); see logs/reminder.log" }
        Write-Host "Check finished; see $DataRoot\logs\reminder.log"
        exit 0
    }
    $CommandXml = [System.Security.SecurityElement]::Escape($ReminderExe)
    $ArgumentsXml = [System.Security.SecurityElement]::Escape($ReminderArgs)
    $WorkingXml = [System.Security.SecurityElement]::Escape($Working)
    $StartBoundary = (Get-Date).AddMinutes(1).ToString("yyyy-MM-ddTHH:mm:ss")
    $Xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo><Description>DDL Assistant reminders: login catch-up and 15 minute checks.</Description></RegistrationInfo>
  <Triggers>
    <LogonTrigger><Enabled>true</Enabled><UserId>$Sid</UserId></LogonTrigger>
    <TimeTrigger>
      <Repetition><Interval>PT15M</Interval><StopAtDurationEnd>false</StopAtDurationEnd></Repetition>
      <StartBoundary>$StartBoundary</StartBoundary><Enabled>true</Enabled>
    </TimeTrigger>
  </Triggers>
  <Principals><Principal id="Author"><UserId>$Sid</UserId><LogonType>InteractiveToken</LogonType><RunLevel>LeastPrivilege</RunLevel></Principal></Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries><StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable><Enabled>true</Enabled><ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
  </Settings>
  <Actions Context="Author"><Exec><Command>$CommandXml</Command><Arguments>$ArgumentsXml</Arguments><WorkingDirectory>$WorkingXml</WorkingDirectory></Exec></Actions>
</Task>
"@
    if ($ExportXml) {
        $Xml | Set-Content -LiteralPath $ExportXml -Encoding Unicode
        exit 0
    }
    # Wait for identity registration before running the scheduled notifier.
    if ($ExeDirectory) {
        $IdentityProcess = Start-Process -FilePath $GuiExe -ArgumentList $IdentityArgs -WindowStyle Hidden -Wait -PassThru
        if ($IdentityProcess.ExitCode -ne 0) { throw "Notification identity registration failed." }
    } else {
        & $GuiExe @IdentityArgs
        if ($LASTEXITCODE -ne 0) { throw "Notification identity registration failed." }
    }
    $XmlPath = Join-Path $DataRoot "reminder-task.xml"
    $Xml | Set-Content -LiteralPath $XmlPath -Encoding Unicode
    & schtasks.exe /Create /TN $TaskName /XML $XmlPath /F
    if ($LASTEXITCODE -ne 0) { throw "Task registration failed: $LASTEXITCODE" }
    & schtasks.exe /Run /TN $TaskName
    if ($LASTEXITCODE -ne 0) { throw "Task start failed: $LASTEXITCODE" }
    "$(Get-Date -Format s) Reminder enabled: $TaskName" | Tee-Object -FilePath $LogPath
} catch {
    "$(Get-Date -Format s) FAILED: $_" | Tee-Object -FilePath $LogPath
    Write-Error $_
    exit 1
}
