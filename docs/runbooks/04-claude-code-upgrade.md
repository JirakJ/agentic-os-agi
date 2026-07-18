# Runbook: Claude Code upgraded and something broke
1. Reproduce with `claude --debug` (hook registration + per-hook stderr) and check
   ~/.jj-agentic-os/hook.log.
2. Hook contract drift (new event names, JSON fields): adjust lib/cc.py first - all hooks
   share it. Run pytest + harness.
3. Plugin didn't load: `/plugin` UI -> reinstall; verify marketplace path still valid.
4. Keep the dispatcher fail-open guarantee: a broken sub-hook must never brick sessions -
   verify by feeding fixtures via scripts/hook-dryrun-harness.sh.
5. Log an ADR if the platform change forces an architectural adjustment.
