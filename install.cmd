@echo off
rem hwp-report-skills installer for Windows. Double-click, or run: install.cmd [--figures] [--link]
setlocal
cd /d "%~dp0"
set "PYCMD="
py -3 -c "import sys; assert sys.version_info >= (3, 9)" >nul 2>nul && set "PYCMD=py -3"
if not defined PYCMD (
  python -c "import sys; assert sys.version_info >= (3, 9)" >nul 2>nul && set "PYCMD=python"
)
if not defined PYCMD goto nopython
%PYCMD% -X utf8 install.py %*
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%

:nopython
echo [hwp-report] Python 3.9 or later was not found.
echo   1) Install Python:  winget install -e --id Python.Python.3.12
echo      or download from https://www.python.org/downloads/  - check "Add python.exe to PATH"
echo   2) Open a new window and run install.cmd again.
echo.
pause
exit /b 2
