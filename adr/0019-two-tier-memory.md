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

# ADR-0019 — Two-tier memory (git core + Obsidian vault) with queue-based capture

## Context and problem statement
The OS needs durable memory across sessions, machines, and runtimes without bloating
context or corrupting notes under concurrent sessions.

## Decision outcome
Tier 1 = this git repo (executable assets). Tier 2 = private Obsidian vault (~/jj-vault),
git-synced every 15 min (jj-sync, gitleaks-guarded, merge=union for append-only folders).
Writers append <4KiB JSONL records to a per-session queue (atomic O_APPEND); a single
flock-guarded drainer in SessionStart materializes inbox notes; SessionStart injects last
3 dailies + open decisions (capped ~9KB). On Copilot (no session hooks) capture is the
explicit memory-capture skill + the same vault via MCP.

### Consequences
Good: crash-safe capture, no write contention, bounded injection. Bad: raw captures need
periodic memory-compact refinement; Copilot capture is opt-in per session.
