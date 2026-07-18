---
description: Run the capability-eval suite and report scores and any regression against baseline
argument-hint: "[--eval ID | --set-baseline | --history]"
---

Run the capability evals — the verification substrate that makes self-improvement safe (ADR-0008).

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/evalctl.py" $ARGUMENTS
```

Evals are not tests. Tests assert correctness now; evals track each capability's score across
changes and catch degradation against a committed baseline. A run that drops below baseline exits
non-zero — that is a revert signal, not a warning to note and move past.

Read the result:

- **A regression** names the capability that dropped and by how much. Bisect the commits since the
  baseline SHA, find the change that caused it, and fix forward or revert (`release.py --pin`). A
  regression is the loop's stop condition.
- **A failing eval** carries a `detail` naming the exact sub-check that broke — act on that, not on
  the aggregate.
- **No baseline yet** means nothing to compare against. Set one at a known-good green state with
  `--set-baseline`, and commit `evals/baseline.json` as the reference point.

When a regression escapes the suite entirely — something broke that no eval covered — the response
is to add the eval that would have caught it, never to loosen the gate. Coverage is the safety
property; a gap in coverage is a gap in safety (ADR-0008).
