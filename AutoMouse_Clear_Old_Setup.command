#!/bin/zsh
set -euo pipefail

PROJECT_DIR="${0:A:h}"
cd "$PROJECT_DIR"

echo "This will move the existing .venv to a timestamped recoverable backup"
echo "and create a clean environment for Möuseley Kräs 0.3.0."
exec "$PROJECT_DIR/AutoMouse_Setup.command" --reset
