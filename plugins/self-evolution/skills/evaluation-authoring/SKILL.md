---
name: evaluation-authoring
description: Write a capability eval — a spec with a deterministic verifier — so a capability can be measured, regression-tracked, and used to gate self-improvement. Use this whenever a new skill, agent or capability is added and needs an eval, whenever the user says "write an eval for this", "how do we test this capability", "add this to the regression suite", or when a capability was adopted without one and now has a coverage gap. Also use it when an eval is flaky or measures the wrong thing and needs to be rewritten.
allowed-tools: Bash, Read, Write, Edit, Grep
metadata:
  version: 1.0.0
  layer: L1-core
---

# Evaluation Authoring

An eval is how a capability becomes measurable, and measurement is the precondition for safe
self-improvement (ADR-0008). A capability with no eval can regress undetected — so every capability
worth keeping is a capability worth an eval, and "add an eval" is a standing obligation, not a
nice-to-have.

## Evals versus tests

They are different tools (ADR-0008). `tests/` assert correctness at a point in time — does this
function do the right thing right now. Evals track a capability's *score across changes* and catch
degradation — did the fleet get worse at this since the baseline. A capability can pass every unit
test and still regress on a dimension the tests do not measure; the eval, tracked against a
baseline, is what catches that.

## The eval spec

Evals live in `${CLAUDE_PLUGIN_ROOT}/evals/*.json`:

```json
{
  "id": "recall-precision",
  "capability": "retrieval",
  "kind": "invariant | script | artifact",
  "description": "Hybrid recall ranks the answering note first, and is empty on a no-match.",
  "verifier": { "type": "...", ... },
  "weight": 1.0
}
```

`id` is unique and stable; `capability` groups related evals into a scored dimension; `description`
says what passing means.

## Choosing a verifier

The verifier is the ground truth, so it must be **deterministic** — same inputs, same result,
every run. Three types, in order of preference:

**`exit_zero`** — run a command; pass iff it exits 0. For invariants that already have a checker:

```json
"verifier": { "type": "exit_zero",
  "command": ["python3", "${REPO_ROOT}/plugins/core-orchestration/scripts/doctor.py", "--quiet"] }
```

**`script`** — run a verifier that builds temp state, exercises the capability, and prints one JSON
line `{"pass": bool, "score": float, "detail": str}`. For capabilities you can drive without a
model — the release tool, the ADR tool, retrieval, the secret guard. This is the workhorse:

```json
"verifier": { "type": "script",
  "script": "${CLAUDE_PLUGIN_ROOT}/evals/verifiers/recall_precision.py" }
```

The verifier locates the repo root itself, builds a fixture, drives the capability as a black box,
and scores it. Look at `evals/verifiers/` for the pattern — each is self-contained, uses a temp
dir, and asserts real behaviour, never a mock.

**`artifact`** — run a verifier against a file an agent produced (`--artifact PATH`). For
model-dependent capabilities whose quality only shows in a produced output. Weaker, because it
needs the artifact to exist first, but it is the honest option when the capability's value is
something only the model can produce (does this skill make Claude cite prior decisions). Score the
artifact deterministically; do not have the verifier itself call a model.

## Scoring

Return a score in [0, 1]. Binary is fine (`1.0` pass, `0.0` fail) and often right. A graded score
(fraction of sub-checks that passed) is better when a capability degrades partially — the
`secret-defense` eval scores the fraction of its battery that behaves correctly, so weakening one
check shows as `0.92`, not a cliff to `0.0`. Graded scores make regressions visible earlier.

## The failing detail matters

When an eval fails, its `detail` is what a human or the loop reads to act. "failed: deny .env" tells
you exactly what broke; "assertion error" tells you nothing. Make the detail name the specific
sub-check that failed.

## Running and baselining

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/evalctl.py"                 # run the suite
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/evalctl.py" --eval <id>     # one eval, while iterating
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/evalctl.py" --set-baseline  # snapshot as the reference
```

The baseline is the reference every future run compares against. Set it when the suite is green and
the capabilities are known-good; commit `evals/baseline.json` as the reference point. A run that
drops below baseline exits non-zero — that is the revert signal the loop gates on.

## When to add one

- A new capability is added → its eval ships with it. A capability without an eval is a coverage
  gap, and a coverage gap is where a regression hides.
- A regression slipped through → the thing that regressed had no eval, or the eval did not cover the
  dimension that broke. Add the eval that would have caught it. The response to an escaped
  regression is always an eval, never a loosened gate (ADR-0008).
- A bug is fixed → an eval that reproduces the bug ensures it stays fixed, exactly as a regression
  test would, but tracked across the capability's whole trajectory.
