@echo off
setlocal

cd /d "%~dp0"

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
set "MODULE=tax_rpa.cli.from_zero_import_person_info"

if not exist "%PYTHON_EXE%" (
    echo Virtual environment Python not found: %PYTHON_EXE%
    exit /b 1
)

"%PYTHON_EXE%" -m "%MODULE%" %*

endlocal
