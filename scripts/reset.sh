#!/usr/bin/env bash
# Quick reset script for Locus forensics database and case evidence files

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "Resetting Locus database and case storage files..."
"${ROOT_DIR}/backend/.venv/bin/python" "${ROOT_DIR}/backend/scripts/reset_environment.py"
