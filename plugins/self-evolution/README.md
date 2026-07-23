# self-evolution

The self-improvement substrate (ADR-0008, ADR-0009, ADR-0010): a capability-eval harness with
regression tracking, an experience miner over the governance audit trail, and a proposal engine
that turns recurring patterns into concrete, buildable capability proposals. Verification comes
*before* self-authoring by design — a system that modifies itself without measuring the result is
taking a random walk — and the loop proposes; it never adopts. The one irreversible step (a
capability landing in core logic) stays a human decision, gated by a normal ADR and atomic commit.

## Components

| Component | Kind | Purpose |
|---|---|---|
| `commands/evals.md` (`/evals`) | command | Run the capability-eval suite; a drop below baseline is a revert signal, not a note-and-move-past |
| `commands/evolve.md` (`/evolve`) | command | Mine the audit trail for signals, generate ranked capability proposals |
| `agents/evolution-strategist.md` | agent | Runs sense → reflect → propose → verify → recommend; stops at the adoption gate |
| `skills/evaluation-authoring` | skill | Write a capability eval — spec + deterministic verifier — so a capability becomes measurable |
| `skills/capability-proposal` | skill | Turn a raw signal into a concrete, buildable, evidenced proposal |
| `skills/self-reflection` | skill | Extract durable lessons from a completed session's audit trail before the experience evaporates |
| `scripts/evalctl.py` | script | The eval harness: discovers `evals/*.json` **across every plugin in the marketplace**, runs verifiers, scores against the committed baseline |
| `scripts/mine.py` | script | Mines the governance audit trail for recurring workflows, repeated failures, couplings |
| `scripts/propose.py` | script | Fuses mined signals with the eval scorecard into ranked, evidenced proposals |
| `hooks/scripts/session_digest.py` | hook (`SessionEnd`) | Appends a compact, payload-free session digest to the experience buffer, precomputing each session's shape for the miner |
| `evals/adr-lifecycle.json` | eval (`governance`) | The decision-record tool allocates numbers, renders MADR, maintains supersession chains on both ends |
| `evals/recall-precision.json` | eval (`retrieval`) | Hybrid recall (`memory-obsidian`) ranks the answering note first, returns nothing for a genuine no-match |
| `evals/release-plan.json` | eval (`release`) | The release tool (`core-orchestration`) derives a correct SemVer bump from Conventional Commits, produces a valid dry-run plan |
| `evals/repo-health.json` | eval (`validation`), invariant | The marketplace validates clean — `doctor.py --quiet` exits 0 |
| `evals/secret-defense.json` | eval (`security`) | The secret guard (`governance-gates`) denies a known credential set and allows a known-safe set |
| `evals/baseline.json` | committed reference | Per-capability scores at the last known-good state; the harness's regression signal |

## The harness measures the whole marketplace, not just this plugin

`evalctl.py` globs `<plugin>/evals/*.json` for **every plugin manifest in the repo**, plus its own
`evals/` dir. `autonomic-loop`, `long-horizon`, `self-evolution` and (indirectly, via
`repo-health`/`release-plan`/`secret-defense`) `governance-gates` and `core-orchestration` all
contribute evals that this harness runs and scores together — nine evals total as of the current
baseline. This plugin owns the *mechanism*; the evidence lives wherever the capability it measures
lives. Evals are not tests (ADR-0008): a test asserts correctness now, an eval tracks a capability's
score across changes and flags degradation against `evals/baseline.json`.

## The loop

**sense → reflect → propose → verify → recommend/adopt.** `mine.py` reads the audit trail
(`governance-gates`' own trail plus this plugin's session digests); `propose.py` fuses the mined
signals with the current scorecard — regressions rank first, because an eval below baseline is
active harm, a capability the fleet already had, now degraded. A proposal without an eval attached
cannot be safely adopted; `evaluation-authoring` is what makes one. Most cycles should produce few
proposals, and some should produce none — a cycle that finds nothing worth building is a valid,
honest outcome, not a failure to be productive.

## How this relates to the rest of the marketplace

`self-evolution` depends on `core-orchestration` and `governance-gates`. It is the verification
substrate `autonomic-loop` calls automatically at `Stop` (`verify_on_change.py`) and at
`SessionEnd` (`evolution_pulse.py` reuses this plugin's `mine.py`/`propose.py`), and the evidence
base `long-horizon`'s self-model and frontier are derived from — this plugin measures, `long-horizon`
orders what the measurement implies should happen next. Adoption of anything this plugin proposes
still goes through `governance-gates`' `commit-adr-gate` like any other core change (ADR-0010): the
`evolution-strategist` agent recommends, verifies no regression, and stops — it does not commit a
self-authored capability to core logic on its own authority.

## Usage

```
/evals [--eval ID | --set-baseline | --history]
/evolve [--top N] [--min-support N]
```

A regression names the capability that dropped and by how much — bisect the commits since the
baseline SHA, fix forward or revert. No baseline yet means nothing to compare against; set one at a
known-good green state and commit `evals/baseline.json` as the reference point. When a regression
escapes the suite entirely, the response is to add the eval that would have caught it, never to
loosen the gate — coverage is the safety property (ADR-0008).

For a full cycle — mine, reflect on what the signals actually mean by reading the code, shape a
proposal, verify it, recommend it — delegate to the `evolution-strategist` agent rather than running
the scripts inline.
