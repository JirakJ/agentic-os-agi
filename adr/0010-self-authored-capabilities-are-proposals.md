---
status: accepted
date: 2026-07-16
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [manifest/self-evolution, agent/evolution-strategist, skill/capability-proposal, command/evolve]
supersedes: []
superseded-by: []
---

# ADR-0010 — Self-authored capabilities are proposals, never auto-merges

## Context and Problem Statement

With verification (ADR-0008) and an experience buffer (ADR-0009) in place, the loop can mine
signals and generate candidate capabilities. The tempting last step is to close the loop fully:
let the system author the skill, run the evals, and if they pass, commit it — unsupervised
recursive self-modification of its own core logic. The question is whether "evals pass" is a
sufficient gate for the system to modify itself without a human or a review step in the loop.

## Decision Drivers

* Passing evals proves no *measured* regression, not correctness — a capability can pass every eval
  and still be wrong in a way no eval covers (ADR-0008's own coverage caveat)
* The blast radius of a self-authored core-logic change is the whole fleet's behaviour, and the
  change modifies the very system doing the authoring — errors can compound
* The governance layer already requires an ADR for behavioural change and an atomic commit per
  component; an unsupervised loop would either bypass those or auto-generate ADRs that justify
  nothing
* Autonomy is a spectrum, and the useful, safe band is "the system does the expensive
  work — mining, drafting, evaluating — and a gate stands before adoption", not "the system rewrites
  itself while you sleep"

## Considered Options

* Full closure: mine → author → eval → auto-commit, unsupervised
* Proposal gate: mine → author → eval → **present for adoption**, human or a distinct review step
  approves the merge
* No loop: keep authoring purely human-initiated

## Decision Outcome

Chosen option: "Proposal gate", because it captures almost all the leverage — the system does the
expensive, tedious work of noticing the gap, drafting the capability, and proving it does not
regress — while keeping a gate at the one step where an error is unrecoverable: modifying its own
core logic. The loop's output is a *proposal*: a drafted capability, its eval, and its evidence,
staged for adoption. Adoption is a deliberate act that goes through the existing governance path (an
ADR that actually reasons, an atomic commit), not an automatic consequence of a green eval run.

The `evolution-strategist` agent runs mine → propose → hand to `skill-author` → eval, and reports a
recommendation. It does not commit the capability to core logic on its own authority.

### Consequences

* Good, because the irreversible step — self-modification of core logic — always has a gate, so a
  capability that passes evals but is wrong in an uncovered way is caught before it ships
* Good, because it composes cleanly with governance: the proposal becomes a normal governed change
  at adoption, with a real ADR and an atomic commit, so the audit and rollback story is unchanged
* Good, because it is honest about what "evals pass" means — necessary, not sufficient — and puts a
  human or a review step exactly where that gap matters
* Bad, because the loop is not fully autonomous. It cannot improve the fleet unattended; it can only
  prepare improvements for a human to wave through, so the throughput of self-improvement is bounded
  by review capacity
* Bad, because a gate a human always rubber-stamps is a gate in name only. The proposal has to carry
  enough evidence — the signal, the eval delta, the diff — that review is real rather than reflexive,
  which puts a quality bar on the proposal artifact itself
* Bad, because it forgoes the most striking demo (a system that visibly rewrites itself) in favour
  of the defensible one (a system that proposes and proves, and is adopted deliberately)

### Confirmation

The gate holds if no capability enters core logic without an adoption step that produced a
reasoning ADR and an atomic commit, and if proposals carry enough evidence that a reviewer rejects
at least some of them on their merits. It is failing if adoption becomes reflexive — if every
proposal is merged unread — which means the proposal artifact is not carrying its evidence and the
fix is a richer proposal, not removal of the gate.

## Pros and Cons of the Options

### Full closure, unsupervised

* Good, because maximum autonomy and the most impressive behaviour
* Bad, because the one irreversible step has no gate, and "evals pass" is not correctness
* Bad, because it either bypasses governance or fills the ADR log with auto-generated justifications
  that defeat the purpose of having decision records at all

### Proposal gate

* Good, because it keeps the leverage and gates only the irreversible step
* Good, because it reuses governance for adoption
* Bad, because throughput is bounded by review, and the gate is only real if proposals carry evidence

### No loop

* Good, because zero new risk surface
* Bad, because it forgoes the entire point — a system that notices its own gaps and drafts its own
  capabilities is the thing being built; refusing the loop is refusing the goal

## More Information

The spectrum this sits on: the system is autonomous in *sensing, drafting and verifying*, and gated
in *adoption of core-logic change*. That band is deliberate — it is where the marginal error is
recoverable on one side and unrecoverable on the other. Revisit the gate only for capability classes
whose adoption is provably reversible and provably covered by evals; for those, a tighter loop may be
defensible, but core-logic self-modification is not one of them. See ADR-0008 (verification) and
ADR-0009 (experience buffer) for the two halves this record closes over.
