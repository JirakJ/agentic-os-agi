---
name: capability-proposal
description: Turn an improvement signal — a recurring workflow, a repeated failure, an eval regression, a coupling — into a concrete, buildable capability proposal that a skill-author can implement and governance can adopt. Use this whenever the user asks to "propose a capability", "what should we build next", "turn this pattern into a skill", "close this gap", or when an evolution cycle has surfaced signals that need shaping into proposals. Also use it when reviewing proposals from propose.py to judge which are worth implementing.
allowed-tools: Bash, Read, Grep
metadata:
  version: 1.0.0
  layer: L1-core
---

# Capability Proposal

Shape a raw signal into a proposal concrete enough to build and evidenced enough to justify
adopting. A proposal that is vague is un-buildable; a proposal without evidence is un-reviewable.

## Generate the raw proposals

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/propose.py"
```

This fuses mined signals with eval regressions and ranks them: regressions first (active harm),
then failures, workflows, couplings. Each carries its evidence — how many sessions, how often, the
eval delta. That output is the starting point, not the finished proposal.

## What makes a proposal buildable

A raw signal names a gap. A buildable proposal answers three more questions:

1. **What exactly is the capability?** Not "a skill for the edit-test pattern" but "a slash command
   `/skill-check <name>` that runs the skill's eval and reports pass/fail, so the edit-verify loop
   is one step instead of three." Name the artifact, its trigger, its output.
2. **Which plugin, and why there?** Use the plugin-selection rule from `skill-authoring`: it goes
   where its *failure* would matter most. A proposal that does not name its home is not ready.
3. **What is its eval?** This is the part that turns a proposal into something adoptable. Before the
   capability is built, define how you will know it works — the eval that will gate it (ADR-0008).
   A capability with no eval can regress undetected, so "propose the eval alongside the capability"
   is not optional.

## Grounding in the code

Signals are pointers, not implementations (ADR-0009): the trail records that a component was
edited, not the edit. So a proposal from a workflow signal *must* be grounded by reading the actual
sessions and the actual code:

```bash
grep -rl "<the component the signal names>" plugins/
```

Read what those sessions were actually doing. The proposal's design comes from the code, not from
the tool names in the trail. A proposal written from the signal alone will encapsulate a
coincidence.

## The evidence a proposal must carry

Because adoption is gated on review (ADR-0010), a proposal a reviewer cannot judge is a proposal
that gets rubber-stamped, which defeats the gate. Carry:

- **The signal**: what recurred, how often, across how many sessions.
- **The design**: the concrete artifact — name, trigger, behaviour, home plugin.
- **The eval**: how adoption will be verified, and what "no regression" means here.
- **The cost**: what this adds — a new component to maintain, a new dependency, a hook on the
  critical path. Every capability has a carrying cost; naming it is what makes the proposal honest.

## What a proposal is not

- It is not an implementation. The proposal is the spec; `skill-author` builds it. Keep them
  separate — a proposal that is already half-built has skipped the review the gate exists for.
- It is not a commitment. Most proposals should be *rejected* on review — that is the gate working,
  not failing. A loop where every proposal is adopted is a loop with no gate (ADR-0010).
- It is not a change. Adoption requires an ADR that reasons and an atomic commit. The proposal
  precedes both.

## Handing off

A shaped proposal goes to the `skill-author` agent to implement, then to `evalctl.py` to confirm no
regression, then — only then — through the normal governed adoption: an ADR, an atomic commit. The
proposal is the first link in that chain, not a shortcut around it.
