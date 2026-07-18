#!/usr/bin/env bash
# hook-dryrun-harness: feed recorded fixtures through the dispatcher and assert decisions.
# Fixtures: plugins/core-guardrails/tests/fixtures/*.json with x-expect: deny|allow|block.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DISPATCH="$ROOT/plugins/core-guardrails/hooks/scripts/dispatch.sh"
FIX="$ROOT/plugins/core-guardrails/tests/fixtures"
PY="$(command -v python3)"
fail=0
for f in "$FIX"/*.json; do
  [ -e "$f" ] || continue
  expect="$("$PY" -c "import json,sys;print(json.load(open('$f')).get('x-expect','allow'))")"
  event="$("$PY" -c "import json,sys;print(json.load(open('$f')).get('hook_event_name','PreToolUse'))")"
  out="$(JJ_HOOK_ACTIVE= "$DISPATCH" "$event" < "$f")" ; rc=$?
  got="allow"
  case "$out" in
    *'"permissionDecision": "deny"'*|*'"permissionDecision":"deny"'*) got="deny";;
    *'"decision": "block"'*|*'"decision":"block"'*) got="block";;
  esac
  [ "$rc" -eq 2 ] && got="deny"
  if [ "$got" = "$expect" ]; then
    printf 'PASS %-38s expect=%s\n' "$(basename "$f")" "$expect"
  else
    printf 'FAIL %-38s expect=%s got=%s\n' "$(basename "$f")" "$expect" "$got"
    fail=1
  fi
done
exit $fail
