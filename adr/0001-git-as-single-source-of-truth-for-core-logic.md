---
status: accepted
date: 2026-07-16
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [marketplace, skill/skill-authoring]
supersedes: []
superseded-by: []
---

# ADR-0001 — Git holds all core logic; Obsidian holds user data

## Context and Problem Statement

The agent fleet's behaviour is defined by text: skills, subagent prompts, hooks, slash commands,
plugin manifests, CLAUDE.md instructions. That text changes constantly during development and each
change alters what the fleet does. Obsidian was already the persistent memory store, but it has no
versioning layer, so a behavioural regression could not be attributed, diffed or reverted. The
question is which store owns which class of state.

## Decision Drivers

* Every behavioural change must be attributable to a diff and revertible in isolation
* Core logic is portable: it must run identically on a fresh machine with nothing but a clone
* User knowledge is long-lived, hand-edited, and heavily interlinked — Git's merge model is a poor
  fit for it, and Obsidian's is not
* Claude Code loads plugins from a Git repo natively; no adapter layer is needed
* Two stores mean a boundary to police; one store means one of the two workloads is badly served

## Considered Options

* Everything in Obsidian, add versioning later
* Everything in Git, including notes
* Git for core logic, Obsidian for user data, strict boundary
* Git for core logic, Obsidian as a Git submodule of the core repo

## Decision Outcome

Chosen option: "Git for core logic, Obsidian for user data, strict boundary", because the two
workloads have opposite requirements — core logic needs atomic diffs, review and rollback, while a
knowledge base needs frictionless append and rich linking — and no single store is good at both.

### Consequences

* Good, because any behavioural change is a diff, and `git revert` is a working undo for exactly
  one component
* Good, because a fresh machine reproduces the fleet with `git clone` plus `/plugin marketplace add`
* Good, because Claude Code's native marketplace model consumes the repo directly — the source of
  truth and the distribution mechanism are the same artifact
* Bad, because there are now two stores and a boundary to police. A note that belongs in the vault
  will occasionally land in the repo, and vice versa
* Bad, because knowledge that *should* influence behaviour (a learned convention) lives in the
  vault, so promoting it into core logic is a manual act

### Confirmation

The boundary holds if `git log --stat` over a month shows no `.md` files under a vault path, and
if a fresh clone on a second machine reproduces fleet behaviour with no manual copying. If either
fails, the split is leaking and this decision needs revisiting.

## Pros and Cons of the Options

### Everything in Obsidian, add versioning later

* Good, because one store, no boundary
* Neutral, because Obsidian Git exists and would give *some* history
* Bad, because Claude Code cannot load plugins from a vault — an export step appears, and the thing
  that runs is no longer the thing that is edited
* Bad, because "add versioning later" means every change before that point is unattributable

### Everything in Git, including notes

* Good, because one store, one history, one mental model
* Bad, because Git's merge and review model actively hurts a personal knowledge base — nobody
  reviews their own notes, and a merge conflict in a daily note is pure friction
* Bad, because vault churn would drown the core-logic history that the rollback story depends on

### Git for core logic, Obsidian for user data, strict boundary

* Good, because each workload gets the store designed for it
* Good, because the repo stays small and its history stays legible
* Bad, because the boundary needs a rule, and rules need enforcement (see ADR-0005)

### Git for core logic, Obsidian as a submodule

* Good, because one clone gets both
* Neutral, because submodule pinning would version the vault against the core
* Bad, because submodules couple the two histories: a rollback of core logic drags the vault
  pointer with it, which is exactly wrong — user knowledge should not roll back when a hook does
* Bad, because Obsidian's own Git plugin fights a submodule checkout

## More Information

Superseded-by: nothing yet. Revisit if a third store (a hosted KB, a shared team vault) enters the
picture, since the two-store boundary would become a three-store boundary and the cost/benefit
shifts. See ADR-0004 for how the vault is versioned without coupling it to this repo.
