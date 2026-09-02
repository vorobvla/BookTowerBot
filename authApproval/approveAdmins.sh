#!/usr/bin/env bash
# ==============================================================================
# BookTower Admin Approval Script
# Interactive one-by-one approval of pending admin registrations.
# ==============================================================================

set -e

# Determine directory where script is located and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

# Use Python virtual environment if available, otherwise system python3
if [ -f "${PROJECT_ROOT}/.venv/bin/python" ]; then
    PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
else
    PYTHON_BIN="python"
fi

export PYTHONPATH="${PROJECT_ROOT}:${PYTHONPATH}"

if [ "$1" = "-c" ] || [ "$1" = "--clear" ] || [ "$1" = "clear" ]; then
    "${PYTHON_BIN}" -m admin.auth.cli clear
elif [ "$1" = "-h" ] || [ "$1" = "--help" ] || [ "$1" = "help" ]; then
    echo "Usage: $0 [options]"
    echo ""
    echo "Interactive approval tool for pending admin registrations."
    echo "Reviews pending users one by one. If a user is not approved, they are removed from the database."
    echo ""
    echo "Options:"
    echo "  (no arguments)       Start interactive approval (one by one)"
    echo "  -c, --clear, clear   Clear all non-approved registrations at once"
    echo "  -h, --help           Display this help message"
else
    "${PYTHON_BIN}" -m admin.auth.cli "$@"
fi
