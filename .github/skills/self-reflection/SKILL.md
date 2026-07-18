---
name: self-reflection
description: Reflect on a completed session or a stretch of work to extract durable lessons and improvement signals from the audit trail, rather than letting the experience evaporate. Use this whenever the user asks "how did that go", "what did we learn", "reflect on this", "what could be better", after finishing substantial work, when the user wants a retrospective, or when deciding whether a session surfaced something worth capturing or proposing. Also use it before running an evolution cycle, to ground proposals in what actually happened.
allowed-tools: Bash, Read
metadata:
  version: 1.0.0
  layer: L2-episodic
---

# Self-Reflection

Turn experience into learning before it evaporates. A session that solved a problem but left no
trace of *how* teaches the fleet nothing; reflection is the step that extracts the transferable
part.

## What reflection reads

The raw material is the audit trail — the append-only record of what the fleet did, from
governance-gates (ADR-0009). It records actions, not payloads: which tools ran, on which
components, whether they succeeded. That is enough to see the *shape* of a session without any
secret or file content ever being involved.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mine.py" --min-support 2
```

At low support this surfaces even one-off patterns — useful for reflecting on a single session
rather than a long trend.

## The reflection itself

Reflection is not summarising what happened. It is extracting what *transfers*. For a session, ask:

- **What was done repeatedly by hand?** A tool sequence run three times in one session is a
  capability the fleet is missing. The miner flags recurring sequences; a single session's repeats
  are visible at `--min-support 1`.
- **What failed, and did the failure recur?** A failure hit once is noise; hit repeatedly it is a
  gap. The trail's failure signals point at these.
- **What was learned that lives nowhere?** A decision, a constraint, a non-obvious fact discovered
  mid-session. If it is not in a commit, an ADR, or the vault, it is about to be lost — capture it
  (the `vault-capture` skill) or record the decision (the `adr-workflow` skill).
- **What would you do differently?** Not as self-criticism, but as a concrete signal: "the release
  failed because git-cliff was missing" becomes "propose a preflight check".

## From reflection to action

Reflection produces one of three outcomes, and naming which is the point:

1. **A durable fact or decision** → capture it (`vault-capture`) or record it (`adr-workflow`). The
   knowledge belongs in the knowledge base or the decision log, not in a fading session.
2. **An improvement signal** → hand it to the evolution loop (`propose.py`, or the `evolve`
   command). A recurring gap becomes a capability proposal.
3. **Nothing worth keeping** → say so and stop. Most sessions produce no durable lesson, and
   inventing one to seem productive pollutes the record. "Nothing to capture here" is a complete,
   honest reflection.

## What reflection is not

- It is not a transcript. Nobody rereads a play-by-play; the value is the extracted lesson.
- It is not self-flagellation. The signal is "here is a gap", not "here is a failing".
- It is not automatic capture. A hook cannot judge what transfers — that judgement is the skill.
  The system deliberately does not auto-write session summaries to the vault (ADR-0003), because a
  vault full of machine-generated reflections is noise that buries the hand-curated signal.

## Grounding proposals

Before an evolution cycle, reflect first. The miner surfaces signals; reflection is what turns a
signal into a *understood* gap. "These five sessions ran edit-test-edit" is a signal; "we lack a
tight edit-test loop for skills, and here is why it keeps coming up" is the reflection that makes
the resulting proposal worth adopting. A proposal without reflection is a pattern without a reason.
