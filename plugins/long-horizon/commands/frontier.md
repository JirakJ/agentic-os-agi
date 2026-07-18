---
description: Show the capability self-model and the evidence-ordered learning frontier — what the system can do, and what it should learn next
argument-hint: "[--json | --no-mine]"
---

Derive what this system should learn next, ordered by evidence (ADR-0012, ADR-0013).

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/frontier.py" $ARGUMENTS
```

For the underlying capability picture on its own:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/selfmodel.py"
```

Reading the output honestly:

- **The order is evidence severity**: weakness (measured harm) > blocked intent (stalled committed
  work) > coverage gaps (where regressions hide) > friction (repeated cost). Each item carries the
  evidence that put it there — interrogate the evidence, not the vibe.
- **"Unmeasured" never means "fine".** A plugin no eval exercises is ignorance on the record, and
  it ranks because a gap in coverage is a gap in safety (ADR-0008).
- **An empty frontier is the goal state.** Nothing weak, nothing blocked, everything measured,
  nothing recurring — a self-directing system is not obligated to invent work. New ambition enters
  as a mission, not a frontier edit.
- **The frontier orders; it does not authorise.** A frontier item still becomes a proposal, an
  implementation, an eval run, and a governed adoption (ADR-0010). Nothing here bypasses the gates.

The live derivation runs the eval suite (seconds, and it is the truth); the self-model's `--cached`
reads the last snapshot when speed matters more than freshness.
