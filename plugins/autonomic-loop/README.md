# autonomic-loop

The autonomic nervous system (ADR-0014): hook-driven policy that makes the rest of the OS
self-triggering instead of waiting to be invoked. It ships **no capability of its own** — no
agents, no skills, nothing that authors anything. Everything it does is wire four other plugins'
tools to Claude Code's event surface so the discipline they define fires by itself instead of
depending on someone remembering to run `/evals` or `/frontier`.

## Components

| Component | Event | Purpose |
|---|---|---|
| `hooks/scripts/change_sentinel.py` | `PostToolUse` (Write\|Edit\|MultiEdit\|NotebookEdit) | Marks the session core-dirty when an edit lands under `plugins/` or `adr/`. Silent bookkeeping. |
| `hooks/scripts/verify_on_change.py` | `Stop`, `SubagentStop` | A core-dirty session runs `self-evolution`'s eval suite before the turn may end. Green clears the debt; a regression or a broken suite **blocks** the stop with the failing capability and the fix path. |
| `hooks/scripts/evolution_pulse.py` | `SessionEnd` | Mines the audit trail and stages ranked capability proposals (via `self-evolution`'s miner/proposer) for the next session's brief. Non-blocking. |
| `hooks/scripts/autonomic_brief.py` | `SessionStart` | Injects a compact brief: any standing regression, the last verified state, and staged proposals — offered once, then cleared. Silent when there is nothing to say. |
| `hooks/scripts/_state.py` | — | Shared state helpers (dirty markers, session state dir, kill-switch check) used by all four hooks above. |
| `commands/autonomic.md` (`/autonomic`) | — | Inspect what the loop currently holds: unverified core debt, last verification, staged proposals, kill-switch status |
| `scripts/autonomic.py` | — | The status tool behind `/autonomic` |
| `evals/autonomic-loop.json` | — | Capability eval (`autonomic`, kind `autonomy`): core edits mark debt, a green verify clears it, a regression blocks the stop with the failure named, the loop guard prevents spinning, the brief stays silent when there is nothing to report, and the kill switch silences everything |

**Kill switch**: `AGENTIC_OS_AUTONOMIC=off` silences every reflex above without uninstalling
anything. The system degrades to fully manual — every tool still works, nothing fires by itself.

## How this relates to the rest of the marketplace

This plugin has no independent capability — it only sequences other plugins' tools onto hook
events. Its `plugin.json` declares hard dependencies on all four:

- **`core-orchestration`** and **`governance-gates`** — the loop's `verify_on_change.py` treats a
  session as "core-dirty" using the same `plugins/` and `adr/` path convention `governance-gates`'
  `commit-adr-gate` enforces at Stop; this plugin does not duplicate that gate, it runs
  *alongside* it.
- **`self-evolution`** — `verify_on_change.py` shells out to
  `plugins/self-evolution/scripts/evalctl.py`; `evolution_pulse.py` shells out to its `mine.py` and
  `propose.py`. If `self-evolution` is not installed, both hooks degrade to silence rather than
  failing the turn — the policy layer never assumes the capability layer is present.
- **`long-horizon`** — deliberately **not** injected by this plugin's `SessionStart` hook. Missions
  are `long-horizon`'s own `mission_brief.py` hook's job; two hooks injecting the same brief would
  double-spend context on every session start.

Read it as the layer that turns "verification exists" (ADR-0008, `self-evolution`) and "experience
gets mined" (ADR-0009) into "verification and mining *happen without being asked*" — the
irreversible step (adopting a capability into core logic) still has a human gate (ADR-0010); this
plugin never crosses it, it only makes the sensing and the enforcement automatic.

## Usage

```
/autonomic [--json]
```

Read the standing state honestly:

- **Unverified core debt** after a turn finished means the loop-guard window was used (the Stop
  hook already blocked once this turn and let the second attempt through rather than spin) — verify
  manually with `/evals` and clear the debt.
- **A standing regression** outranks whatever the session came to do (ADR-0008): fix forward or
  revert, then re-run the suite to confirm green.
- **Staged proposals** are offered exactly once, at the next session start, then cleared — they
  are proposals, not authorised work; the adoption gate is untouched by this layer.
- The kill switch degrading the system to manual is a feature, not an escape hatch — say why when
  you use it.

Nothing here is invoked directly beyond `/autonomic`; the rest is hooks, and hook changes are not
hot-reloaded — `/reload-plugins` or a restart after editing `hooks/hooks.json` or any script here.
