@echo off
setlocal EnableExtensions DisableDelayedExpansion
pushd "%~dp0"
if errorlevel 1 exit /b 1

if exist ".venv-windows\Scripts\python.exe" (
    ".venv-windows\Scripts\python.exe" -I -c "import ensurepip, struct, sys, venv; sys.exit(0 if sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
    if not errorlevel 1 goto managed_python
)
py -3.12 -I -c "import ensurepip, struct, sys, venv; sys.exit(0 if sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
if not errorlevel 1 goto python_launcher
python -I -c "import ensurepip, struct, sys, venv; sys.exit(0 if sys.version_info[:2] == (3, 12) and struct.calcsize('P') == 8 else 1)" >nul 2>&1
if not errorlevel 1 goto python_command

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0heo\application\bootstrap_windows.ps1" --open-existing %*
set "heo_status=%errorlevel%"
goto finish

:managed_python
".venv-windows\Scripts\python.exe" -X utf8 -I "%~dp0heo\application\launcher.py" --open-existing %*
set "heo_status=%errorlevel%"
goto finish

:python_launcher
py -3.12 -X utf8 -I "%~dp0heo\application\launcher.py" --open-existing %*
set "heo_status=%errorlevel%"
goto finish

:python_command
python -X utf8 -I "%~dp0heo\application\launcher.py" --open-existing %*
set "heo_status=%errorlevel%"

:finish
popd
if "%heo_status%"=="0" exit /b 0
if "%heo_status%"=="130" exit /b 130
echo.
echo HEO wurde nicht gestartet oder wurde mit einem Fehler beendet. Bitte die Meldung oben pruefen.
pause
exit /b %heo_status%
