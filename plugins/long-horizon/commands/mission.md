---
description: Manage durable missions — goals that outlive sessions, with structural resumability
argument-hint: "[new \"Title\" --steps \"a;b\" | list | show <id> | step-done <id> <n> | block <id> --on \"...\" | resume <id> | complete <id> | abandon <id> --why \"...\"]"
---

Operate on durable missions: goal state that outlives any session (ADR-0011).

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/mission.py" $ARGUMENTS
```

The judgement calls the tool cannot make for you:

- **Decomposition is the hard part.** Steps must be session-sized and verifiable — a fresh session
  takes the next open step cold, and each step's completion is a checkable fact. The
  `mission-planning` skill covers what makes a mission resumable versus a wish with a checklist.
- **State discipline is load-bearing.** Update the file the moment a step is true, block with the
  real reason the moment you stall, and commit the file with the work. The next session resumes
  from this file; leave it true.
- **`complete` refuses open steps — that is the design, not an obstacle.** The honest exits are
  finishing the steps or `abandon --why` with the real reason. Abandonment on the record beats a
  mission rotting as "active" or a completion that lies.

To execute in-flight work, delegate to the `mission-runner` agent; to see how blocked missions rank
against everything else worth doing, run `/frontier`.
