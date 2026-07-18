---
status: accepted
date: 2026-07-18
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [manifest/long-horizon, skill/self-assessment, command/frontier]
supersedes: []
superseded-by: []
---

# ADR-0012 — The capability self-model is derived from evidence, never asserted

## Context and Problem Statement

Planning — which mission to take, which proposal to build, what to delegate — presupposes an answer
to "what is this system actually good at". That answer can be asserted (a hand-written capability
list) or derived (computed from the eval scorecard, the component inventory, and the audit trail).
Asserted self-models drift: the list says "strong at retrieval" long after a regression, or claims
a capability no eval has ever exercised. A system whose self-image diverges from its measured
reality plans confidently and fails predictably. The question is what the self-model is allowed to
be built from.

## Decision Drivers

* The failure mode to prevent is *confident miscalibration* — believing a capability exists or is
  strong when the evidence says otherwise
* The evidence already exists and is maintained under discipline: eval scores against a baseline
  (ADR-0008), the component inventory (validated by doctor), and the audit trail of what actually
  gets used (ADR-0009)
* A derived model is rebuildable and therefore cheap to keep honest; an asserted model is a second
  source of truth that must be manually synchronised with reality
* Absence of evidence is itself signal: a capability with no eval is not "assumed fine", it is
  *unmeasured*, and the model must say so

## Considered Options

* Derive the self-model from evals + inventory + usage, on demand
* Maintain a hand-curated capability manifest
* Hybrid: derived scores plus hand-written capability descriptions

## Decision Outcome

Chosen option: "Derive on demand", because it makes miscalibration structurally difficult: the
model cannot claim strength an eval contradicts, cannot claim existence the inventory contradicts,
and must surface what is unmeasured as unmeasured. The self-model is a *view*, like the retrieval
index (ADR-0003's L4): computed from sources of truth, never itself a source of truth, and
regenerated rather than edited.

Concretely: `selfmodel.py` reads the current eval scorecard (running the suite, or a supplied one),
the committed baseline for trend, the plugin inventory for what exists, and the audit trail for
what is used — and emits per-capability scores with trend, coverage gaps (plugins no eval
exercises), and an evidence-thinness flag where a capability rests on a single eval.

### Consequences

* Good, because the self-model is calibrated by construction: it can only claim what the evidence
  supports, and it degrades honestly ("unmeasured") where evidence is absent
* Good, because it is rebuildable derived data — no synchronisation burden, no drift, no second
  source of truth to govern
* Good, because coverage gaps become first-class output: "no eval exercises this plugin" is exactly
  the input the learning frontier needs (ADR-0013), so honesty about ignorance feeds the agenda
* Bad, because the model is only as good as the eval suite. Thin coverage yields a thin self-model,
  and a capability whose eval measures the wrong thing yields a *precisely wrong* self-assessment —
  the model inherits every weakness of its evidence
* Bad, because deriving on demand costs a suite run when freshness matters; the cached path (last
  ledger snapshot) trades freshness for speed and must say which it is doing
* Bad, because some real capabilities — judgement, prose quality, model-dependent behaviours —
  have no deterministic eval yet, so the model will understate the system precisely where
  measurement is hardest. That understatement is the honest choice, but it is a known bias

### Confirmation

The model is working if its claims track eval reality with no manual synchronisation — a regression
shows as a weakened capability on the next derivation, a new evaluated capability appears without
anyone editing a manifest. It is failing if agents route around it because it is stale or wrong —
which points at coverage or eval quality, and the fix is better evidence, never a hand-edited
override.

## Pros and Cons of the Options

### Derived on demand

* Good, because calibration is structural and drift is impossible
* Bad, because inherits eval-coverage limits and costs a run for freshness

### Hand-curated manifest

* Good, because it can describe capabilities no eval measures
* Bad, because it *will* drift — the whole failure mode this record exists to prevent — and keeping
  it synchronised is unpaid, undone work

### Hybrid

* Good, because descriptions add context scores lack
* Bad, because the hand-written half still drifts, and a model that is half-evidence half-assertion
  makes it impossible to know which half a given claim comes from — worse than either pure option

## More Information

The self-model deliberately reports three distinct things and never conflates them: *measured*
(eval-scored, with trend), *present but unmeasured* (in the inventory, no eval — a coverage gap),
and *used* (audit-trail frequency, which is engagement, not quality). See ADR-0013 for how the
frontier consumes all three.
