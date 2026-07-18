#!/usr/bin/env bash
# jj-agentic-os bootstrap - idempotent installer. Run from the repo root after unzip/clone.
#
#   bash scripts/bootstrap.sh [--vault DIR] [--no-vault] [--target-repo DIR]
#
# What it does:
#   1. Seeds the Obsidian vault (two-tier memory) from the template + git-inits it.
#   2. Seeds ~/.jj-agentic-os (gate modes, state dir).
#   3. Installs the git-hook enforcement layer (lefthook or raw hooks) in this repo.
#   4. Seeds preflight.toml via auto-detection.
#   5. With --target-repo: copies the generated Copilot artifacts + enforcement layer into
#      another repository (AGENTS.md, .github/*, .vscode/mcp.json, lefthook.yml, scripts/).
#   6. Prints the Claude Code install commands and per-OS scheduler registration.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VAULT="${JJ_VAULT_ROOT:-$HOME/jj-vault}"
NO_VAULT=0
TARGET=""
while [ $# -gt 0 ]; do
  case "$1" in
    --vault) VAULT="$2"; shift 2 ;;
    --no-vault) NO_VAULT=1; shift ;;
    --target-repo) TARGET="$2"; shift 2 ;;
    *) echo "bootstrap: unknown arg $1" >&2; exit 2 ;;
  esac
done

echo "== jj-agentic-os bootstrap (v$(cat "$ROOT/VERSION"))"

# 1. Vault
if [ "$NO_VAULT" -eq 0 ]; then
  if [ ! -d "$VAULT" ]; then
    cp -R "$ROOT/plugins/memory-fabric/vault-template" "$VAULT"
    echo "vault: seeded $VAULT from template"
  else
    echo "vault: $VAULT exists - leaving content untouched"
  fi
  if [ ! -d "$VAULT/.git" ]; then
    git -C "$VAULT" init -q -b main
    git -C "$VAULT" add -A && git -C "$VAULT" commit -qm "chore(vault): initial template" || true
    echo "vault: git initialized (add your PRIVATE remote: git -C $VAULT remote add origin <url>)"
  fi
fi

# 2. State + gate modes
JJ_HOME="${JJ_HOME:-$HOME/.jj-agentic-os}"
mkdir -p "$JJ_HOME"
if [ ! -f "$JJ_HOME/gates.json" ]; then
  cp "$ROOT/plugins/core-guardrails/hooks/scripts/gates.json" "$JJ_HOME/gates.json"
  echo "gates: seeded $JJ_HOME/gates.json (tunable gates start in dry-run; promote to"
  echo "       enforce per gate once telemetry shows FP < 2% - see guardrail-forge skill)"
fi

# 3. Git-hook layer for THIS repo
if [ -d "$ROOT/.git" ]; then
  (cd "$ROOT" && bash scripts/install-hooks.sh)
else
  echo "hooks: $ROOT is not a git repo yet - run 'git init' then scripts/install-hooks.sh"
fi

# 4. preflight.toml
if [ -d "$ROOT/.git" ] && [ ! -f "$ROOT/preflight.toml" ]; then
  (cd "$ROOT" && bash scripts/preflight.sh --init) || true
fi

# 5. Optional: install the Copilot + enforcement layer into another repository
if [ -n "$TARGET" ]; then
  [ -d "$TARGET/.git" ] || { echo "bootstrap: --target-repo $TARGET is not a git repo" >&2; exit 2; }
  echo "target: installing dual-runtime layer into $TARGET"
  mkdir -p "$TARGET/.github" "$TARGET/.vscode" "$TARGET/scripts"
  cp -R "$ROOT/.github/instructions" "$ROOT/.github/prompts" "$ROOT/.github/agents" \
        "$ROOT/.github/skills" "$TARGET/.github/" 2>/dev/null || true
  cp "$ROOT/.github/copilot-instructions.md" "$ROOT/.github/mcp.json" "$TARGET/.github/"
  cp "$ROOT/AGENTS.md" "$ROOT/lefthook.yml" "$ROOT/.mcp.json" "$TARGET/"
  cp "$ROOT/.vscode/mcp.json" "$TARGET/.vscode/mcp.json"
  cp "$ROOT/scripts/preflight.py" "$ROOT/scripts/preflight.sh" \
     "$ROOT/scripts/verify-attestation.sh" "$ROOT/scripts/install-hooks.sh" "$TARGET/scripts/"
  chmod +x "$TARGET/scripts/"*.sh
  mkdir -p "$TARGET/.github/workflows"
  cp "$ROOT/.github/workflows/jj-preflight.yml" "$ROOT/.github/workflows/copilot-setup-steps.yml" \
     "$TARGET/.github/workflows/"
  (cd "$TARGET" && bash scripts/install-hooks.sh && bash scripts/preflight.sh --init) || true
  echo "target: done. Add a required status check on 'jj-preflight / preflight' via a"
  echo "        repository ruleset to make the gate non-bypassable server-side."
fi

cat <<TXT

== Next steps =================================================================
Claude Code (from $ROOT parent directory, or any path):
  claude
  /plugin marketplace add $ROOT
  /plugin install core-guardrails@jj-agentic-os
  /plugin install memory-fabric@jj-agentic-os
  /plugin install business-ops@jj-agentic-os
  /plugin install day-job@jj-agentic-os

GitHub Copilot: artifacts are pre-generated in this repo (.github/, AGENTS.md,
  .vscode/mcp.json). Copilot auto-loads .github/skills; VS Code: enable
  chat.useAgentsMdFile for AGENTS.md. Coding agent MCP: paste .github/mcp.json's
  mcpServers object into repo Settings > Copilot > Coding agent.

Vault sync scheduler (pick your OS):
  macOS : cp scripts/schedulers/com.jakubjirak.jj-sync.plist ~/Library/LaunchAgents/ \
          && launchctl load ~/Library/LaunchAgents/com.jakubjirak.jj-sync.plist
  Linux : mkdir -p ~/.config/systemd/user && cp scripts/schedulers/jj-sync.{service,timer} \
          ~/.config/systemd/user/ && systemctl --user enable --now jj-sync.timer
  Windows: scripts\\schedulers\\register-windows-task.cmd

Environment (add to your shell profile):
  export JJ_VAULT_ROOT="$VAULT"
  export OBSIDIAN_REST_API_KEY="<key from Obsidian Local REST API plugin>"
===============================================================================
TXT
