@echo off
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"

where py >nul 2>nul
if errorlevel 1 goto run_python

py -3 "%SCRIPT_DIR%yunji_vendor.py" %*
exit /b %ERRORLEVEL%

:run_python
where python >nul 2>nul
if errorlevel 1 goto no_python

python "%SCRIPT_DIR%yunji_vendor.py" %*
exit /b %ERRORLEVEL%

:no_python
echo Python 3.10 or later is required. Install Python from python.org, then retry.
exit /b 9009
