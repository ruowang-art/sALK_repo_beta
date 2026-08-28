#!/bin/zsh
# Repairs a symptom where `automouse`/`xolpotsxol`/`xolpotsxol-serve` (or any
# editable-installed command in either project's .venv) fails with
# "ModuleNotFoundError", even though setup previously succeeded.
#
# Root cause: some Mac configurations (observed here after a Finder-declutter
# or backup-exclusion action, and confirmed to recur after installing an
# additional package with pip directly into an existing venv) mark files
# inside .venv with the macOS "hidden" file flag. Python 3.14's site.py
# silently skips any hidden .pth file — exactly the file editable installs
# use to register a package's source directory — so the package "disappears"
# even though it's still correctly installed.
#
# This is always safe to re-run: it only clears a display/backup-related
# file flag, never touches file contents.
set -euo pipefail
PROJECT_DIR="${0:A:h:h}"
for venv in "$PROJECT_DIR/.venv" "$PROJECT_DIR/xol-pots-xol/.venv"; do
  if [[ -d "$venv" ]]; then
    chflags -R nohidden "$venv"
    echo "Cleared the hidden flag on: $venv"
  fi
done
echo "Done. Re-run automouse/xolpotsxol directly to confirm it's fixed."
