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

# ADR-0016 — Dual-runtime architecture with src/ as single source of truth

## Context and problem statement
The OS must run natively as a Claude Code plugin AND on all GitHub Copilot surfaces
(VS Code, CLI, coding agent, JetBrains) for an enterprise org rollout, without maintaining two
asset trees.

## Decision outcome
Canonical assets live in `src/` (rules, commands, agents, MCP, agent instructions) and
skills live in `plugins/*/skills` (SKILL.md is already runtime-neutral - Copilot reads
`.claude/skills` and `.github/skills` natively). `scripts/build-adapters.py` generates all
runtime targets with DO-NOT-EDIT headers; `--check` in CI blocks drift. Generated files
are COMMITTED so a plain clone works on every surface with zero build step.

### Consequences
Good: one edit -> every runtime; installable zip works offline. Bad: generated files in
git require the drift gate; contributors must learn "edit src/, not .github/".
