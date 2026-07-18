---
status: accepted
date: 2026-07-08
decision-makers: [Jakub Jirak]
consulted: []
informed: []
affects: [manifest/proto-forge]
supersedes: []
superseded-by: []
---

# ADR-0015 — Ship proto-forge as a marketplace plugin wrapping the vendored skill

## Context

BRS-PROTO-FORGE-001 v1.1.0 §17.1 requires two artifacts: the `proto-forge` skill (the
engine) and a thin plugin publishable to a private marketplace. The skill is developed
at `~/.claude/skills/proto-forge` and passed its full acceptance (BRS §16: `pnpm verify`
exit 0 on the template and on a generated app; BR-14 two-run structural diff). agentic-os
is the private marketplace this repo already operates.

## Decision

Add `plugins/proto-forge` containing the skill vendored at a pinned version under
`skills/proto-forge/`. Claude Code plugins have no cross-artifact reference mechanism, so
"versioned reference" is realized as vendoring plus a lockstep release ritual documented
in the plugin README (rsync from the canonical copy → `make release` → sha pin in
marketplace.json). Seed provenance (BRS §17.2): the template's `seed.lock` pins the
vendored `@jj/proto-ui` tree by sha256, re-verified by the generated app's
`snapshot:diff` gate; `seed.lock.sha` records the agentic-os commit that vendored it.

## Consequences

- proto-forge becomes installable/distributable from the agentic-os marketplace with
  ref+sha pinning like every other plugin.
- Two copies of the skill exist (canonical dev copy + vendored release copy); drift is
  bounded by the release ritual and the seed sha256 gate, not by discipline alone.
- Repo grows ~650 KB (template incl. its committed pnpm-lock.yaml — required, since the
  lockfile is the prototype's reproducibility contract).

## Alternatives considered

- Symlink from the plugin into `~/.claude/skills` — breaks for every other consumer of
  the marketplace; rejected.
- Making the plugin the canonical home — changes the local invocation surface
  (`proto-forge` → plugin-namespaced) and couples skill development to this repo's
  release cadence; rejected for now, revisit if the personal copy retires.
