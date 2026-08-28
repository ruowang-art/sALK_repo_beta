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
  # Note: "status" is a special read-only parameter in zsh, so a distinct
  # name is required here or the trap itself fails.
  local exit_status=$?
  if (( exit_status != 0 )); then
    echo ""
    echo "Möuseley Kräs stopped with an error. Review the message above."
    pause_if_interactive
  fi
}
trap on_exit EXIT

if [[ ! -x .venv/bin/python ]]; then
  echo "Möuseley Kräs is not set up. Double-click AutoMouse_Setup.command first."
  exit 1
fi
if ! PYTHONPATH="$PROJECT_DIR/src" .venv/bin/python -c 'import automouse' >/dev/null 2>&1; then
  echo "The Möuseley Kräs source package is unreadable."
  echo "Double-click AutoMouse_Clear_Old_Setup.command to rebuild it safely."
  exit 1
fi

typeset -a RAW_INPUTS
if (( $# > 0 )); then
  RAW_INPUTS=("$@")
else
  SELECTED_FILES=""
  if ! SELECTED_FILES=$(/usr/bin/osascript - "$PROJECT_DIR" <<'APPLESCRIPT'
on run argv
  set startingFolder to POSIX file (item 1 of argv) as alias
  set pickedFiles to choose file with prompt "Choose one or more raw Transnetyx CSV files (Command-click or Shift-click)" default location startingFolder with multiple selections allowed
  set outputText to ""
  repeat with pickedFile in pickedFiles
    set outputText to outputText & POSIX path of pickedFile & linefeed
  end repeat
  return outputText
end run
APPLESCRIPT
  ); then
    echo "Selection cancelled; no files were processed."
    exit 0
  fi
  RAW_INPUTS=("${(@f)SELECTED_FILES}")
fi

typeset -a VALIDATED_INPUTS
for input_path in "${RAW_INPUTS[@]}"; do
  [[ -z "$input_path" ]] && continue
  if [[ ! -f "$input_path" ]]; then
    echo "Selected input does not exist: $input_path"
    exit 1
  fi
  if [[ "${input_path:e:l}" != "csv" ]]; then
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
integer input_number=1
for input_path in "${VALIDATED_INPUTS[@]}"; do
  echo "  $input_number. $input_path"
  (( input_number += 1 ))
done

# Exit code 3 means Möuseley Kräs blocked the run because one or more selected
# files were already archived in an earlier run (see cli.py). That is not a
# generic failure, so it is handled separately below instead of falling
# through to on_exit's generic error message.
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
    read -q "REPLY?Re-run anyway? [y/N] "
    echo ""
  fi
  if [[ "$REPLY" == [Yy] ]]; then
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
  exit $STATUS
fi

echo ""
echo "Batch completed. Review the exception report and Live Label workbook in:"
echo "$PROJECT_DIR/outputs/019fb5fc-cfb6-7a51-9423-58940a90cde9/automouse_runtime"
pause_if_interactive
