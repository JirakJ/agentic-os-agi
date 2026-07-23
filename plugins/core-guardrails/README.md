# core-guardrails 4.0.0
18 hooks behind one dispatcher (`hooks/scripts/dispatch.sh <Event>`): gate-protection,
security-gate, commit-integrity, no-placeholder, ship-gate (PreToolUse); test-gate,
i18n-complete, skill-usage-logger, context-budget-guard (PostToolUse); memory-reader
(SessionStart); memory-writer, telemetry-collector (SessionEnd); context-bridge,
subagent-gate (SubagentStop); context-preserver (PreCompact); security-gate, test-gate,
i18n-complete (Stop - whole-tree/aggregate checks: gitleaks+semgrep+osv-scanner, full
test suite + coverage ratchet, `.xcstrings` completeness; ADR-0027 brought these in from
former machine-local `~/.claude/hooks/*.mjs` scripts, vendored verbatim under
`hooks/scripts/Stop/vendor/` and run via `lib.nodegate`). Modes: env JJ_GATE_* >
~/.jj-agentic-os/gates.json > hooks/scripts/gates.json - the Stop-level and
PreToolUse/PostToolUse halves of security-gate/test-gate/i18n-complete share one mode
each, gates.json is their only source of truth. Skills: guardrail-forge, skill-forge.
Commands: /gate-status, /gate-unlock, /preflight, /memory-capture.
Tests: tests/ (pytest) + tests/fixtures (harness: scripts/hook-dryrun-harness.sh).
