---
status: accepted
date: 2026-07-18
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: []
supersedes: []
superseded-by: []
---

# ADR-0018 — Enforcement parity on Copilot via git hooks + CI + rulesets (no agent hooks)

## Context and problem statement
GitHub Copilot has no deterministic PreToolUse-style deny hook on any GA surface
(JetBrains agent hooks are preview-only). The commit gate must still hold for engineers
using Copilot exclusively - and for the autonomous coding agent.

## Decision outcome
Layering: (1) lefthook pre-commit/pre-push run `verify-attestation.sh` (fast, local,
bypassable with --no-verify BY DESIGN); (2) reusable `jj-preflight.yml` required status
check runs the identical pipeline server-side; (3) a repository ruleset (require PR,
require the check, no bypass) is the authoritative backstop that neither --no-verify nor
the coding agent can evade. Claude keeps its stronger in-agent deny on top.

### Consequences
Good: one bar for humans, Claude, and Copilot; org-scalable via template repo + ruleset.
Bad: local Copilot feedback arrives at commit time, not tool-call time.
