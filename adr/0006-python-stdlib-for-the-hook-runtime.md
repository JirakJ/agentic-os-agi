---
status: accepted
date: 2026-07-16
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [hook/secret-guard, hook/commit-adr-gate, hook/manifest-validator, hook/audit-logger, hook/core-change-tracker]
supersedes: []
superseded-by: []
---

# ADR-0006 — Hooks are Python stdlib, not bash + jq

## Context and Problem Statement

Hooks receive a JSON event on stdin and answer with an exit code or JSON on stdout. The community
default is bash piping through `jq`. These hooks do more than field extraction: git introspection,
path classification against glob sets, regex scanning, SemVer comparison, subprocess orchestration.
The runtime choice sets both the latency floor and the ceiling on what a gate can reasonably do.

## Decision Drivers

* Hooks run synchronously on the critical path and stack — every millisecond is paid on every tool call
* A hook that cannot be tested end-to-end is a hook that is wrong and nobody knows it
* Dependencies are liabilities: `brew install jq` is a step between a clone and a working system
* `commit_adr_gate` alone needs porcelain parsing, diff scanning and component grouping — that is
  not a `jq` filter, it is a program

## Considered Options

* bash + jq
* Python 3 stdlib
* A compiled binary (Rust/Go) shipped per platform
* Node.js

## Decision Outcome

Chosen option: "Python 3 stdlib", because the gates are programs rather than filters, and the
runtime that can express them is also the one already present on the target machine with no install
step.

Constraint that keeps the cost honest: **stdlib only**, and imports stay minimal (`json`, `os`,
`re`, `sys`, `subprocess`, `pathlib`, `fnmatch`). No PyYAML — `doctor.py` carries a ~40-line
frontmatter parser instead, because a dependency for the subset of YAML actually in use is a bad
trade.

### Consequences

* Good, because every hook is testable by piping a real payload into it: `echo '{...}' | python3
  secret_guard.py`. All eight secret-guard cases and the full commit-gate lifecycle are verified
  this way, against a real repo, not mocks
* Good, because zero install: `git clone` and the gates run
* Good, because the logic that needs to exist — porcelain parsing, glob classification, supersession
  chains — is expressible without contortion
* Bad, because Python cold start is ~30–50 ms versus ~5 ms for jq. With two PostToolUse hooks
  stacked, that is ~60–100 ms per file write. Real, and the reason `audit_logger` and
  `core_change_tracker` stay import-light and never call git
* Bad, because it assumes `python3` on PATH. On macOS that means Command Line Tools — safe here,
  but it is an assumption a distributed product would have to state explicitly

### Confirmation

Wrong if measured hook overhead exceeds 150 ms p95 per tool call, or if `python3` is ever absent on
a target machine. At 150 ms the split is: keep the hot path (secret guard, audit) in a compiled
binary, leave the cold path (validator, commit gate) in Python.

## Pros and Cons of the Options

### bash + jq

* Good, because ~5 ms cold start — the lowest achievable without compiling
* Good, because it is the community default, so examples abound
* Bad, because `jq` is an install step, and one that could not be performed in the environment
  where these hooks were built and tested — which means shipping them untested
* Bad, because `commit_adr_gate`'s logic in bash would be a 300-line unreadable liability

### Python 3 stdlib

* Good, because present on macOS, testable, and expressive enough for the actual logic
* Bad, because ~40 ms cold start on the critical path

### Compiled binary (Rust/Go)

* Good, because ~1 ms start and no runtime assumption at all
* Neutral, because it would fit the platform's performance-first bias
* Bad, because it needs a build step, per-platform artifacts and a release pipeline — for hooks
  that spend most of their wall-clock inside `git`, the win is noise
* Bad, because editing a gate would stop being "edit a file and rerun"

### Node.js

* Good, because JSON is native
* Bad, because ~80 ms cold start — worse than Python on the exact axis that motivated the question
* Bad, because it assumes a Node install for a system that otherwise needs none

## More Information

Measured overhead: single hook ~40 ms, PostToolUse pair ~85 ms on M-series. `manifest_validator`
scopes `doctor.py` to the touched component kind rather than running the full sweep, keeping it
inside its 25 s timeout with a wide margin.

Revisit if the hook set grows past roughly eight synchronous gates.
