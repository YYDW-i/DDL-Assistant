# 安装/卸载 DDL Assistant 后台提醒的 Windows 计划任务。
# 用法：
#   安装：powershell -ExecutionPolicy Bypass -File scripts\install_reminder.ps1
#   卸载：powershell -ExecutionPolicy Bypass -File scripts\install_reminder.ps1 -Uninstall
#   测试：powershell -ExecutionPolicy Bypass -File scripts\install_reminder.ps1 -Test

param(
    [switch]$Uninstall,
    [switch]$Test
)

$ErrorActionPreference = "Stop"
$TaskName = "DDL Assistant Reminder"

# 项目根目录（脚本在 scripts/ 下）
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
}

if ($Uninstall) {
    Write-Host "正在删除计划任务 $TaskName ..."
    schtasks /Delete /TN $TaskName /F 2>$null
    Write-Host "已删除。"
    exit 0
}

if ($Test) {
    Write-Host "立即运行一次提醒脚本（dry-run）..."
    & (Join-Path $ProjectRoot ".venv\Scripts\python.exe") -m app.reminder --dry-run
    exit 0
}

if (-not (Test-Path $PythonExe)) {
    Write-Error "未找到虚拟环境 Python：$PythonExe，请先创建 .venv 并安装依赖。"
    exit 1
}

Write-Host "Python: $PythonExe"
Write-Host "项目根: $ProjectRoot"

# 先删除旧任务（若存在）
schtasks /Delete /TN $TaskName /F 2>$null

# 用 XML 定义任务，最稳妥：登录时触发 + 每 15 分钟重复一次，无限持续
$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>DDL Assistant 后台提醒：每 15 分钟检查一次，登录时补推错过的通知。</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <Repetition>
        <Interval>PT15M</Interval>
        <Duration>P9999D</Duration>
        <StopAtDurationEnd>false</StopAtDurationEnd>
      </Repetition>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT10M</ExecutionTimeLimit>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>$($PythonExe -replace '\\','\\')</Command>
      <Arguments>-m app.reminder</Arguments>
      <WorkingDirectory>$($ProjectRoot -replace '\\','\\')</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

$xmlPath = Join-Path $env:TEMP "ddl_assistant_task.xml"
$xml | Out-File -FilePath $xmlPath -Encoding Unicode

Write-Host "注册计划任务..."
schtasks /Create /TN $TaskName /XML $xmlPath /F
if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ 计划任务已安装。"
    Write-Host "   - 每次登录时自动运行，并每 15 分钟重复检查"
    Write-Host "   - 关机/休眠期间错过的提醒，下次登录会自动补推"
    Write-Host "   - 查看任务：schtasks /Query /TN `"$TaskName`""
    Write-Host "   - 立即测试：powershell -File scripts\install_reminder.ps1 -Test"
} else {
    Write-Error "注册失败，错误码 $LASTEXITCODE"
}
