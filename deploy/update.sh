#!/usr/bin/env bash
# Deploy the checker on the host. Usage:
#   bash deploy/update.sh            update /opt/informatics-checker from origin/main
#   bash deploy/update.sh --rollback go back one commit
#   bash deploy/update.sh --backup   only copy the database
set -euo pipefail
cd "$(dirname "$0")/.."
exec ./.venv/bin/python deploy/update.py "$@"
