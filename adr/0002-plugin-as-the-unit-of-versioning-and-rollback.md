---
status: accepted
date: 2026-07-16
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [skill/release-flow, skill/commit-discipline, skill/skill-authoring, marketplace]
supersedes: []
superseded-by: []
---

# ADR-0002 — The plugin is the unit of versioning, distribution and rollback

## Context and Problem Statement

A rollback needs a unit: the thing that carries a version number and that you can move backwards
independently of everything else. Claude Code offers three candidate granularities — the whole
marketplace, the plugin, or the individual skill/agent — and versions resolve from `plugin.json`,
then the marketplace entry, then the commit SHA. Picking the wrong unit makes rollback either
too coarse (revert one hook, lose a week of skill work) or unenforceable (the runtime has no
concept of a skill version).

## Decision Drivers

* Claude Code installs, updates and pins **plugins**; it has no per-skill version concept at all
* A rollback must move one thing back without dragging unrelated work with it
* `plugin.json` `version` silently shadows the marketplace entry's `version` — a footgun that must
  be designed out, not documented around
* An unchanged `version` makes an update a no-op for existing installs; stale versions are silent
* Commit-SHA versioning works solo but produces unannounced updates the moment a second machine
  consumes the marketplace

## Considered Options

* Version the marketplace as a whole; roll back by reverting the repo
* Version each plugin; roll back by re-pinning the marketplace entry's `sha`
* Version each skill with a resolver layer on top of Git that materialises pinned versions

## Decision Outcome

Chosen option: "Version each plugin", because it is the only granularity the runtime actually
enforces — installs, updates, dependency ranges and pins all operate on plugins, so any finer unit
would be a fiction maintained by tooling the runtime ignores.

Concretely: `version` lives in `plugin.json` and **nowhere else**; the marketplace entry carries
`source` + `ref` + `sha`, with `sha` as the effective pin; each plugin gets its own tag namespace
`<plugin>/vX.Y.Z`. Skills still carry `version` in `skill.json` — for drift detection and
dependency documentation — but that number never installs anything.

### Consequences

* Good, because rollback is one line: re-pin the entry's `sha` to an older tag; nothing else moves
* Good, because it matches Anthropic's own submission pipeline, which pins approved plugins to
  specific commits — the mechanism is load-bearing upstream, not a local invention
* Good, because native `dependencies` with semver-range intersection works at exactly this
  granularity, so no bespoke resolver is needed
* Bad, because a plugin is coarser than a skill: rolling back `memory-obsidian` to undo one bad
  skill also reverts every other skill in that plugin. Mitigated by atomic commits — `git revert`
  of the one commit is the finer-grained lever — but the *installed* unit stays coarse
* Bad, because three plugins means three version numbers, three tag namespaces and three changelogs
  to keep straight

### Confirmation

This decision is wrong if a rollback ever requires touching more than one marketplace entry, or if
per-plugin rollback repeatedly reverts unrelated working code. If either happens more than twice,
the plugins are drawn along the wrong seams and should be split.

## Pros and Cons of the Options

### Version the marketplace as a whole

* Good, because one version number to reason about
* Bad, because rolling back a hook would roll back every skill and agent in the repo — the blast
  radius is the whole system
* Bad, because it throws away the per-plugin dependency resolution the runtime already gives you

### Version each plugin

* Good, because it aligns with the only unit the runtime enforces
* Good, because `sha`-pinning survives branch deletion and force-pushes; the pin is content-addressed
* Bad, because coarser than a single skill

### Version each skill with a resolver layer

* Good, because the finest possible rollback granularity
* Neutral, because prior art exists (pixi-skills pins skills in `pixi.lock`; skill-semver does
  per-skill SemVer via an MCP server)
* Bad, because Claude Code has no per-skill version concept — the resolver would have to
  materialise a working tree per pin, and every runtime change upstream could break it
* Bad, because it is a package manager. Building one to manage nine skills is a category error

## More Information

Version resolution order (first wins): `plugin.json` `version` → marketplace entry `version` →
commit SHA. Setting it in two places is a silent shadowing bug; `doctor.py --manifests` treats a
`version` in a marketplace entry as an error for this reason.

Revisit when a single plugin exceeds roughly ten skills — at that point the coarseness of
plugin-level rollback starts costing more than the split would.
