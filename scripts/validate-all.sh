#!/usr/bin/env bash
# One-shot local validation: everything CI runs, in order.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="$(command -v python3)"
echo "== compileall";       "$PY" -m compileall -q scripts plugins
echo "== adapters --check"; "$PY" scripts/build-adapters.py --check
echo "== validate-copilot"; "$PY" scripts/validate-copilot.py
echo "== skill budget";     "$PY" scripts/skill-budget-lint.py
echo "== hook harness";     bash scripts/hook-dryrun-harness.sh
echo "== pytest";           "$PY" -m pytest -q
echo "validate-all: GREEN"
