---
name: mission-planning
description: Decompose a multi-session goal into a durable mission with verifiable, session-sized steps, and maintain its state so any future session can resume it cold. Use this whenever work will outlive the current session, when the user says "let's make this a mission", "track this goal", "we'll finish this later", "plan this out over time", when starting something too large for one sitting, or when resuming, re-planning, blocking or closing an existing mission. Also use it to judge whether something should be a mission at all versus just done now.
allowed-tools: Bash, Read
metadata:
  version: 1.0.0
  layer: L2-episodic
---

# Mission Planning

A mission is goal state that outlives any session (ADR-0011): the objective, the decomposition, the
progress, the blockers — in one git-tracked file a cold session can resume from. Sessions are
stateless executors; the mission file is the memory of the goal. Planning well means writing that
file so a session with zero context can pick it up and act.

## Should this be a mission at all?

Not everything is. A mission earns its file when the work **cannot finish this session** and its
loss would cost direction. One-session work is just work — do it. A vague aspiration with no
decomposition is not a mission either; it is a note for the vault until it has steps. The test:
would a fresh session, given only this file, know what to do next and how to tell when it is done?

## Decomposing the goal

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mission.py" new "Title" \
  --objective "What done means, verifiably." --steps "first;second;third" --priority high
```

The parts that matter:

- **The objective states what *done* means, not what busy looks like.** "Every capability class has
  at least one eval" is verifiable; "improve eval coverage" is a mood. If completion cannot be
  checked, the mission cannot honestly complete.
- **Steps are session-sized.** A step a session cannot finish will straddle sessions and its state
  will lie in between. Split until each step fits one sitting; a fresh session should be able to
  take the next open step cold.
- **Steps are verifiable.** "Add the eval spec and its verifier; the suite runs it green" beats
  "work on evals". Each step's completion should be a checkable fact, ideally a commit.
- **Order encodes dependency.** Steps are executed top-down; if step 3 needs step 1's output, that
  is the order they appear in.

## Maintaining state — the discipline that makes it real

The whole design stands on one habit: **update state as you go, not at the end**. A session that
works but does not update the file leaves the next session resuming from a lie.

```bash
mission.py step-done m-0001 2 --note "committed as abc123"   # the moment it is true
mission.py block m-0001 --on "needs the upstream API key"     # the moment you stall
mission.py step-add m-0001 "handle the edge case found in 2"  # plans change; the file follows
```

Blocking requires a reason because the frontier ranks blocked intent (ADR-0013) — "blocked" with no
*on what* is a dead entry nobody can unblock. And commit the mission file with the work it
describes; `git log` over the file should read as the history of the goal.

## Closing honestly

`complete` refuses while steps are open — a mission with open steps is not done, and forcing it
would make the record lie. The honest exits are: finish the steps, or `abandon --why` with the real
reason. Abandonment is a first-class outcome, not a failure state; a goal that stopped being worth
pursuing should say so on the record rather than rot as "active".

When a mission completes, the durable *learning* moves out: knowledge to the vault
(`vault-capture`), decisions to an ADR. The mission file stays as the record of execution — it is
operational state, not the knowledge base (ADR-0011).
