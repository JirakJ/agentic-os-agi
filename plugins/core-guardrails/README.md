# core-guardrails 3.0.0
15 hooks behind one dispatcher (`hooks/scripts/dispatch.sh <Event>`): gate-protection,
security-gate, commit-integrity, no-placeholder, ship-gate (PreToolUse); test-gate,
i18n-complete, skill-usage-logger, context-budget-guard (PostToolUse); memory-reader
(SessionStart); memory-writer, telemetry-collector (SessionEnd); context-bridge,
subagent-gate (SubagentStop); context-preserver (PreCompact). Modes: env JJ_GATE_* >
~/.jj-agentic-os/gates.json > hooks/scripts/gates.json. Skills: guardrail-forge,
skill-forge. Commands: /gate-status, /gate-unlock, /preflight, /memory-capture.
Tests: tests/ (pytest) + tests/fixtures (harness: scripts/hook-dryrun-harness.sh).
