#!/usr/bin/env bash
# jj-agentic-os preflight entrypoint. Builds, tests, lints, scans and smoke-runs the EXACT
# staged tree and writes the attestation the commit-integrity gate verifies.
# Usage: scripts/preflight.sh [--ci] [--init]
set -euo pipefail
export JJ_HOOK_ACTIVE="${JJ_HOOK_ACTIVE:-preflight}"   # never re-trigger agent hooks
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$(command -v python3 || command -v python)"
exec "$PY" "$DIR/preflight.py" "$@"
