---
status: accepted
date: 2026-07-16
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [manifest/self-evolution, skill/self-reflection, command/evolve]
supersedes: []
superseded-by: []
---

# ADR-0009 — The audit trail is the experience buffer for self-improvement

## Context and Problem Statement

A system that improves from its own experience needs that experience in a form it can mine: what
was done, in what sequence, to what, and whether it worked. The `audit-logger` hook already writes
an append-only JSONL trail of every tool call — actions, components touched, success flags. The
question is whether to mine that existing trail for improvement signals, or to build a separate,
richer instrumentation layer purpose-built for the learning loop.

## Decision Drivers

* The signal for "what capability is missing" is behavioural — repeated tool sequences, recurring
  failures, files always edited together — and that behaviour is exactly what the audit trail
  already records
* A second instrumentation layer means two sources of truth about what the fleet did, which drift
* The audit trail deliberately records actions, not payloads (ADR-0006), so mining it is
  privacy-preserving by construction — no secrets, no file contents, ever entered it
* Whatever mines experience must tolerate a sparse or absent trail — a fresh install has no history,
  and the loop must degrade to "nothing to propose yet" rather than fail

## Considered Options

* Mine the existing audit trail for improvement signals
* Build a separate, richer episodic-instrumentation layer for the learning loop
* Reconstruct experience from git history alone

## Decision Outcome

Chosen option: "Mine the existing audit trail", because the improvement signal is behavioural and
the audit trail is already a faithful, privacy-clean behavioural record — building a second one
would duplicate the substrate and introduce drift for signal the first one already carries. The
miner reads the trail plus git history and surfaces three signal classes: recurring tool n-grams
(candidate workflows), recurring failures (candidate fixes or guards), and co-edit clusters
(candidate compound capabilities).

Where the raw trail is too low-level, it is *enriched* at the source rather than replaced: an
optional `SessionEnd` hook appends a compact session-outcome record (goal, components, success) to
the same buffer, raising the signal without forking the store.

### Consequences

* Good, because there is one behavioural source of truth, and the learning loop reads the same trail
  the audit command reports from
* Good, because mining inherits the trail's privacy property — it physically cannot surface a secret
  or a file's contents, because those were never written
* Good, because it composes: the trail that answers "what happened, for compliance" also answers
  "what should we build next", from the same bytes
* Bad, because the audit trail is lossy by design. It records that `Edit` touched a component, not
  what the edit was, so the miner can propose "these files change together" but not "here is the
  refactor" — the proposal is a pointer, and turning it into a capability needs a step that reads
  the actual code
* Bad, because signal quality scales with usage. A fresh install has nothing to mine, so the loop is
  quiet until enough history accrues — self-improvement has a cold start
* Bad, because n-gram and co-edit mining over a personal-scale trail is heuristic. It will surface
  coincidences as candidate workflows, so proposals need ranking by evidence strength and a human or
  eval gate before they become capabilities (ADR-0010)

### Confirmation

Mining is working if a deliberately-repeated workflow (the same tool sequence run across several
sessions) is surfaced as a ranked signal, and if an empty or malformed trail yields "no signals"
rather than an error. It is mis-scoped if the signals it surfaces are dominated by coincidence over
genuine recurring patterns — which is a ranking and threshold problem, addressed in the miner, not a
reason to abandon the trail.

## Pros and Cons of the Options

### Mine the existing audit trail

* Good, because one source of truth, privacy-clean, already present
* Bad, because lossy — signals are pointers, not implementations

### Separate richer instrumentation layer

* Good, because it could capture edit diffs and intent, making signals richer
* Bad, because two behavioural stores that drift, and a second thing to keep privacy-clean — the
  audit trail's "actions not payloads" guarantee would have to be re-earned
* Bad, because it is a large build for signal the trail mostly already carries

### Reconstruct from git history alone

* Good, because git is already the source of truth for what changed
* Neutral, because git shows *what changed* but not *what was attempted-and-abandoned* or *what
  sequence of tools produced the change* — the behavioural signal is thinner
* Bad, because git commits are the *outcome* of work, so mining them misses the failures and
  retries that are the richest improvement signal

## More Information

The miner reads `${CLAUDE_PLUGIN_DATA}/.../audit/*.jsonl` (governance-gates' trail) and `git log`,
and writes ranked signals. Because the trail records actions not payloads, a signal names components
and frequencies, never contents. See ADR-0008 for why proposals are gated on verification, and
ADR-0010 for why the miner's output is a proposal rather than an automatic change.
