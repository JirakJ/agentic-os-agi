# long-horizon

Long-horizon autonomy: goal state that outlives a single session, a capability self-model derived
from evidence rather than assertion, and a learning frontier that orders what the system should
learn next. Three separable ideas, one plugin, because all three answer the same underlying
question — "what should this system be doing, beyond what fits in one context window?" — from three
different angles.

## Components

| Component | Kind | Purpose |
|---|---|---|
| `commands/mission.md` (`/mission`) | command | Create, list, show, advance, block, resume, complete or abandon a durable mission |
| `commands/frontier.md` (`/frontier`) | command | Show the capability self-model and the evidence-ordered learning frontier |
| `agents/mission-runner.md` | agent | Resume a mission cold from its file, execute the next session-sized step(s), leave state true |
| `skills/mission-planning` | skill | Decompose a multi-session goal into a durable mission with verifiable, session-sized steps |
| `skills/self-assessment` | skill | Ground any capability claim in the evidence-derived self-model rather than assertion |
| `scripts/mission.py` | script | Mission CRUD and lifecycle: `new`, `list`, `show`, `step-done`, `block`, `resume`, `complete`, `abandon` |
| `scripts/selfmodel.py` | script | Derives what the system can do from eval scores, the component inventory, and the audit trail |
| `scripts/frontier.py` | script | Fuses the self-model, blocked missions and mined friction into an evidence-ordered agenda |
| `hooks/scripts/mission_brief.py` | hook (`SessionStart`) | Injects a compact brief of in-flight missions so a fresh session discovers durable goals without a human re-brief. Silent when nothing is active. |
| `evals/mission-lifecycle.json` | eval (`autonomy`) | The mission tool holds its lifecycle: create, advance, block with a reason, refuse dishonest completion, resume, complete, silent brief when nothing is in flight |
| `evals/self-model-accuracy.json` | eval (`self-knowledge`) | The self-model derives calibrated claims: weak capabilities flagged, strong ones not, thin evidence marked, coverage reported per plugin |
| `evals/frontier-ranking.json` | eval (`self-knowledge`) | The frontier ranks by evidence severity — weakness > blocked intent > coverage gaps — every item carries evidence, and empty inputs yield an empty agenda |

## The three ideas

**Missions** (ADR-0011) are durable, git-tracked goal state: an objective, a decomposition into
session-sized verifiable steps, and a log. `mission_brief.py` makes resumability structural — a
fresh session discovers what is in flight without anyone re-explaining it. `complete` refuses open
steps mechanically; the honest exits are finishing the steps or `abandon --why` with the real
reason.

**The self-model** (ADR-0012) derives what the system can actually do from the eval scorecard, the
component inventory, and the audit trail — never from assertion — and reports *measured*,
*unmeasured* and *used* as three distinct claims. "Unmeasured" never means "fine": a plugin no eval
exercises is ignorance on the record.

**The frontier** (ADR-0013) fuses the self-model, blocked missions, and mined friction into a single
evidence-ordered learning agenda: weakness (measured harm) > blocked intent (stalled committed
work) > coverage gaps (where regressions hide) > friction (repeated cost). An empty frontier is the
goal state, not a sign of nothing to do — a self-directing system is not obligated to invent work.

## How this relates to the rest of the marketplace

`long-horizon`'s `plugin.json` depends on `core-orchestration`, `governance-gates` and
`self-evolution` (`^1.1.0`). The self-model and the frontier are both derived data over
`self-evolution`'s eval scorecard and audit-trail miner — this plugin adds no measurement of its
own, it orders what `self-evolution` already measures against durable goals and stalled intent.
`mission-runner` hands finished work back through the normal commit and (where behaviour changed)
ADR path; it does not bypass `governance-gates`' `commit-adr-gate`. The frontier orders; it does
not authorise — a frontier item still becomes a proposal (`self-evolution`'s
`capability-proposal` skill), an implementation (`skill-author`), an eval run, and a governed
adoption (ADR-0010). Nothing here shortcuts a gate another plugin owns.

`autonomic-loop`'s `SessionStart` hook deliberately does **not** inject missions — that stays this
plugin's `mission_brief.py`'s job alone, so two hooks never spend the same context twice on the
same information.

## Usage

```
/mission new "Title" --steps "a;b;c"
/mission list
/mission show <id>
/mission step-done <id> <n> --note "commit sha / what proves it"
/mission block <id> --on "the real reason"
/mission complete <id>
/mission abandon <id> --why "the real reason"
```

Decomposition is the hard part — steps must be session-sized and independently verifiable so a
fresh session can take the next open one cold. State discipline is load-bearing: update the file
the moment a step is true, and commit it with the work it documents. To execute in-flight work
rather than just track it, delegate to the `mission-runner` agent.

```
/frontier [--json | --no-mine]
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/selfmodel.py"     # the self-model on its own, cached with --cached
```

The live derivation runs the eval suite (seconds, and it is the truth); read the frontier's
evidence, not its vibe — interrogate what put an item there before acting on it.
