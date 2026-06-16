#!/bin/bash
cd "$(dirname "$0")" || exit 1
echo "=================================================="
echo " OpenBeat Collector - Easy Start (macOS)"
echo "=================================================="

PY=""
command -v python3 >/dev/null 2>&1 && PY=python3
if [ -z "$PY" ]; then
  echo ""
  echo "[ERROR] python3 not found."
  echo "  Install Python 3.10 or later from https://www.python.org/downloads/,"
  echo "  then open this file again."
  echo ""
  read -n 1 -s -r -p "Press Enter to exit..."
  exit 1
fi

if [ ! -x ".venv/bin/python3" ]; then
  echo "First-time setup: creating a dedicated runtime environment..."
  "$PY" -m venv .venv || { echo "[ERROR] Failed to create the environment."; read -n 1 -s -r; exit 1; }
fi
VENV_PY=".venv/bin/python3"

if [ ! -f ".venv/.deps_ok" ]; then
  echo "Installing the needed parts (first run only; may take a few minutes)..."
  "$VENV_PY" -m pip install --upgrade pip >/dev/null 2>&1
  "$VENV_PY" -m pip install -r requirements.txt || { echo "[ERROR] Failed to install parts. Check your internet connection."; read -n 1 -s -r; exit 1; }
  echo ok > .venv/.deps_ok
fi

echo ""
echo "Starting the collector. A browser opens automatically in a few seconds (http://127.0.0.1:5000)."
echo "New here? Press \"Try it now with samples\" in the UI to see results right away."
echo "To stop, close this window."
echo "(For a Japanese UI, run with OPENBEAT_LANG=ja: OPENBEAT_LANG=ja ./start_mac.command)"
echo ""
"$VENV_PY" app.py
