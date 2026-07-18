---
description: Inspect the autonomic loop — unverified core debt, last verification, staged proposals, kill switch
argument-hint: "[--json]"
---

Show what the autonomic nervous system currently holds (ADR-0014).

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/autonomic.py" $ARGUMENTS
```

How to read it:

- **Unverified core debt** is a session that changed core logic and has not yet passed a green
  suite run. The Stop reflex will demand payment before that session's turn may end — a standing
  entry here after a turn finished means the loop-guard window was used; verify manually
  (`/evals`) and clear the debt honestly.
- **A standing regression** outranks whatever the session came to do (ADR-0008): fix forward or
  revert (`release.py --pin`), then re-run the suite to confirm green. If the drop is intended,
  re-baseline deliberately and say so in the commit.
- **Staged proposals** were mined at a session's end and are offered exactly once at the next
  session start. They are proposals, not authorised work — the adoption gate (ADR-0010) is
  untouched by this layer.
- **The kill switch** (`AGENTIC_OS_AUTONOMIC=off`) silences every reflex without uninstalling
  anything. The system degrades to manual: every tool still works, nothing fires by itself. Being
  able to switch autonomy off cleanly is a feature, not an escape hatch — say why when you do.
