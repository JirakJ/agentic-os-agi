---
status: accepted
date: 2026-07-18
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [manifest/governance-gates, manifest/core-guardrails, hook/secret_guard, hook/20_security_gate, hook/commit_adr_gate, hook/30_commit_integrity]
supersedes: []
superseded-by: []
---

# ADR-0022 — One gate runtime per concern; `governance-gates` keeps only what is unique

## Context and Problem Statement

Both merged lineages shipped a hook-based gate system, and they overlap on the two concerns
that matter most:

| Concern | `governance-gates` (lineage A) | `core-guardrails` (lineage B) |
| --- | --- | --- |
| secret paths | `secret_guard.py` path layer | `PreToolUse/20_security_gate.py` |
| secrets in shell | `secret_guard.py` bash layer | `20_security_gate.py` `_SECRET_IN_BASH` |
| secrets in written content | `secret_guard.py` content layer | *absent* |
| commit / ADR discipline | `commit_adr_gate.py` (Stop) | `PreToolUse/30_commit_integrity.py` |
| manifest + SemVer validation | `manifest_validator.py` | *absent* |
| audit trail | `audit_logger.py` | `20_telemetry_collector.py` |

Installed together, one mistake produces two denials with different wording and two telemetry
records for one event. Worse, the two secret scanners disagree on their escape hatch:
`20_security_gate.py` honours `/gate-unlock`, `secret_guard.py` does not — so the human-approved
override silently half-works.

## Decision Drivers

* A gate that fires twice trains people to disable gates
* Exactly one component must own each denial, so its wording and its escape hatch are coherent
* Neither plugin is a superset; deleting either loses real coverage
* `core-guardrails` is the battle-tested runtime: numbered dispatch ordering, `gates.py`
  enforcing/advisory modes, telemetry, fail-closed error handling, `/gate-unlock`

## Considered Options

* **Delete `governance-gates`.** Loses manifest/SemVer validation and content scanning — the
  two things this marketplace repo most needs, since it publishes plugins.
* **Delete `core-guardrails`.** Loses the dispatch runtime, telemetry and the override path.
* **Keep both, narrow `governance-gates` to its unique layers.** Chosen.

## Decision Outcome

`core-guardrails` is the gate runtime. It owns every concern it already covers: secret paths,
destructive and secret-bearing Bash, commit integrity, boundary writes.

`governance-gates` is narrowed to what the runtime does not do:

* `secret_guard.py` — **content layer only**. Never write a live credential into a file. The
  path and bash layers are deleted; `20_security_gate.py` owns them.
* `manifest_validator.py` — unchanged. Nothing else validates `plugin.json` / `marketplace.json`
  or catches a stale SemVer, and a stale version makes updates a silent no-op for installed users.
* `core_change_tracker.py` + `audit_logger.py` — unchanged. These feed `self-evolution`'s
  experience buffer (ADR-0009); `20_telemetry_collector.py` records gate decisions, which is a
  different dataset with a different consumer.
* `commit_adr_gate.py` — unchanged, and deliberately **not** merged into `30_commit_integrity.py`.
  They fire on different events for different reasons: the ADR gate runs at `Stop` and asks
  "was a decision made without a record?"; commit integrity runs at `PreToolUse` on `git commit`
  and asks "is this tree fit to commit?". Overlap in subject, not in question.

### Consequences

Good: one denial per mistake, one owner per concern, `/gate-unlock` behaves consistently
because only runtime-owned gates deny on secrets.

Bad: the split is not obvious from the plugin names — "governance-gates" now holds three
unrelated leftovers plus a content scanner, which is a weak cohesion story. If a third gate
concern arrives, revisit whether `manifest_validator` belongs in `core-orchestration` (which
already owns release discipline) and whether the audit pair belongs in `self-evolution`
(which is their only consumer). Not done now: moving hooks between plugins changes install
identity for anyone already running them, and this merge is disruptive enough.
