#!/usr/bin/env bash
# Linux equivalent of AutoMouse_Run.command. Same batch-processing logic and
# same duplicate-input confirmation flow; the macOS AppleScript file picker
# is replaced with a numbered-list picker (no extra GUI-toolkit dependency
# assumed) when no file paths are given on the command line.
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
    echo "Möuseley Kräs stopped with an error. Review the message above."
    pause_if_interactive
  fi
}
trap on_exit EXIT

if [[ ! -x .venv/bin/python ]]; then
  echo "Möuseley Kräs is not set up. Run launchers/linux/AutoMouse_Setup.sh first."
  exit 1
fi
if ! PYTHONPATH="$PROJECT_DIR/src" .venv/bin/python -c 'import automouse' >/dev/null 2>&1; then
  echo "The Möuseley Kräs source package is unreadable."
  echo "Re-run launchers/linux/AutoMouse_Setup.sh --reset to rebuild it safely."
  exit 1
fi

RAW_INPUTS=()
if (( $# > 0 )); then
  RAW_INPUTS=("$@")
else
  if [[ ! -t 0 ]]; then
    echo "No CSV files were given, and there is no terminal to prompt for a selection."
    echo "Usage: $0 <file1.csv> [file2.csv ...]"
    exit 1
  fi
  read -r -p "Directory to choose raw Transnetyx CSVs from [$PROJECT_DIR]: " PICK_DIR
  PICK_DIR="${PICK_DIR:-$PROJECT_DIR}"
  if [[ ! -d "$PICK_DIR" ]]; then
    echo "Not a directory: $PICK_DIR"
    exit 1
  fi
  CANDIDATES=()
  while IFS= read -r -d '' candidate; do
    CANDIDATES+=("$candidate")
  done < <(find "$PICK_DIR" -maxdepth 1 -iname '*.csv' -print0 | sort -z)
  if (( ${#CANDIDATES[@]} == 0 )); then
    echo "No .csv files found in: $PICK_DIR"
    exit 1
  fi
  echo "Found ${#CANDIDATES[@]} CSV file(s):"
  for i in "${!CANDIDATES[@]}"; do
    echo "  $((i + 1)). ${CANDIDATES[$i]}"
  done
  read -r -p "Enter the numbers to process, space-separated (e.g. '1 3 4'): " SELECTION
  if [[ -z "$SELECTION" ]]; then
    echo "Selection cancelled; no files were processed."
    exit 0
  fi
  for token in $SELECTION; do
    if ! [[ "$token" =~ ^[0-9]+$ ]] || (( token < 1 || token > ${#CANDIDATES[@]} )); then
      echo "Invalid selection: $token"
      exit 1
    fi
    RAW_INPUTS+=("${CANDIDATES[$((token - 1))]}")
  done
fi

VALIDATED_INPUTS=()
for input_path in "${RAW_INPUTS[@]}"; do
  [[ -z "$input_path" ]] && continue
  if [[ ! -f "$input_path" ]]; then
    echo "Selected input does not exist: $input_path"
    exit 1
  fi
  extension="$(echo "${input_path##*.}" | tr '[:upper:]' '[:lower:]')"
  if [[ "$extension" != "csv" ]]; then
    echo "Selected input is not a CSV file: $input_path"
    exit 1
  fi
  VALIDATED_INPUTS+=("$input_path")
done

if (( ${#VALIDATED_INPUTS[@]} == 0 )); then
  echo "No CSV files were selected."
  exit 1
fi

echo "Möuseley Kräs will process ${#VALIDATED_INPUTS[@]} file(s) as one batch:"
input_number=1
for input_path in "${VALIDATED_INPUTS[@]}"; do
  echo "  $input_number. $input_path"
  (( input_number += 1 ))
done

# Exit code 3 means Möuseley Kräs blocked the run because one or more selected
# files were already archived in an earlier run (see cli.py) — handled
# separately below instead of falling through to on_exit's generic message.
DUPLICATE_INPUT_EXIT_CODE=3

set +e
PYTHONPATH="$PROJECT_DIR/src" .venv/bin/python -m automouse \
  --config config/pipeline_run.yaml \
  run --verbose \
  "${VALIDATED_INPUTS[@]}"
STATUS=$?
set -e

if (( STATUS == DUPLICATE_INPUT_EXIT_CODE )); then
  echo ""
  echo "One or more selected files were already processed in an earlier run."
  echo "Only choose to re-run if this is an intentional retry (for example, a"
  echo "corrected re-download); Möuseley Kräs will reprocess the file as new data."
  REPLY="n"
  if [[ -t 0 ]]; then
    read -r -p "Re-run anyway? [y/N] " REPLY
  fi
  if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    echo "Re-running with duplicate input allowed..."
    set +e
    PYTHONPATH="$PROJECT_DIR/src" .venv/bin/python -m automouse \
      --config config/pipeline_run.yaml \
      run --verbose --allow-duplicate-input \
      "${VALIDATED_INPUTS[@]}"
    STATUS=$?
    set -e
  else
    echo "Not re-running. No files were processed."
  fi
fi

if (( STATUS != 0 )); then
  exit "$STATUS"
fi

echo ""
echo "Batch completed. Review the exception report and Live Label workbook in:"
echo "$PROJECT_DIR/outputs/019fb5fc-cfb6-7a51-9423-58940a90cde9/automouse_runtime"
pause_if_interactive
