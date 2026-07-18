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

# ADR-0013 — The learning frontier orders what to learn next by evidence, not ambition

## Context and Problem Statement

The evolution loop (ADR-0008..0010) answers "given these signals, what could we build". It does not
answer the prior question a self-directing system needs: *of everything that could be improved,
what should be learned next, and why that first*. Without an ordering, self-improvement is
reactive — it follows whatever signal fired most recently — or aspirational, following whatever
sounds most impressive. Both waste the scarcest resource, which is verified adoption capacity
(ADR-0010 bounds throughput by review). The question is what is allowed to rank the learning
agenda.

## Decision Drivers

* Review capacity is bounded, so ordering is not cosmetic — building the wrong thing first crowds
  out the right thing
* Three evidence streams already exist under discipline: measured weakness (eval scores and
  regressions, ADR-0008), measured ignorance (coverage gaps from the self-model, ADR-0012), and
  blocked intent (missions stuck on a missing capability, ADR-0011)
* Ambition-driven agendas ("build the impressive thing") are how systems accrete capabilities
  nobody needed while known weaknesses persist
* The frontier must be recomputable and explainable: every item must carry the evidence that put
  it there, or the ranking cannot be reviewed and becomes an oracle

## Considered Options

* Rank from evidence: regressions and weakness first, then blocked missions, then coverage gaps,
  then observed friction
* Rank by human-assigned priority alone
* No frontier; let the evolution loop's per-signal ranking stand

## Decision Outcome

Chosen option: "Rank from evidence", with a fixed severity order reflecting real urgency:

1. **Weakness** — a capability scoring below threshold or regressed: the system is measurably bad
   at something it claims to do; that is active, quantified harm.
2. **Blocked intent** — a mission stuck on a missing capability: committed work is stalled, and the
   stall is attributable.
3. **Coverage gap** — a present-but-unmeasured capability: a place regressions can hide (a gap in
   coverage is a gap in safety, ADR-0008).
4. **Friction** — recurring mined failures: cost paid repeatedly, but the fleet still functions.

`frontier.py` fuses the self-model, the missions, and the miner's signals into that ordered agenda,
each item carrying its evidence and a suggested next action. The frontier feeds the evolution loop;
it does not replace its gates — a frontier item still becomes a proposal, an implementation, an
eval run, and a governed adoption.

### Consequences

* Good, because "what should we learn next" gets a reviewable, recomputable answer grounded in the
  same evidence the rest of the system runs on — the agenda is derived, like the self-model, never
  asserted
* Good, because it closes the autonomy loop: self-model says where the system is weak, missions say
  where it is stuck, the frontier orders the response, and the evolution loop executes it under its
  existing gates
* Good, because every item is explainable — the review that adoption requires (ADR-0010) can
  interrogate *why this first*, not just *whether this*
* Bad, because evidence-only ranking is conservative by construction: a genuinely valuable
  capability nothing yet measures, blocks, or fails at will rank low or not appear. Vision does not
  emerge from a frontier; the human supplies it, typically by creating a mission — which then
  surfaces through the blocked-intent stream
* Bad, because the severity order is a judgement frozen into code; a context where a blocked
  flagship mission matters more than a minor regression is mis-served by the default and needs the
  human to override, which is friction
* Bad, because a frontier is only as current as its inputs — a stale self-model or unmaintained
  missions produce a confidently wrong agenda, so the frontier inherits the discipline dependencies
  of ADR-0011 and ADR-0012

### Confirmation

The frontier is working if the top items, read cold, are defensible to a reviewer from their
attached evidence alone, and if closing the top item measurably moves an eval score, unblocks a
mission, or removes a coverage gap. It is failing if the agenda is dominated by items nobody acts
on — which means the evidence streams are stale or the threshold is miscalibrated, and the fix is
upstream, not a hand-reordered list.

## Pros and Cons of the Options

### Evidence-ranked frontier

* Good, because reviewable, recomputable, and grounded in existing discipline
* Bad, because conservative — it cannot originate vision, only order responses to evidence

### Human priority alone

* Good, because vision and context the evidence lacks
* Bad, because it silently decays into whatever was last prioritised, and known regressions wait on
  a human noticing them — the system stops directing its own learning, which is the property being
  built

### No frontier

* Good, because one less derived view to maintain
* Bad, because the evolution loop then optimises locally per signal with no global ordering, and
  review capacity is spent in whatever order signals happen to fire

## More Information

The frontier is deliberately a *reader* of the three streams, not a store: it owns no state, so it
cannot drift from its inputs. Human vision enters the system as a mission (ADR-0011), not as a
frontier edit — that keeps exactly one place where intent lives. See ADR-0008 for why coverage
gaps rank as safety issues, and ADR-0010 for the gates every frontier item still passes through.
