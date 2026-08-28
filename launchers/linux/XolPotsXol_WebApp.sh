#!/usr/bin/env bash
# Linux equivalent of XolPotsXol_WebApp.command. Identical behavior.
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
    echo "Xol-Pots-Xol web app stopped with an error. Review the message above."
    pause_if_interactive
  fi
}
trap on_exit EXIT

XPX_VENV="$PROJECT_DIR/xol-pots-xol/.venv"

if [[ ! -x "$XPX_VENV/bin/python" ]]; then
  echo "Xol-Pots-Xol's own environment is not set up. Run launchers/linux/XolPotsXol_Setup.sh first."
  exit 1
fi
if ! "$XPX_VENV/bin/python" -c 'import xolpotsxol, flask, openpyxl' >/dev/null 2>&1; then
  echo "Xol-Pots-Xol's environment is missing a required package. Run"
  echo "launchers/linux/XolPotsXol_Setup.sh to repair it, then try again."
  exit 1
fi

echo "Starting the Xol-Pots-Xol web app..."
echo "A browser tab may not open automatically on all Linux desktop environments; if not,"
echo "open the URL printed below manually. Leave this window open while you use it;"
echo "closing this window or pressing Control-C here stops the web app."
echo ""

"$XPX_VENV/bin/xolpotsxol-serve" \
  --runtime-root "$PROJECT_DIR/xol-pots-xol/runtime"
