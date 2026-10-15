# Runbook: new machine / full recovery
1. Install: git, python3.11+, uv, lefthook, osv-scanner, opengrep (or semgrep).
2. Clone jj-agentic-os; clone the PRIVATE vault to ~/jj-vault.
3. `bash scripts/bootstrap.sh` (idempotent: gates seed, git hooks, preflight.toml).
4. Claude Code: /plugin marketplace add + install the four plugins; restart.
5. Export JJ_VAULT_ROOT and OBSIDIAN_REST_API_KEY in the shell profile; register the
   jj-sync scheduler for the OS (scripts/schedulers/).
6. Verify: `bash scripts/validate-all.sh` green; `/gate-status` shows attestation state.
