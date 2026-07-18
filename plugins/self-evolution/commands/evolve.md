---
description: Run a self-improvement cycle — mine the audit trail for signals and generate ranked capability proposals
argument-hint: "[--top N] [--min-support N]"
---

Run a self-improvement cycle: mine accumulated experience for signals, then turn them into ranked,
evidenced capability proposals.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/propose.py" $ARGUMENTS
```

Read the proposals with judgement, do not act on them mechanically:

- **Regressions rank first.** An eval below baseline is active harm — a capability the fleet already
  had, now degraded. Fix or revert (`release.py --pin`) before building anything new.
- **A proposal is a pointer, not a plan.** The audit trail records tools, not edits (ADR-0009), so a
  workflow proposal names a gap the sessions revealed — the actual design comes from reading the
  code those sessions touched. Ground it before building it.
- **Most proposals should be declined.** A cycle that surfaces ten candidates and adopts one is the
  gate working. Adopting all ten is a gate in name only (ADR-0010).

For a proposal worth building, hand it to the `skill-author` agent, then run `/evals` to confirm no
regression before adoption. Adoption is a governed decision — an ADR that reasons, an atomic commit
— not an automatic consequence of a green run. This command proposes; it does not change the system.

If it surfaces nothing, that is a valid outcome. A self-improving system is not obligated to change
to prove it is alive; sometimes the honest read is that nothing recurring is worth encapsulating yet.
