#!/bin/zsh
set -euo pipefail

PROJECT_DIR="${0:A:h}"
cd "$PROJECT_DIR"

pause_if_interactive() {
  if [[ -t 0 ]]; then
    read -k 1 "?Press any key to close..."
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
  echo "Xol-Pots-Xol's own environment is not set up. Double-click XolPotsXol_Setup.command first."
  exit 1
fi
if ! "$XPX_VENV/bin/python" -c 'import xolpotsxol, flask, openpyxl' >/dev/null 2>&1; then
  echo "Xol-Pots-Xol's environment is missing a required package. Double-click"
  echo "XolPotsXol_Setup.command to repair it, then try again."
  exit 1
fi

echo "Starting the Xol-Pots-Xol web app..."
echo "A browser tab will open automatically. Leave this window open while you use it;"
echo "closing this window or pressing Control-C here stops the web app."
echo ""

"$XPX_VENV/bin/xolpotsxol-serve" \
  --runtime-root "$PROJECT_DIR/xol-pots-xol/runtime"
