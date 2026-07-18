---
status: accepted
date: 2026-07-18
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [manifest/autonomic-loop, command/autonomic]
supersedes: []
superseded-by: []
---

# ADR-0014 — Autonomy is a hook-driven policy layer, separable from capability

## Context and Problem Statement

The system has the capabilities of a self-improving, long-horizon agent — evals, mining, proposals,
missions, a self-model, a frontier — but every one of them waits to be invoked. Skills trigger only
when the model decides their description matches; commands trigger only when a human types them. A
loop that runs only when someone remembers to run it is not autonomous; it is a well-organised
toolbox. The question is what mechanism makes the loop self-triggering, and where that triggering
logic should live.

## Decision Drivers

* Claude Code offers exactly one deterministic trigger surface: hooks. Skills are model-invoked
  (probabilistic), commands are human-invoked (optional); hooks fire structurally on session and
  tool events
* Verification that depends on being remembered is verification that will be skipped precisely
  when it matters — after a rushed change
* Triggering policy ("when does the suite run, what gets injected at session start") is a
  different kind of decision from capability ("how does the suite score") and changes on a
  different cadence
* Autonomy must be removable without losing ability: being able to switch the system back to
  manual is itself a safety property
* The existing Stop gate (ADR-0005) proved the pattern: a structural block at turn's end turns a
  discipline from aspirational into real

## Considered Options

* A dedicated policy plugin whose hooks orchestrate the capability plugins
* Extend each capability plugin with its own automation hooks
* Rely on skill descriptions and session-start briefs to prompt the model into running the loop

## Decision Outcome

Chosen option: "A dedicated policy plugin", named `autonomic-loop` — the autonomic nervous system:
it runs without being consciously invoked. Capability plugins stay pure tools; this plugin owns
*when they fire*:

- **PostToolUse** (`change_sentinel`) — an edit under `plugins/` or `adr/` marks the session
  "core-dirty". Cheap, silent bookkeeping.
- **Stop** (`verify_on_change`) — a core-dirty session runs the eval suite before it is allowed to
  finish. A regression (or a broken suite) blocks the stop with the failing detail and the fix
  path; a green run clears the dirty marker and records the verified state. Mirrors the commit
  gate: stopping with changed core logic and unverified capabilities is a dishonest stop.
- **SessionEnd** (`evolution_pulse`) — mines the trail and stages ranked proposals to a pending
  file. Non-blocking; the expensive sensing happens after the human has left.
- **SessionStart** (`autonomic_brief`) — injects the last verified state, any standing regression,
  and pending proposals into the next session, with explicit instructions. Silent when there is
  nothing to say.

A kill switch (`AGENTIC_OS_AUTONOMIC=off`) disables all four without uninstalling anything.

Two honest boundaries. First, hooks can inject *instructions* deterministically, but skill
selection remains model-invoked — the brief therefore names the skill to apply, which is the
strongest guarantee the primitives offer. Second, the loop senses, verifies, stages and blocks; it
never authors or adopts. ADR-0010's gate is untouched: nothing in this plugin commits a capability.

### Consequences

* Good, because the loop now runs itself: every core change is verified before the turn ends,
  every session ends by staging what was learned, every session starts knowing the system's state
  — with zero reliance on memory, habit, or the model choosing to
* Good, because policy is separable from capability: uninstall (or switch off) `autonomic-loop`
  and the system degrades to manual — every tool still works, nothing is lost but the automation.
  The reverse decomposition (automation woven through each plugin) cannot be switched off in one
  move
* Good, because the policy has one home: "when does verification run" is answered in one
  `hooks.json` and one decision record, not scattered across five plugins
* Bad, because Stop-time verification costs latency exactly when the user wants the turn to end.
  The suite is seconds today; if it grows, the gate will make every core-touching turn slower, and
  the pressure to weaken the gate will come from the gate's own success. The mitigation is scoping
  (verify only when core changed, cache while nothing changed), never loosening the block
* Bad, because a blocking Stop hook can spin; the `stop_hook_active` guard means the *second* stop
  attempt passes with the regression standing, trading loop-safety for a window where a dishonest
  stop succeeds once
* Bad, because injected briefs and instructions consume context in every session that has standing
  state, and a stale pending file injects stale guidance; silence-when-empty and staging files that
  clear on consumption bound this, but do not remove it
* Bad, because cross-plugin orchestration hard-wires this plugin to the others' CLI contracts; a
  breaking change in `evalctl` or `propose` now breaks automation, which is exactly the coupling
  the dependency pins (`^1.1.0`) exist to manage

### Confirmation

The layer is working if a deliberately-introduced regression cannot survive to a finished turn
undetected — the Stop gate names it before the human ever runs a command — and if switching the
kill switch restores the previous manual behaviour exactly. It is failing if the gate is routinely
bypassed via its loop-guard window or the brief is routinely stale — the first is a discipline
signal, the second a staging-lifecycle bug; neither is a reason to remove the layer.

## Pros and Cons of the Options

### Dedicated policy plugin

* Good, because separable, single-home policy, and capability plugins stay pure
* Bad, because it couples to the other plugins' CLI contracts and adds a fifth dependency edge

### Automation hooks inside each capability plugin

* Good, because each plugin is self-contained, automation included
* Bad, because the policy fragments — four `hooks.json` files answer "when does the loop run" — and
  turning autonomy off means editing every plugin
* Bad, because capability releases and policy changes get entangled in the same version stream

### Prompt the model via descriptions and briefs alone

* Good, because zero new hooks and zero Stop latency
* Bad, because it is probabilistic where the requirement is structural: the model *usually*
  running verification after a core change is exactly the "aspirational discipline" this system
  was built to replace (ADR-0005)

## More Information

The biological analogy is load-bearing: the autonomic nervous system runs breathing without a
decision to breathe, and its failure mode — running consciously — is not an upgrade. See ADR-0005
for the Stop-gate pattern this extends, ADR-0008 for why verification gates change, and ADR-0010
for the adoption gate this layer deliberately does not touch.
