#!/usr/bin/env bash
# jj-sync: vault synchronization for macOS/Linux. Pull-rebase, secret-scan, commit, push.
# Safe to run from a scheduler; exits quietly when nothing changed or offline.
set -euo pipefail
VAULT="${JJ_VAULT_ROOT:-$HOME/jj-vault}"
[ -d "$VAULT/.git" ] || { echo "jj-sync: $VAULT is not a git repo" >&2; exit 1; }
cd "$VAULT"
git pull --rebase --autostash --quiet || echo "jj-sync: pull failed (offline?) - continuing local commit" >&2
if [ -z "$(git status --porcelain)" ]; then exit 0; fi
git add -A
if command -v gitleaks >/dev/null 2>&1; then
  if ! gitleaks git --staged --no-banner --redact -v; then
    git reset --quiet
    echo "jj-sync: BLOCKED - gitleaks found secrets in the vault delta. Fix and rerun." >&2
    exit 1
  fi
fi
git commit --quiet -m "chore(vault): sync $(hostname -s) $(date -u +%Y-%m-%dT%H:%M:%SZ)"
git push --quiet || echo "jj-sync: push failed (offline?) - will retry next run" >&2
