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

# ADR-0017 — Commit-integrity gate via out-of-band attestation

## Context and problem statement
"Only fully tested, buildable, runnable, error-free code without security debt gets
committed." Hooks must answer in <50ms; builds and tests take minutes. Timeout-limited
in-hook pipelines would be both slow and bypassable by staging races.

## Decision outcome
`scripts/preflight.py` runs the full pipeline on an isolated `git checkout-index` export
of the staged tree and writes `.git/jj-attest/<git write-tree>.json` (schema_version,
results, overall, ts, ttl_s=1800, toolchain_fingerprint). Verifiers only compare
tree hash + overall + freshness: Claude PreToolUse hook (deny JSON, /gate-unlock only
override), `verify-attestation.sh` for git hooks (plain exit 1, auto-runs preflight when
stale), and CI (`preflight.sh --ci`) as the ruleset-required check. Missing scanner tools
degrade to "skipped" unless `[security].strict = true` (air-gapped machines preseed DBs).

### Consequences
Good: exact-content guarantees, identical logic in all layers, fail-fast UX. Bad: TTL
means re-running preflight after 30 idle minutes; strict mode needs tool provisioning.
