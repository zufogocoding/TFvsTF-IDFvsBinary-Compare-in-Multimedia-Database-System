@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 (
    echo Please install Python 3.12 64-bit, then run this file again.
    pause
    exit /b 1
  )
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo Dependency installation failed. See README.md.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py --open-browser
pause
