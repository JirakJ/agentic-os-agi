---
status: superseded
date: 2026-07-18
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [script/skill-budget-lint]
supersedes: []
superseded-by: [0024]
---

# ADR-0023 — The full distribution does not fit a 200k listing budget; install a subset

## Context and Problem Statement

Merging the two lineages produced 11 plugins carrying ~30 skills. Every installed skill
contributes `name + description` to the always-on skill listing, which is charged against the
context window of *every* session before any work happens. `scripts/skill-budget-lint.py`
measures this and, on the merged tree, reports:

```
skill-budget-lint: 3383 tokens = 169% of 2000-token listing budget
FAIL: over 90% - trim descriptions or split plugins.
```

The 2000-token budget is 1% of a 200k context. The number is not arbitrary and the failure is
not a false positive: on a 200k runtime, installing all 11 plugins really does spend 1.7% of
the window on a menu.

## Decision Drivers

* A guardrail that gets raised the first time it fires is not a guardrail
* The budget's denominator is a property of the runtime, not of this repo — 1% of 1M is 10000
* This repo is a *marketplace*. Nobody is required to install everything, and ADR-0002 already
  makes the plugin the unit of distribution
* Trimming ~30 descriptions to fit degrades skill selection, which is the one thing those
  descriptions exist to do

## Considered Options

* **Raise the constant to fit.** Silently converts a real constraint into a rubber stamp.
* **Trim every description until it fits.** Buys ~1400 tokens by making the router worse at
  routing. The descriptions are load-bearing.
* **Split the marketplace back into two repos.** Undoes the merge this repo exists to be.
* **Keep the strict default, make the denominator explicit, install a subset.** Chosen.

## Decision Outcome

`skill-budget-lint` keeps its conservative 200k default, so the gate still fails loudly for
anyone on a small-context runtime. The denominator becomes an explicit input:

```bash
AGENTIC_OS_CONTEXT_TOKENS=1000000 python3 scripts/skill-budget-lint.py   # 3383 = 34%, passes
```

Guidance that follows from the measurement:

| Runtime context | What fits |
| --- | --- |
| 200k | a subset — core-guardrails + memory-fabric + one domain plugin |
| 400k | most of the distribution |
| 1M | all 11 plugins, at ~34% of the listing budget |

The full-install case is therefore *supported but declared*, not assumed. `make validate` on a
default shell will fail on this repo until the variable is set, and that is the intended
behaviour: it forces the person installing to answer "what context am I on?" once.

### Consequences

Good: no guardrail was weakened to make a merge look clean. The real number (3383 tokens) is
recorded, reproducible, and fails by default.

Bad: the repo's own `make validate` is red out of the box, which is a bad first impression and
will tempt someone to export the variable in CI and forget why. If that happens, the gate is
dead in exactly the way this record tried to prevent. A better long-term fix is to measure the
*installed* set rather than the repo's set — the lint currently globs `plugins/*/skills/*` and
so charges you for plugins you never installed. That is the real bug; this record only makes
the constraint honest until someone fixes the measurement.
