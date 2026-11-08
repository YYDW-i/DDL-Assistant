# PyInstaller 打包脚本：生成单文件 EXE。
# 用法：powershell -ExecutionPolicy Bypass -File scripts\build.ps1
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    Write-Error "未找到虚拟环境 Python：$Python"
    exit 1
}

Set-Location $ProjectRoot

# 清理旧产物
if (Test-Path "build") { Remove-Item -Recurse -Force "build" }
if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }

Write-Host "开始打包（主程序）..."
& $Python -m PyInstaller `
    --noconfirm `
    --onefile `
    --windowed `
    --name "DDLAssistant" `
    --collect-submodules app `
    --hidden-import windows_toasts `
    --hidden-import winrt.windows.ui.notifications `
    app\main.py

Write-Host ""
Write-Host "打包完成："
Write-Host "  主程序: dist\DDLAssistant.exe"
Write-Host ""
Write-Host "提醒脚本（供任务计划程序调用，无窗口）："
& $Python -m PyInstaller --noconfirm --onefile --console --name "DDLAssistantReminder" app\reminder\__main__.py

Write-Host ""
Write-Host "✅ 全部完成。dist\ 目录下："
Get-ChildItem dist\ | Format-Table Name, Length
