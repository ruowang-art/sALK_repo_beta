#!/usr/bin/env bash
# Linux equivalent of AutoMouse_WebApp.command. Identical behavior; no
# platform-specific parts to translate here.
#
# Implemented but NOT verified on a real Linux machine or CI (Phase 3, not
# Phase 4) — only smoke-tested via bash on macOS.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_DIR"

pause_if_interactive() {
  if [[ -t 0 ]]; then
    read -n 1 -r -p "Press any key to close..." || true
    echo ""
  fi
}

on_exit() {
  local exit_status=$?
  if (( exit_status != 0 )); then
    echo ""
    echo "Möuseley Kräs web app stopped with an error. Review the message above."
    pause_if_interactive
  fi
}
trap on_exit EXIT

if [[ ! -x .venv/bin/python ]]; then
  echo "Möuseley Kräs is not set up. Run launchers/linux/AutoMouse_Setup.sh first."
  exit 1
fi
if ! PYTHONPATH="$PROJECT_DIR/src" .venv/bin/python -c 'import automouse, flask' >/dev/null 2>&1; then
  echo "The Möuseley Kräs web app is not available yet."
  echo "Run launchers/linux/AutoMouse_Setup.sh to install its remaining requirement (Flask), then try again."
  exit 1
fi

echo "Starting the Möuseley Kräs web app..."
echo "A browser tab may not open automatically on all Linux desktop environments; if not,"
echo "open the URL printed below manually. Leave this window open while you use it;"
echo "closing this window or pressing Control-C here stops the web app."
echo ""

PYTHONPATH="$PROJECT_DIR/src" .venv/bin/python -m automouse \
  --config config/pipeline_run.yaml \
  serve
