#!/bin/zsh
set -euo pipefail

PROJECT_DIR="${0:A:h}"
XPX_DIR="$PROJECT_DIR/xol-pots-xol"
cd "$XPX_DIR"

pause_if_interactive() {
  if [[ -t 0 ]]; then
    read -k 1 "?Press any key to close..."
  fi
}
on_exit() {
  local exit_status=$?
  if (( exit_status != 0 )); then
    pause_if_interactive
  fi
}
trap on_exit EXIT

echo "Xol-Pots-Xol Macintosh setup"
echo "Project: $XPX_DIR"

if [[ ! -f pyproject.toml || ! -d src/xolpotsxol ]]; then
  echo "This does not appear to be the Xol-Pots-Xol project directory."
  exit 1
fi

# Xol-Pots-Xol is a standalone sibling project (see CLAUDE.md) — it gets its
# own venv, independent of Möuseley Kräs's root .venv, so the two projects
# can never drift into sharing (or silently depending on) each other's
# installed package versions.
PYTHON_BIN=""
for candidate in python3.14 python3.13 python3.12 python3.11 python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    if "$candidate" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      PYTHON_BIN="$candidate"
      break
    fi
  fi
done

if [[ -z "$PYTHON_BIN" ]]; then
  echo ""
  echo "Python 3.11 or newer is required."
  echo "Install it from https://www.python.org/downloads/macos/ and run setup again."
  exit 1
fi

if [[ ! -x .venv/bin/python ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

# Reconcile to requirements.lock.txt on EVERY run, not just when a required
# library is missing, so an existing environment converges to the pinned
# versions instead of silently keeping whatever was already installed.
if [[ -f requirements.lock.txt ]]; then
  if .venv/bin/python -m pip install -r requirements.lock.txt; then
    echo "Installed/verified exact, pinned dependency versions from requirements.lock.txt."
  else
    echo ""
    echo "WARNING: could not install from requirements.lock.txt (offline and not cached?)."
    if .venv/bin/python -c 'import openpyxl, flask' >/dev/null 2>&1; then
      echo "Continuing with the versions already installed in this venv — they are NOT"
      echo "guaranteed to match requirements.lock.txt. Run this script again once online"
      echo "to reconcile to the pinned versions."
    else
      echo "Falling back to installing required libraries by version range (not pinned)..."
      .venv/bin/python -m pip install 'openpyxl>=3.1' 'Flask>=3.0'
    fi
    echo ""
  fi
else
  if ! .venv/bin/python -c 'import openpyxl, flask' >/dev/null 2>&1; then
    echo "Installing required Python libraries (no requirements.lock.txt found; using version ranges)..."
    .venv/bin/python -m pip install 'openpyxl>=3.1' 'Flask>=3.0'
  else
    echo "Required Python libraries are already installed; using them offline."
  fi
fi

if ! .venv/bin/python -c 'import setuptools' >/dev/null 2>&1; then
  .venv/bin/python -m pip install --no-deps 'setuptools>=68' >/dev/null
fi
.venv/bin/python -m pip install --no-deps --no-build-isolation -e . >/dev/null

# See AutoMouse_Setup.command for why: some Mac configurations mark files
# inside .venv with the macOS "hidden" flag, which Python 3.14's site.py
# silently respects by skipping hidden .pth files — breaking the editable
# install above. Clearing it is idempotent and harmless if never set.
chflags -R nohidden .venv 2>/dev/null || true

echo "Checking Xol-Pots-Xol directly from this project..."
.venv/bin/python -c \
  'import xolpotsxol; print("Xol-Pots-Xol from", xolpotsxol.__file__)'
.venv/bin/xolpotsxol --help >/dev/null
echo "Direct commands work: xol-pots-xol/.venv/bin/xolpotsxol, xolpotsxol-serve"
.venv/bin/python -m unittest discover -s tests -v

echo ""
echo "Setup and workflow tests completed successfully."
echo "Next: double-click XolPotsXol_WebApp.command to start the web app."
pause_if_interactive
