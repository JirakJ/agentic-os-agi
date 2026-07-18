---
status: accepted
date: 2026-07-16
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [manifest/memory-obsidian, skill/vault-capture]
supersedes: []
superseded-by: []
---

# ADR-0004 — The vault is its own repository, versioned by Obsidian Git

## Context and Problem Statement

ADR-0001 puts user knowledge in Obsidian and core logic in Git, but the vault still lacks a
versioning layer — the original complaint. The vault needs history without being coupled to the
core repo's history, because the two roll back for different reasons and at different times.

## Decision Drivers

* Rolling back a hook must never roll back the knowledge base — they are unrelated events
* The vault is edited by a human all day; commits must be automatic or they will not happen
* Obsidian's own tooling should keep working (index, backlinks, live edit) — a versioning scheme
  that fights the editor loses
* Apple Silicon desktop is the platform; mobile is a nice-to-have

## Considered Options

* Vault as a Git submodule of the core repo
* Vault as its own repo, versioned with Obsidian Git
* Vault unversioned; rely on Time Machine / iCloud
* Vault inside the core repo under a `vault/` directory

## Decision Outcome

Chosen option: "Vault as its own repo, versioned with Obsidian Git", because it gives the vault a
real history while keeping the two rollback stories completely independent — which is the entire
point of the split in ADR-0001.

Setup: `git init` in the vault, Obsidian Git plugin (Vinzent03) with scheduled commit-and-sync,
`.gitignore` for `.obsidian/workspace.json` and other per-machine state.

### Consequences

* Good, because vault history exists and is queryable, with zero manual commit discipline
* Good, because a core rollback cannot touch the knowledge base, and vice versa
* Good, because Obsidian keeps its index and live editing — the plugin commits underneath the editor
  rather than around it
* Bad, because two repos means two remotes, two auth setups and two things that can drift
* Bad, because scheduled auto-commit produces a low-signal history ("vault backup: 2026-07-16
  09:31"); the vault's log is a safety net, not a narrative. Do not expect to read it

### Confirmation

Wrong if a core-repo rollback ever requires a matching vault action, or if the vault's auto-commit
noise ever makes finding a specific note version impractical (>1 min). Revisit if a second person
starts editing the vault, since auto-commit-and-sync conflicts scale badly.

## Pros and Cons of the Options

### Vault as a Git submodule

* Good, because one clone gets both
* Good, because the submodule pointer would pin vault state against core state
* Bad, because that pinning is exactly the coupling to avoid — `git revert` of a hook would move
  the vault pointer backwards, silently un-writing notes
* Bad, because Obsidian Git and a submodule checkout fight over the same working tree

### Vault as its own repo, Obsidian Git

* Good, because independent histories, independent rollback
* Good, because the plugin is desktop-native git on macOS
* Bad, because two remotes to manage
* Bad, because mobile support is unstable (isomorphic-git), so this is a desktop-first story

### Vault unversioned; Time Machine / iCloud

* Good, because zero setup
* Bad, because snapshots are not diffs — you can restore a file but you cannot see what changed or
  why, which is the actual requirement
* Bad, because it leaves the original complaint unfixed

### Vault inside the core repo under `vault/`

* Good, because one repo, one history
* Bad, because vault churn drowns the core history that ADR-0002's rollback depends on
* Bad, because a marketplace consumer would clone the user's private notes

## More Information

The `memory-obsidian` plugin reaches the vault via the Local REST API plugin's built-in MCP server
(see ADR-0007), not via raw filesystem writes — writing under a live Obsidian process risks
conflicting with its index.
