#!/usr/bin/env bash
# jj-agentic-os hook dispatcher. One entry per event; routes to numbered Python sub-hooks.
# Contract: sub-hooks read stdin JSON, print at most one JSON object (or plain text for
# SessionStart), exit 0. A printed permissionDecision:"deny" or decision:"block"
# short-circuits (first block wins). Exit 2 from a sub-hook propagates (hard block via
# stderr). Any dispatcher failure fails OPEN - a broken hook must never break the session.
set -uo pipefail
export PATH="/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"

# Recursion guard: headless/preflight children of a hook must not re-trigger hooks.
if [ -n "${JJ_HOOK_ACTIVE:-}" ]; then exit 0; fi
export JJ_HOOK_ACTIVE=1

EVENT="${1:-}"
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOOK_DIR="$SELF_DIR/$EVENT"
LOG="${JJ_HOME:-$HOME/.jj-agentic-os}/hook.log"
mkdir -p "$(dirname "$LOG")" 2>/dev/null || true

[ -d "$HOOK_DIR" ] || exit 0
PY="$(command -v python3 || command -v python || true)"
[ -n "$PY" ] || exit 0
TIMEOUT_BIN="$(command -v timeout || command -v gtimeout || true)"

# Per-sub-hook wall-clock budget. PreToolUse/PostToolUse/etc. sub-hooks are fast pattern
# matches (25s is generous); Stop's security-gate/test-gate/i18n-complete (ADR-0027) shell
# out to gitleaks/semgrep/osv-scanner or a full test suite and need real minutes. This is
# still the one shared dispatcher - only the budget is event-aware, not the mechanism.
case "$EVENT" in
  Stop) SUBHOOK_TIMEOUT=210 ;;
  *)    SUBHOOK_TIMEOUT=25 ;;
esac

INPUT="$(cat)"
export PYTHONPATH="$SELF_DIR${PYTHONPATH:+:$PYTHONPATH}"
export HOOK_EVENT="$EVENT"

TMP="$(mktemp)"; trap 'rm -f "$TMP"' EXIT

for h in "$HOOK_DIR"/*.py; do
  [ -e "$h" ] || continue
  if [ -n "$TIMEOUT_BIN" ]; then
    OUT="$(printf '%s' "$INPUT" | "$TIMEOUT_BIN" "$SUBHOOK_TIMEOUT" "$PY" "$h" 2>>"$LOG")"; rc=$?
  else
    OUT="$(printf '%s' "$INPUT" | "$PY" "$h" 2>>"$LOG")"; rc=$?
  fi
  if [ "$rc" -eq 2 ]; then
    # Hard block path (fail-closed hooks). stderr already logged; re-emit a reason.
    printf 'jj-agentic-os: %s blocked the action (see %s)\n' "$(basename "$h")" "$LOG" >&2
    exit 2
  fi
  if [ -n "$OUT" ]; then
    if printf '%s' "$OUT" | grep -Eq '"permissionDecision"[[:space:]]*:[[:space:]]*"(deny|ask)"|"decision"[[:space:]]*:[[:space:]]*"block"'; then
      printf '%s\n' "$OUT"
      exit 0
    fi
    printf '%s\0' "$OUT" >> "$TMP"
  fi
done

if [ -s "$TMP" ]; then
  "$PY" "$SELF_DIR/lib/merge_outputs.py" < "$TMP" || true
fi
exit 0
