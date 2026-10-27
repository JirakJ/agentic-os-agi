---
status: accepted
date: 2026-10-27
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [manifest/proto-forge, marketplace]
supersedes: [0015]
superseded-by: []
---

# ADR-0030 — proto-forge installs from its own marketplace, not from a vendored copy

## Context and Problem Statement

ADR-0015 vendored the proto-forge skill under `plugins/proto-forge/skills/proto-forge/`
(and, through the Copilot adapter, `.github/skills/proto-forge/`) because the skill then
lived only in `~/.claude/skills`. Since then proto-forge became its own repository
(`JirakJ/proto-forge`) with its own marketplace, ten templates and four skills. The copy
here stalled at skill v0.3.0 while upstream reached 0.12.x; every security bump had to be
applied three times, and the two vendored lockfiles kept the workspace security gate busy.

## Decision

Remove `plugins/proto-forge` and its generated `.github/skills/proto-forge` copy, and drop
the marketplace entry. proto-forge is installed from its source of truth:

```
/plugin marketplace add JirakJ/proto-forge
/plugin install proto-forge@proto-forge
```

The plugin declares no dependency on any agentic-os plugin, so nothing here breaks.

## Consequences

- One copy, one release flow (upstream tags `vX.Y.Z`); no lockstep sync.
- Installed `proto-forge@agentic-os-agi` should be uninstalled in favour of
  `proto-forge@proto-forge`.
- The last vendored release stays reachable at tag `proto-forge/v0.2.0` for rollback.
