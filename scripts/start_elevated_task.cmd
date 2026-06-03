@echo off
setlocal

cd /d "%~dp0.."

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_elevated_task.ps1" %*
exit /b %ERRORLEVEL%
