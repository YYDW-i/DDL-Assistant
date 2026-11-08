@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
if errorlevel 1 (
    echo Installation failed. Close DDL Assistant before updating and check the message above.
    pause
    exit /b 1
)
