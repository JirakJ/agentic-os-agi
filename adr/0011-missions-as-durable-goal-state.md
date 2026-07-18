---
status: accepted
date: 2026-07-18
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [manifest/long-horizon, skill/mission-planning, agent/mission-runner, command/mission]
supersedes: []
superseded-by: []
---

# ADR-0011 — Missions are durable goal state; sessions are stateless executors

## Context and Problem Statement

The system operates per-session: a session starts, works, ends, and its goals evaporate with its
context window. Anything spanning more than one session — a multi-day build, a capability gap being
closed step by step — survives only if a human re-briefs the next session by hand. A system that
cannot pursue an objective across sessions is bounded by the length of one context window, which is
the single hardest ceiling on its autonomy. The question is where goal state should live and what
owns it.

## Decision Drivers

* Long-horizon work needs state that outlives any session: the objective, the decomposition, what
  is done, what is blocked and why
* The context window is the scarcest resource; goal state must be *loadable on demand*, compact,
  and not require replaying history
* Goal state is intent, not derived data — losing it loses the work's direction, so it needs the
  same durability and auditability guarantees as core logic (ADR-0001)
* A fresh session must discover in-flight work without being told — resumability has to be
  structural, not a human courtesy

## Considered Options

* Missions as git-tracked L2 files, injected as a brief at session start
* Goal state in the plugin data dir (like the retrieval index)
* Goal state in the Obsidian vault (L3)
* No goal state; each session is re-briefed by the human

## Decision Outcome

Chosen option: "Missions as git-tracked L2 files, injected at session start", because goal state is
source-of-truth intent: it must survive machine loss, be attributable diff by diff, and be
revertible — which is exactly the git guarantee (ADR-0001), and it slots into the existing L2
episodic layer (ADR-0003) rather than inventing a fifth layer.

Concretely: one markdown file per mission under `memory/missions/`, with frontmatter (id, status,
priority, blocked_on) and a checklist of steps sized so a session can complete at least one. A
`SessionStart` hook injects a compact brief of active missions into new sessions, so resumability
is structural. Sessions execute steps and update state as they go; the mission file, not the
session, is the memory of the goal.

### Consequences

* Good, because the horizon of work is no longer bounded by a context window — a mission survives
  any number of sessions, machine restarts, and model swaps
* Good, because goal state inherits git's audit story: every step completion is a diff, every
  abandonment is attributable, and `git log memory/missions/` is the history of intent
* Good, because the brief is cheap: a fresh session learns what is in flight from a few lines, not
  from replaying transcripts
* Bad, because state discipline becomes load-bearing. A session that works but does not update the
  mission file leaves the state stale, and the next session resumes from a lie. The mission-runner
  agent and the mission-planning skill exist to make updating structural, but the failure mode is
  real
* Bad, because missions add a second thing the Stop gate does not enforce: mission-file updates are
  L2, not core logic, so the commit gate deliberately does not block on them — the trade is less
  friction for more trust in discipline
* Bad, because a brief injected into every session costs context in sessions that have nothing to
  do with any mission; the hook keeps it to a few lines and stays silent when nothing is active

### Confirmation

The design is working if a mission started in one session is advanced by a later session without a
human re-brief, and if `git log` over a mission file reads as a coherent history of the goal. It is
failing if mission files are routinely stale relative to actual work — which is a discipline
problem to fix in the skill and agent, not a reason to move state off git.

## Pros and Cons of the Options

### Git-tracked L2 mission files + session-start brief

* Good, because durability, auditability and revertibility come free from the existing substrate
* Good, because it composes with the memory architecture instead of adding a layer
* Bad, because it depends on sessions maintaining the discipline of updating state

### Plugin data dir

* Good, because zero repo footprint
* Bad, because the data dir is for *derived, rebuildable* artifacts (ADR-0003); goal state is not
  derived and not rebuildable — losing it loses direction, which is a category error

### Obsidian vault (L3)

* Good, because missions would be human-browsable next to knowledge
* Bad, because L3 is the *knowledge base* — curated understanding, not operational state; mixing
  live workflow state into it erodes the L2/L3 boundary ADR-0003 exists to keep
* Bad, because the vault is optional infrastructure (ADR-0004); goal state cannot depend on an
  optional layer

### No goal state

* Good, because nothing to maintain
* Bad, because it caps autonomy at one context window, which is the ceiling this record exists to
  remove

## More Information

Missions are operational goal state, not knowledge: when a mission completes, anything durably
learned belongs in the vault or an ADR, and the mission file is the record of execution. See
ADR-0013 for how blocked missions feed the learning frontier.
