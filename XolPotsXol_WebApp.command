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

if [[ ! -x .venv/bin/python ]]; then
  echo "The shared Python environment is not set up. Double-click AutoMouse_Setup.command first."
  exit 1
fi
if ! PYTHONPATH="$PROJECT_DIR/xol-pots-xol/src" .venv/bin/python -c 'import xolpotsxol, flask, openpyxl' >/dev/null 2>&1; then
  echo "Installing Xol-Pots-Xol's requirements (openpyxl, Flask)..."
  .venv/bin/python -m pip install 'openpyxl>=3.1' 'Flask>=3.0'
fi

echo "Starting the Xol-Pots-Xol web app..."
echo "A browser tab will open automatically. Leave this window open while you use it;"
echo "closing this window or pressing Control-C here stops the web app."
echo ""

PYTHONPATH="$PROJECT_DIR/xol-pots-xol/src" .venv/bin/python -m xolpotsxol.serve \
  --runtime-root "$PROJECT_DIR/xol-pots-xol/runtime"
