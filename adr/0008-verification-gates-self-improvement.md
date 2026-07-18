---
status: accepted
date: 2026-07-16
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [manifest/self-evolution, skill/evaluation-authoring, command/evals]
supersedes: []
superseded-by: []
---

# ADR-0008 — Self-improvement is gated on verification, not the reverse

## Context and Problem Statement

The system can already author skills and agents (the `skill-author` agent). The step toward a
system that compounds capability is to let it author them *in response to its own experience* —
observe a repeated failure or a repeated manual task, propose a capability, adopt it. But a system
that modifies itself without a way to measure whether a modification helped is not improving; it is
taking a random walk, and every self-authored change is as likely to degrade the fleet as to
improve it. The question is what has to exist *before* the self-authoring loop is safe to run.

## Decision Drivers

* A self-modification with no measurable outcome is indistinguishable from noise — you cannot keep
  the good ones and revert the bad ones if you cannot tell which is which
* The failure mode is silent: a self-authored skill that subtly degrades recall or breaks a manifest
  does not announce itself; it just makes the fleet quietly worse
* Regression is the thing to catch, and regression is a property of a *trajectory*, not a point —
  it needs a baseline to measure against
* The governance layer already makes every change atomic and revertible (ADR-0002, ADR-0005); what
  it does not do is tell you whether a change was an improvement

## Considered Options

* Let the loop propose and adopt capabilities, measure quality later
* Build a capability-eval harness first; gate every self-authored change on "no regression against
  baseline"
* Require a human to approve every self-authored capability, no automated measurement

## Decision Outcome

Chosen option: "Eval harness first, gate on no-regression", because it is the only option that lets
the system distinguish an improvement from a degradation *at adoption time*, which is the
precondition for keeping the loop from walking into decay. Verification is not a feature added
alongside self-improvement — it is the foundation self-improvement stands on, so it is built first
and the loop is wired to fail closed when it is absent.

Concretely: capabilities are defined as eval specs with **deterministic verifiers**; `evalctl.py`
runs them, records a scored snapshot per git SHA to a ledger, and compares against a named baseline.
A self-authored capability is adopted only if the full suite — the existing evals plus the new
capability's own eval — shows no regression below baseline. A regression is a revert signal
(`release.py --pin`), not a warning to note and move past.

### Consequences

* Good, because every self-authored change now has a pass/fail gate rooted in measurement, so the
  loop can keep improvements and reject degradations mechanically
* Good, because the regression suite catches the silent failure — a change that breaks an unrelated
  capability is caught by that capability's eval, not discovered weeks later
* Good, because it composes with the governance gates: verification answers "did it get better",
  governance answers "is it atomic and justified", and adoption requires both
* Bad, because it front-loads the unglamorous work. The eval harness must exist and have real
  coverage before the self-authoring loop delivers any value, so the first phase is verification
  with nothing visibly "intelligent" to show for it
* Bad, because an eval suite is only as good as its coverage. A capability with no eval can regress
  undetected, so "add an eval" becomes a standing obligation and a gap in coverage is a gap in
  safety
* Bad, because deterministic verifiers cannot score everything. Model-dependent qualities (does a
  skill make Claude reason better) need a verifier against a produced artifact, which is weaker than
  a script-driven check and needs the artifact to exist first

### Confirmation

The gate is working if no self-authored capability is ever adopted while any eval sits below
baseline, and if a deliberately-broken capability (one that breaks `doctor`) is caught by the suite
before adoption. It is mis-designed if capabilities are regularly adopted that later prove to have
regressed something no eval covered — which means coverage is the problem, and the response is an
eval, not a loosened gate.

## Pros and Cons of the Options

### Propose and adopt, measure later

* Good, because the loop delivers visible self-authoring immediately
* Bad, because "later" never comes with the context that made the regression cheap to catch, and by
  then the fleet has built on top of the degraded capability
* Bad, because it is precisely the random walk this record exists to prevent

### Eval harness first, gate on no-regression

* Good, because self-modification becomes measurable and therefore reversible-on-evidence
* Good, because it reuses the governance substrate rather than duplicating it
* Bad, because coverage is a permanent obligation and the payoff is deferred

### Human approves every capability

* Good, because a human catches things no eval encodes
* Neutral, because human review is worth keeping *as well*, for adoption of core-logic changes
* Bad, because it does not scale and it does not compose into an automated loop — the whole point is
  a system that improves faster than a human can hand-approve each step. Human-in-the-loop for
  adoption, yes; human-as-the-only-measurement, no

## More Information

The eval harness measures the system's *functional* capabilities via deterministic verifiers and
tracks them as a regression suite across changes — distinct from `tests/`, which assert correctness
at a point in time. Tests answer "is this correct now"; evals answer "did the fleet get worse at
anything since the baseline". See ADR-0010 for why the loop proposes rather than auto-merges, and
ADR-0009 for where the improvement signal comes from.
