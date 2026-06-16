@echo off
setlocal
cd /d "%~dp0"
echo ==================================================
echo  OpenBeat Collector - Easy Start (Windows)
echo ==================================================

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
  echo.
  echo [ERROR] Python not found.
  echo   Install Python 3.10 or later from https://www.python.org/downloads/,
  echo   check "Add python.exe to PATH" during installation, then run this file again.
  echo.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo First-time setup: creating a dedicated runtime environment...
  %PY% -m venv .venv || ( echo [ERROR] Failed to create the environment. & pause & exit /b 1 )
)
set "VENV_PY=.venv\Scripts\python.exe"

if not exist ".venv\.deps_ok" (
  echo Installing the needed parts (first run only; may take a few minutes)...
  "%VENV_PY%" -m pip install --upgrade pip >nul 2>nul
  "%VENV_PY%" -m pip install -r requirements.txt || ( echo [ERROR] Failed to install parts. Check your internet connection. & pause & exit /b 1 )
  echo ok> ".venv\.deps_ok"
)

echo.
echo Starting the collector. A browser opens automatically in a few seconds (http://127.0.0.1:5000).
echo New here? Press "Try it now with samples" in the UI to see results right away.
echo To stop, close this window.
echo (For a Japanese UI, set OPENBEAT_LANG=ja before running: set OPENBEAT_LANG=ja)
echo.
"%VENV_PY%" app.py
pause
