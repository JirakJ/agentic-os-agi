---
status: accepted
date: 2026-07-16
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [hook/commit-adr-gate, hook/manifest-validator, skill/commit-discipline, skill/adr-workflow]
supersedes: []
superseded-by: []
---

# ADR-0005 — Hooks enforce atomic commits and decision records at Stop

## Context and Problem Statement

ADR-0002's rollback story depends entirely on commits being atomic per component — `git revert
<sha>` restores one skill only if that commit touched one skill only. Discipline that depends on
remembering is discipline that decays: three months in, a session ends with four components dirty,
and the rollback lever silently stops working. The question is where to put the enforcement, and
how hard.

## Decision Drivers

* The rollback guarantee is worthless if it holds only when someone remembers
* Enforcement must fire before the state is lost — after the turn ends, the ledger of what changed
  is gone
* A gate that fires wrongly gets disabled, and a disabled gate enforces nothing. False-positive
  cost is asymmetric and high
* Hooks run synchronously and stack; the budget is ~200 ms per hook
* Claude must be able to *resolve* a block itself, not just report it to the human

## Considered Options

* Documentation only — write the discipline into the skills and trust it
* PreToolUse block on any core edit until an ADR exists
* Stop/SubagentStop gate: block turn completion while core logic is dirty
* Server-side only: a CI check on push

## Decision Outcome

Chosen option: "Stop/SubagentStop gate", because it is the last moment at which the session still
knows what changed and the first at which "should this have been committed?" has a definite answer.
Earlier is guesswork; later is too late.

Two checks: dirty core logic always blocks; a *behavioural* change without a decision record also
blocks. Prose edits and version bumps are exempt — the marker set keys on contract-shaped diffs
(`allowed-tools`, `description`, `dependencies`, blocking rules), not on any edit.

`stop_hook_active` short-circuits the gate on retry so a block cannot spin.

### Consequences

* Good, because the rollback guarantee is now structural rather than aspirational
* Good, because the block carries the exact `git add` / `git commit` lines per component, so Claude
  fixes it in the same turn instead of bouncing to the human
* Good, because the same hook runs on `SubagentStop`, so delegated work is held to the identical
  standard — an agent cannot launder a sloppy commit
* Bad, because a genuinely exploratory session now ends in a block. `git checkout -- <paths>` is
  the escape, and it must be documented where people will actually find it
* Bad, because the behavioural-marker regex set is a heuristic. It will occasionally demand an ADR
  for a rename, and occasionally miss a semantic change with an innocent diff. It is tuned toward
  false positives on the theory that an unnecessary ADR costs five minutes and a missing one costs
  a year
* Bad, because the gate only sees the marketplace repo. Core logic edited elsewhere is unguarded

### Confirmation

The gate is mis-tuned if it blocks a turn that genuinely needed no commit more than once a week, or
if a month of history contains any commit touching two components. The first means the markers are
too eager; the second means the gate is being worked around.

## Pros and Cons of the Options

### Documentation only

* Good, because zero latency, zero false positives, zero maintenance
* Bad, because it fails exactly when it matters: late in a long session, when attention is gone
* Bad, because ADR-0002's rollback lever degrades silently — you find out it is broken when you
  need it

### PreToolUse block until an ADR exists

* Good, because nothing uncommitted is ever written
* Bad, because it makes exploration impossible — you cannot know whether a change needs an ADR
  before you have made it
* Bad, because it fires on every edit; the false-positive rate would guarantee the hook gets turned
  off within a day

### Stop/SubagentStop gate

* Good, because it fires once per turn, when the answer is knowable
* Good, because it covers subagents identically
* Bad, because it is the last line of defence — bad state exists on disk until the gate catches it

### CI check on push

* Good, because it cannot be bypassed locally and it sees the whole history
* Neutral, because it is worth adding *as well* — and it is (see `.github/workflows/validate.yml`)
* Bad, because it fires minutes-to-hours after the mistake, by which point the session context that
  would have made the commit easy to write is gone

## More Information

Both `Stop` and `SubagentStop` are wired to the same script. The gate deliberately does not run on
`PreToolUse`: blocking a write because a *future* commit might be wrong is a category error.

Revisit if the false-positive rate on the ADR check exceeds roughly one per week — at that point the
markers should narrow to `allowed-tools` and blocking-rule changes only.
