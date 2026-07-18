---
status: accepted
date: 2026-07-18
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [manifest/memory-obsidian, manifest/memory-fabric, hook/session_memory, hook/10_memory_writer]
supersedes: []
superseded-by: []
---

# ADR-0021 — One memory model: hooks enqueue candidates, curation stays deliberate

## Context and Problem Statement

This repository is the merge of two independently-grown agentic OS lineages. Each brought a
memory design, and on the surface they contradicted each other:

* ADR-0003 defines **four layers** (L1 git core logic, L2 git durable episodic, L3 Obsidian
  vault, L4 SQLite index) and `memory-obsidian/hooks/scripts/session_memory.py` states in its
  own docstring that it *"deliberately does NOT write session summaries to the vault. What is
  worth keeping is a judgement call, and a hook cannot make it."*
* ADR-0019 defines **two tiers** (git repo, Obsidian vault) with queue-based capture, and
  `core-guardrails/hooks/scripts/SessionEnd/10_memory_writer.py` does exactly what the sentence
  above forbids: it pattern-matches the transcript and enqueues capture records automatically.

Installing both plugins means two hooks writing memory on `SessionEnd` under two mutually
exclusive philosophies. That is the sharpest logical contradiction in the merge and it cannot
be left to "whichever hook runs last".

## Decision Drivers

* One source of truth per piece of state, or reconciliation becomes a permanent tax (ADR-0003)
* Crash-safe capture under concurrent sessions is a real requirement, not a nicety (ADR-0019)
* A vault full of machine noise is worse than an empty one — it destroys retrieval precision
* Neither lineage's mechanism is wrong; they answer different halves of the question

## Considered Options

* **Pick one lineage, delete the other.** Loses either the four-layer separation (which L4
  retrieval depends on) or the flock-guarded queue (which is the only crash-safe writer we have).
* **Run both, accept duplicate writes.** Split brain: two vaults, two schemas, no answer to
  "where does this session's decision live?".
* **Separate the layer model from the capture mechanism.** Chosen.

## Decision Outcome

The two ADRs describe different axes and only *appear* to compete. Reconciled:

| ADR-0003 layer | ADR-0019 tier | Owner after this record |
| --- | --- | --- |
| L1 git core logic | Tier 1 | this repo |
| L2 git durable episodic (`memory/`) | Tier 1 | this repo |
| L3 Obsidian vault | Tier 2 (`~/jj-vault`) | memory-fabric (write), memory-obsidian (read) |
| L4 SQLite FTS index | *absent* | memory-obsidian — additive, not in conflict |

ADR-0003's layer model stands. ADR-0019 contributes the concrete vault location and the
crash-safe capture mechanism (per-session JSONL queue, atomic `O_APPEND`, single flock-guarded
drainer), which ADR-0003 deliberately left unspecified.

The philosophical conflict is resolved by narrowing ADR-0003 rather than overturning it:

> **Hooks may enqueue candidates. Hooks may not publish knowledge.**

`10_memory_writer.py` keeps running: it pre-filters to decision/blocker/retro/fix lines and
appends to a queue. That is a *candidate*, not a vault note — it is exactly the "judgement call"
being deferred rather than made. Materialization is the drainer's job, and refinement into
durable knowledge stays deliberate, via `memory-capture` / `memory-compact` / `vault-capture`.

`session_memory.py` keeps running unchanged: it refreshes the L4 index and writes nothing.
Its docstring's objection was to hooks writing *summaries into the knowledge layer*, which
nothing in this repo now does.

### Consequences

Good: both mechanisms survive with no overlapping writes; one vault, one schema, one index.
The `SessionEnd` pair is now complementary — one enqueues, one indexes.

Bad: the split between "candidate" and "knowledge" is a convention, not an enforced boundary.
If a future hook starts writing vault notes directly, this record is the thing it violates, and
nothing will fail loudly. A queue whose drainer never runs is silent data loss — the drainer's
health is worth a check in `make doctor` before this is load-bearing.
