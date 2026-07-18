#!/usr/bin/env bash
# Install the runtime-agnostic git-hook layer (lefthook preferred, raw .git/hooks fallback).
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
if command -v lefthook >/dev/null 2>&1; then
  lefthook install
  echo "install-hooks: lefthook installed (pre-commit + pre-push)."
else
  mkdir -p .git/hooks
  cat > .git/hooks/pre-commit <<'HOOK'
#!/usr/bin/env bash
exec bash "$(git rev-parse --show-toplevel)/scripts/verify-attestation.sh" --staged
HOOK
  cat > .git/hooks/pre-push <<'HOOK'
#!/usr/bin/env bash
exec bash "$(git rev-parse --show-toplevel)/scripts/verify-attestation.sh" --require-fresh
HOOK
  chmod +x .git/hooks/pre-commit .git/hooks/pre-push
  echo "install-hooks: lefthook not found - installed raw .git/hooks fallback."
  echo "install-hooks: recommended: brew install lefthook (or scoop/apt), then re-run."
fi
