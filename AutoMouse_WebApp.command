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
  # "status" is a special read-only parameter in zsh; a distinct name is
  # required here or the trap itself fails.
  local exit_status=$?
  if (( exit_status != 0 )); then
    echo ""
    echo "Möuseley Kräs web app stopped with an error. Review the message above."
    pause_if_interactive
  fi
}
trap on_exit EXIT

if [[ ! -x .venv/bin/python ]]; then
  echo "Möuseley Kräs is not set up. Double-click AutoMouse_Setup.command first."
  exit 1
fi
if ! PYTHONPATH="$PROJECT_DIR/src" .venv/bin/python -c 'import automouse, flask' >/dev/null 2>&1; then
  echo "The Möuseley Kräs web app is not available yet."
  echo "Double-click AutoMouse_Setup.command to install its remaining requirement (Flask), then try again."
  exit 1
fi

echo "Starting the Möuseley Kräs web app..."
echo "A browser tab will open automatically. Leave this window open while you use it;"
echo "closing this window or pressing Control-C here stops the web app."
echo ""

PYTHONPATH="$PROJECT_DIR/src" .venv/bin/python -m automouse \
  --config config/pipeline_run.yaml \
  serve
