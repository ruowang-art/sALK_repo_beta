#!/bin/zsh
set -euo pipefail

PROJECT_DIR="${0:A:h}"
cd "$PROJECT_DIR"

pause_if_interactive() {
  if [[ -t 0 ]]; then
    read -k 1 "?Press any key to close..."
  fi
}

LEGACY_TARGET=""
restore_reset_environment_on_failure() {
  local exit_code=$?
  if (( exit_code != 0 )) && [[ -n "$LEGACY_TARGET" && -d "$LEGACY_TARGET" ]]; then
    set +e
    local failed_target="${LEGACY_TARGET:h}/.venv_failed_$(date +%Y%m%d_%H%M%S)"
    if [[ -d .venv ]]; then
      mv .venv "$failed_target"
      echo "Preserved the incomplete replacement at: $failed_target"
    fi
    mv "$LEGACY_TARGET" .venv
    echo "Setup failed, so the previous environment was restored."
  fi
  if (( exit_code != 0 )); then
    pause_if_interactive
  fi
  return $exit_code
}
trap restore_reset_environment_on_failure EXIT

RESET_ENVIRONMENT=false
case "${1:-}" in
  "") ;;
  --reset|--clean) RESET_ENVIRONMENT=true ;;
  *)
    echo "Usage: $0 [--reset]"
    exit 2
    ;;
esac

echo "Möuseley Kräs Macintosh setup"
echo "Project: $PROJECT_DIR"

if [[ ! -f pyproject.toml || ! -d src/automouse ]]; then
  echo "This does not appear to be the Möuseley Kräs project directory."
  exit 1
fi

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

if [[ ! -x /usr/local/bin/Rscript ]] && ! command -v Rscript >/dev/null 2>&1; then
  echo ""
  echo "Rscript was not found. Install R from https://cran.r-project.org/bin/macosx/"
  exit 1
fi

if [[ "$RESET_ENVIRONMENT" == true && -d .venv ]]; then
  LEGACY_DIR="$PROJECT_DIR/AutoMouse_legacy_environments"
  LEGACY_TARGET="$LEGACY_DIR/.venv_$(date +%Y%m%d_%H%M%S)"
  mkdir -p "$LEGACY_DIR"
  mv .venv "$LEGACY_TARGET"
  echo "Moved the old recoverable environment to: $LEGACY_TARGET"
fi

if [[ ! -x .venv/bin/python ]]; then
  "$PYTHON_BIN" -m venv .venv
fi

# Reconcile to requirements.lock.txt on EVERY run (not just when a required
# library is missing) so an existing environment converges to the pinned
# versions instead of silently keeping whatever was already installed.
if [[ -f requirements.lock.txt ]]; then
  if .venv/bin/python -m pip install -r requirements.lock.txt; then
    echo "Installed/verified exact, pinned dependency versions from requirements.lock.txt."
  else
    echo ""
    echo "WARNING: could not install from requirements.lock.txt (offline and not cached?)."
    if .venv/bin/python -c 'import yaml, openpyxl, pandas, flask' >/dev/null 2>&1; then
      echo "Continuing with the versions already installed in this venv — they are NOT"
      echo "guaranteed to match requirements.lock.txt. Run this script again once online"
      echo "to reconcile to the pinned versions."
    else
      echo "Falling back to installing required libraries by version range (not pinned)..."
      .venv/bin/python -m pip install \
        'PyYAML>=6.0' \
        'openpyxl>=3.1' \
        'pandas>=2.2' \
        'Flask>=3.0'
    fi
    echo ""
  fi
else
  if ! .venv/bin/python -c 'import yaml, openpyxl, pandas, flask' >/dev/null 2>&1; then
    echo "Installing required Python libraries (no requirements.lock.txt found; using version ranges)..."
    .venv/bin/python -m pip install \
      'PyYAML>=6.0' \
      'openpyxl>=3.1' \
      'pandas>=2.2' \
      'Flask>=3.0'
  else
    echo "Required Python libraries are already installed; using them offline."
  fi
fi

# Register the automouse package + its "automouse" console-script entry point
# in this venv, so it can be run directly (.venv/bin/automouse --help)
# without setting PYTHONPATH by hand. --no-deps because the exact
# dependency versions were already installed/verified above; setuptools is
# installed first so the editable build works fully offline on a repeat run.
if ! .venv/bin/python -c 'import setuptools' >/dev/null 2>&1; then
  .venv/bin/python -m pip install --no-deps 'setuptools>=68' >/dev/null
fi
.venv/bin/python -m pip install --no-deps --no-build-isolation -e . >/dev/null

# The Google Sheet DOB/Wean_By overlay (config/pipeline_run.yaml's
# sheets_overlay section) needs these libraries only if it is enabled; skip
# quietly (with a warning at run time, not a setup failure) if offline.
if ! .venv/bin/python -c 'import googleapiclient, google.oauth2.service_account' >/dev/null 2>&1; then
  echo "Installing optional Google Sheets overlay libraries..."
  .venv/bin/python -m pip install \
    'google-api-python-client>=2.100' \
    'google-auth>=2.23' || echo "Could not install the Sheets overlay libraries; the batch will warn and continue without them."
else
  echo "Google Sheets overlay libraries are already installed; using them offline."
fi

RSCRIPT_BIN="/usr/local/bin/Rscript"
if [[ ! -x "$RSCRIPT_BIN" ]]; then
  RSCRIPT_BIN="$(command -v Rscript)"
fi
"$RSCRIPT_BIN" -e 'missing <- setdiff(c("dplyr", "purrr"), rownames(installed.packages())); if (length(missing)) stop(paste("Missing R packages:", paste(missing, collapse=", ")))' 

# Some Mac configurations mark files inside .venv with the "hidden" macOS
# file flag (observed here after a manual Finder-declutter/backup-exclusion
# action on an earlier setup, not something this script itself does). Python
# 3.14's site.py silently skips any hidden .pth file, which breaks the
# editable install above with a confusing "No module named 'automouse'" —
# this is the actual root cause of the ModuleNotFoundError this project
# previously worked around by abandoning editable installs entirely. Clearing
# the flag (idempotent, harmless if never set) keeps editable installs
# working instead of avoiding them.
chflags -R nohidden .venv 2>/dev/null || true

echo "Checking Möuseley Kräs directly from this project..."
.venv/bin/python -c \
  'import automouse; print("Möuseley Kräs", automouse.__version__, "from", automouse.__file__)'
.venv/bin/automouse --help >/dev/null
echo "Direct command works: .venv/bin/automouse (no PYTHONPATH needed)"
PYTHONPATH="$PROJECT_DIR/src" .venv/bin/python -m automouse --help >/dev/null
PYTHONPATH="$PROJECT_DIR/src" .venv/bin/python -m unittest discover -s tests -v

echo ""
echo "Setup, source-path smoke tests, and workflow tests completed successfully."
echo "Next: double-click AutoMouse_Run.command and choose one or more raw CSV files."
pause_if_interactive
